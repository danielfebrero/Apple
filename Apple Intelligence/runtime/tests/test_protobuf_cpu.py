"""Independent mathematical checks; optional dependencies/firmware skip explicitly."""
import importlib.util
import math
from pathlib import Path
import struct
import tempfile
import unittest

AVAILABLE = all(importlib.util.find_spec(x) is not None for x in ("numpy", "coremltools"))
if AVAILABLE:
    import numpy as np
    from coremltools.proto import Model_pb2, MIL_pb2
    from apple_firmware_runtime.protobuf_cpu import evaluate, predict_file, value, validate_inputs


@unittest.skipUnless(AVAILABLE, "Optional CPU dependencies absent: install .[cpu]")
class ProtobufMathTests(unittest.TestCase):
    def make_tree(self, classifier=False):
        s = Model_pb2.Model()
        f = s.description.input.add(); f.name = "x"; f.type.doubleType.SetInParent()
        f = s.description.output.add(); f.name = "label" if classifier else "y"
        if classifier:
            s.description.predictedFeatureName = "label"
            s.description.predictedProbabilitiesName = "probability"
            s.description.output.add().name = "probability"
            m = s.treeEnsembleClassifier; m.int64ClassLabels.vector.extend([0, 1])
            m.postEvaluationTransform = 2
        else: m = s.treeEnsembleRegressor
        m.treeEnsemble.numPredictionDimensions = 1; m.treeEnsemble.basePredictionValue.append(0.5)
        root = m.treeEnsemble.nodes.add(); root.nodeId = 10; root.nodeBehavior = 0
        root.branchFeatureValue = 2.; root.trueChildNodeId = 20; root.falseChildNodeId = 30
        for node_id, score in ((20, 1.), (30, -2.)):
            n = m.treeEnsemble.nodes.add(); n.nodeId = node_id; n.nodeBehavior = 6
            n.evaluationInfo.add().evaluationValue = score
        return s

    def test_tree_boundary_and_base(self):
        s = self.make_tree()
        self.assertEqual(evaluate(s, {"x": 2.}, Path(".")), {"y": 1.5})
        self.assertEqual(evaluate(s, {"x": 2.0001}, Path(".")), {"y": -1.5})

    def test_binary_logistic(self):
        r = evaluate(self.make_tree(True), {"x": 2}, Path("."))
        self.assertEqual(r["label"], 1)
        self.assertAlmostEqual(r["probability"]["1"], 1 / (1 + math.exp(-1.5)), places=14)
        self.assertAlmostEqual(sum(r["probability"].values()), 1.)

    def test_bad_tree_input_and_cycle(self):
        s = self.make_tree()
        for x in (True, "2", math.nan, math.inf):
            with self.assertRaises(ValueError): evaluate(s, {"x": x}, Path("."))
        s.treeEnsembleRegressor.treeEnsemble.nodes[0].trueChildNodeId = 10
        with self.assertRaises(ValueError): evaluate(s, {"x": 0}, Path("."))

    def test_blob_header_and_payload(self):
        v = MIL_pb2.Value(); v.type.tensorType.dataType = MIL_pb2.FLOAT32
        v.type.tensorType.dimensions.add().constant.size = 2
        v.blobFileValue.fileName = "@model_path/weights.bin"; v.blobFileValue.offset = 64
        blob = struct.pack("<II", 1, 2).ljust(64, b"\0")
        blob += struct.pack("<IIQQ", 0xDEADBEEF, 2, 8, 128).ljust(64, b"\0")
        blob += struct.pack("<ff", 1.25, -3.5)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "weights.bin"; p.write_bytes(blob)
            np.testing.assert_array_equal(value(v, Path(d)), [1.25, -3.5])
            p.write_bytes(blob[:-1])
            with self.assertRaises(ValueError): value(v, Path(d))
            p.write_bytes(blob[:64] + b"\0" * 64 + blob[128:])
            with self.assertRaises(ValueError): value(v, Path(d))
            v.blobFileValue.fileName = "@model_path/../outside"
            with self.assertRaises(ValueError): value(v, Path(d))

    def test_mixed_boolean_tensor_rejected(self):
        s = Model_pb2.Model(); f = s.description.input.add(); f.name = "x"
        f.type.multiArrayType.shape.append(2); f.type.multiArrayType.dataType = 65568
        for data in ([1, True], [1, "2"], [1, math.inf]):
            with self.assertRaises(ValueError): validate_inputs(s, {"x": data})

    def test_mil_dense_and_sigmoid_against_scalar_formula(self):
        s = Model_pb2.Model()
        feature = s.description.input.add(); feature.name = "x"
        feature.type.multiArrayType.shape.extend([1, 2]); feature.type.multiArrayType.dataType = 65568
        feature = s.description.output.add(); feature.name = "p"
        feature.type.multiArrayType.shape.extend([1, 1]); feature.type.multiArrayType.dataType = 65568
        func = s.mlProgram.functions["main"]; block = func.block_specializations["CoreML7"]
        for name, data, shape in (("w", [2., -3.], [1, 2]), ("b", [0.5], [1])):
            op = block.operations.add(); op.type = "const"
            v = op.attributes["val"]; v.type.tensorType.dataType = MIL_pb2.FLOAT32
            for n in shape: v.type.tensorType.dimensions.add().constant.size = n
            v.immediateValue.tensor.floats.values.extend(data)
            out = op.outputs.add(); out.name = name; out.type.CopyFrom(v.type)
        for typ, output, inputs in (("linear", "z", {"x": "x", "weight": "w", "bias": "b"}),
                                     ("sigmoid", "p", {"x": "z"})):
            op = block.operations.add(); op.type = typ
            for arg, name in inputs.items(): op.inputs[arg].arguments.add().name = name
            out = op.outputs.add(); out.name = output; out.type.tensorType.dataType = MIL_pb2.FLOAT32
        r = evaluate(s, {"x": [[1., 2.]]}, Path("."))
        self.assertAlmostEqual(float(r["p"][0, 0]), 1 / (1 + math.exp(3.5)), places=7)
        block.operations[-1].type = "while_loop"
        with self.assertRaises(ValueError): evaluate(s, {"x": [[1., 2.]]}, Path("."))


