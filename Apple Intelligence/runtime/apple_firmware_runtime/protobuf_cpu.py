"""Independent, deliberately bounded Core ML protobuf/MIL CPU evaluator.

Uses Core ML Tools only for protobuf definitions, never MLModel.predict.
No dynamic code, Apple binaries, or replacement weights are executed.
"""
from __future__ import annotations

import math
import operator
import struct
from pathlib import Path

import numpy as np
from coremltools.proto import Model_pb2, MIL_pb2
from google.protobuf.message import DecodeError


MAX_ELEMENTS = 10_000_000
DTYPES = {"FLOAT16": "<f2", "FLOAT32": "<f4", "FLOAT64": "<f8",
          "INT32": "<i4", "INT64": "<i8", "UINT16": "<u2", "BOOL": "?", "STRING": "U"}
BLOB_DTYPES = {1: "<f2", 2: "<f4", 3: "u1", 4: "i1", 6: "<i2", 7: "<u2", 14: "<i4", 15: "<u4"}
MIL_OPS = {"const", "cast", "split", "gather", "gather_along_axis", "transpose", "reshape",
           "linear", "relu", "sigmoid", "softmax", "concat", "mul", "add", "sub", "less",
           "select", "reduce_sum", "reduce_argmax"}


def dtype(t):
    name = MIL_pb2.DataType.Name(t)
    if name not in DTYPES:
        raise ValueError(f"Unsupported MIL dtype: {name}")
    return np.dtype(DTYPES[name])


def bounded_shape(shape):
    if any(type(x) is not int or x < 0 for x in shape) or math.prod(shape) > MAX_ELEMENTS:
        raise ValueError("Invalid or oversized tensor shape")
    return tuple(shape)


def finite(a):
    if np.asarray(a).dtype.kind in "fiu" and not np.isfinite(a).all():
        raise ValueError("Nonfinite tensor or overflow")
    return a


def value(v, model_dir):
    tt = v.type.tensorType
    shape = bounded_shape([int(d.constant.size) if d.WhichOneof("dimension") == "constant"
                           else -1 for d in tt.dimensions])
    dt = dtype(tt.dataType)
    storage = v.WhichOneof("value")
    if storage == "immediateValue":
        tensor = v.immediateValue.tensor
        kind = tensor.WhichOneof("value")
        if kind == "bytes":
            a = np.frombuffer(tensor.bytes.values, dtype=dt)
        elif kind in {"floats", "doubles", "ints", "longInts", "bools", "strings"}:
            a = np.asarray(getattr(tensor, kind).values, dtype=dt)
        else:
            raise ValueError(f"Unsupported MIL immediate: {kind}")
    elif storage == "blobFileValue":
        ref = v.blobFileValue
        prefix = "@model_path/"
        if not ref.fileName.startswith(prefix):
            raise ValueError("Unsupported blob reference")
        rel = Path(ref.fileName[len(prefix):])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe blob reference")
        path = model_dir / rel
        if not path.resolve().is_relative_to(model_dir.resolve()) or path.is_symlink():
            raise ValueError("Blob escapes model directory")
        with path.open("rb") as f:
            header = f.read(64)
            if len(header) != 64 or struct.unpack_from("<I", header, 4)[0] != 2:
                raise ValueError("Unsupported MIL blob version")
            if ref.offset < 64 or ref.offset % 64:
                raise ValueError("Invalid MIL blob metadata offset")
            f.seek(ref.offset)
            meta = f.read(64)
            if len(meta) != 64:
                raise ValueError("Truncated MIL blob metadata")
            magic, typ, size, offset = struct.unpack_from("<IIQQ", meta)
            if magic != 0xDEADBEEF or typ not in BLOB_DTYPES or np.dtype(BLOB_DTYPES[typ]) != dt:
                raise ValueError("MIL blob sentinel/dtype mismatch")
            if size != math.prod(shape) * dt.itemsize or offset % 64 or offset < ref.offset + 64:
                raise ValueError("MIL blob size/alignment mismatch")
            if offset + size > path.stat().st_size:
                raise ValueError("MIL blob data outside file")
            f.seek(offset)
            a = np.frombuffer(f.read(size), dtype=dt)
    else:
        raise ValueError(f"Unsupported MIL storage: {storage}")
    if a.size != math.prod(shape):
        raise ValueError("MIL tensor length mismatch")
    return finite(a.reshape(shape))


