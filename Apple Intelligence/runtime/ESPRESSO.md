# Portable Espresso inference: one attested graph

`apple_firmware_runtime.espresso` computes the actual firmware weights on Linux
or another Python 3.10+ host. It uses the standard library and does not substitute
another model or manufacture outputs. It is an independent CPU graph evaluator;
it does not execute Apple's Espresso/Core ML binaries.

The current whitelist accepts the exact `EntitySimilarityLinearModel.mlmodelc`
graph under `IntelligencePlatformCore.framework`: a dense layer with 62 inputs,
one output and a bias, followed by a sigmoid. `model.espresso.net` names the
operator and weight sections; `model.espresso.shape` gives tensor dimensions;
`metadata.json` explicitly corroborates `InnerProduct: 1, ActivationSigmoid: 1`.
Other graphs, quantized graphs and additional operators are rejected.

The original 440-byte `model.espresso.weights` has SHA-256
`a2cde4443ca52b95feb4895c7352d390d59abdd0d55b58081d16c25c0266a0c7`.
The decoder reads little-endian 64-bit section count `4`, then four 64-bit
`(id, byte length)` pairs: `(0,56), (1,16), (2,48), (3,248)`. The sections follow
the 72-byte table. The first Float32 in section 1 is the bias
`-0.005316493567079306`; its remaining bytes are padding. Section 3 contains the
62 Float32 coefficients. The parser checks lengths, padding and finite values.
The local catalogue/store independently verifies the complete asset's hashes.

`inspect_bundle(Path)` returns the supported schema or raises `ValueError`.
`predict_bundle(Path, inputs)` requires `{"x": [[62 finite numbers]]}` and returns
`{"backend": "espresso-linear-cpu-experimental", "outputs": {"var_9": number}, ...}`.
Inputs and weights are Float32. Products, accumulation and the stable sigmoid
are evaluated in Float64; the scalar output is rounded to Float32.

Five reference vectors were calculated separately using 70-digit Decimal
arithmetic on the original decoded bytes. All-zero input returns
`0.49867087602615356`; all-one input returns `0.6698617339134216`. Integration
tests also reject corrupt section tables, nonfinite values, malformed inputs
and unsupported graph mutations. Run from this directory:

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -p test_espresso.py -v
```

The actual firmware bundle is in the local firmware corpus under
`../models/cache/rootfs/System/Library/PrivateFrameworks/IntelligencePlatformCore.framework/`.
Set `APPLE_ENTITY_SIMILARITY_BUNDLE` to an independently acquired complete bundle
to run these tests elsewhere. The integration tests skip when that fixture is
absent; no firmware weights are embedded in the tests.

The firmware metadata declares `computePrecision: Float16`. No comparison with
the Apple runtime has been performed, so these results establish the specified
CPU mathematics using authentic weights, not bitwise device parity or the
quality of an entity matching task. This model consumes 62 numeric features;
the firmware feature extraction pipeline is outside this evaluator. It is not
an Apple Foundation Model and does not generate text, Genmoji or images.

The sigmoid formula is also specified in Apple's [Core ML format reference](https://apple.github.io/coremltools/mlmodel/Format/NeuralNetwork.html).
