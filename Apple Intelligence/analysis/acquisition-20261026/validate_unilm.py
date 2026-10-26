#!/usr/bin/env python3
"""Independent NumPy Float64 full-context check against the cached Torch decoder.

This validates the stated reconstruction, not Apple's unobserved Espresso kernels.
The reference reads graph bindings and weight extents independently, uses dense
causal attention over the whole prefix, and does not use the Torch KV cache.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
import torch
import unilm_linux as impl


class Reference:
    def __init__(self, source):
        raw = source['unilm_joint.espresso.weights']
        count = int.from_bytes(raw[:8], 'little')
        table = np.frombuffer(raw, '<u8', count*2, 8).reshape(-1,2)
        ends = np.r_[8+count*16, 8+count*16+np.cumsum(table[:,1])]
        assert int(ends[-1]) == len(raw)
        self.data = {int(row[0]):raw[int(ends[i]):int(ends[i+1])] for i,row in enumerate(table)}
        self.layers = {l['name']:l for l in json.loads(source['unilm_joint_cpu.espresso.net'])['layers']}
        self.cached = {}

    def read(self, key, dtype, shape):
        return np.frombuffer(self.data[key], dtype=dtype).reshape(shape).astype(np.float64)

    def emb(self, name):
        if name not in self.cached:
            l = self.layers[name]; w = l['weights']
            x = self.read(w['W_t_int8'],'i1',(l['nB'],l['nC']))
            x *= self.read(w['Qscale_t'],'<f4',(l['nB'],))[:,None]
            self.cached[name] = x.astype(np.float32).astype(np.float64)
        return self.cached[name]

    def linear(self, x, name):
        if name not in self.cached:
            q,d = self.layers[name+'/quantized'],self.layers[name+'/dequantize']
            n,k = q['nC'],q['nB']; w = d['weights']
            mat = self.read(q['weights']['W_int8'],'i1',(n,k)) * self.read(w['Qscale'],'<f4',(n,))[:,None]
            bias = self.read(w['biases'],'<f4',(n,)) if 'biases' in w else np.zeros(n)
            self.cached[name] = (mat.astype(np.float32).astype(np.float64),bias)
        w,b = self.cached[name]
        return x @ w.T + b

    def norm(self, x, name):
        l = self.layers[name];w=l['weights']
        g = self.read(w['wGamma'],'<f4',(512,));b=self.read(w['wBeta'],'<f4',(512,))
        y = x-x.mean(-1,keepdims=True)
        return y/np.sqrt((y*y).mean(-1,keepdims=True)+l['eps'])*g+b

    @staticmethod
    def gelu(x):
        return .5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+.044715*x*x*x)))

    @staticmethod
    def softmax(x):
        e = np.exp(x-x.max(-1,keepdims=True))
        return e/e.sum(-1,keepdims=True)

    def full(self, ids):
        t=len(ids)
        x = self.emb('embed')[ids]+self.emb('embed_position')[np.arange(t)]+self.emb('embed_segment')[0]
        for i in range(6):
            name = 'ane_gpt2_transformer_layer_3d'+('_'+str(i) if i else '')
            h = self.norm(x,name+'/ln_pre_attn')
            q,k,v = [self.linear(h,name+':'+z+'_fc').reshape(t,8,64).transpose(1,0,2)
                     for z in ['query','key','value']]
            scores = (q @ k.transpose(0,2,1))*.125
            scores[:,np.triu_indices(t,1)[0],np.triu_indices(t,1)[1]] = -np.inf
            ctx = (self.softmax(scores) @ v).transpose(1,0,2).reshape(t,512)
            x = x+self.linear(ctx,name+'/attn_fc')
            h=self.norm(x,name+'/ln_pre_ffn')
            x=x+self.linear(self.gelu(self.linear(h,name+'/ffn_expand')),name+'/ffn_contract')
        h=self.norm(x,'decoder/ln_final')
        h=self.norm(self.gelu(self.linear(h,'lm_head/transform')),'lm_head/lnorm')
        return self.linear(h,'final_fc')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=impl.BASE)
    p.add_argument('--generation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    torch.set_num_threads(2)
    source,_=impl.verified_sources(a.root)
    model=impl.UniLM(source);reference=Reference(source)
    proof=json.loads(a.generation.read_text())
    checks=[]
    for row in proof['runs']:
        ids=row['prompt_token_ids']+row['generated_token_ids'][:4]
        full=reference.full(ids)
        cache=[None]*6
        for pos,idx in enumerate(ids):
            actual=model.step(idx,pos,cache).numpy()
            error=float(np.max(np.abs(actual-full[pos])))
            checks.append({'prompt':row['prompt'],'position':pos,
                           'max_abs_logits_error':error,'torch_top1':int(actual.argmax()),
                           'numpy_top1':int(full[pos].argmax()),'finite':bool(np.isfinite(actual).all())})
            assert error < 1e-3
            assert int(actual.argmax()) == int(full[pos].argmax())
        # Replay the recorded generation without looking at its expected token
        # until after computing the prediction.
        replay=impl.generate(model,impl.Tokenizer(source['sp.dat']),row['prompt'],len(row['generated_token_ids']))
        assert replay['generated_token_ids'] == row['generated_token_ids']
        assert replay['generated_text'] == row['generated_text']
        assert [x['logits_sha256'] for x in replay['trace']] == [x['logits_sha256'] for x in row['trace']]
    negatives=[]
    for name,func in [
        ('truncated_weights',lambda:impl.sections(source['unilm_joint.espresso.weights'][:-1])),
        ('out_of_range_position',lambda:model.step(1,256,[None]*6)),
        ('out_of_range_token',lambda:model.step(15000,0,[None]*6)),
        ('unported_normalizer_prompt',lambda:impl.Tokenizer(source['sp.dat']).encode('bonjour\n')),
    ]:
        try:
            func()
        except ValueError as e:
            negatives.append({'test':name,'rejected':True,'diagnostic':str(e)})
        else:
            raise AssertionError('Expected rejection: '+name)
    out={'status':'passed','comparison':'NumPy Float64 causal full-context vs PyTorch FP32 KV cache',
         'apple_runtime_parity_verified':False,'comparisons':len(checks),'checks':checks,
         'max_abs_logits_error':max(x['max_abs_logits_error'] for x in checks),
         'generation_replays':len(proof['runs']),'all_recorded_logits_hashes_match':True,
         'negative_tests':negatives,'all_15000_logits_checked_per_comparison':True}
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['checks','negative_tests']},indent=2))


if __name__=='__main__':
    main()