def validate_inputs(spec, inputs):
    if set(inputs) != {f.name for f in spec.description.input}:
        raise ValueError("Input names must exactly match the model description")
    result = {}
    for feature in spec.description.input:
        v = inputs[feature.name]
        typ = feature.type.WhichOneof("Type")
        if typ == "doubleType":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"Expected finite scalar: {feature.name}")
            result[feature.name] = float(v)
        elif typ == "multiArrayType":
            desc = feature.type.multiArrayType
            if desc.HasField("shapeRange") or desc.HasField("enumeratedShapes") or feature.type.isOptional:
                raise ValueError("Flexible/optional inputs are not implemented")
            shape = bounded_shape(list(desc.shape))
            if isinstance(v, dict):
                if set(v) != {"shape", "data"} or v["shape"] != list(shape):
                    raise ValueError("Tensor shape does not match model")
                v = v["data"]
                reshape = True
            else:
                reshape = False
            def check_numbers(x):
                if isinstance(x, np.ndarray):
                    if x.dtype.kind not in "fiu": raise ValueError("Tensor must be numeric")
                elif isinstance(x, list):
                    for y in x: check_numbers(y)
                elif type(x) not in (int, float) and not isinstance(x, np.number):
                    raise ValueError("Tensor contains a nonnumeric value or boolean")
            check_numbers(v)
            raw = np.asarray(v)
            if raw.dtype.kind not in "fiu" or raw.size > MAX_ELEMENTS:
                raise ValueError("Tensor must contain finite numbers, no booleans")
            dt = {65552: np.float16, 65568: np.float32, 65600: np.float64, 131104: np.int32}.get(desc.dataType)
            if dt is None:
                raise ValueError("Unsupported input dtype")
            finite(raw)
            if dt == np.int32 and (np.any(raw != np.trunc(raw)) or np.any(raw < -2147483648) or np.any(raw > 2147483647)):
                raise ValueError("Input is not representable as Int32")
            a = finite(raw.astype(dt))
            if reshape:
                a = a.reshape(shape)
            if a.shape != shape:
                raise ValueError(f"Expected shape {shape}, got {a.shape}")
            result[feature.name] = a
        else:
            raise ValueError(f"Unsupported input type: {typ}")
    return result


def sigmoid(x):
    x = np.asarray(x)
    z = np.exp(-np.abs(x))
    return np.where(x >= 0, 1 / (1 + z), z / (1 + z))


def trees(spec, env, kind):
    model = getattr(spec, kind)
    te = model.treeEnsemble
    features = np.concatenate([np.asarray(env[f.name], dtype=np.float64).reshape(-1)
                               for f in spec.description.input])
    n = int(te.numPredictionDimensions)
    if not 0 < n <= MAX_ELEMENTS or len(te.basePredictionValue) not in (0, n):
        raise ValueError("Invalid tree output dimensions")
    scores = np.asarray(te.basePredictionValue or [0.] * n, dtype=np.float64).copy()
    groups = {}
    for node in te.nodes:
        nodes = groups.setdefault(node.treeId, {})
        if node.nodeId in nodes:
            raise ValueError("Duplicate tree node")
        nodes[node.nodeId] = node
    comparisons = [operator.le, operator.lt, operator.ge, operator.gt, operator.eq, operator.ne]
    for nodes in groups.values():
        children = {c for node in nodes.values() if node.nodeBehavior != 6
                    for c in (node.trueChildNodeId, node.falseChildNodeId)}
        roots = set(nodes) - children
        if len(roots) != 1 or not children.issubset(nodes):
            raise ValueError("Tree must have one root and valid child references")
        current = roots.pop()
        # Validate the whole tree, including branches this input does not take.
        reachable = set()
        pending = [current]
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                raise ValueError("Cyclic tree or node shared by multiple parents")
            reachable.add(node_id)
            node = nodes[node_id]
            if node.nodeBehavior != 6:
                pending.extend((node.trueChildNodeId, node.falseChildNodeId))
        if reachable != set(nodes):
            raise ValueError("Unreachable tree nodes")
        visited = set()
        while True:
            if current in visited:
                raise ValueError("Cyclic tree")
            visited.add(current)
            node = nodes[current]
            if node.nodeBehavior == 6:
                for item in node.evaluationInfo:
                    if item.evaluationIndex >= n:
                        raise ValueError("Leaf output index outside score vector")
                    scores[item.evaluationIndex] += item.evaluationValue
                break
            if node.nodeBehavior >= len(comparisons) or node.branchFeatureIndex >= features.size:
                raise ValueError("Unsupported branch or feature index")
            go = comparisons[node.nodeBehavior](features[node.branchFeatureIndex], node.branchFeatureValue)
            current = node.trueChildNodeId if go else node.falseChildNodeId
    transform = model.postEvaluationTransform
    if transform in (1, 3):
        if transform == 3:
            scores = np.concatenate(([0.], scores))
        scores = np.exp(scores - scores.max()); scores /= scores.sum()
    elif transform == 2:
        scores = sigmoid(scores)
    elif transform != 0:
        raise ValueError("Unsupported tree transform")
    finite(scores)
    if kind == "treeEnsembleRegressor":
        if len(spec.description.output) != 1:
            raise ValueError("Unsupported regressor output schema")
        return {spec.description.output[0].name: scores.item() if scores.size == 1 else scores}
    label_type = model.WhichOneof("ClassLabels")
    labels = list(getattr(model, label_type).vector) if label_type else []
    if len(labels) == 2 and scores.size == 1:
        scores = np.asarray([1 - scores[0], scores[0]])
    if len(labels) != scores.size or not labels:
        raise ValueError("Class label/score length mismatch")
    return {spec.description.predictedFeatureName: labels[int(scores.argmax())],
            spec.description.predictedProbabilitiesName: {str(k): float(v) for k, v in zip(labels, scores)}}


