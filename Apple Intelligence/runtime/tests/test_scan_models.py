"""Coverage regressions found while auditing every image of the local IPSW."""
import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('scan_models', BASE/'models/scan_models.py')
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class SelectionTests(unittest.TestCase):
    def selected(self, *paths):
        return scanner.select([{'path':p,'kind':kind} for kind,p in paths])

    def test_new_graph_packages_include_opaque_sidecars(self):
        root='/System/Library/Frameworks/MetalFX.framework/a.mpsgraphpackage'
        rows=self.selected((4,root),(8,root+'/model_0.mpsgraph'),(8,root+'/resources.bin'),
                           (8,root+'/reflection.fb'))
        self.assertEqual(len(rows),3)
        self.assertEqual({bundle for _,bundle in rows},{root})

    def test_explicit_weights_and_language_sidecars_are_covered(self):
        paths=['/CreateML/PretrainedHandActionClassifier.weights',
               '/CreateMLComponents/diffusionTrackerWeights.bin',
               '/CreateMLComponents/diffusionTrackerWeightsDescription.json',
               '/LinguisticData/RequiredAssets_en.bundle/AssetData/en.lm/unilm.bundle/sp.dat',
               '/DocumentUnderstanding/l4-smolberto.nlembedding',
               '/Vision/weights/gaze.bin', '/Models/known.bin',
               '/Vision/neuralhash_128x96_seed1.dat']
        self.assertEqual(len(self.selected(*[(8,p) for p in paths])),len(paths))

    def test_unrelated_binary_schemas_and_lightweight_plan_are_not_models(self):
        paths=['/AWD/Metadata/AwdMetadata-0x66-ProactiveAppPrediction.bin',
               '/Trace/Plans/lightweight.json','/Radio/firmware.bin','/db/Schema.mom',
               '/CoreAI/default.metallib']
        self.assertEqual(self.selected(*[(8,p) for p in paths]),[])

    def test_old_espresso_group_identity_survives_new_bin_sidecar(self):
        net='/LinguisticData/a.cpml/ctc_model.espresso.net'
        weights=net.removesuffix('.net')+'.bin'
        old=scanner.group_key({'path':net},'')
        new=scanner.group_key({'path':weights},'')
        self.assertEqual(old,new)
        self.assertEqual(scanner.classify(weights),('espresso_weights','weights'))

    def test_old_standalone_language_model_id_is_not_regrouped(self):
        p='/LinguisticData/RequiredAssets_th.bundle/AssetData/th.rnnlm/model.bin'
        rows=self.selected((4,p.rsplit('/',1)[0]),(8,p))
        self.assertEqual(rows[0][1],'')
        self.assertEqual(scanner.group_key(rows[0][0],''),(p,p.rsplit('/',1)[0],'file'))


if __name__=='__main__':
    unittest.main()
