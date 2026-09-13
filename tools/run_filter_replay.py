#!/usr/bin/env python3
"""Replay JSONL raw/candidate/gain records through the experiment contract."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, yaml
from filter_experiment_loop import bounded_gain, rate_limit_gain, compose, safety_project

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--input',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    c=yaml.safe_load(Path(a.config).read_text()) or {}; auth=c['authority']; safety=c['safety']; prev=None; prev_gain=None; out=[]
    for line in Path(a.input).read_text().splitlines():
        if not line.strip(): continue
        row=json.loads(line); raw=np.asarray(row['raw'],dtype=np.float32); cand=np.asarray(row['candidate'],dtype=np.float32)
        gain=bounded_gain(auth['mode'],model_gain=row.get('gain'),alpha=float(auth.get('alpha',0)),alpha_max=float(auth['alpha_max']),fallback_alpha=float(auth.get('fallback_alpha',0)))
        gain=rate_limit_gain(gain,prev_gain,float(auth.get('alpha_rate',0)),float(row.get('dt_s',1.0)/max(float(c['runtime']['inference_hz']),1)))
        composed=compose(raw,cand,gain); issued=safety_project(composed,prev,float(safety['max_delta_rad']),float(safety['max_step_rad']))
        out.append({**row,'gain':gain,'composed':composed.tolist(),'issued':issued.tolist()}); prev,prev_gain=issued,gain
    Path(a.output).write_text('\n'.join(json.dumps(x,separators=(',',':')) for x in out)+'\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