def mil(spec, env, model_dir):
    if set(spec.mlProgram.functions) != {"main"}:
        raise ValueError("Only a single main MIL function is supported")
    func = spec.mlProgram.functions["main"]
    if len(func.block_specializations) != 1:
        raise ValueError("Ambiguous MIL specialization")
    block = next(iter(func.block_specializations.values()))
    unknown = {o.type for o in block.operations} - MIL_OPS
    if unknown or any(o.blocks for o in block.operations):
        raise ValueError(f"Unsupported MIL operators/control flow: {sorted(unknown)}")
    for op in block.operations:
        args = {}
        for k, binding in op.inputs.items():
            vals = [env[a.name] if a.WhichOneof("binding") == "name" else value(a.value, model_dir)
                    for a in binding.arguments]
            args[k] = vals if k == "values" else vals[0] if len(vals) == 1 else vals
        x = args.get("x")
        typ = op.type
        if typ == "const": y = value(op.attributes["val"], model_dir)
        elif typ == "cast":
            dt = str(args["dtype"].item())
            cast_types = {"fp16": np.float16, "fp32": np.float32, "int32": np.int32, "uint16": np.uint16}
            if dt not in cast_types: raise ValueError(f"Unsupported cast: {dt}")
            y = x.astype(cast_types[dt])
        elif typ == "split":
            axis = int(args["axis"])
            if "split_sizes" in args:
                sizes = args["split_sizes"].reshape(-1)
                if np.any(sizes < 0) or sizes.sum() != x.shape[axis]: raise ValueError("Invalid split sizes")
                y = np.split(x, np.cumsum(sizes)[:-1], axis=axis)
            else: y = np.split(x, int(args["num_splits"]), axis=axis)
        elif typ in {"gather", "gather_along_axis"}:
            if int(args.get("batch_dims", 0)) != 0: raise ValueError("Batched gather not supported")
            indices = args["indices"]
            axis = int(args["axis"])
            if np.any(indices < 0) or np.any(indices >= x.shape[axis]): raise ValueError("Gather index outside tensor")
            y = (np.take if typ == "gather" else np.take_along_axis)(x, indices, axis=axis)
        elif typ == "transpose": y = np.transpose(x, tuple(args["perm"].reshape(-1)))
        elif typ == "reshape": y = np.reshape(x, tuple(args["shape"].reshape(-1)))
        elif typ == "linear":
            # FP16 weights/inputs, Float32 accumulation, rounded to declared output dtype below.
            y = x.astype(np.float32) @ args["weight"].astype(np.float32).T + args["bias"].astype(np.float32)
        elif typ == "relu": y = np.maximum(x, 0)
        elif typ == "sigmoid": y = sigmoid(x)
        elif typ == "softmax":
            y = np.exp(x - x.max(axis=int(args["axis"]), keepdims=True)); y /= y.sum(axis=int(args["axis"]), keepdims=True)
        elif typ == "concat":
            if bool(args.get("interleave", False)): raise ValueError("Interleaved concat not supported")
            y = np.concatenate(args["values"], axis=int(args["axis"]))
        elif typ in {"mul", "add", "sub", "less"}:
            y = {"mul": np.multiply, "add": np.add, "sub": np.subtract, "less": np.less}[typ](x, args["y"])
        elif typ == "select": y = np.where(args["cond"], args["a"], args["b"])
        elif typ == "reduce_sum": y = np.sum(x, axis=tuple(args["axes"].reshape(-1)), keepdims=bool(args["keep_dims"]))
        elif typ == "reduce_argmax": y = np.argmax(x, axis=int(args["axis"]), keepdims=bool(args["keep_dims"]))
        else: raise ValueError(f"Unsupported MIL op: {typ}")
        ys = y if typ == "split" else [y]
        if len(ys) != len(op.outputs): raise ValueError("MIL output count mismatch")
        for out, a in zip(op.outputs, ys):
            a = finite(np.asarray(a, dtype=dtype(out.type.tensorType.dataType)))
            if a.size > MAX_ELEMENTS: raise ValueError("Oversized intermediate tensor")
            env[out.name] = a
    return {f.name: env[f.name] for f in spec.description.output}


