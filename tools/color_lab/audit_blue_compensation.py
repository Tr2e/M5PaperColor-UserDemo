#!/usr/bin/env python3
"""Isolated ablations of legacy source compensation; never changes firmware sources."""
import csv, hashlib, io, json, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
FLAGS=['PRIMARY_WHITE_BUDGET','PRIMARY_PEAK_PRESERVATION','EXACT_PIGMENT_ANCHOR','BLUE_SECONDARY_BALANCE','SECONDARY_WHITE_REDUCTION','CHROMATIC_EDGE_GUARD','WARM_COMPENSATION_BYPASS']
NAMES={0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    src=ROOT/'.cache/firmware/warm-ab-chart-v1/source/main/display/papercolor_photo_dither.cpp';original=src.read_text()
    old=json.loads((ROOT/'artifacts/color_calibration/warm-bypass-comparison.json').read_text())
    assert sha(src.read_bytes())==old['source_hashes']['main/display/papercolor_photo_dither.cpp']
    chart=Image.open(ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB');rgbchart=np.asarray(chart)
    spec=json.loads((ROOT/'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
    report={'warning':'Nominal target and native code diagnostics, not physical color acceptance','source_sha256':sha(src.read_bytes()),'variants':{}}
    targets={};frames={};traces={}
    with tempfile.TemporaryDirectory(prefix='papercolor-blue-audit-') as d:
        tmp=Path(d)
        for name,match in [('baseline',None),('purple_off','if (mask == MASK_RED_BLUE && original[2] > original[0] &&'),('cyan_off','if (mask == MASK_GREEN_BLUE && original[2] > original[1])')]:
            code=original if match is None else original.replace(match,match.replace('if (','if (false && ',1),1)
            assert match is None or code!=original
            cpp=tmp/(name+'.cpp');cpp.write_text(code)
            probe=tmp/(name+'-targets.cpp');probe.write_text((ROOT/'tools/color_lab/probe_targets.cpp').read_text().replace('"display/papercolor_photo_dither.cpp"','"'+str(cpp)+'"'))
            for kind in ('frame','targets'):
                files=[ROOT/'main/display/papercolor_lut.cpp']+([cpp,ROOT/'tools/color_lab/probe_frame.cpp'] if kind=='frame' else [probe])
                subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],'-I'+str(ROOT/'main'),*map(str,files),'-o',str(tmp/(name+'-'+kind))],check=True)
            frame=subprocess.run([str(tmp/(name+'-frame')),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],input=chart.tobytes(),capture_output=True,check=True).stdout
            assert len(frame)==240000 and set(frame)<=set(NAMES)
            frames[name]=np.frombuffer(frame,np.uint8).reshape(600,400)
            out=subprocess.run([str(tmp/(name+'-targets'))],capture_output=True,text=True,check=True).stdout
            traces[name]=list(csv.DictReader(io.StringIO(out)))
            targets[name]=np.array([[float(t['target_'+c]) for c in 'rgb'] for t in traces[name]])
            patches=[]
            for p in spec['patches']:
                x,y,x1,y1=p['rect_xyxy'];fill=np.all(rgbchart[y:y1,x:x1]==p['rgb'],axis=2);v=frames[name][y:y1,x:x1][fill]
                packed=((p['rgb'][0]>>3)<<11)|((p['rgb'][1]>>2)<<5)|(p['rgb'][2]>>3)
                t=traces[name][packed]
                patches.append({'id':p['id'],'counts':{NAMES[c]:int(sum(v==c)) for c in NAMES},'rgb565':[int(t[c]) for c in 'rgb'],'compensated':[int(t['comp_'+c]) for c in 'rgb'],'target':targets[name][packed].tolist()})
            report['variants'][name]={'frame_sha256':sha(frame),'patches':patches}
        assert report['variants']['baseline']['frame_sha256']==old['variants']['candidate']['frame_sha256']
        index=np.arange(65536);pairs=[]
        for step,valid in ((2048,(index>>11)<31),(32,((index>>5)&63)<63),(1,(index&31)<31)):
            a=index[valid];pairs.append((a,a+step))
        a=np.concatenate([p[0] for p in pairs]);b=np.concatenate([p[1] for p in pairs]);base=targets['baseline'];oldsteps=np.linalg.norm(base[a]-base[b],axis=1)
        masks=np.array([int(t['mask']) for t in traces['baseline']]);rgb=np.array([[int(t[c]) for c in 'rgb'] for t in traces['baseline']])
        for name in ('purple_off','cyan_off'):
            eligible=((masks==43)&(rgb[:,2]>rgb[:,0])&(2*rgb[:,0]>=rgb[:,2])) if name=='purple_off' else ((masks==99)&(rgb[:,2]>rgb[:,1]))
            changed=np.any(targets[name]!=base,axis=1);assert not np.any(changed&~eligible)
            steps=np.linalg.norm(targets[name][a]-targets[name][b],axis=1);boundary=eligible[a]!=eligible[b];touch=eligible[a]|eligible[b]
            regress=np.where((oldsteps<=30)&(steps>30))[0]
            report['variants'][name]['checks']={'eligible_targets':int(sum(eligible)),'changed_targets':int(sum(changed)),'old_max':float(max(oldsteps)),'new_max':float(max(steps)),'old_boundary_max':float(max(oldsteps[boundary])),'new_boundary_max':float(max(steps[boundary])),'old_touch_max':float(max(oldsteps[touch])),'new_touch_max':float(max(steps[touch])),'new_edges_over_30':len(regress),'new_edge_examples':[{'a':rgb[a[i]].tolist(),'b':rgb[b[i]].tolist(),'old':float(oldsteps[i]),'new':float(steps[i])} for i in regress[:10]],'changed_frame_pixels':int(sum((frames[name]!=frames['baseline']).flat))}
    dest=ROOT/'artifacts/color_calibration/blue-compensation-ablation.json';dest.write_text(json.dumps(report,indent=2)+'\n')
    for name in ('purple_off','cyan_off'):
        print(name,json.dumps(report['variants'][name]['checks']))
        for before,after in zip(report['variants']['baseline']['patches'],report['variants'][name]['patches']):
            if before['target']!=after['target']: print(before['id'],before['counts'],'->',after['counts'],'target',before['target'],'->',after['target'])
if __name__=='__main__':main()
