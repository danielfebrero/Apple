"""Optional Apple Core AI Linux runtime, using its actual tensor signatures."""

from __future__ import annotations

import asyncio
import importlib.metadata
import math
import platform
from pathlib import Path

from .catalog import RuntimeFailure

MAX_ELEMENTS = 10_000_000
DTYPES = {"float16", "float32", "float64", "int8", "int16", "int32", "int64",
          "uint8", "uint16", "uint32", "uint64", "bool"}


def _api():
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeFailure("backend_unavailable", "This Core AI CPU integration is verified on Linux x86_64",
                             required="Linux x86_64, glibc >=2.34, Python >=3.11; pip install '.[coreai]'")
    try:
        import numpy as np
        from coreai.authoring import AIModelAsset
        from coreai.runtime import NDArray
    except (ImportError, OSError) as exc:
        raise RuntimeFailure("backend_unavailable", "Install Apple Core AI: pip install '.[coreai]'",
                             diagnostic=str(exc)) from exc
    return np, AIModelAsset, NDArray


def _schema(descriptor) -> dict:
    return {"dtype": descriptor.dtype, "shape": list(descriptor.shape)}


def _tensor(value, descriptor, np):
    shape = list(descriptor.shape)
    if any(type(n) is not int or n < 0 for n in shape) or math.prod(shape) > MAX_ELEMENTS:
        raise RuntimeFailure("invalid_inputs", "Core AI backend requires bounded static tensor shapes", shape=shape)
    if descriptor.dtype not in DTYPES:
        raise RuntimeFailure("unsupported_dtype", "Core AI JSON tensor dtype is not supported", dtype=descriptor.dtype)
    target = np.dtype(descriptor.dtype)
    flattened = isinstance(value, dict)
    if flattened:
        keys = set(value)
        if keys not in ({"shape", "data"}, {"shape", "data", "dtype"}):
            raise RuntimeFailure("invalid_inputs", "Tensor objects require shape and data, with optional dtype")
        declared_shape = value["shape"]
        if (not isinstance(declared_shape, list) or any(type(n) is not int for n in declared_shape)
                or declared_shape != shape):
            raise RuntimeFailure("invalid_inputs", "Input tensor shape differs from Core AI signature", expected_shape=shape)
        if "dtype" in value and value["dtype"] != descriptor.dtype:
            raise RuntimeFailure("invalid_inputs", "Explicit input dtype differs from Core AI signature",
                                 expected_dtype=descriptor.dtype)
        value = value["data"]
    try:
        raw = np.asarray(value)
    except (ValueError, TypeError) as exc:
        raise RuntimeFailure("invalid_inputs", "Input must be a rectangular numeric tensor") from exc
    if raw.size > MAX_ELEMENTS or raw.dtype.kind not in "biuf":
        raise RuntimeFailure("invalid_inputs", "Input must contain bounded numeric tensor values")
    if target.kind == "b":
        if raw.dtype.kind != "b":
            raise RuntimeFailure("invalid_inputs", "Boolean tensors require boolean values")
    else:
        def has_boolean(item):
            if isinstance(item, (list, tuple)):
                return any(has_boolean(child) for child in item)
            if isinstance(item, np.ndarray):
                return item.dtype.kind == "b" or (item.dtype.kind == "O" and any(has_boolean(x) for x in item.flat))
            return isinstance(item, (bool, np.bool_))
        if has_boolean(value):
            raise RuntimeFailure("invalid_inputs", "Numeric tensors do not accept boolean values")
    if not np.isfinite(raw).all():
        raise RuntimeFailure("invalid_inputs", "Input tensor contains non-finite values")
    if target.kind in "iu":
        limits = np.iinfo(target)
        if any(int(v) != v or int(v) < limits.min or int(v) > limits.max for v in raw.flat):
            raise RuntimeFailure("invalid_inputs", "Integer input would truncate or overflow")
    with np.errstate(over="ignore", invalid="ignore"):
        converted = raw.astype(target)
    if not np.isfinite(converted).all():
        raise RuntimeFailure("invalid_inputs", "Input tensor overflows its declared dtype")
    if flattened:
        if converted.size != math.prod(shape):
            raise RuntimeFailure("invalid_inputs", "Input element count differs from Core AI signature")
        converted = converted.reshape(shape)
    if list(converted.shape) != shape:
        raise RuntimeFailure("invalid_inputs", "Input tensor shape differs from Core AI signature",
                             expected_shape=shape, actual_shape=list(converted.shape))
    return np.ascontiguousarray(converted).reshape(shape)


async def _execute(bundle: Path, inputs: dict | None, function_name: str) -> dict:
    np, AIModelAsset, NDArray = _api()
    if bundle.suffix != ".aimodel" or not AIModelAsset.is_valid(bundle):
        raise RuntimeFailure("unsupported_format", "Core AI backend needs a complete .aimodel asset directory")
    asset = AIModelAsset.load(bundle)
    async with asset.executable() as model:
        if function_name not in model.function_names:
            raise RuntimeFailure("invalid_entrypoint", "Core AI function is absent", functions=list(model.function_names))
        function = model.load_function(function_name)
        desc = function.desc
        if desc.state_names:
            raise RuntimeFailure("unsupported_state", "Stateful Core AI functions require an explicit state API",
                                 states=list(desc.state_names))
        result = {"backend": "coreai-cpu", "runtime_version": importlib.metadata.version("coreai-core"),
                  "function": function_name, "functions": list(model.function_names),
                  "prediction_performed": inputs is not None,
                  "input_schema": {n: _schema(desc.input_descriptor(n)) for n in desc.input_names},
                  "output_schema": {n: _schema(desc.output_descriptor(n)) for n in desc.output_names},
                  "compatibility": "Apple Core AI local Linux runtime; no claim of AFM or Core ML compatibility"}
        if inputs is None:
            return result
        if not isinstance(inputs, dict) or set(inputs) != set(desc.input_names):
            raise RuntimeFailure("invalid_inputs", "Input names differ from Core AI signature",
                                 expected_names=list(desc.input_names))
        tensors = {n: NDArray(_tensor(inputs[n], desc.input_descriptor(n), np)) for n in desc.input_names}
        outputs = await function(tensors)
        converted = {}
        for name, value in outputs.items():
            # Materialize while the model's buffers are alive.
            array = value.numpy().copy()
            if array.dtype.kind not in "biuf" or not np.isfinite(array).all():
                raise RuntimeFailure("invalid_output", "Core AI produced an unsupported or non-finite JSON tensor")
            converted[name] = {"dtype": str(array.dtype), "shape": list(array.shape), "data": array.tolist()}
        return result | {"outputs": converted}


def run_bundle(bundle: Path, inputs: dict | None = None, *, function_name: str = "main") -> dict:
    """Load/execute a caller-verified asset; never translate Core ML into Core AI."""
    try:
        return asyncio.run(_execute(bundle, inputs, function_name))
    except RuntimeFailure:
        raise
    except (ValueError, TypeError, RuntimeError, OSError, KeyError) as exc:
        raise RuntimeFailure("coreai_failed", "Apple Core AI could not load or execute this asset",
                             diagnostic=str(exc)) from exc
