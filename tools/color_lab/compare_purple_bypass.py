#!/usr/bin/env python3
"""Purple-compensation bypass A/B against IMG_9944; nominal, not physical QA."""
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
FLAGS = ['PRIMARY_WHITE_BUDGET','PRIMARY_PEAK_PRESERVATION','EXACT_PIGMENT_ANCHOR',
         'BLUE_SECONDARY_BALANCE','SECONDARY_WHITE_REDUCTION','CHROMATIC_EDGE_GUARD','WARM_COMPENSATION_BYPASS']
NAMES = {0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
PALETTE = np.array([[0,0,0],[255,255,255],[255,243,56],[191,0,0],
                    [255,255,255],[100,64,255],[67,138,28]],float)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    source = ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png'
    chart = Image.open(source).convert('RGB')
    spec = json.loads(source.with_suffix('.json').read_text())
    old = json.loads((ROOT/'artifacts/color_calibration/warm-bypass-comparison.json').read_text())
    assert sha(source.read_bytes()) == old['source_sha256']
    controls = {'red':(255,0,0),'green':(0,255,0),'blue':(0,0,255),'native_blue':(100,64,255),
                'gray96':(96,96,96),'pale_red':(255,160,160),'orange':(255,102,51),'lime':(153,255,0),
                'magenta':(255,0,255),'cyan':(0,255,255),'light_purple':(153,51,204),'blue_cyan':(0,173,254),
                'teal':(51,153,102),'dark_purple':(76,38,115),'pale_magenta':(240,224,240),'pale_cyan':(224,240,240)}
    ramps = {'purple_ratio_threshold':((70,50,200),(130,50,200)),
             'purple_blue_threshold':((100,50,170),(100,50,230)),
             'blue_black':((0,0,255),(0,0,0)),'blue_white':((0,0,255),(255,255,255)),
             'blue_cyan':((0,0,255),(0,255,255)),'blue_magenta':((0,0,255),(255,0,255)),
             'red_white':((255,0,0),(255,255,255)),'neutral':((0,0,0),(255,255,255)),
             'magenta_white':((255,0,255),(255,255,255)),'cyan_white':((0,255,255),(255,255,255)),
             'magenta_black':((255,0,255),(0,0,0)),'cyan_black':((0,255,255),(0,0,0)),
             'purple_light_dark':((153,51,204),(76,38,115)),
             'edge_white':((0,173,254),(255,255,255)),'edge_black':((0,173,254),(0,0,0)),
             'edge_neutral_red':((0,174,255),(64,174,255)),
             'edge_green':((0,140,255),(0,220,255)),
             'red_blue_edge':((191,0,0),(100,64,255)),
             'orange_blue_threshold':((255,102,0),(255,102,96)),
             'orange_red_gap':((128,101,49),(255,101,49)),
             'orange_white':((255,102,51),(255,255,255)),
             'orange_black':((255,102,51),(0,0,0)),
             'orange_yellow':((255,102,51),(255,204,0)),
             'orange_red':((255,102,51),(204,51,0))}
    report = {'baseline':'IMG_9944 warm bypass','candidate':'purple source compensation bypass',
              'warning':'Native-code and nominal RGB diagnostics, not physical color accuracy.',
              'source_sha256':sha(source.read_bytes()),'source_hashes':{},'variants':{}}
    for p in ['main/display/papercolor_photo_dither.cpp','main/display/papercolor_photo_dither.h',
              'main/display/papercolor_gamut.h','tools/color_lab/probe_frame.cpp',
              'tools/color_lab/probe_targets.cpp','artifacts/color_lut/nominal-5bit.lut']:
        report['source_hashes'][p] = sha((ROOT/p).read_bytes())
    frames, traces = {}, {}
    with tempfile.TemporaryDirectory(prefix='papercolor-purple-bypass-') as directory:
        tmp = Path(directory)
        (tmp/'targets.cpp').write_text((ROOT/'tools/color_lab/probe_targets.cpp').read_text())
        for enabled in (False,True):
            name = 'candidate' if enabled else 'baseline'
            flags = ['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS]
            flags += ['-DCONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS='+str(int(enabled))]
            for kind in ('frame','targets'):
                files = [str(ROOT/'main/display/papercolor_lut.cpp')]
                files += ([str(ROOT/'main/display/papercolor_photo_dither.cpp'),str(ROOT/'tools/color_lab/probe_frame.cpp')]
                          if kind=='frame' else [str(tmp/'targets.cpp')])
                subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*flags,
                                '-I'+str(ROOT/'main'),*files,'-o',str(tmp/(name+'-'+kind))],check=True)
            def render(im):
                data = subprocess.run([str(tmp/(name+'-frame')),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],
                                      input=im.tobytes(),capture_output=True,check=True).stdout
                assert len(data)==240000 and set(data)<=set(NAMES)
                return data
            frame = render(chart)
            assert render(chart)==frame
            frames[name] = np.frombuffer(frame,np.uint8).reshape(600,400)
            result = {'frame_sha256':sha(frame),'patches':[],'uniform':{},'ramps':{}}
            rgb = np.asarray(chart)
            for p in spec['patches']:
                x0,y0,x1,y1 = p['rect_xyxy']
                fill = np.all(rgb[y0:y1,x0:x1]==p['rgb'],axis=2)
                values = frames[name][y0:y1,x0:x1][fill]
                counts = Counter(values)
                row = {'id':p['id'],'name':p['name'],'fill_pixels':len(values),
                       'native_counts':{NAMES[c]:int(counts[c]) for c in NAMES},
                       'native_percent':{NAMES[c]:100*counts[c]/len(values) for c in NAMES}}
                if p['id']==10:
                    row['rare_code_coordinates'] = {}
                    for c in (0,1):
                        yy,xx = np.where(fill & (frames[name][y0:y1,x0:x1]==c))
                        row['rare_code_coordinates'][NAMES[c]] = [[int(x+x0),int(y+y0)] for x,y in zip(xx,yy)]
                if p['id'] in (5,7,8,19): assert set(values)=={dict([(5,5),(7,3),(8,6),(19,5)])[p['id']]}
                if p['id']>=21: assert set(values)<={0,1}
                result['patches'].append(row)
            for key,color in controls.items():
                data = render(Image.new('RGB',(400,600),color))
                counts = Counter(data)
                result['uniform'][key] = {'sha256':sha(data),
                    'native_percent':{NAMES[c]:100*counts[c]/len(data) for c in NAMES}}
            for key,(a,b) in ramps.items():
                line = [tuple(round(u+(v-u)*x/399) for u,v in zip(a,b)) for x in range(400)]
                im = Image.new('RGB',(400,600)); im.putdata(line*600)
                data = render(im)
                codes = np.frombuffer(data,np.uint8).reshape(600,400)
                if key=='neutral': assert set(data)<={0,1}
                means = [PALETTE[codes[32:568,x:x+25]].mean(axis=(0,1)).tolist() for x in range(0,400,25)]
                white = [float(np.mean(codes[32:568,x:x+25]==1)) for x in range(0,400,25)]
                if key.endswith('_white') or key=='neutral':
                    assert all(a<=b+.01 for a,b in zip(white,white[1:])),key
                columns = PALETTE[codes[32:568]].mean(axis=0)
                result['ramps'][key] = {'sha256':sha(data),'nominal_mean_rgb_bins':means,'white_bins':white,
                    'nominal_mean_rgb_columns':columns.tolist()}
            out = subprocess.run([str(tmp/(name+'-targets'))],capture_output=True,text=True,check=True).stdout
            traces[name] = list(csv.DictReader(io.StringIO(out)))
            report['variants'][name] = result
    base,new = (report['variants'][k] for k in ('baseline','candidate'))
    assert base['frame_sha256']==old['variants']['candidate']['frame_sha256']
    assert base['patches'][9]['native_counts']['white']==base['patches'][9]['native_counts']['black']==0
    assert new['patches'][9]['native_counts']['white']==new['patches'][9]['native_counts']['black']==0
    for key in controls:
        if key not in ('light_purple','dark_purple'): assert base['uniform'][key]==new['uniform'][key],key
    green = new['uniform']['blue_cyan']['native_percent']['green']
    assert 34<green<35
    previous=np.array([[float(a['target_'+c]) for c in 'rgb'] for a in traces['baseline']])
    current=np.array([[a['target_'+c] for c in 'rgb'] for a in traces['candidate']],float)
    masks=np.array([int(a['mask']) for a in traces['baseline']])
    rgb=np.array([[int(a[c]) for c in 'rgb'] for a in traces['baseline']])
    eligible=(masks==43)&(rgb[:,2]>rgb[:,0])&(2*rgb[:,0]>=rgb[:,2])
    changed=np.any(previous!=current,axis=1)
    assert not np.any(changed & ~eligible)
    for a,b in zip(traces['baseline'],traces['candidate']):
        if int(b['mask'])==43:
            assert all(int(b['comp_'+c])==int(b[c]) for c in 'rgb')
    # Unlike the raw projection probe, the final target retains peak, hue and
    # white policies. Do not compare it to the uncompensated diagnostic column.
    index=np.arange(65536); old_steps=[]; new_steps=[]; boundary=[]; purple_edges=[]
    for step,valid in ((2048,(index>>11)<31),(32,((index>>5)&63)<63),(1,(index&31)<31)):
        a=index[valid];b=a+step
        old_steps.extend(np.linalg.norm(previous[a]-previous[b],axis=1))
        new_steps.extend(np.linalg.norm(current[a]-current[b],axis=1))
        boundary.extend(eligible[a]!=eligible[b])
        purple_edges.extend(eligible[a]|eligible[b])
    old_steps,new_steps=np.array(old_steps),np.array(new_steps)
    boundary=np.array(boundary); purple_edges=np.array(purple_edges)
    assert not np.any((old_steps<=30)&(new_steps>30))
    continuity={'changed_targets':int(sum(changed)),'eligible_targets':int(sum(eligible)),
        'neighbor_edges':len(old_steps),'old_max':float(max(old_steps)),'new_max':float(max(new_steps)),
        'new_edges_over_30':int(sum((old_steps<=30)&(new_steps>30))),
        'purple_touching_edges':int(sum(purple_edges)),
        'old_purple_max':float(max(old_steps[purple_edges])),'new_purple_max':float(max(new_steps[purple_edges])),
        'old_activation_boundary_max':float(max(old_steps[boundary])),
        'new_activation_boundary_max':float(max(new_steps[boundary]))}
    assert continuity['new_activation_boundary_max']<continuity['old_activation_boundary_max']
    PROTECTED_RAMPS={'blue_black','blue_cyan','red_white','neutral','magenta_white','cyan_white','magenta_black','cyan_black','edge_white','edge_black','edge_neutral_red','edge_green',*[k for k in ramps if k.startswith('orange_')]}
    ramp_deltas = {}; local_deltas = {}
    for key in ramps:
        a,b = (np.array(v['ramps'][key]['nominal_mean_rgb_bins']) for v in (base,new))
        delta = float(np.max(np.abs(a-b)))
        # Diagnostic bound in nominal RGB only, not a physical visibility test.
        if key in PROTECTED_RAMPS: assert delta==0,key
        ramp_deltas[key] = delta
        a,b = (np.array(v['ramps'][key]['nominal_mean_rgb_columns']) for v in (base,new))
        old_steps,new_steps = (np.linalg.norm(np.diff(v,axis=0),axis=1) for v in (a,b))
        local_deltas[key] = {'max_column_channel_change':float(np.max(np.abs(a-b))),
            'old_max_adjacent_step':float(max(old_steps)), 'new_max_adjacent_step':float(max(new_steps)),
            'max_adjacent_step_increase':float(max(new_steps-old_steps)),
            'new_steps_from_under_6_to_over_12':int(np.sum((old_steps<6)&(new_steps>12)))}
        indices = np.where((old_steps<6)&(new_steps>12))[0]
        local_deltas[key]['new_step_details'] = [{'x':int(i),'old':a[i:i+2].tolist(),'new':b[i:i+2].tolist()} for i in indices]
        # Single-column means are sensitive to serpentine dot phase (including
        # large oscillations already present in the baseline). Keep them as
        # diagnostics, and separately bound the envelope over nine columns.
        envelope_delta = max(float(np.max(np.abs(a[i:i+9].mean(0)-b[i:i+9].mean(0)))) for i in range(392))
        local_deltas[key]['nine_column_envelope_change'] = envelope_delta
        if key in PROTECTED_RAMPS: assert envelope_delta==0,key
        # Keep raw adjacent-step changes for review; dither phase is not target continuity.
    report['checks'] = {'targets_scanned':len(traces['candidate']),'continuity':continuity,
        'protected_uniform_byte_identical':len(controls)-2,
        'ramps':len(ramps),'max_per_channel_ramp_bin_change':ramp_deltas,
        'local_ramp_checks':local_deltas,
        'byte_identical_ramps':[k for k in ramps if base['ramps'][k]['sha256']==new['ramps'][k]['sha256']],
        'changed_chart_pixels':int(np.sum(frames['baseline']!=frames['candidate']))}
    dest = ROOT/'artifacts/color_calibration/purple-bypass-comparison.json'
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['checks'],indent=2))
    for a,b in zip(base['patches'],new['patches']):
        print(a['id'],a['native_counts'],'->',b['native_counts'])

if __name__=='__main__':
    main()