@unittest.skipUnless(AVAILABLE, "Optional CPU dependencies absent")
class FirmwareMathTests(unittest.TestCase):
    def test_real_three_tree_regressor_against_manual_leaf_sum(self):
        root = Path(__file__).resolve().parents[2] / "models/cache"
        files = list(root.rglob("gbdt.mlmodel"))
        if not files: self.skipTest("Actual firmware fixture absent")
        s = Model_pb2.Model(); s.ParseFromString(files[0].read_bytes())
        te = s.treeEnsembleRegressor.treeEnsemble
        # This fixture has three 3-node stumps. Independently choose a root child,
        # not the runtime's recursive generic traversal or node-index structure.
        self.assertEqual(len(te.nodes), 9)
        expected = sum(te.basePredictionValue)
        for tree_id in sorted({n.treeId for n in te.nodes}):
            nodes = [n for n in te.nodes if n.treeId == tree_id]
            branches = [n for n in nodes if n.nodeBehavior != 6]
            self.assertEqual(len(branches), 1)
            b = branches[0]; self.assertEqual(b.nodeBehavior, 0)
            chosen = b.trueChildNodeId if 0 <= b.branchFeatureValue else b.falseChildNodeId
            leaf = next(n for n in nodes if n.nodeId == chosen)
            expected += sum(e.evaluationValue for e in leaf.evaluationInfo)
        r = predict_file(files[0], {f.name: 0. for f in s.description.input})
        self.assertAlmostEqual(r["outputs"]["predictedValue"], expected, places=14)

    def test_real_ranker_against_double_precision_normalized_dot(self):
        root = Path(__file__).resolve().parents[2] / "models/cache"
        files = list(root.rglob("item_model_with_feature_order_and_model_type_metadata.mlmodel"))
        if not files: self.skipTest("Actual firmware fixture absent")
        s = Model_pb2.Model(); s.ParseFromString(files[0].read_bytes())
        layers = s.neuralNetwork.layers
        mean = list(layers[0].loadConstantND.data.floatValue)
        inv_std = list(layers[2].loadConstantND.data.floatValue)
        dense = layers[4].innerProduct
        z = math.fsum(-m * v * w for m, v, w in zip(mean, inv_std, dense.weights.floatValue)) + dense.bias.floatValue[0]
        expected = 1 / (1 + math.exp(-z))
        r = predict_file(files[0], {"features": {"shape": [500, 471], "data": [0.] * (500 * 471)}})
        output = r["outputs"]["fc/post_act"]
        self.assertEqual(output["shape"], [500])
        for score in output["data"]: self.assertAlmostEqual(score, expected, places=6)
