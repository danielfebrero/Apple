"""Nonuniform convolution tests plus independent real quantized CNN references."""
import importlib.util
import math
from pathlib import Path
import unittest

AVAILABLE = all(importlib.util.find_spec(x) is not None for x in ("numpy", "coremltools"))
if AVAILABLE:
    import numpy as np
    from coremltools.proto import Model_pb2, NeuralNetwork_pb2
    from coremltools.models.neural_network.quantization_utils import _dequantize_wp
    from apple_firmware_runtime.protobuf_cpu import evaluate, nn_convolution, nn_weights, predict_file
    p = Path(__file__).resolve().parents[1] / "examples/demo_cnn_runtime.py"
    module_spec = importlib.util.spec_from_file_location("cnn_math_reference", p)
    reference = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(reference)


@unittest.skipUnless(AVAILABLE, "Optional CPU dependencies absent: install .[cpu]")
class NeuralSpatialTests(unittest.TestCase):
    def weights(self, raw, scales, biases):
        w = NeuralNetwork_pb2.WeightParams(); w.rawValue = bytes(raw)
        w.quantization.numberOfBits = 8
        w.quantization.linearQuantization.scale.extend(scales)
        w.quantization.linearQuantization.bias.extend(biases)
        return w

    def convolution(self):
        op = NeuralNetwork_pb2.ConvolutionLayerParams()
        op.outputChannels = 2; op.kernelChannels = 2; op.nGroups = 1; op.hasBias = True
        op.kernelSize.extend([2, 2]); op.stride.extend([1, 2]); op.dilationFactor.extend([1, 1])
        op.valid.SetInParent()
        op.weights.CopyFrom(self.weights([1, 4, 2, 5, 3, 6, 8, 7, 12, 9, 11, 10, 14, 13, 16, 15],
                                         [0.125, 0.25], [-0.75, -2.]))
        op.bias.CopyFrom(self.weights([2, 7], [0.1], [-0.2]))
        return op

    def test_quantization_matches_explicit_affine_values_and_official_decoder(self):
        w = self.weights([0, 255, 1, 254], [0.25, 0.5], [-1., -2.])
        np.testing.assert_array_equal(nn_weights(w, (2, 2)), [-1., 62.75, -1.5, 125.])
        official = NeuralNetwork_pb2.WeightParams(); official.CopyFrom(w)
        _dequantize_wp(official, (2, 2))
        np.testing.assert_array_equal(nn_weights(w, (2, 2)), official.floatValue)
        bias = self.weights([0, 255], [0.25], [-1.])
        np.testing.assert_array_equal(nn_weights(bias, (2,)), [-1., 62.75])

    def test_nonuniform_multichannel_convolution_against_scalar_spatial_sums(self):
        op = self.convolution()
        x = (np.arange(48, dtype=np.float32).reshape(2, 2, 3, 4) - 17) / 7
        weights = reference.scalar_dequantize(op.weights, (2, 2, 2, 2))
        bias = reference.scalar_dequantize(op.bias, (2,))
        expected = np.empty((2, 2, 2, 2), dtype=np.float64)
        for n in range(2):
            for out in range(2):
                for y in range(2):
                    for z in range(2):
                        expected[n, out, y, z] = math.fsum([bias[out]] + [
                            weights[((out * 2 + c) * 2 + ky) * 2 + kx] * float(x[n, c, y + ky, z * 2 + kx])
                            for c in range(2) for ky in range(2) for kx in range(2)])
        np.testing.assert_allclose(nn_convolution(x, op), expected, atol=3e-6, rtol=2e-6)

    def test_maxpool_nonuniform_windows_and_strides(self):
        s = Model_pb2.Model(); f = s.description.input.add(); f.name = "x"
        f.type.multiArrayType.shape.extend([1, 1, 3, 4]); f.type.multiArrayType.dataType = 65568
        s.description.output.add().name = "y"; s.neuralNetwork.arrayInputShapeMapping = 1
        layer = s.neuralNetwork.layers.add(); layer.input.append("x"); layer.output.append("y")
        op = layer.pooling; op.type = 0; op.kernelSize.extend([2, 2]); op.stride.extend([1, 2]); op.valid.SetInParent()
        x = [[[[-1., 4., 2., 8.], [3., 0., 5., 7.], [11., 6., 9., 12.]]]]
        np.testing.assert_array_equal(evaluate(s, {"x": x}, Path("."))["y"], [[[[4., 8.], [11., 12.]]]])
        op.type = 1
        with self.assertRaisesRegex(ValueError, "max pooling"): evaluate(s, {"x": x}, Path("."))
        op.type = 0; layer.input.append("x")
        with self.assertRaisesRegex(ValueError, "input arity"): evaluate(s, {"x": x}, Path("."))

    def test_unsupported_quantization_and_invalid_weight_lengths_refused(self):
        w = self.weights([0, 1, 2, 3], [0.25, 0.5], [-1., -2.])
        variants = []
        for change in ("bits", "scales", "payload", "mixed", "signed"):
            bad = NeuralNetwork_pb2.WeightParams(); bad.CopyFrom(w)
            if change == "bits": bad.quantization.numberOfBits = 4
            elif change == "scales": bad.quantization.linearQuantization.scale.append(1.)
            elif change == "payload": bad.rawValue = bad.rawValue[:-1]
            elif change == "mixed": bad.floatValue.append(0.)
            elif change == "signed": bad.int8RawValue = b"\0"
            variants.append((change, bad))
        for name, bad in variants:
            with self.subTest(variant=name):
                with self.assertRaises(ValueError): nn_weights(bad, (2, 2))
        plain = NeuralNetwork_pb2.WeightParams(); plain.floatValue.append(1.)
        with self.assertRaisesRegex(ValueError, "length"): nn_weights(plain, (2,))

    def test_duplicate_normalized_neural_expand_axes_refused(self):
        s = Model_pb2.Model(); f = s.description.input.add(); f.name = "x"
        f.type.multiArrayType.shape.extend([2, 2]); f.type.multiArrayType.dataType = 65568
        s.description.output.add().name = "y"; s.neuralNetwork.arrayInputShapeMapping = 1
        layer = s.neuralNetwork.layers.add(); layer.input.append("x"); layer.output.append("y")
        layer.expandDims.axes.extend([0, -4])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            evaluate(s, {"x": [[1., 2.], [3., 4.]]}, Path("."))

    def test_unsupported_convolution_variants_and_oversized_windows_refused(self):
        x = np.zeros((1, 2, 3, 4), dtype=np.float32)
        for variant in ("grouped", "dilated", "transposed", "same", "padding", "oversized"):
            op = self.convolution()
            if variant == "grouped": op.nGroups = 2
            elif variant == "dilated": op.dilationFactor[1] = 2
            elif variant == "transposed": op.isDeconvolution = True
            elif variant == "same": op.same.SetInParent()
            elif variant == "padding": op.valid.paddingAmounts.borderAmounts.add().startEdgeSize = 1
            elif variant == "oversized": op.kernelSize[0] = 4
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError): nn_convolution(x, op)
        op = self.convolution(); op.kernelSize[:] = [32, 32]; op.stride[:] = [1, 1]
        with self.assertRaisesRegex(ValueError, "oversized tensor shape"):
            nn_convolution(np.zeros((1, 2, 128, 128), dtype=np.float32), op)

    def test_real_quantized_cnn_scores_against_scalar_constant_channel_reference(self):
        root = Path(__file__).resolve().parents[2] / "models/cache"
        for name, classes in (("mainModel_USEN.mlmodel", 3), ("subClassModel_USEN.mlmodel", 4)):
            files = list(root.rglob(name))
            if not files: self.skipTest("Actual quantized CNN firmware fixtures absent")
            path = files[0]; spec = Model_pb2.Model(); spec.ParseFromString(path.read_bytes())
            for fill in (0, 1):
                with self.subTest(model=name, fill=fill):
                    result = predict_file(path, {"inp": {"shape": [1, 512, 1, 256], "data": [fill] * (512 * 256)}})
                    output = result["outputs"]["linear_0"]
                    self.assertEqual(output["shape"], [1, classes])
                    np.testing.assert_allclose(output["data"], reference.constant_cnn_reference(spec, fill),
                                               atol=2e-5, rtol=2e-5)
                    self.assertFalse(result["apple_runtime_parity_verified"])


if __name__ == "__main__": unittest.main()
