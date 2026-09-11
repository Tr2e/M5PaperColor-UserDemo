#!/usr/bin/env python3
"""Pre-render baseline/smooth cyan ratio with the real photo code, then compose native A/B/B/A crops.

No physical color model or alternate ordered dither is introduced. Pillow is
used for source pixels and a nominal preview; C++ supplies both photo variants
and the exact firmware crop sampler. The original HEIC photos are not inputs.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
IDS=[20,-1,-2,16,17,10]
FLAGS=['PRIMARY_WHITE_BUDGET','PRIMARY_PEAK_PRESERVATION','EXACT_PIGMENT_ANCHOR',
       'BLUE_SECONDARY_BALANCE','CHROMATIC_EDGE_GUARD','SECONDARY_WHITE_REDUCTION','WARM_COMPENSATION_BYPASS','PURPLE_COMPENSATION_SMOOTH']
COLORS={0:(0,0,0),1:(255,255,255),2:(255,243,56),3:(191,0,0),5:(100,64,255),6:(67,138,28)}
NAMES={0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
INPUTS=['main/display/papercolor_photo_dither.cpp','main/display/papercolor_photo_dither.h',
        'main/display/papercolor_gamut.h','main/display/papercolor_cyan_ratio.h','main/display/papercolor_lut.cpp','main/display/papercolor_lut.h',
        'main/display/papercolor_native_chart.h','main/display/papercolor_cyan_ratio_ab_chart.h','main/display/papercolor_cyan_ratio_ab_chart.cpp',
        'tools/color_lab/probe_frame.cpp','tools/color_lab/probe_cyan_ratio_ab_chart.cpp',
        'tools/color_lab/generate_cyan_ratio_ab_chart.py','artifacts/color_lut/nominal-5bit.lut',
        'artifacts/color_calibration/papercolor-calibration-v1.png',
        'artifacts/color_calibration/papercolor-calibration-v1.json']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    chart=Image.open(ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB')
    spec=json.loads((ROOT/'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
    patches={p['id']:p for p in spec['patches']}
    reference=json.loads((ROOT/'artifacts/color_calibration/cyan-ratio-comparison.json').read_text())
    for name,h in reference['source_hashes'].items():
        assert sha((ROOT/name).read_bytes())==h, f'Cyan comparison source changed: {name}'
    # Separate diagnostic stimulus: gradients replace patch 13/14 interiors.
    # Canonical controls are always cropped from the untouched original frame.
    stimulus=chart.copy()
    ramp_specs={-1:{'rect':patches[13]['rect_xyxy'],'a':[0,160,220],'b':[0,255,220]},
                -2:{'rect':patches[14]['rect_xyxy'],'a':[0,255,255],'b':[240,255,255]}}
    for ramp in ramp_specs.values():
        x0,y0,x1,y1=ramp['rect']
        for x in range(x0+1,x1-1):
            color=tuple(round(a+(b-a)*(x-x0-1)/85) for a,b in zip(ramp['a'],ramp['b']))
            for y in range(y0+1,y1-1):stimulus.putpixel((x,y),color)
    frames={}; stimulus_frames={}; crops={}; records=[]; payload=bytearray()
    with tempfile.TemporaryDirectory(prefix='papercolor-cyan-ratio-ab-') as directory:
        tmp=Path(directory)
        for enabled,name in ((False,'A'),(True,'B')):
            binary=tmp/('render-'+name)
            subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
                *['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],
                '-DCONFIG_PAPERCOLOR_CYAN_RATIO_SMOOTH='+str(int(enabled)),
                '-I'+str(ROOT/'main'),str(ROOT/'main/display/papercolor_photo_dither.cpp'),
                str(ROOT/'main/display/papercolor_lut.cpp'),str(ROOT/'tools/color_lab/probe_frame.cpp'),
                '-o',str(binary)],check=True)
            def render(source):
                return subprocess.run([str(binary),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],
                    input=source.tobytes(),capture_output=True,check=True).stdout
            frame=render(chart)
            assert len(frame)==240000 and set(frame)<=set(COLORS)
            assert render(chart)==frame
            frames[name]=frame
            stimulus_frames[name]=render(stimulus)
            assert len(stimulus_frames[name])==240000 and set(stimulus_frames[name])<=set(COLORS)
            assert render(stimulus)==stimulus_frames[name]
        assert sha(frames['A'])==reference['variants']['baseline']['frame_sha256'], 'A must reproduce IMG_9952 exactly'
        assert sha(frames['B'])==reference['variants']['candidate']['frame_sha256'], 'B must reproduce audited cyan candidate exactly'
        # Render both *entire* source frames first. No per-patch resets, scaling,
        # crop-local diffusion or compositing through another photo pass.
        for row,pid in enumerate(IDS):
            if pid<0:
                ramp=ramp_specs[pid]; rect=ramp['rect']; data=stimulus_frames
                record={'id':pid,'source':'separate stimulus full frame','ramp':ramp,'variants':{}}
            else:
                patch=patches[pid]; rect=patch['rect_xyxy']; data=frames
                record={'id':pid,'name':patch['name'],'source':'unchanged canonical full frame',
                        'source_rgb':patch['rgb'],'source_rect_xyxy':rect,'variants':{}}
            x0,y0,x1,y1=rect
            assert (x1-x0,y1-y0)==(88,50)
            for name in ('A','B'):
                crop=bytes(data[name][y*400+x] for y in range(y0,y1) for x in range(x0,x1))
                crops[row,name]=crop
                payload.extend((crop[i]<<4)|crop[i+1] for i in range(0,len(crop),2))
                fill=[data[name][y*400+x] for y in range(y0+1,y1-1) for x in range(x0+1,x1-1)]
                assert len(fill)==4128
                counts=Counter(fill)
                record['variants'][name]={'crop_sha256':sha(crop),'fill_pixels':len(fill),
                    'native_counts':{NAMES[c]:counts[c] for c in COLORS},
                    'native_percent':{NAMES[c]:100*counts[c]/len(fill) for c in COLORS}}
                if pid==10:assert set(fill)<={5,6}
                if pid<0:
                    columns=[[sum(COLORS[data[name][y*400+x]][c] for y in range(y0+1,y1-1))/48
                              for c in range(3)] for x in range(x0+1,x1-1)]
                    record['variants'][name]['nominal_rgb_columns']=columns
            if pid>0 and pid!=20:assert crops[row,'A']==crops[row,'B']
            else:assert crops[row,'A']!=crops[row,'B']
            records.append(record)
        assert len(payload)==26400
        packed=tmp/'cyan-ratio-ab-v1.bin';packed.write_bytes(payload)
        binary=tmp/'sampler'
        subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
            '-I'+str(ROOT/'main'),str(ROOT/'tools/color_lab/probe_cyan_ratio_ab_chart.cpp'),'-o',str(binary)],check=True)
        codes=subprocess.run([str(binary),str(packed)],capture_output=True,check=True).stdout
    assert len(codes)==240000 and set(codes)<=set(COLORS)|{255}
    expected=bytearray([255])*240000
    for i,c in enumerate([0,1,2,3,5,6]):
        for y in range(52,72):
            for x in range(12+64*i,68+64*i):expected[y*400+x]=c
    for row in range(6):
        for col,name in enumerate(('A','B','B','A')):
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
    label('CYAN RATIO SMOOTH A/B',12,8,True)
    label('v1  A: NOW  B: LESS GREEN',12,30)
    for i,name in enumerate(['BLACK','WHITE','YELLOW','RED','BLUE','GREEN']):
        label(name,12+i*64,42);draw.rectangle((11+i*64,51,68+i*64,72),outline='black')
    for col,name in enumerate(('A','B','B','A')):label(name,52+96*col,84)
    labels=['20 CYAN  0,255,255','RAMP G:160-255  R:0 B:220',
            'RAMP R:0-240  G:255 B:255','16 MAGENTA CONTROL  255,0,255',
            '17 LIGHT PURPLE  153,51,204','10 BLUE CYAN EDGE  0,173,254']
    for row,text in enumerate(labels):label(text,12,103+74*row)
    for text,y in [('A B B A: identical repeats check uneven light',552),
        ('Compare hue, brightness and grain in each row',566),('Keep whole chart visible. Button A: home',582)]:label(text,12,y)
    for x in (2,392):
        for y in (2,592):draw.rectangle((x,y,x+5,y+5),fill='black')
    dest=ROOT/'artifacts/color_calibration/cyan-ratio-ab-v1'
    dest.with_suffix('.bin').write_bytes(payload)
    image.save(dest.with_suffix('.png'))
    hashes={p:sha((ROOT/p).read_bytes()) for p in INPUTS}
    manifest={'version':1,'warning':'Nominal preview only. Crops are real host-compiled PhotoBalanced outputs, transferred as native codes without a second dither. Physical texture/color still requires panel review.',
        'columns':['A','B','B','A'],'rows':records,'patch_size':[88,50],
        'A':'current IMG_9952 baseline; cyan ratio correction disabled',
        'B':'smooth cyan ratio transfer, up to 6.25pp colored green to blue, white/black target unchanged',
        'frame_sha256':{k:sha(v) for k,v in frames.items()},
        'stimulus_frame_sha256':{k:sha(v) for k,v in stimulus_frames.items()},
        'stimulus_rgb888_sha256':sha(stimulus.tobytes()),'ramps':ramp_specs,
        'payload_bytes':len(payload),'payload_sha256':sha(payload),'sampler_codes_sha256':sha(codes),
        'source_hashes':hashes,'common_enabled_flags':['CONFIG_PAPERCOLOR_'+f for f in FLAGS]}
    dest.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes['artifacts/color_calibration/cyan-ratio-ab-v1.bin']=sha(payload)
    dest.with_suffix('.sha256').write_text(''.join(h+' '+p+'\n' for p,h in hashes.items()))
    print('Verified: A canonical frame reproduces IMG_9952; B matches audited candidate; cyan and separate ramps differ; all 24 crops and native anchors match C++ sampler.')
    print('Payload:',len(payload),'bytes',sha(payload))
    for row in records:
        print(row['id'], {k:round(v['native_percent']['white'],3) for k,v in row['variants'].items()})
    print(dest.with_suffix('.png'))

if __name__=='__main__':main()
