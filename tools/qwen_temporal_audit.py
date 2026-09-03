#!/usr/bin/env python3
"""Audit causal multi-frame windows with Qwen2.5-VL and emit boundary labels."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

PROMPT = '''You are auditing a robot manipulation sequence. The images are ordered oldest to newest and come from two cameras. Return exactly JSON with:
phase: one of approach, align, correction, recovery, terminal, unknown
correction_active: true, false, or null
correction_start: true or false
correction_end: true or false
confidence: number 0..1
notes: short evidence-based text
Use correction_start only when the sequence shows a transition into fine operator adjustment; use correction_end only when it shows a transition out. Do not infer hidden force or intent.'''

def parse(text):
    m=re.search(r'\{.*\}',text,re.S)
    try: return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError: return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--windows',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--model',type=Path,required=True); ap.add_argument('--device',default='cuda'); ap.add_argument('--max-samples',type=int,default=24); a=ap.parse_args()
    windows=[json.loads(x) for x in a.windows.read_text().splitlines() if x.strip()]
    if a.output.exists(): raise SystemExit(f'refusing to overwrite: {a.output}')
    windows=windows[:a.max_samples]
    try:
        import torch
        from PIL import Image,ImageDraw
        from transformers import AutoProcessor,Qwen2_5_VLForConditionalGeneration
    except ImportError as e: raise SystemExit('install requirements-vlm.txt in teleop-train') from e
    processor=AutoProcessor.from_pretrained(str(a.model),local_files_only=True,use_fast=False)
    model=Qwen2_5_VLForConditionalGeneration.from_pretrained(str(a.model),local_files_only=True,torch_dtype='auto').to(a.device).eval()
    out=[]
    for w in windows:
        imgs=[]
        for cam in w.get('camera_ids',[]):
            for f in w.get('frames',{}).get(cam,[]):
                ref=f.get('reference');
                if isinstance(ref,str) and Path(ref).is_file():
                    with Image.open(ref) as im: imgs.append(im.convert('RGB').resize((224,224)))
        if not imgs: continue
        contact=Image.new('RGB',(224*min(len(imgs),24),224),'black')
        for i,im in enumerate(imgs[:24]): contact.paste(im,(224*i,0))
        messages=[{'role':'user','content':[{'type':'image','image':contact},{'type':'text','text':PROMPT}]}]
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        inputs=processor(text=[text],images=[contact],padding=True,return_tensors='pt'); dev=next(model.parameters()).device; inputs={k:(v.to(dev) if hasattr(v,'to') else v) for k,v in inputs.items()}
        with torch.inference_mode(): gen=model.generate(**inputs,max_new_tokens=180,do_sample=False)
        raw=processor.batch_decode(gen[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0].strip(); parsed=parse(raw)
        out.append({'schema':'robot_teleop.vlm-temporal-audit/v0.1','anchor_timestamp_ns':w['anchor_timestamp_ns'],'window_start_ns':w['window_start_ns'],'window_end_ns':w['window_end_ns'],'causal':w.get('causal',False),'human_labels':w.get('labels',{}),'audit':parsed,'raw_response':raw,'parse_valid':parsed is not None})
        print(json.dumps({'anchor_timestamp_ns':w['anchor_timestamp_ns'],'parse_valid':parsed is not None}),flush=True)
    if not out: raise SystemExit('no temporal audits generated')
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out)); print(json.dumps({'output':str(a.output),'rows':len(out)}))
if __name__=='__main__': main()
