#!/usr/bin/env python3
"""Serve a read-only localhost dashboard for a completed filter round."""
from __future__ import annotations
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = """<!doctype html><meta charset=utf-8><title>Filter round</title>
<style>body{font:14px sans-serif;max-width:1100px;margin:2em auto}pre{background:#f5f5f5;padding:1em;overflow:auto}canvas{width:100%;height:300px;border:1px solid #ddd}</style>
<h1>Visual residual-filter round</h1><div id=summary>loading…</div><canvas id=plot></canvas><h2>Training report</h2><pre id=train></pre><h2>Evaluation report</h2><pre id=eval></pre>
<script>
const R=location.pathname.replace(/\\/$/,''); Promise.all([fetch(R+'/model/training_report.json').then(r=>r.json()),fetch(R+'/evaluation/evaluation_report.json').then(r=>r.json()),fetch(R+'/evaluation/predictions.jsonl').then(r=>r.text())]).then(([t,e,p])=>{summary.textContent=`device=${t.device} | train episodes=${t.split.train_episode_ids.length} | windows=${e.aggregate.windows} | MAE=${e.aggregate.mae_rad}`;train.textContent=JSON.stringify(t,null,2);eval.textContent=JSON.stringify(e,null,2);let a=p.trim().split('\\n').filter(Boolean).map(JSON.parse),c=document.querySelector('canvas'),x=c.getContext('2d');c.width=1100;c.height=300;x.strokeStyle='#1677ff';x.beginPath();a.slice(0,500).forEach((v,i)=>{let y=150-(v.predicted_residual_rad||[0])[0]*3000;x.lineTo(i*2,y)});x.stroke()}).catch(e=>summary.textContent=e);
</script>"""

class Handler(BaseHTTPRequestHandler):
    def __init__(self, *a, root: Path, **kw): self.root=root; super().__init__(*a, **kw)
    def do_GET(self):
        rel=self.path.split('?',1)[0].lstrip('/')
        if not rel: rel='index.html'
        if rel=='index.html': data=HTML.encode(); typ='text/html'
        else:
            p=(self.root/rel).resolve()
            if self.root not in p.parents or not p.is_file(): self.send_error(404); return
            data=p.read_bytes(); typ='application/json' if p.suffix=='.json' else 'text/plain'
        self.send_response(200); self.send_header('Content-Type',typ); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--round',type=Path,required=True); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8765); a=ap.parse_args(); root=a.round.resolve();
    if not (root/'model/training_report.json').is_file(): raise SystemExit('round lacks model/training_report.json')
    server=ThreadingHTTPServer((a.host,a.port),lambda *x: Handler(*x,root=root)); print(f'http://{a.host}:{a.port}/'); server.serve_forever()
if __name__=='__main__': main()
