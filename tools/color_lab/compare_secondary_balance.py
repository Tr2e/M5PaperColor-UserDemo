#!/usr/bin/env python3
"""Full-chart/continuous-target A/B against the IMG_9933 verified renderer.

Requires Pillow and numpy. Measures nominal mixing/continuity, not physical color.
The disabled variant must reproduce the previously flashed full-frame hash.
"""
import csv
import hashlib
import io
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
NAMES = {0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
FLAGS = ['-DCONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1',
         '-DCONFIG_PAPERCOLOR_PRIMARY_PEAK_PRESERVATION=1',
         '-DCONFIG_PAPERCOLOR_EXACT_PIGMENT_ANCHOR=1']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    source=ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png'
    chart=Image.open(source).convert('RGB')
    spec=json.loads(source.with_suffix('.json').read_text())
    baseline_hash=json.loads((ROOT/'artifacts/color_calibration/exact-pigment-comparison.json').read_text())['frame_sha256']['after']
    pixels=list(chart.getdata())
    report={'baseline':'IMG_9933 exact-pigment candidate', 'candidate':'blue secondary chroma balance',
            'warning':'Nominal target/code statistics only; physical hue must be checked on the panel.',
            'source_sha256':sha(source.read_bytes()),
            'source_hashes':{p:sha((ROOT/p).read_bytes()) for p in (
                'main/display/papercolor_photo_dither.cpp','main/display/papercolor_gamut.h',
                'tools/color_lab/probe_frame.cpp','tools/color_lab/probe_targets.cpp',
                'artifacts/color_lut/nominal-5bit.lut')}, 'variants':{}}
    traces={}
    frames={}
    with tempfile.TemporaryDirectory(prefix='papercolor-secondary-') as directory:
        for enabled in (False,True):
            name='candidate' if enabled else 'baseline'
            def build(probe):
                binary=str(Path(directory)/(name+'-'+probe))
                subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*FLAGS,
                    '-DCONFIG_PAPERCOLOR_BLUE_SECONDARY_BALANCE='+str(int(enabled)),
                    '-I'+str(ROOT/'main'),
                    *([str(ROOT/'main/display/papercolor_photo_dither.cpp')] if probe=='probe_frame' else []),
                    str(ROOT/'main/display/papercolor_lut.cpp'),str(ROOT/f'tools/color_lab/{probe}.cpp'),'-o',binary],check=True)
                return binary
            binary=build('probe_frame')
            def render(image):
                data=subprocess.run([binary,str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],input=image.tobytes(),capture_output=True,check=True).stdout
                assert len(data)==240000 and set(data)<=set(NAMES)
                return data
            frame=render(chart)
            assert render(chart)==frame
            frames[name]=frame
            result={'frame_sha256':sha(frame),'patches':[],'uniform':{},'ramps':{}}
            for p in spec['patches']:
                x0,y0,x1,y1=p['rect_xyxy']
                indices=[y*400+x for y in range(y0,y1) for x in range(x0,x1) if pixels[y*400+x]==tuple(p['rgb'])]
                counts=Counter(frame[i] for i in indices)
                result['patches'].append({'id':p['id'],'name':p['name'],'source_rgb':p['rgb'],
                    'fill_pixels':len(indices),'native_counts':{NAMES[c]:counts[c] for c in NAMES},
                    'native_percent':{NAMES[c]:100*counts[c]/len(indices) for c in NAMES}})
                if p['id'] in (5,7,8,19):
                    assert set(frame[i] for i in indices)=={dict([(5,5),(7,3),(8,6),(19,5)])[p['id']]}
                if p['id']>=21: assert set(frame[i] for i in indices)<={0,1}
            controls={'red':(255,0,0),'green':(0,255,0),'blue':(0,0,255),'native_blue':(100,64,255),
                      'gray96':(96,96,96),'pale_red':(255,160,160),'orange':(255,102,51),'lime':(153,255,0),
                      'magenta':(255,0,255),'cyan':(0,255,255),'light_purple':(153,51,204),'blue_cyan':(0,173,254)}
            for key,rgb in controls.items():
                data=render(Image.new('RGB',(400,600),rgb)); counts=Counter(data)
                result['uniform'][key]={'sha256':sha(data),'native_percent':{NAMES[c]:100*counts[c]/len(data) for c in NAMES}}
            ramps={'blue_black':((0,0,255),(0,0,0)),'blue_white':((0,0,255),(255,255,255)),
                   'blue_cyan':((0,0,255),(0,255,255)),'blue_magenta':((0,0,255),(255,0,255)),
                   'red_white':((255,0,0),(255,255,255)),'neutral':((0,0,0),(255,255,255)),
                   'magenta_white':((255,0,255),(255,255,255)),'cyan_white':((0,255,255),(255,255,255)),
                   'magenta_black':((255,0,255),(0,0,0)),'cyan_black':((0,255,255),(0,0,0)),
                   'purple_light_dark':((153,51,204),(76,38,115))}
            for key,(a,b) in ramps.items():
                image=Image.new('RGB',(400,600))
                image.putdata([tuple(round(u+(v-u)*x/399) for u,v in zip(a,b)) for y in range(600) for x in range(400)])
                data=render(image)
                if key=='neutral': assert set(data)<={0,1}
                bins=[]
                for x0 in range(0,400,25):
                    counts=Counter(data[y*400+x] for y in range(32,568) for x in range(x0,x0+25))
                    bins.append({NAMES[c]:counts[c]/13400 for c in NAMES})
                if key.endswith('_white') or key=='neutral':
                    assert all(a['white']<=b['white']+.01 for a,b in zip(bins,bins[1:])),key
                result['ramps'][key]={'sha256':sha(data),'bins':bins}
            output=subprocess.run([build('probe_targets')],capture_output=True,text=True,check=True).stdout
            traces[name]=list(csv.DictReader(io.StringIO(output)))
            report['variants'][name]=result
    base,candidate=(report['variants'][k] for k in ('baseline','candidate'))
    assert base['frame_sha256']==baseline_hash
    for key in ('red','green','blue','native_blue','gray96','pale_red','orange','lime'):
        assert base['uniform'][key]==candidate['uniform'][key],key
    for key in ('blue_black','blue_white','red_white','neutral'):
        assert base['ramps'][key]==candidate['ramps'][key],key
    for key in ('magenta','cyan','light_purple','blue_cyan'):
        for c in ('black','white'):
            assert abs(base['uniform'][key]['native_percent'][c]-candidate['uniform'][key]['native_percent'][c])<.3,(key,c)
    targets={k:np.array([[float(row['target_'+c]) for c in 'rgb'] for row in rows]) for k,rows in traces.items()}
    old,new=targets['baseline'],targets['candidate']
    masks=np.array([int(row['mask']) for row in traces['baseline']])
    assert np.array_equal(old[~np.isin(masks,[43,99])],new[~np.isin(masks,[43,99])])
    max_neutral_error=0
    for mask,pigment in ((43,[191,0,0]),(99,[67,138,28])):
        matrix=np.array([[255,255,255],pigment,[100,64,255]],dtype=float).T
        a,b=(np.linalg.solve(matrix,t[masks==mask].T).T for t in (old,new))
        # Derive coefficient tolerances from the inverse mixing matrix and
        # half a Q4 unit per channel, rather than an arbitrary percentage.
        inverse=np.linalg.inv(matrix)
        bounds=np.sum(np.abs(inverse),axis=1)/32 + 1e-6
        black_bound=np.sum(np.abs(np.sum(inverse,axis=0)))/32 + 1e-6
        assert np.all(b >= -bounds) and np.all(np.sum(b,axis=1)<=1+black_bound)
        white_error=float(np.max(np.abs(a[:,0]-b[:,0])))
        black_error=float(np.max(np.abs(np.sum(a,axis=1)-np.sum(b,axis=1))))
        max_neutral_error=max(max_neutral_error,white_error,black_error)
        assert white_error<=2*bounds[0] and black_error<=2*black_bound
    index=np.arange(65536); old_steps=[];new_steps=[]
    for step,allowed in ((2048,(index>>11)<31),(32,((index>>5)&63)<63),(1,(index&31)<31)):
        i=index[allowed]
        old_steps.extend(np.linalg.norm(old[i]-old[i+step],axis=1))
        new_steps.extend(np.linalg.norm(new[i]-new[i+step],axis=1))
    old_steps=np.array(old_steps);new_steps=np.array(new_steps)
    continuity={'edge_count':len(old_steps),'baseline_max_step':float(max(old_steps)),
        'candidate_max_step':float(max(new_steps)),'max_step_increase':float(max(new_steps-old_steps)),
        'new_edges_over_30':int(np.sum((old_steps<=30)&(new_steps>30))),
        'changed_targets':int(np.sum(np.any(old!=new,axis=1))),
        'max_black_white_weight_drift':max_neutral_error,
        'note':'Nominal RGB distance; 30 ranks diagnostic seams, not a visibility or Delta-E threshold.'}
    report['continuity']=continuity
    report['changed_chart_pixels']=sum(a!=b for a,b in zip(frames['baseline'],frames['candidate']))
    print(json.dumps(continuity,indent=2))
    for a,b in zip(base['patches'],candidate['patches']):
        print(a['id'],a['name'],{k:round(v,2) for k,v in a['native_percent'].items() if v},'->',{k:round(v,2) for k,v in b['native_percent'].items() if v})
    # No larger worst-case seam than the accepted target map. Retain old seams
    # as explicit debt; this policy does not claim to remove legacy switches.
    assert max(new_steps)<=max(old_steps)+.1
    dest=ROOT/'artifacts/color_calibration/secondary-balance-comparison.json'
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print(dest)

if __name__=='__main__':
    main()
