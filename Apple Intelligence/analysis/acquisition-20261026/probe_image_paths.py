#!/usr/bin/env python3
"""Inspect actual image-related payloads and test the available MLIR loader.

Never substitutes random/synthetic weights, a third-party diffusion network,
an upscaled image, or a keypoint vector for Image Playground generation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=BASE)
    p.add_argument('--coreai-python',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    models=json.loads((a.root/'models/manifest.json').read_text())['models']
    refs=list(map(json.loads,(a.root/'models/references.jsonl').open()))
    needed=[r for r in refs if 'image_diffusion_v1' in r['identifier']]
    def raw_asset(model,name):
        f=next(x for x in model['files'] if x['path']==name)
        path=a.root/model['source_path']/name
        raw=path.read_bytes()
        if len(raw)!=f['size'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:
            raise ValueError('Integrity mismatch: '+str(path))
        return path,raw
    packages=[]
    for m in models:
        if m['format']!='apple_mpsgraph_package':
            continue
        row={'model_id':m['id'],'firmware_path':m['firmware_path'],'files':[],
             'role':'MetalFX image processing candidate; no identification as Apple image diffusion'}
        for f in m['files']:
            path,raw=raw_asset(m,f['path'])
            item={'path':f['path'],'size':len(raw),'sha256':f['sha256']}
            if path.suffix=='.mpsgraph':
                for permissive in (False,True):
                    context='c=Context(); c._mlir_context.allow_unregistered_dialects=True; ' if permissive else ''
                    argument=',c._mlir_context' if permissive else ''
                    code=('import resource; resource.setrlimit(resource.RLIMIT_CORE,(0,0)); '
                          'from coreai.authoring import AIProgram,Context; from pathlib import Path; import sys; '
                          +context+'p=AIProgram._load_bytecode(Path(sys.argv[1])'+argument+'); print("bytecode parsed")')
                    key='coreai_permissive_bytecode_probe' if permissive else 'coreai_bytecode_probe'
                    try:
                        r=subprocess.run([str(a.coreai_python),'-c',code,str(path)],capture_output=True,text=True,timeout=30)
                        item[key]={'exit_code':r.returncode,'stdout':r.stdout[-500:],
                                   'stderr':r.stderr[-2400:],'prediction_performed':False,
                                   'allow_unregistered_dialects':permissive,
                                   'api':'AIProgram._load_bytecode; internal API probe only; child process with core dumps disabled'}
                    except subprocess.TimeoutExpired:
                        item[key]={'timeout_seconds':30,'prediction_performed':False}
            row['files'].append(item)
        packages.append(row)
    trackers=[]
    for m in models:
        if 'diffusionTracker' not in m['firmware_path'] or not m['firmware_path'].endswith('Description.json'):
            continue
        _,raw=raw_asset(m,m['files'][0]['path'])
        tensors=json.loads(raw)
        trackers.append({'model_id':m['id'],'path':m['firmware_path'],'sha256':hashlib.sha256(raw).hexdigest(),
                         'tensor_descriptions':len(tensors),
                         'heads':[x for x in tensors if x['name'].startswith('heads.')],
                         'observation':'Declared DiffusionKeyPoints3D dense output has 24 components; tracking/confidence heads.',
                         'image_generation_proven':False})
    codemaps=[{'model_id':m['id'],'path':m['firmware_path'],'format':m['format'],'bytes':m['total_size_bytes']}
              for m in models if '/CoreHandwriting.framework/diffusion_' in m['firmware_path']]
    out={'status':'blocked_missing_identified_apple_image_generation_payload',
         'image_generation_proven':False,'generation_attempted':False,
         'reason':'No complete identified Image Playground / image_diffusion_v1 trained payload in the seven inventoried images.',
         'reference_only_image_diffusion_identifiers':[{'id':r['id'],'identifier':r['identifier'],
                                                        'weights_proven':r['weights_proven'],
                                                        'first_evidence':r['evidence'][0]} for r in needed],
         'metalfx_packages':packages,'diffusion_named_trackers':trackers,'handwriting_metadata':codemaps,
         'next_step':{'asset_family':'com.apple.MobileAsset.UAF.FM.Visual',
                      'required':'Acquire an actual catalogue with payload BaseURL/RelativePath and expected identity, or complete downloaded device bundles including manifests, trained denoiser/decoder and conditioning resources.',
                      'available_local_downloader':'python3 models/download_asset.py catalogue CATALOGUE; then fetch with actual URL/size/SHA-256',
                      'runtime_after_acquisition':'Identify true container and graph; port its learned operators and scheduler to Linux and save prompt/seed/image/hash. Current Core AI backend handles .aimodel, not arbitrary .mpsgraph or .mlmodelc.'},
         'limits':['Name-based candidates and explicit selectors do not identify every opaque firmware blob.',
                   'A failed bytecode load establishes this tested loader boundary, not impossibility of another port.']}
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'reference_only_image_models':len(needed),
                      'mpsgraph_packages_probed':len(packages),'tracker_descriptions':len(trackers),
                      'coreai_exit_codes':[f['coreai_bytecode_probe'].get('exit_code') for m in packages for f in m['files'] if 'coreai_bytecode_probe' in f]},indent=2))


if __name__=='__main__':
    main()
