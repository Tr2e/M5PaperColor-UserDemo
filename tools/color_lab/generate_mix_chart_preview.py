#!/usr/bin/env python3
"""Preview actual C++ native fill codes; labels approximate the device font.

Nominal palette preview only, never a simulation of physical panel color.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]

def main():
    with tempfile.TemporaryDirectory(prefix='papercolor-mix-preview-') as tmp:
        binary=str(Path(tmp)/'probe')
        subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'main'),
            str(ROOT/'tools/color_lab/probe_mix_chart.cpp'),'-o',binary],check=True)
        codes=subprocess.run([binary],capture_output=True,check=True).stdout
    assert len(codes)==240000
    palette=json.loads((ROOT/'tools/color_lab/profiles/nominal.json').read_text())['colors']
    colors={p['native']:tuple(p['rgb']) for p in palette};colors[255]=(255,255,255)
    image=Image.new('RGB',(400,600),'white')
    image.putdata([colors[c] for c in codes])
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',10)
    big=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',20)
    def label(text,x,y,large=False):
        draw.text((x,y),text,font=big if large else font,fill='black',anchor='lt')
    label('MIX RATIO CHECK',12,10,True)
    label('v1 / SAME-SCREEN COLOR AND WHITE COMPARISON',12,32)
    for i,name in enumerate(['BLACK','WHITE','YELLOW','RED','BLUE','GREEN']):
        label(name,12+i*64,44)
        draw.rectangle((11+i*64,53,68+i*64,78),outline='black')
    records=[]
    for panel,top in enumerate([126,344]):
        label('A / RED + BLUE : MAGENTA / PURPLE' if panel==0 else 'B / GREEN + BLUE : CYAN / TEAL',12,top-32)
        label('R:' if panel==0 else 'G:',4,top-16)
        for col,value in enumerate([25,37.5,50,62.5,75]):label(f'{value}%',48+col*68,top-16)
        for row,value in enumerate([0,12.5,25,37.5]):
            label(['W 0%','W12.5%','W 25%','W37.5%'][row],4,top+row*44+12)
            for col,fraction in enumerate([25,37.5,50,62.5,75]):
                x=48+col*68;y=top+row*44
                draw.rectangle((x-1,y-1,x+64,y+32),outline='black')
                counts=Counter(codes[yy*400+xx] for yy in range(y,y+32) for xx in range(x,x+64))
                first=3 if panel==0 else 6
                assert counts[1]==2048*value/100
                assert counts[first]==(2048-counts[1])*fraction/100
                assert counts[5]==2048-counts[1]-counts[first]
                assert set(counts)<={1,first,5}
                records.append({'panel':'A' if panel==0 else 'B','white_percent':value,
                    'first_pigment':'red' if panel==0 else 'green','first_share_of_chromatic_percent':fraction,
                    'fill_xyxy':[x,y,x+64,y+32],'native_counts':dict(counts),
                    'native_percent':{str(k):v/2048*100 for k,v in counts.items()}})
    for text,y in [('ROWS: white share of ALL pixels',530),('COLS: red/green share of COLORED pixels',544),
        ('Compare hue, brightness and visible grain.',558),('Photograph whole chart in even light.',572),('A: return home',586)]:label(text,12,y)
    for x,y in [(2,2),(392,2),(2,592),(392,592)]:draw.rectangle((x,y,x+5,y+5),fill='black')
    dest=ROOT/'artifacts/color_calibration/mix-ratio-v1'
    image.save(dest.with_suffix('.png'))
    manifest={'warning':'Nominal RGB preview, not physical colors. C++ supplies exact native fill codes; preview font approximates device labels.',
        'fill_codes_sha256':hashlib.sha256(codes).hexdigest(),'source_sha256':hashlib.sha256((ROOT/'main/display/papercolor_mix_chart.h').read_bytes()).hexdigest(),
        'tile':[16,8],'grid_patch_count':40,'patches':records}
    dest.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(dest.with_suffix('.png'))
    print('40 exact mixtures verified; native code frame SHA256:',manifest['fill_codes_sha256'])

if __name__=='__main__':main()
