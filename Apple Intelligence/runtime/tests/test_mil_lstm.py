"""Independent scalar checks for the bounded recurrent MIL CPU implementation."""
import importlib.util
from pathlib import Path
import unittest

AVAILABLE = all(importlib.util.find_spec(x) is not None for x in ("numpy", "coremltools"))
if AVAILABLE:
    import numpy as np
    from coremltools.proto import MIL_pb2, Model_pb2
    from apple_firmware_runtime.protobuf_cpu import evaluate, mil_lstm, predict_file
    example_path = Path(__file__).resolve().parents[1] / "examples/demo_tte_runtime.py"
    module_spec = importlib.util.spec_from_file_location("tte_math_reference", example_path)
    reference = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(reference)


@unittest.skipUnless(AVAILABLE, "Optional CPU dependencies absent: install .[cpu]")
class MilLstmTests(unittest.TestCase):
    def args(self):
        return {"x": np.asarray([[[0.1, -0.3], [0.7, 0.2]],
                                  [[0.9, -0.6], [-0.2, 0.4]],
                                  [[0.8, 0.5], [-0.4, 0.3]]], dtype=np.float32),
                "initial_h": np.asarray([[0.2, -0.1], [0.4, -0.3]], dtype=np.float32),
                "initial_c": np.asarray([[-0.3, 0.7], [0.8, -0.6]], dtype=np.float32),
                "weight_ih": (np.arange(16, dtype=np.float32).reshape(8, 2) - 7) / 10,
                "weight_hh": (np.arange(16, dtype=np.float32).reshape(8, 2) - 4) / 13,
                "bias": np.asarray([0.2, -0.1, 0.7, 0.9, -0.4, 0.6, 0.3, -0.8], dtype=np.float32),
                "output_sequence": np.asarray(True)}

    def const(self, block, name, data):
        a = np.asarray(data)
        op = block.operations.add(); op.type = "const"
        v = op.attributes["val"]
        v.type.tensorType.dataType = {"f": MIL_pb2.FLOAT32, "i": MIL_pb2.INT32,
                                     "b": MIL_pb2.BOOL}[a.dtype.kind]
        v.type.tensorType.rank = a.ndim
        for n in a.shape: v.type.tensorType.dimensions.add().constant.size = n
        kind = {"f": "floats", "i": "ints", "b": "bools"}[a.dtype.kind]
        getattr(v.immediateValue.tensor, kind).values.extend(a.reshape(-1).tolist())
        out = op.outputs.add(); out.name = name; out.type.CopyFrom(v.type)

    def graph(self, args):
        s = Model_pb2.Model()
        f = s.description.input.add(); f.name = "x"
        f.type.multiArrayType.shape.extend(args["x"].shape); f.type.multiArrayType.dataType = 65568
        block = s.mlProgram.functions["main"].block_specializations["CoreML5"]
        for name, data in args.items():
            if name != "x": self.const(block, name, data)
        op = block.operations.add(); op.type = "lstm"
        for name in args: op.inputs[name].arguments.add().name = name
        for name in ("sequence", "h", "c"):
            out = op.outputs.add(); out.name = name; out.type.tensorType.dataType = MIL_pb2.FLOAT32
            s.description.output.add().name = name
        return s

    def test_multibatch_multistep_gate_order_against_scalar_reference(self):
        args = self.args()
        expected = reference.scalar_lstm_reference(args)
        h0, c0 = args["initial_h"].copy(), args["initial_c"].copy()
        result = evaluate(self.graph(args), {"x": args["x"]}, Path("."))
        for name, want in zip(("sequence", "h", "c"), expected):
            np.testing.assert_allclose(result[name], want, atol=2e-7, rtol=2e-6)
            self.assertEqual(result[name].dtype, np.float32)
        np.testing.assert_array_equal(args["initial_h"], h0)
        np.testing.assert_array_equal(args["initial_c"], c0)

    def test_default_bias_and_last_step_output(self):
        args = self.args(); args.pop("output_sequence"); args.pop("bias")
        expected = reference.scalar_lstm_reference(args | {"bias": np.zeros(8, dtype=np.float32)})
        result = mil_lstm(args)
        self.assertEqual(result[0].shape, (1, 2, 2))
        for observed, want in zip(result, (expected[0][-1:], expected[1], expected[2])):
            np.testing.assert_allclose(observed, want, atol=2e-7, rtol=2e-6)

    def test_unsupported_lstm_variants_and_invalid_shapes_refused(self):
        variants = ({"direction": np.asarray("reverse")}, {"activation": np.asarray("relu")},
                    {"direction": np.asarray(["forward"])},
                    {"peephole": np.zeros(6, dtype=np.float32)}, {"clip": np.asarray(1, dtype=np.float32)},
                    {"output_sequence": np.asarray(1)}, {"initial_h": np.zeros((1, 2), dtype=np.float32)},
                    {"bias": np.zeros((8, 1), dtype=np.float32)},
                    {"weight_ih": np.zeros((9, 2), dtype=np.float32)},
                    {"weight_hh": np.zeros((8, 2), dtype=np.float16)},
                    {"x": np.zeros((0, 2, 2), dtype=np.float32)},
                    {"x": np.full((3, 2, 2), np.nan, dtype=np.float32)})
        for variant in variants:
            with self.subTest(arguments=list(variant)):
                with self.assertRaises(ValueError): mil_lstm(self.args() | variant)

    def test_overflowing_gates_refused_before_saturating_activations(self):
        args = self.args() | {"x": np.full((3, 2, 2), 3e38, dtype=np.float32),
                              "weight_ih": np.full((8, 2), 3e38, dtype=np.float32)}
        with np.errstate(over="ignore"):
            with self.assertRaisesRegex(ValueError, "Nonfinite"): mil_lstm(args)

    def test_lstm_work_budget_checked_before_recurrence(self):
        args = {"x": np.zeros((7000, 1, 1), dtype=np.float32),
                "initial_h": np.zeros((1, 64), dtype=np.float32),
                "initial_c": np.zeros((1, 64), dtype=np.float32),
                "weight_ih": np.zeros((256, 1), dtype=np.float32),
                "weight_hh": np.zeros((256, 64), dtype=np.float32)}
        with self.assertRaisesRegex(ValueError, "work limit"): mil_lstm(args)

    def transform_graph(self, axes, reps):
        s = Model_pb2.Model(); f = s.description.input.add(); f.name = "x"
        f.type.multiArrayType.shape.extend([2, 2]); f.type.multiArrayType.dataType = 65568
        s.description.output.add().name = "tiled"
        block = s.mlProgram.functions["main"].block_specializations["CoreML5"]
        self.const(block, "axes", np.asarray(axes, dtype=np.int32))
        self.const(block, "reps", np.asarray(reps, dtype=np.int32))
        for typ, out, inputs in (("expand_dims", "expanded", {"x": "x", "axes": "axes"}),
                                  ("tile", "tiled", {"x": "expanded", "reps": "reps"})):
            op = block.operations.add(); op.type = typ
            for name, source in inputs.items(): op.inputs[name].arguments.add().name = source
            o = op.outputs.add(); o.name = out; o.type.tensorType.dataType = MIL_pb2.FLOAT32
        return s

    def test_expand_negative_axes_and_tile_preserve_element_order(self):
        result = evaluate(self.transform_graph([-1, 0], [1, 1, 2, 1]),
                          {"x": [[1., 2.], [3., 4.]]}, Path("."))["tiled"]
        self.assertEqual(result.shape, (1, 2, 4, 1))
        self.assertEqual(result.reshape(-1).tolist(), [1., 2., 1., 2., 3., 4., 3., 4.])

    def test_expand_and_tile_invalid_or_oversized_shapes_refused(self):
        for axes, reps in (([3], [1, 1, 1]), ([-4], [1, 1, 1]), ([0], [1, 0, 1]),
                           ([0], [1, 1]), ([0], [10000000, 1, 1]), ([0, -4], [1, 1, 1, 1])):
            with self.subTest(axes=axes, reps=reps):
                with self.assertRaises(ValueError):
                    evaluate(self.transform_graph(axes, reps), {"x": [[1., 2.], [3., 4.]]}, Path("."))

    def test_real_tte_lstm_all_states_against_independent_raw_blob_reference(self):
        root = Path(__file__).resolve().parents[2] / "models/cache"
        files = list(root.rglob("TTE_Model/Data/com.apple.CoreML/model.mlmodel"))
        if not files: self.skipTest("Actual TTE firmware fixture absent")
        path = files[0]; spec = Model_pb2.Model(); spec.ParseFromString(path.read_bytes())
        for fill in (0, 1):
            with self.subTest(fill=fill):
                args = reference.independent_tte_lstm_args(spec, path.parent, fill)
                expected = reference.scalar_lstm_reference(args)
                inputs = {"temporal_features": {"shape": [1, 19, 5], "data": [fill] * 95},
                          "static_features": {"shape": [1, 10], "data": [fill] * 10}}
                for observed, want in zip(reference.evaluate_tte_lstm_prefix(spec, inputs, path.parent), expected):
                    np.testing.assert_allclose(observed, want, atol=2e-6, rtol=2e-5)
                result = predict_file(path, inputs)
                self.assertEqual(result["outputs"]["var_80"]["shape"], [1, 19, 1])
                self.assertFalse(result["apple_runtime_parity_verified"])


if __name__ == "__main__": unittest.main()
