#!/usr/bin/env python3
"""Probe secondary hue ratios at fixed white using a temporary host-only target perturbation, then compose native A/B/C/A crops.

No physical color model or alternate ordered dither is introduced. Pillow is
used for source pixels and a nominal preview; C++ supplies both photo variants
and the exact firmware crop sampler. The original HEIC photos are not inputs.
"""
from collections import Counter
import csv
import io
import numpy as np
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
IDS=[16,20,17,10,19,22]
FLAGS=['PRIMARY_WHITE_BUDGET','PRIMARY_PEAK_PRESERVATION','EXACT_PIGMENT_ANCHOR',
       'BLUE_SECONDARY_BALANCE','CHROMATIC_EDGE_GUARD','SECONDARY_WHITE_REDUCTION','WARM_COMPENSATION_BYPASS','PURPLE_COMPENSATION_SMOOTH']
COLORS={0:(0,0,0),1:(255,255,255),2:(255,243,56),3:(191,0,0),5:(100,64,255),6:(67,138,28)}
NAMES={0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
INPUTS=['main/display/papercolor_photo_dither.cpp','main/display/papercolor_photo_dither.h',
        'main/display/papercolor_gamut.h','main/display/papercolor_lut.cpp','main/display/papercolor_lut.h',
        'main/display/papercolor_native_chart.h','main/display/papercolor_secondary_ratio_abc_chart.h','main/display/papercolor_secondary_ratio_abc_chart.cpp',
        'tools/color_lab/probe_frame.cpp','tools/color_lab/probe_secondary_ratio_abc_chart.cpp',
        'tools/color_lab/generate_secondary_ratio_abc_chart.py','tools/color_lab/secondary_ratio_probe.h','tools/color_lab/probe_targets.cpp','artifacts/color_lut/nominal-5bit.lut',
        'artifacts/color_calibration/papercolor-calibration-v1.png',
        'artifacts/color_calibration/papercolor-calibration-v1.json']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    chart=Image.open(ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB')
    spec=json.loads((ROOT/'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
    patches={p['id']:p for p in spec['patches']}
    reference=json.loads((ROOT/'artifacts/color_calibration/purple-smooth-comparison.json').read_text())
    for name,h in reference['source_hashes'].items():
        assert sha((ROOT/name).read_bytes())==h, f'Purple comparison source changed: {name}'
    frames={}; crops={}; records=[]; payload=bytearray(); traces={}; checks={}
    with tempfile.TemporaryDirectory(prefix='papercolor-secondary-ratio-') as directory:
        tmp=Path(directory)
        original=(ROOT/'main/display/papercolor_photo_dither.cpp').read_text()
        needle='        cached.edge_pigment = 0;'
        assert original.count(needle)==1
        modified='#include "secondary_ratio_probe.h"\n'+original.replace(needle,
            '        p = papercolor_diagnostic::secondary_ratio_target(original,p,PAPERCOLOR_DIAGNOSTIC_RATIO_OFFSET);\n'+needle)
        implementation=tmp/'diagnostic.cpp';implementation.write_text(modified)
        target_probe=(ROOT/'tools/color_lab/probe_targets.cpp').read_text().replace(
            '#include "display/papercolor_photo_dither.cpp"','#include "'+str(implementation)+'"')
        (tmp/'targets.cpp').write_text(target_probe)
        for name,offset in [('A',0),('B',-0.0625),('C',0.0625)]:
            flags=[*['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],
                   '-DPAPERCOLOR_DIAGNOSTIC_RATIO_OFFSET='+str(float(offset))+'f']
            for kind in ['frame','targets']:
                binary=tmp/(name+'-'+kind)
                files=([str(implementation),str(ROOT/'tools/color_lab/probe_frame.cpp')]
                       if kind=='frame' else [str(tmp/'targets.cpp')])
                subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*flags,
                    '-I'+str(ROOT/'main'),'-I'+str(ROOT/'tools/color_lab'),*files,
                    str(ROOT/'main/display/papercolor_lut.cpp'),'-o',str(binary)],check=True)
            def render():
                return subprocess.run([str(tmp/(name+'-frame')),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],
                    input=chart.tobytes(),capture_output=True,check=True).stdout
            frame=render();assert len(frame)==240000 and set(frame)<=set(COLORS)
            assert render()==frame
            frames[name]=frame
            out=subprocess.check_output([str(tmp/(name+'-targets'))],text=True)
            traces[name]=list(csv.DictReader(io.StringIO(out)))
        assert sha(frames['A'])==reference['variants']['candidate']['frame_sha256'], 'A must match IMG_9952'
        base=np.array([[float(r['target_'+c]) for c in 'rgb'] for r in traces['A']])
        for name,offset in [('B',-0.0625),('C',0.0625)]:
            target=np.array([[float(r['target_'+c]) for c in 'rgb'] for r in traces[name]])
            changed=np.where(np.any(target!=base,axis=1))[0].tolist()
            assert changed==[0x07ff,0xf81f],changed
            checks[name]={'changed_rgb565':changed,'targets':{}}
            for key,pigment in [(0xf81f,[191,0,0]),(0x07ff,[67,138,28])]:
                matrix=np.array([[255,255,255],pigment,[100,64,255]],float).T
                old=np.linalg.solve(matrix,base[key]);new=np.linalg.solve(matrix,target[key])
                # Each of two Q4 RGB vectors has <=1/32 channel rounding
                # error. Propagate their difference through the inverse basis.
                inverse=np.linalg.inv(matrix)
                white_bound=np.abs(inverse[0]).sum()/16+1e-6
                total_bound=np.abs(inverse.sum(axis=0)).sum()/16+1e-6
                assert abs(new[0]-old[0])<=white_bound
                assert abs(sum(new)-sum(old))<=total_bound
                assert abs(new[1]/sum(new[1:])-old[1]/sum(old[1:])-offset)<0.001
                checks[name]['targets'][str(key)]={'before':base[key].tolist(),'after':target[key].tolist(),
                    'q4_white_error_bound':float(white_bound),'q4_total_error_bound':float(total_bound),
                    'old_white_pigment_blue_weights':old.tolist(),'new_white_pigment_blue_weights':new.tolist()}
        for row,pid in enumerate(IDS):
            p=patches[pid];x0,y0,x1,y1=p['rect_xyxy']
            assert (x1-x0,y1-y0)==(88,50)
            record={'id':pid,'name':p['name'],'source_rgb':p['rgb'],'source_rect_xyxy':p['rect_xyxy'],
                    'source':'host target perturbation for 16/20' if pid in (16,20) else 'baseline A canonical crop in every column',
                    'variants':{}}
            for name in ('A','B','C'):
                data=frames[name if pid in (16,20) else 'A']
                crop=bytes(data[y*400+x] for y in range(y0,y1) for x in range(x0,x1))
                crops[row,name]=crop
                payload.extend((crop[i]<<4)|crop[i+1] for i in range(0,len(crop),2))
                fill=[data[y*400+x] for y in range(y0+1,y1-1) for x in range(x0+1,x1-1)]
                assert len(fill)==4128
                counts=Counter(fill)
                record['variants'][name]={'crop_sha256':sha(crop),'fill_pixels':len(fill),
                    'native_counts':{NAMES[c]:counts[c] for c in COLORS},
                    'native_percent':{NAMES[c]:100*counts[c]/len(fill) for c in COLORS}}
                if pid==10:assert set(fill)<={5,6}
                if pid==19:assert set(fill)=={5}
                if pid==22:assert set(fill)<={0,1}
            if pid in (16,20):
                for name in ('B','C'):
                    a=record['variants']['A']['native_counts'];b=record['variants'][name]['native_counts']
                    assert abs(b['white']-a['white'])<=10, (pid,name,a,b)
                    assert b['black']==a['black']==0
                    pigment='red' if pid==16 else 'green'
                    old=a[pigment]/(a[pigment]+a['blue']);new=b[pigment]/(b[pigment]+b['blue'])
                    assert abs(new-old-(-0.0625 if name=='B' else 0.0625))<0.005
            else:assert crops[row,'A']==crops[row,'B']==crops[row,'C']
            records.append(record)
        assert len(payload)==39600
        packed=tmp/'secondary-ratio-abc-v1.bin';packed.write_bytes(payload)
        binary=tmp/'sampler'
        subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'main'),str(ROOT/'tools/color_lab/probe_secondary_ratio_abc_chart.cpp'),'-o',str(binary)],check=True)
        codes=subprocess.run([str(binary),str(packed)],capture_output=True,check=True).stdout
    assert len(codes)==240000 and set(codes)<=set(COLORS)|{255}
    expected=bytearray([255])*240000
    for i,c in enumerate([0,1,2,3,5,6]):
        for y in range(52,72):
            for x in range(12+64*i,68+64*i):expected[y*400+x]=c
    for row in range(6):
        for col,name in enumerate(('A','B','C','A')):
            crop=crops[row,name]
            for y in range(50):
                start=(118+74*row+y)*400+12+96*col
                expected[start:start+88]=crop[y*88:(y+1)*88]
    assert codes==expected, 'Firmware sampler differs from independently composed 24 native crops'
    assert sum(c!=255 for c in codes)==24*4400+6*56*20
    image=Image.new('RGB',(400,600),'white')
    image.putdata([COLORS.get(c,(255,255,255)) for c in codes])
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',10)
    big=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',20)
    def label(text,x,y,large=False):
        draw.text((x,y),text,font=big if large else font,fill='black',anchor='lt')
    label('SECONDARY RATIO A/B/C',12,8,True)
    label('A: NOW  B: LESS R/G  C: MORE R/G',12,30)
    for i,name in enumerate(['BLACK','WHITE','YELLOW','RED','BLUE','GREEN']):
        label(name,12+i*64,42);draw.rectangle((11+i*64,51,68+i*64,72),outline='black')
    for col,name in enumerate(('A','B','C','A')):label(name,52+96*col,84)
    labels=['16 MAGENTA  RED / BLUE','20 CYAN  GREEN / BLUE','17 LIGHT PURPLE CONTROL',
            '10 BLUE CYAN EDGE CONTROL','19 PURE BLUE CONTROL','22 GRAY CONTROL']
    for row,text in enumerate(labels):label(text,12,103+74*row)
    for text,y in [('A B C A: white target fixed; A repeats',552),
        ('Compare hue, brightness and grain in each row',566),('Keep whole chart visible. Button A: home',582)]:label(text,12,y)
    for x in (2,392):
        for y in (2,592):draw.rectangle((x,y,x+5,y+5),fill='black')
    dest=ROOT/'artifacts/color_calibration/secondary-ratio-abc-v1'
    dest.with_suffix('.bin').write_bytes(payload)
    image.save(dest.with_suffix('.png'))
    hashes={p:sha((ROOT/p).read_bytes()) for p in INPUTS}
    manifest={'version':1,'warning':'Nominal preview only. Crops are real host-compiled PhotoBalanced outputs, transferred as native codes without a second dither. Physical texture/color still requires panel review.',
        'columns':['A','B','C','A'],'rows':records,'patch_size':[88,50],
        'A':'current accepted photo target; full frame equals IMG_9952',
        'B':'host diagnostic only: colored red/green share minus 6.25 percentage points at source16/20',
        'C':'host diagnostic only: colored red/green share plus 6.25 percentage points at source16/20',
        'frame_sha256':{k:sha(v) for k,v in frames.items()},'target_checks':checks,
        'production_color_algorithm_changed':False,
        'payload_bytes':len(payload),'payload_sha256':sha(payload),'sampler_codes_sha256':sha(codes),
        'source_hashes':hashes,'common_enabled_flags':['CONFIG_PAPERCOLOR_'+f for f in FLAGS]}
    dest.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes['artifacts/color_calibration/secondary-ratio-abc-v1.bin']=sha(payload)
    dest.with_suffix('.sha256').write_text(''.join(h+' '+p+'\n' for p,h in hashes.items()))
    print('Verified: baseline equals IMG_9952; only two host diagnostic targets change; white/black targets preserved; controls identical; full sampler matches.')
    print('Payload:',len(payload),'bytes',sha(payload))
    for row in records:
        print(row['id'], {k:round(v['native_percent']['white'],3) for k,v in row['variants'].items()})
    print(dest.with_suffix('.png'))

if __name__=='__main__':main()