def nn_weights(w):
    if w.HasField("quantization") or w.rawValue or w.int8RawValue:
        raise ValueError("Quantized neural weights not supported")
    if w.float16Value:
        return finite(np.frombuffer(w.float16Value, dtype="<f2").astype(np.float32))
    return finite(np.asarray(w.floatValue, dtype=np.float32))


def neural(spec, env):
    net = spec.neuralNetwork
    # The attested ranking graph uses exact tensor shapes, not legacy rank-5 mapping.
    if net.arrayInputShapeMapping != 1 or net.preprocessing:
        raise ValueError("Only exact-shape neural networks without image preprocessing supported")
    for layer in net.layers:
        kind = layer.WhichOneof("layer")
        op = getattr(layer, kind)
        xs = [env[k] for k in layer.input]
        if len(layer.output) != 1: raise ValueError("Neural output arity unsupported")
        if kind == "loadConstantND": y = nn_weights(op.data).reshape(tuple(op.shape))
        elif kind in {"subtractBroadcastable", "multiplyBroadcastable"}:
            if len(xs) != 2: raise ValueError("Binary neural layer requires two inputs")
            y = (np.subtract if kind == "subtractBroadcastable" else np.multiply)(*xs)
        elif kind == "innerProduct":
            if len(xs) != 1 or xs[0].ndim != 2 or xs[0].shape[-1] != op.inputChannels:
                raise ValueError("Only rank-2 dense layers supported")
            w = nn_weights(op.weights).reshape(op.outputChannels, op.inputChannels)
            y = xs[0] @ w.T
            if op.hasBias: y += nn_weights(op.bias)
        elif kind == "squeeze":
            y = np.squeeze(xs[0], axis=None if op.squeezeAll else tuple(op.axes))
        elif kind == "activation":
            activation = op.WhichOneof("NonlinearityType")
            if activation == "sigmoid": y = sigmoid(xs[0])
            elif activation == "ReLU": y = np.maximum(xs[0], 0)
            else: raise ValueError(f"Unsupported neural activation: {activation}")
        else: raise ValueError(f"Unsupported neural layer: {kind}")
        y = finite(np.asarray(y, dtype=np.float32))
        if y.size > MAX_ELEMENTS: raise ValueError("Oversized neural tensor")
        env[layer.output[0]] = y
    return {f.name: env[f.name] for f in spec.description.output}


def evaluate(spec, inputs, model_dir):
    env = validate_inputs(spec, inputs)
    kind = spec.WhichOneof("Type")
    if kind in {"pipelineRegressor", "pipelineClassifier", "pipeline"}:
        pipe = getattr(spec, kind)
        if kind != "pipeline": pipe = pipe.pipeline
        for child in pipe.models:
            env.update(evaluate(child, {f.name: env[f.name] for f in child.description.input}, model_dir))
        return {f.name: env[f.name] for f in spec.description.output}
    if kind == "featureVectorizer":
        if len(spec.description.output) != 1: raise ValueError("Unsupported vectorizer schema")
        values = []
        for col in spec.featureVectorizer.inputList:
            a = np.asarray(env[col.inputColumn]).reshape(-1)
            if a.size != col.inputDimensions: raise ValueError("Vectorizer input dimension mismatch")
            values.extend(a)
        return {spec.description.output[0].name: np.asarray(values, dtype=np.float64)}
    if kind in {"treeEnsembleRegressor", "treeEnsembleClassifier"}: return trees(spec, env, kind)
    if kind == "mlProgram": return mil(spec, env, model_dir)
    if kind == "neuralNetwork": return neural(spec, env)
    raise ValueError(f"Unsupported protobuf model type: {kind}")


def encode(v):
    if isinstance(v, np.ndarray):
        return {"shape": list(v.shape), "dtype": str(v.dtype), "data": v.reshape(-1).tolist()}
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, dict): return {k: encode(x) for k, x in v.items()}
    return v


def predict_file(path, inputs):
    spec = Model_pb2.Model()
    try:
        spec.ParseFromString(path.read_bytes())
    except DecodeError as exc:
        raise ValueError("Invalid Core ML protobuf") from exc
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        outputs = evaluate(spec, inputs, path.parent)
    return {"backend": "coreml-protobuf-cpu-experimental", "model_type": spec.WhichOneof("Type"),
            "outputs": encode(outputs), "apple_runtime_parity_verified": False,
            "limitation": "Independent CPU mathematics; Apple runtime parity and application preprocessing not established"}
