#!/usr/bin/env python3
"""Align a Filter replay to raw episodes and analyze its URDF FK trajectories."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

SIGN=np.array([1,1,1,1,1,-1,1],float)
JOINTS=["Right_Shoulder_Pitch_Joint","Right_Shoulder_Roll_Joint","Right_Shoulder_Yaw_Joint","Right_Elbow_Pitch_Joint","Right_Wrist_Yaw_Joint","Right_Wrist_Roll_Joint","Right_Wrist_Pitch_Joint"]
TIP="Right_Wrist_Roll_Link"

def tf(xyz=(0,0,0),rpy=(0,0,0)):
 t=np.eye(4); t[:3,:3]=Rotation.from_euler('xyz',rpy).as_matrix(); t[:3,3]=xyz; return t
def axis_tf(axis,q):
 t=np.eye(4); t[:3,:3]=Rotation.from_rotvec(np.asarray(axis)*q).as_matrix(); return t
def pose(T): return [*T[:3,3].tolist(),*Rotation.from_matrix(T[:3,:3]).as_quat().tolist()]
def pose_tf(p):
 p=np.asarray(p,float); t=np.eye(4); t[:3,3]=p[:3]; t[:3,:3]=Rotation.from_quat(p[3:7]).as_matrix(); return t

class UrdfFK:
 def __init__(self,path:Path,tip=TIP):
  root=ET.parse(path).getroot(); by_child={}
  for j in root.findall('joint'):
   o=j.find('origin'); xyz=[float(x) for x in (o.get('xyz','0 0 0') if o is not None else '0 0 0').split()]; rpy=[float(x) for x in (o.get('rpy','0 0 0') if o is not None else '0 0 0').split()]
   a=j.find('axis'); axis=[float(x) for x in (a.get('xyz','1 0 0') if a is not None else '1 0 0').split()]
   by_child[j.find('child').get('link')]=(j.get('name'),j.get('type'),j.find('parent').get('link'),tf(xyz,rpy),axis)
  chain=[]; link=tip
  while link in by_child: chain.append(by_child[link]); link=by_child[link][2]
  self.base=link; self.tip=tip; self.chain=chain[::-1]
  names=[x[0] for x in self.chain if x[1] in ('revolute','continuous')]
  if names != JOINTS: raise ValueError(f"unexpected right-arm chain: {names}")
 def __call__(self,q):
  q=np.asarray(q,float)
  if q.shape!=(7,): raise ValueError('FK requires 7 joints')
  T=np.eye(4); k=0
  for _,typ,_,origin,axis in self.chain:
   T=T@origin
   if typ in ('revolute','continuous'): T=T@axis_tf(axis,q[k]); k+=1
  return T

def estimate_fixed(urdf,recorded):
 Rs=np.stack([b[:3,:3]@a[:3,:3].T for a,b in zip(urdf,recorded)])
 R=Rotation.from_matrix(Rs).mean().as_matrix()
 ts=np.stack([b[:3,3]-R@a[:3,3] for a,b in zip(urdf,recorded)])
 T=np.eye(4); T[:3,:3]=R; T[:3,3]=np.median(ts,axis=0); return T
def geodesic(A,B): return Rotation.from_matrix(A[:3,:3].T@B[:3,:3]).magnitude()
def stats(x):
 x=np.asarray(x,float); return {'rmse':float(np.sqrt(np.mean(x*x))),'median':float(np.median(x)),'p95':float(np.percentile(x,95)),'max':float(np.max(x))}
def path_metrics(Ts,t,episode_ids=None):
 p=np.stack([x[:3,3] for x in Ts]); ids=np.asarray(episode_ids if episode_ids is not None else ['one']*len(p)); groups=[np.flatnonzero(ids==x) for x in dict.fromkeys(ids.tolist())]; vs=[]; acc=[]; js=[]; lengths=[]; endpoints=[]
 for g in groups:
  pp=p[g]; tt=t[g]; dtt=np.maximum(np.diff(tt)/1e9,1e-9); vv=np.diff(pp,axis=0)/dtt[:,None]; aa=np.diff(vv,axis=0)/dtt[1:,None]; jj=np.diff(aa,axis=0)/dtt[2:,None]
  vs.extend(vv); acc.extend(aa); js.extend(jj); lengths.append(float(np.linalg.norm(np.diff(pp,axis=0),axis=1).sum())); endpoints.append(float(np.linalg.norm(pp[-1]-pp[0])))
 v=np.asarray(vs); a=np.asarray(acc); j=np.asarray(js)
 def mag(x): return {'median':float(np.median(np.linalg.norm(x,axis=1))) if len(x) else 0.,'p95':float(np.percentile(np.linalg.norm(x,axis=1),95)) if len(x) else 0.,'max':float(np.max(np.linalg.norm(x,axis=1))) if len(x) else 0.}
 return {'path_length_m':float(sum(lengths)),'path_length_m_per_episode':lengths,'endpoint_displacement_m_mean':float(np.mean(endpoints)),'endpoint_displacement_m_per_episode':endpoints,'velocity_m_s':mag(v),'acceleration_m_s2':mag(a),'jerk_m_s3':mag(j)}
def find_raw(source,episode_id):
 candidates=[source]
 for parent in source.parents:
  candidates += [parent/'export/episode.jsonl', parent/'derived/task3_screwdriver_filter_v1/export/episode.jsonl']
 for p in candidates:
  if p.is_file():
   first=json.loads(next(x for x in p.read_text().splitlines() if x.strip()))
   if first.get('episode_id')==episode_id and first.get('tcp_pose_base') is not None:return p
 for root in (Path('/media/ilex/Cyan_data/ICRA2027_DATA/Task_Data'),Path('/media/ilex/data1')):
  if root.exists():
   for episode_dir in root.glob(f'*/{episode_id}'):
    for p in episode_dir.glob('derived/*/export/episode.jsonl'):
     first=json.loads(next(x for x in p.read_text().splitlines() if x.strip()))
     if first.get('episode_id')==episode_id and first.get('tcp_pose_base') is not None:return p
 raise FileNotFoundError(f'raw episode with tcp_pose_base not found for {episode_id}')
def load_rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def html(rows,out):
 data=json.dumps(rows,separators=(',',':'))
 page='''<!doctype html><meta charset=utf-8><title>Filter FK replay</title><style>body{font:14px sans-serif;margin:16px}canvas{border:1px solid #bbb;margin:4px}.bar{display:flex;gap:12px;flex-wrap:wrap}label{margin-right:8px}</style><h2>Filter FK Cartesian replay</h2><div id=c></div><input id=s type=range min=0 value=0 style="width:95%"><div id=t></div><div class=bar><canvas id=xyz width=620 height=520></canvas><canvas id=curves width=620 height=520></canvas></div><script>const D=DATA,K=['raw','measured','candidate','reference','cv'],C={raw:'#777',measured:'#111',candidate:'#d33',reference:'#17a',cv:'#2a5'};c.innerHTML=K.map(k=>`<label><input type=checkbox id="x${k}" checked>${k}</label>`).join('');s.max=D.length-1;function line(ctx,a,fx,fy,col){ctx.strokeStyle=col;ctx.beginPath();a.forEach((r,i)=>{let x=fx(r),y=fy(r);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}function draw(){let n=+s.value;t.textContent=`frame ${n}/${D.length-1} stamp ${D[n].header_stamp_ns}`;let q=document.querySelector('#xyz').getContext('2d');q.clearRect(0,0,620,520);let all=K.flatMap(k=>D.map(r=>r[k].slice(0,3))),mn=[0,1,2].map(j=>Math.min(...all.map(x=>x[j]))),mx=[0,1,2].map(j=>Math.max(...all.map(x=>x[j])));let P=(v,j,o,z)=>o+(v-mn[j])/(mx[j]-mn[j]||1)*z;K.forEach(k=>{if(!document.querySelector('#x'+k).checked)return;line(q,D,r=>P(r[k][0],0,20,270),r=>250-P(r[k][1],1,10,220),C[k]);line(q,D,r=>P(r[k][0],0,330,270),r=>250-P(r[k][2],2,10,220),C[k]);line(q,D,r=>P(r[k][1],1,20,270),r=>500-P(r[k][2],2,10,220),C[k])});q.fillText('XY',20,15);q.fillText('XZ',330,15);q.fillText('YZ',20,275);let g=document.querySelector('#curves').getContext('2d');g.clearRect(0,0,620,520);let keys=['candidate_raw_position_m','candidate_reference_position_m','candidate_raw_orientation_rad','candidate_reference_orientation_rad','correction_probability','gain'];keys.forEach((k,i)=>line(g,D,(r)=>20+r.index/(D.length-1)*580,(r)=>20+i*80+60-Math.min(1,Math.abs(r[k]||0))*60,['#d33','#17a','#d83','#71a','#555','#090'][i]));keys.forEach((k,i)=>g.fillText(k,20,15+i*80));}s.oninput=draw;document.querySelectorAll('input[type=checkbox]').forEach(x=>x.onchange=draw);draw()</script>'''.replace('DATA',data)
 out.write_text(page)

def main():
 p=argparse.ArgumentParser(); p.add_argument('--predictions',type=Path,required=True); p.add_argument('--report',type=Path,required=True); p.add_argument('--urdf',type=Path,required=True); p.add_argument('--output-dir',type=Path,required=True); a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
 report=json.loads(a.report.read_text()); sources={e['episode_id']:Path(e['source']) for e in report['episodes']}; preds=load_rows(a.predictions); raw={}
 for eid,source in sources.items():
  rp=find_raw(source,eid)
  for r in load_rows(rp): raw[(eid,int(r['header_stamp_ns']))]=r
 keys=[(r['episode_id'],int(r['header_stamp_ns'])) for r in preds]
 if len(keys)!=len(set(keys)): raise ValueError('duplicate prediction alignment key')
 missing=[k for k in keys if k not in raw]
 if missing: raise ValueError(f'{len(missing)} predictions lack exact raw timestamp alignment; first={missing[0]}')
 fk=UrdfFK(a.urdf); aligned=[raw[k] for k in keys]; measured=[fk(np.asarray(r['robot_joint_state_rad'])) for r in aligned]; recorded=[pose_tf(r['tcp_pose_base']) for r in aligned]; X=estimate_fixed(measured,recorded)
 def F(q,filter_space=True): return X@fk(np.asarray(q)*SIGN if filter_space else np.asarray(q))
 raw_q=[np.asarray(r['master_joint_raw'],float) for r in aligned]; candidate_q=[np.asarray(r['predicted_action_rad'],float) for r in preds]
 learned_q=[q+float(p.get('alpha') or 0.)*(c-q) for q,c,p in zip(raw_q,candidate_q,preds)]
 fixed_q=[q+.05*(c-q) for q,c in zip(raw_q,candidate_q)]
 tracks={'raw':[F(q) for q in raw_q],'measured':[X@x for x in measured],'recorded':recorded,'candidate':[F(q) for q in candidate_q],'learned_composed':[F(q) for q in learned_q],'fixed_005_composed':[F(q) for q in fixed_q],'reference':[F(r['target_action_rad']) for r in preds],'cv':[F(r['constant_velocity_action_rad']) for r in preds]}
 ts=np.array([k[1] for k in keys]); out=[]; crp=[]; crr=[]; cap=[]; car=[]
 for i,(pr,rr) in enumerate(zip(preds,aligned)):
  crp.append(np.linalg.norm(tracks['candidate'][i][:3,3]-tracks['reference'][i][:3,3])); cap.append(np.linalg.norm(tracks['candidate'][i][:3,3]-tracks['raw'][i][:3,3])); crr.append(geodesic(tracks['candidate'][i],tracks['reference'][i])); car.append(geodesic(tracks['candidate'][i],tracks['raw'][i]))
  out.append({'episode_id':keys[i][0],'header_stamp_ns':keys[i][1],'index':i,'raw_tcp_pose':pose(tracks['raw'][i]),'measured_state_tcp_pose':pose(tracks['measured'][i]),'recorded_tcp_pose':pose(recorded[i]),'candidate_tcp_pose':pose(tracks['candidate'][i]),'reference_tcp_pose':pose(tracks['reference'][i]),'constant_velocity_tcp_pose':pose(tracks['cv'][i]),'raw':pose(tracks['raw'][i]),'measured':pose(tracks['measured'][i]),'candidate':pose(tracks['candidate'][i]),'reference':pose(tracks['reference'][i]),'cv':pose(tracks['cv'][i]),'correction_probability':pr.get('correction_probability'),'gain':pr.get('alpha',pr.get('gain')),'candidate_raw_position_m':cap[-1],'candidate_reference_position_m':crp[-1],'candidate_raw_orientation_rad':car[-1],'candidate_reference_orientation_rad':crr[-1]})
 pos=[np.linalg.norm(x[:3,3]-y[:3,3]) for x,y in zip(tracks['measured'],recorded)]; ori=[geodesic(x,y) for x,y in zip(tracks['measured'],recorded)]
 def diff(a,b): return {'position_m':stats([np.linalg.norm(x[:3,3]-y[:3,3]) for x,y in zip(a,b)]),'orientation_geodesic_rad':stats([geodesic(x,y) for x,y in zip(a,b)])}
 metrics={'schema':'robot_teleop.filter-fk-replay/v1','frames':len(out),'urdf':str(a.urdf.resolve()),'fk_base_link':fk.base,'fk_output_link':fk.tip,'pose_quaternion_order':'xyzw','filter_to_vendor_sign':SIGN.tolist(),'T_recorded_from_urdf':X.tolist(),'alignment':{'key':['episode_id','header_stamp_ns'],'matched':len(out),'missing':0},'fk_recorded_validation':{'position_m':stats(pos),'orientation_geodesic_rad':{k:v for k,v in stats(ori).items() if k!='rmse'}},'raw_reference_difference':diff(tracks['raw'],tracks['reference']),'candidate_reference_difference':diff(tracks['candidate'],tracks['reference']),'candidate_raw_difference':diff(tracks['candidate'],tracks['raw']),'learned_composed_raw_difference':diff(tracks['learned_composed'],tracks['raw']),'learned_composed_reference_difference':diff(tracks['learned_composed'],tracks['reference']),'fixed_005_composed_raw_difference':diff(tracks['fixed_005_composed'],tracks['raw']),'fixed_005_composed_reference_difference':diff(tracks['fixed_005_composed'],tracks['reference']),'trajectories':{k:path_metrics(v,ts,[x[0] for x in keys]) for k,v in tracks.items()}}
 (a.output_dir/'fk_trajectories.jsonl').write_text('\n'.join(json.dumps(x,separators=(',',':')) for x in out)+'\n'); (a.output_dir/'fk_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n'); html(out,a.output_dir/'fk_trajectory_viewer.html'); print(json.dumps(metrics['fk_recorded_validation'],indent=2))
if __name__=='__main__': main()
