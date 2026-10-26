"""Integration checks against the actual ignored firmware fixture, no fake weights."""

import json
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from apple_firmware_runtime.espresso import inspect_bundle, predict_bundle


DEFAULT_BUNDLE = Path(__file__).resolve().parents[2] / "models/cache/rootfs/System/Library/PrivateFrameworks/IntelligencePlatformCore.framework/EntitySimilarityLinearModel.mlmodelc"


class EspressoFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = Path(os.environ.get("APPLE_ENTITY_SIMILARITY_BUNDLE", str(DEFAULT_BUNDLE)))
        if not (cls.bundle / "model.espresso.weights").is_file():
            raise unittest.SkipTest("Actual firmware fixture missing; extract with models/scan_models.py --extract")

    def test_real_weight_identity_and_declared_sigmoid(self):
        result = inspect_bundle(self.bundle)
        self.assertEqual(result["weight_sha256"], "a2cde4443ca52b95feb4895c7352d390d59abdd0d55b58081d16c25c0266a0c7")
        self.assertEqual(result["operators"], ["inner_product", "sigmoid"])
        self.assertFalse(result["apple_runtime_parity_verified"])

    def test_real_model_numerical_vectors(self):
        # Goldens independently calculated with 70-digit Decimal.exp from the
        # actual firmware's Float32 bias at byte 128 and 62 weights at byte 192.
        # These check CPU mathematics, not parity with Apple's unavailable runtime.
        vectors = [
            ([0] * 62, 0.49867087602615356),
            ([1] * 62, 0.6698617339134216),
            ([1] + [0] * 61, 0.4974478483200073),
            ([(-1) ** i for i in range(62)], 0.4855302572250366),
            ([0] * 30 + [1] + [0] * 31, 0.5324782133102417),
        ]
        for vector, expected in vectors:
            with self.subTest(expected=expected):
                result = predict_bundle(self.bundle, {"x": [vector]})
                self.assertEqual(result["outputs"]["var_9"], expected)

    def test_input_contract_rejects_bad_tensors(self):
        malformed = [{}, {"x": [0] * 62}, {"x": [[0] * 61]}, {"x": [[0] * 62], "y": 0}]
        for value in [True, "1", None, math.inf, math.nan, 1e100, 10 ** 500]:
            malformed.append({"x": [[value] + [0] * 61]})
        for inputs in malformed:
            with self.subTest(inputs=repr(inputs)[:80]), self.assertRaises(ValueError):
                predict_bundle(self.bundle, inputs)

    def test_extreme_finite_input_uses_stable_sigmoid(self):
        for value in [-3e38, 3e38]:
            probability = predict_bundle(self.bundle, {"x": [[value] * 62]})["outputs"]["var_9"]
            self.assertIn(probability, (0.0, 1.0))

    def _copy(self, parent):
        path = Path(parent) / "Entity.mlmodelc"
        path.mkdir()
        for name in ["metadata.json", "model.espresso.net", "model.espresso.shape", "model.espresso.weights"]:
            shutil.copyfile(self.bundle / name, path / name)
        return path

    def test_graph_mutations_rejected(self):
        for mutation in ["new_layer", "quantization", "wrong_activation", "wrong_shape", "missing_sigmoid_attestation", "malformed_properties"]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                path = self._copy(temp)
                target = path / "model.espresso.net"
                value = json.loads(target.read_text())
                if mutation == "new_layer":
                    value["layers"].append({"type": "identity"})
                elif mutation == "quantization":
                    value["layers"][0]["weights"] = {"W_U8": 3}
                elif mutation == "wrong_activation":
                    value["layers"][1]["mode"] = 1
                elif mutation == "malformed_properties":
                    value["properties"] = []
                elif mutation == "wrong_shape":
                    target = path / "model.espresso.shape"
                    value = json.loads(target.read_text())
                    value["layer_shapes"]["x"]["w"] = 61
                else:
                    target = path / "metadata.json"
                    value = json.loads(target.read_text())
                    value[0]["neuralNetworkLayerTypeHistogram"] = {"ActivationReLU": 1, "InnerProduct": 1}
                target.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    inspect_bundle(path)

    def test_weight_corruption_rejected(self):
        original = (self.bundle / "model.espresso.weights").read_bytes()
        changes = [
            original[:-1],
            struct.pack("<Q", 5) + original[8:],
            original[:24] + struct.pack("<Q", 0) + original[32:],
            original[:128] + struct.pack("<f", math.nan) + original[132:],
            original[:192] + struct.pack("<f", math.inf) + original[196:],
            original[:144] + b"\x01" + original[145:],
        ]
        for index, corrupt in enumerate(changes):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                path = self._copy(temp)
                (path / "model.espresso.weights").write_bytes(corrupt)
                with self.assertRaises(ValueError):
                    predict_bundle(path, {"x": [[0] * 62]})


if __name__ == "__main__":
    unittest.main()
