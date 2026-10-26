#!/usr/bin/env python3
"""Experimental FP32 reconstruction of the firmware's English UniLM decoder.

All learned tensors come from the verified IPSW cache. This is NOT AFM, Apple's
Espresso runtime, or a claim of parity with its dynamic int8 activation kernels.
Weight scales are applied to actual int8 tensors; activation arithmetic is FP32.
The tokenizer uses the observed mmap piece/score tables, not its opaque trie or
Apple's custom2 normalizer. Prompts are restricted to exactly encodable ASCII.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import time
import numpy as np
import torch
import torch.nn.functional as F

BASE = Path(__file__).resolve().parents[2]
BUNDLE = 'System/Library/LinguisticData/RequiredAssets_en.bundle/AssetData/en.lm/unilm.bundle'
FILES = ['unilm_joint_cpu.espresso.net', 'unilm_joint_cpu.espresso.shape',
         'unilm_joint.espresso.weights', 'sp.dat', 'modelInfo.plist']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verified_sources(root):
    assets = {x['firmware_path']: x for x in map(json.loads, (root/'models/assets.jsonl').open())
              if x['source']['volume_id'] == 'rootfs'}
    result, evidence = {}, []
    for name in FILES:
        fw = '/' + BUNDLE + '/' + name
        asset = assets[fw]
        raw = (root/'models/cache/rootfs'/BUNDLE/name).read_bytes()
        if len(raw) != asset['size_bytes'] or digest(raw) != asset['sha256']:
            raise ValueError('Cache integrity mismatch: ' + name)
        result[name] = raw
        evidence.append({k: asset[k] for k in ['id','model_id','firmware_path','size_bytes','sha256','source']})
    return result, evidence


def sections(raw):
    count, = struct.unpack_from('<Q', raw)
    if not 1 <= count <= 10000 or 8 + 16*count > len(raw):
        raise ValueError('Invalid Espresso section table')
    cursor, result = 8 + 16*count, {}
    for i in range(count):
        key, length = struct.unpack_from('<QQ', raw, 8+16*i)
        if key in result or cursor+length > len(raw):
            raise ValueError('Invalid section extent')
        result[key] = raw[cursor:cursor+length]
        cursor += length
    if cursor != len(raw):
        raise ValueError('Unaccounted bytes in weights')
    return result


class Tokenizer:
    def __init__(self, raw):
        if len(raw) < 36:
            raise ValueError('Truncated mmap tokenizer')
        self.count, = struct.unpack_from('<I', raw, 32)
        n = self.count
        if n != 15000 or len(raw) < 36+9*n+20:
            raise ValueError('Unexpected tokenizer table layout')
        self.types = raw[36:36+n]
        self.scores = np.frombuffer(raw, '<f4', n, 36+n).copy()
        offsets = struct.unpack_from('<'+str(n+5)+'I', raw, 36+5*n)
        base = 36+9*n+20
        self.pieces = []
        for off in offsets[5:]:
            if base+off >= len(raw):
                raise ValueError('Invalid tokenizer piece offset')
            end = raw.index(b'\0', base+off)
            self.pieces.append(raw[base+off:end].decode('utf-8'))
        if self.pieces[:4] != ['<pad>', '<s>', '</s>', '<unk>']:
            raise ValueError('Special token IDs differ')
        self.by_first = {}
        for i, text in enumerate(self.pieces):
            if self.types[i] == 1 and text:
                self.by_first.setdefault(text[0], []).append((text, i))

    def encode(self, text):
        if not text or not text.isascii() or any(c.isspace() and c != ' ' for c in text):
            raise ValueError('Probe supports nonempty ASCII prompts with ordinary spaces only')
        text = text.replace(' ', '▁')
        best = [-math.inf] * (len(text)+1)
        back = [None] * (len(text)+1)
        best[0] = 0.
        for pos, char in enumerate(text):
            if not math.isfinite(best[pos]):
                continue
            for piece, idx in self.by_first.get(char, []):
                end = pos+len(piece)
                score = best[pos]+float(self.scores[idx])
                if text.startswith(piece, pos) and score > best[end]:
                    best[end], back[end] = score, (pos, idx)
        if back[-1] is None:
            raise ValueError('Prompt cannot be exactly encoded without the unported normalizer')
        ids, cursor = [], len(text)
        while cursor:
            cursor, idx = back[cursor]
            ids.append(idx)
        ids.reverse()
        if self.decode(ids) != text.replace('▁', ' '):
            raise ValueError('Tokenizer round trip failed')
        return ids

    def decode(self, ids):
        return ''.join(self.pieces[i].replace('▁', ' ') for i in ids if i >= 24)


class UniLM:
    def __init__(self, source):
        self.graph = json.loads(source['unilm_joint_cpu.espresso.net'])
        self.layers = {x['name']: x for x in self.graph['layers']}
        if len(self.graph['layers']) != 254 or self.graph['storage'] != 'unilm_joint.espresso.weights':
            raise ValueError('Unexpected graph; this backend is bound to the audited decoder')
        self.sec = sections(source['unilm_joint.espresso.weights'])
        self.bindings = []
        self.emb = self.embedding('embed')
        self.pos = self.embedding('embed_position')
        self.seg = self.embedding('embed_segment')
        self.blocks = []
        for i in range(6):
            name = 'ane_gpt2_transformer_layer_3d' + ('_'+str(i) if i else '')
            self.blocks.append({
                'ln1': self.norm(name+'/ln_pre_attn'),
                'q': self.linear(name+':query_fc'),
                'k': self.linear(name+':key_fc'),
                'v': self.linear(name+':value_fc'),
                'attn': self.linear(name+'/attn_fc'),
                'ln2': self.norm(name+'/ln_pre_ffn'),
                'up': self.linear(name+'/ffn_expand'),
                'down': self.linear(name+'/ffn_contract')})
            if self.layers[name+'/ffn_act']['mode'] != 22:
                raise ValueError('Unexpected FFN activation')
            if self.layers[name+':scaled_raw_score']['alpha'] != .125:
                raise ValueError('Unexpected attention scale')
        self.final_norm = self.norm('decoder/ln_final')
        self.head = self.linear('lm_head/transform')
        self.head_norm = self.norm('lm_head/lnorm')
        final = self.linear('final_fc')
        if not torch.equal(final[0], self.emb):
            raise ValueError('Expected tied token embeddings / output projection')
        self.final = final

    def array(self, section, dtype, shape):
        x = np.frombuffer(self.sec[section], dtype=dtype)
        if x.size != math.prod(shape):
            raise ValueError(f'Section {section} does not have shape {shape}')
        if dtype != 'i1' and not np.isfinite(x).all():
            raise ValueError('Nonfinite learned tensor')
        self.bindings.append({'section':section,'dtype':dtype,'shape':list(shape),
                              'sha256':digest(self.sec[section])})
        return torch.from_numpy(x.copy().reshape(shape)).float()

    def embedding(self, name):
        l = self.layers[name]
        if l['quantization_mode'] != 2 or l['is_lookup'] != 1:
            raise ValueError('Unexpected embedding encoding')
        n, d, w = l['nB'], l['nC'], l['weights']
        return self.array(w['W_t_int8'], 'i1', (n,d)) * self.array(w['Qscale_t'],'<f4',(n,))[:,None]

    def linear(self, name):
        q, d = self.layers[name+'/quantized'], self.layers[name+'/dequantize']
        if q['quantization_mode'] != 5 or d['simple_mode'] != 1:
            raise ValueError('Unexpected dense encoding')
        n, k, w = q['nC'], q['nB'], d['weights']
        matrix = self.array(q['weights']['W_int8'],'i1',(n,k)) * self.array(w['Qscale'],'<f4',(n,))[:,None]
        bias = self.array(w['biases'],'<f4',(n,)) if 'biases' in w else None
        return matrix, bias

    def norm(self, name):
        l = self.layers[name]
        if l.get('tf_layernorm') != 1 or l.get('eps_in_square_root') != 1:
            raise ValueError('Unexpected normalization')
        w = l['weights']
        return self.array(w['wGamma'],'<f4',(512,)), self.array(w['wBeta'],'<f4',(512,)), l['eps']

    @staticmethod
    def ln(x, weights):
        gamma, beta, eps = weights
        return F.layer_norm(x, (512,), gamma, beta, eps)

    @torch.inference_mode()
    def step(self, idx, position, cache, segment=0):
        if not 0 <= idx < 15000 or not 0 <= position < 256 or segment not in (0,1):
            raise ValueError('Decoder index out of range')
        x = self.emb[idx] + self.pos[position] + self.seg[segment]
        for i,b in enumerate(self.blocks):
            h = self.ln(x,b['ln1'])
            q,k,v = [F.linear(h,*b[z]).reshape(8,64) for z in ['q','k','v']]
            if cache[i] is None:
                ks, vs = k[:,None,:], v[:,None,:]
            else:
                ks = torch.cat((cache[i][0],k[:,None,:]),dim=1)
                vs = torch.cat((cache[i][1],v[:,None,:]),dim=1)
            cache[i] = (ks,vs)
            scores = (q[:,None,:]*ks).sum(-1) * .125
            ctx = (scores.softmax(-1)[:,:,None]*vs).sum(1).reshape(512)
            x = x + F.linear(ctx,*b['attn'])
            h = self.ln(x,b['ln2'])
            x = x + F.linear(F.gelu(F.linear(h,*b['up']),approximate='tanh'),*b['down'])
        x = self.ln(x,self.final_norm)
        x = F.gelu(F.linear(x,*self.head),approximate='tanh')
        logits = F.linear(self.ln(x,self.head_norm),*self.final)
        if not torch.isfinite(logits).all():
            raise ValueError('Nonfinite logits')
        return logits


def generate(model, tokenizer, prompt, steps):
    ids = [1] + tokenizer.encode(prompt)
    if len(ids)+steps > 256:
        raise ValueError('Context exceeds the acquired positional embedding table')
    cache = [None]*6
    for position, idx in enumerate(ids):
        logits = model.step(idx,position,cache)
    generated, trace = [], []
    for _ in range(steps):
        probabilities = logits.softmax(-1)
        idx = int(logits.argmax())
        top = torch.topk(probabilities,5)
        trace.append({'token_id':idx,'piece':tokenizer.pieces[idx],
                      'logits_sha256':digest(logits.numpy().tobytes()),
                      'probability':float(probabilities[idx]),
                      'top5':[{'id':int(j),'piece':tokenizer.pieces[int(j)],'p':float(v)}
                              for j,v in zip(top.indices,top.values)]})
        generated.append(idx)
        if idx == 2:
            break
        logits = model.step(idx,len(ids)+len(generated)-1,cache)
    return {'prompt':prompt,'prompt_token_ids':ids,'generated_token_ids':generated,
            'generated_text':tokenizer.decode(generated),'trace':trace,
            'decoding':'greedy argmax; no logits masking, penalties, sampling or text substitution'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=BASE)
    p.add_argument('--prompt',action='append',required=True)
    p.add_argument('--steps',type=int,default=24)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    if not 1 <= a.steps <= 128:
        p.error('--steps must be between 1 and 128')
    torch.set_num_threads(2)
    started = time.monotonic()
    source,evidence = verified_sources(a.root)
    model,tokenizer = UniLM(source),Tokenizer(source['sp.dat'])
    result = {'status':'executed','model':'English firmware UniLM / LOCALHOST-2023-05-01-CPU-quant',
              'build':'24B115','artifact_kind':'real_pretrained_firmware_language_model',
              'afm':False,'apple_runtime_parity_verified':False,
              'backend':'independent PyTorch FP32 reconstruction of dequantized learned weights',
              'limitations':['Dynamic int8 activation quantization is bypassed; not bit parity with Espresso.',
                             'Activation mode 22 interpreted as tanh-approximate GELU.',
                             'ASCII unigram Viterbi from mmap tables; custom2 normalizer/trie unported.',
                             'Explicit BOS=1, segment=0; firmware calling convention not dynamically observed.'],
              'torch_version':torch.__version__,'numpy_version':np.__version__,
              'sources':evidence,'weight_sections':len(model.sec),'tensor_bindings':model.bindings,
              'architecture':{'blocks':6,'width':512,'heads':8,'head_dim':64,'ffn_width':2048,
                              'vocabulary':15000,'position_count':256,'weight_tying':True},
              'runs':[generate(model,tokenizer,prompt,a.steps) for prompt in a.prompt],
              'elapsed_seconds':time.monotonic()-started}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for row in result['runs']:
        print(repr(row['prompt']),'=>',repr(row['generated_text']))


if __name__ == '__main__':
    main()
