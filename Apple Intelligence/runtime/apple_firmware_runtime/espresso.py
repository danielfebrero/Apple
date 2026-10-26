"""Evaluate one attested firmware Espresso graph on a portable CPU.

This is a deliberately small, independent graph evaluator, not Apple's Espresso
runtime. Unsupported graphs or ambiguous weight encodings are rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

BACKEND = "espresso-linear-cpu-experimental"
_PRECISION = "Float32 inputs and weights; Float64 product/accumulation/sigmoid; Float32 output"
_SEMANTICS = "62 numeric features; firmware feature extraction and task semantics are not implemented"
_LAYERS = [
    {
        "nB": 62, "top": "8", "has_biases": 1, "weights": {},
        "nC": 1, "blob_weights": 3, "type": "inner_product",
        "has_relu": 0, "bottom": "x", "blob_biases": 1,
        "has_tanh": 0, "debug_info": "8", "name": "8", "has_prelu": 0,
    },
    {
        "bottom": "8", "weights": {}, "mode": 3, "debug_info": "9",
        "top": "var_9", "type": "activation", "name": "9",
        "attributes": {"is_output": 1},
    },
]
_SHAPES = {
    "8": {"k": 1, "w": 1, "n": 1, "_rank": 2, "h": 1},
    "x": {"k": 1, "w": 62, "n": 1, "_rank": 2, "h": 1},
    "var_9": {"k": 1, "w": 1, "n": 1, "_rank": 2, "h": 1},
}


def _reject(message: str) -> ValueError:
    return ValueError(f"{BACKEND}: {message}")


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _reject(f"cannot read {path.name}: {exc}") from exc


def _weights(raw: bytes) -> tuple[float, tuple[float, ...]]:
    """Decode the section table and Float32 sections observed in this graph."""
    if len(raw) != 440:
        raise _reject("expected exactly 440 bytes of unquantized weights")
    count = struct.unpack_from("<Q", raw)[0]
    if count != 4:
        raise _reject("expected four weight sections")
    table = [struct.unpack_from("<QQ", raw, 8 + i * 16) for i in range(4)]
    if table != [(0, 56), (1, 16), (2, 48), (3, 248)]:
        raise _reject("unsupported weight section table")
    cursor = 8 + 16 * count
    sections = {}
    for section_id, length in table:
        sections[section_id] = raw[cursor:cursor + length]
        cursor += length
    if cursor != len(raw):
        raise _reject("weight sections do not consume the file")
    if any(sections[0]) or any(sections[1][4:]) or any(sections[2]):
        raise _reject("unexpected nonzero weight padding")
    bias = struct.unpack("<f", sections[1][:4])[0]
    weights = struct.unpack("<62f", sections[3])
    if not all(math.isfinite(x) for x in (bias, *weights)):
        raise _reject("weights must be finite Float32 values")
    return bias, weights


def _load_bundle(path: Path):
    path = Path(path)
    net = _json(path / "model.espresso.net")
    shape = _json(path / "model.espresso.shape")
    metadata = _json(path / "metadata.json")
    if not isinstance(net, dict) or type(net.get("format_version")) is not int or net.get("format_version") != 200:
        raise _reject("only Espresso JSON format version 200 is supported")
    # A full layer comparison rejects fused, quantized, lookup, branching and
    # additional operators. Metadata corroborates the otherwise private mode 3.
    if json.dumps(net.get("layers"), sort_keys=True) != json.dumps(_LAYERS, sort_keys=True):
        raise _reject("only the attested 62-to-1 InnerProduct + sigmoid graph is supported")
    if net.get("storage") != "model.espresso.weights":
        raise _reject("unexpected weight storage path")
    if net.get("metadata_in_weights") != []:
        raise _reject("embedded weight metadata is unsupported")
    if net.get("properties") != {"mldb_token": "mldb-8vajz8kgz6"}:
        raise _reject("model identity is not the attested EntitySimilarity graph")
    if set(net) != {"storage", "analyses", "properties", "format_version", "metadata_in_weights", "layers"} or net.get("analyses") != {}:
        raise _reject("unexpected additional graph data")
    if json.dumps(shape, sort_keys=True) != json.dumps({"layer_shapes": _SHAPES}, sort_keys=True):
        raise _reject("unexpected tensor shapes")
    if not isinstance(metadata, list) or len(metadata) != 1 or not isinstance(metadata[0], dict):
        raise _reject("expected one model metadata record")
    meta = metadata[0]
    if (
        meta.get("generatedClassName") != "EntitySimilarityLinearModel"
        or meta.get("modelType") != {"name": "MLModelType_neuralNetwork"}
        or meta.get("storagePrecision") != "Float32"
        or meta.get("neuralNetworkLayerTypeHistogram") != {"ActivationSigmoid": 1, "InnerProduct": 1}
    ):
        raise _reject("metadata does not attest the supported Float32 sigmoid graph")
    ins, outs = meta.get("inputSchema"), meta.get("outputSchema")
    if not isinstance(ins, list) or len(ins) != 1 or not isinstance(ins[0], dict):
        raise _reject("expected exactly one input schema")
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], dict):
        raise _reject("expected exactly one output schema")
    for schema, name, dimensions in [(ins[0], "x", "[1, 62]"), (outs[0], "var_9", "[]")]:
        if (
            schema.get("name") != name
            or schema.get("type") != "MultiArray"
            or schema.get("dataType") != "Float32"
            or schema.get("shape") != dimensions
            or schema.get("hasShapeFlexibility") != "0"
            or schema.get("isOptional") != "0"
        ):
            raise _reject(f"unexpected {name} schema")
    try:
        raw = (path / "model.espresso.weights").read_bytes()
    except OSError as exc:
        raise _reject(f"cannot read model.espresso.weights: {exc}") from exc
    bias, weights = _weights(raw)
    return meta, raw, bias, weights


def inspect_bundle(path: Path) -> dict:
    """Validate every supported graph/shape/weight precondition or raise ValueError."""
    meta, raw, _, _ = _load_bundle(path)
    return {
        "backend": BACKEND,
        "supported": True,
        "model": "EntitySimilarityLinearModel",
        "inputs": {"x": {"shape": [1, 62], "dtype": "float32"}},
        "outputs": {"var_9": {"shape": [], "dtype": "float32"}},
        "operators": ["inner_product", "sigmoid"],
        "weight_sha256": hashlib.sha256(raw).hexdigest(),
        "precision": _PRECISION,
        "semantics": _SEMANTICS,
        "apple_compute_precision": meta.get("computePrecision"),
        "apple_runtime_parity_verified": False,
    }


def _f32(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _reject("input values must be numbers, excluding booleans")
    try:
        number = float(value)
        if not math.isfinite(number):
            raise _reject("input values must be finite")
        converted = struct.unpack("<f", struct.pack("<f", number))[0]
    except (OverflowError, struct.error) as exc:
        raise _reject("input value is outside the finite Float32 range") from exc
    if not math.isfinite(converted):
        raise _reject("input value is outside the finite Float32 range")
    return converted


def predict_bundle(path: Path, inputs: dict) -> dict:
    """Compute the actual decoded weights: sigmoid(bias + sum(weights * x))."""
    _, raw, bias, weights = _load_bundle(path)
    if not isinstance(inputs, dict) or set(inputs) != {"x"}:
        raise _reject("inputs must contain exactly the key 'x'")
    tensor = inputs["x"]
    if not isinstance(tensor, list) or len(tensor) != 1 or not isinstance(tensor[0], list) or len(tensor[0]) != 62:
        raise _reject("x must have the declared shape [1, 62]")
    vector = tuple(_f32(value) for value in tensor[0])
    logit = math.fsum([bias, *(w * x for w, x in zip(weights, vector))])
    # This stable branch prevents exp overflow at finite extreme Float32 input.
    if logit >= 0:
        probability = 1.0 / (1.0 + math.exp(-logit))
    else:
        exponential = math.exp(logit)
        probability = exponential / (1.0 + exponential)
    probability = struct.unpack("<f", struct.pack("<f", probability))[0]
    return {
        "backend": BACKEND,
        "model": "EntitySimilarityLinearModel",
        "outputs": {"var_9": probability},
        "prediction_performed": True,
        "precision": _PRECISION,
        "semantics": _SEMANTICS,
        "weight_sha256": hashlib.sha256(raw).hexdigest(),
        "apple_runtime_parity_verified": False,
    }
