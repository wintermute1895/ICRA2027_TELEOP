#!/usr/bin/env python3
"""Compare timestamped VLM audit rows with reviewed human correction events."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def load(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def ts(row): return int(row.get("timestamp_ns", row.get("anchor_timestamp_ns")))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--vlm',type=Path,required=True); ap.add_argument('--human-events',type=Path,required=True); ap.add_argument('--tolerance-ms',type=float,default=500); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    vlm=sorted(load(a.vlm),key=ts); events=sorted(load(a.human_events),key=ts); tol=a.tolerance_ms*1e6
    intervals=[]; active=None
    for e in events:
        if e.get('event_type')=='correction_start': active=ts(e)
        elif e.get('event_type')=='correction_end' and active is not None: intervals.append((active,ts(e))); active=None
    if active is not None: intervals.append((active,ts(vlm[-1]) if vlm else active))
    rows=[]; matched=0; correct=0
    for row in vlm:
        t=ts(row); audit=row.get('audit') or {}; human=any(s<=t<=e for s,e in intervals)
        pred=bool(audit.get('correction_active', audit.get('fine_adjustment', False)))
        nearest=min((abs(t-ts(e)) for e in events),default=None)
        rows.append({'timestamp_ns':t,'human_correction_active':human,'vlm_correction_active':pred,'confidence':audit.get('confidence'),'nearest_event_error_ms':None if nearest is None else nearest/1e6,'parse_valid':row.get('parse_valid',False)})
        matched += int(nearest is not None and nearest<=tol); correct += int(human==pred)
    report={'schema':'robot_teleop.vlm-human-audit-comparison/v0.1','vlm_rows':len(vlm),'human_correction_intervals':intervals,'tolerance_ms':a.tolerance_ms,'nearest_event_matches':matched,'agreement':correct/len(rows) if rows else 0.0,'rows':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({'output':str(a.output),'agreement':report['agreement'],'rows':len(rows)}))
if __name__=='__main__': main()
