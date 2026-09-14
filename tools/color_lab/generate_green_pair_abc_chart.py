#!/usr/bin/env python3
"""Compose fixed-axis lime/teal A/B/C crops from full real photo renders."""
from collections import Counter
import hashlib,json,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
FLAGS=['PRIMARY_WHITE_BUDGET','PRIMARY_PEAK_PRESERVATION','EXACT_PIGMENT_ANCHOR',
 'BLUE_SECONDARY_BALANCE','SECONDARY_WHITE_REDUCTION','CHROMATIC_EDGE_GUARD',
 'WARM_COMPENSATION_BYPASS','PURPLE_COMPENSATION_SMOOTH','CYAN_RATIO_SMOOTH','NATIVE_565_RECONSTRUCTION']
COLORS={0:(0,0,0),1:(255,255,255),2:(255,243,56),3:(191,0,0),5:(100,64,255),6:(67,138,28)}
NAMES={0:'black',1:'white',2:'yellow',3:'red',5:'blue',6:'green'}
ROWS=[(11,[0,1,2]),(12,[0,3,4]),(12,[0,5,6]),(10,[0,0,0]),(20,[0,0,0]),(17,[0,0,0])]
INPUTS=['main/display/papercolor_photo_dither.cpp','main/display/papercolor_photo_dither.h',
 'main/display/papercolor_gamut.h','main/display/papercolor_cyan_ratio.h','main/display/papercolor_lut.cpp',
 'main/display/papercolor_green_pair_abc_chart.h','main/display/papercolor_green_pair_abc_chart.cpp',
 'tools/color_lab/green_pair_probe.h','tools/color_lab/generate_green_pair_abc_chart.py',
 'tools/color_lab/probe_frame.cpp','tools/color_lab/probe_green_pair_abc_chart.cpp',
 'artifacts/color_lut/nominal-5bit.lut','artifacts/color_calibration/papercolor-calibration-v1.png',
 'artifacts/color_calibration/papercolor-calibration-v1.json']
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
 chart=Image.open(ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB')
 spec=json.loads((ROOT/'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
 patches={p['id']:p for p in spec['patches']}
 reference=json.loads((ROOT/'artifacts/color_calibration/native565-comparison.json').read_text())
 original=(ROOT/'main/display/papercolor_photo_dither.cpp').read_text()
 needle='        cached.edge_pigment = 0;';assert original.count(needle)==1
 modified='#include "green_pair_probe.h"\n'+original.replace(needle,
  '        p = papercolor_diagnostic::green_pair_target(original,p,PAPERCOLOR_DIAGNOSTIC_GREEN_MODE);\n'+needle)
 frames={};crops={};records=[];payload=bytearray()
 with tempfile.TemporaryDirectory(prefix='papercolor-green-pair-') as directory:
  tmp=Path(directory);impl=tmp/'diagnostic.cpp';impl.write_text(modified)
  for mode in range(7):
   binary=tmp/f'render-{mode}'
   subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
    *['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],f'-DPAPERCOLOR_DIAGNOSTIC_GREEN_MODE={mode}',
    '-I'+str(ROOT/'main'),'-I'+str(ROOT/'tools/color_lab'),str(impl),
    str(ROOT/'main/display/papercolor_lut.cpp'),str(ROOT/'tools/color_lab/probe_frame.cpp'),'-o',str(binary)],check=True)
   def render():return subprocess.run([str(binary),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],input=chart.tobytes(),capture_output=True,check=True).stdout
   frame=render();assert len(frame)==240000 and set(frame)<=set(COLORS);assert render()==frame;frames[mode]=frame
  assert sha(frames[0])==reference['variants']['candidate']['frame_sha256']
  for row,(pid,modes) in enumerate(ROWS):
   p=patches[pid];x0,y0,x1,y1=p['rect_xyxy'];assert (x1-x0,y1-y0)==(88,50)
   record={'id':pid,'name':p['name'],'source_rgb':p['rgb'],'modes':modes,'variants':{}}
   for variant,mode in enumerate(modes):
    data=frames[mode];crop=bytes(data[y*400+x] for y in range(y0,y1) for x in range(x0,x1));crops[row,variant]=crop
    payload.extend((crop[i]<<4)|crop[i+1] for i in range(0,len(crop),2))
    count=Counter(data[y*400+x] for y in range(y0+1,y1-1) for x in range(x0+1,x1-1))
    record['variants']['ABC'[variant]]={'mode':mode,'crop_sha256':sha(crop),'native_counts':{NAMES[c]:count[c] for c in COLORS}}
   if row>=3:assert crops[row,0]==crops[row,1]==crops[row,2]
   else:assert len(set(crops[row,v] for v in range(3)))==3
   records.append(record)
  assert len(payload)==39600
  packed=tmp/'green-pair-abc-v1.bin';packed.write_bytes(payload)
  sampler=tmp/'sampler';subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror',
   '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'main'),
   str(ROOT/'tools/color_lab/probe_green_pair_abc_chart.cpp'),'-o',str(sampler)],check=True)
  codes=subprocess.run([str(sampler),str(packed)],capture_output=True,check=True).stdout
 assert len(codes)==240000 and set(codes)<=set(COLORS)|{255}
 expected=bytearray([255])*240000
 for i,c in enumerate([0,1,2,3,5,6]):
  for y in range(52,72):
   for x in range(12+64*i,68+64*i):expected[y*400+x]=c
 for row in range(6):
  for col,variant in enumerate((0,1,2,0)):
   crop=crops[row,variant]
   for y in range(50):
    start=(118+74*row+y)*400+12+96*col;expected[start:start+88]=crop[y*88:(y+1)*88]
 assert codes==expected
 image=Image.new('RGB',(400,600),'white');image.putdata([COLORS.get(c,(255,255,255)) for c in codes]);draw=ImageDraw.Draw(image)
 font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',10);big=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',20)
 def label(t,x,y,f=font):draw.text((x,y),t,font=f,fill='black')
 label('GREEN PAIR A/B/C',12,8,big);label('A: NOW   B/C: ONE AXIS ONLY',12,30)
 for i,n in enumerate(['BLACK','WHITE','YELLOW','RED','BLUE','GREEN']):label(n,12+i*64,42);draw.rectangle((11+i*64,51,68+i*64,72),outline='black')
 for col,n in enumerate('ABCA'):label(n,52+96*col,84)
 labels=['11 LIME  B:+GREEN C:-GREEN','12 TEAL RATIO B:-GREEN C:+GREEN','12 TEAL WHITE B:HALF C:NONE',
  '10 BLUE CYAN EDGE CONTROL','20 CYAN CONTROL','17 LIGHT PURPLE CONTROL']
 for row,n in enumerate(labels):label(n,12,103+74*row)
 label('A B C A; ratio and white tested separately',12,552);label('Compare hue, brightness, white dots and grain',12,566);label('Keep whole chart visible. Button A: home',12,582)
 for x in (2,392):
  for y in (2,592):draw.rectangle((x,y,x+5,y+5),fill='black')
 dest=ROOT/'artifacts/color_calibration/green-pair-abc-v1';dest.with_suffix('.bin').write_bytes(payload);image.save(dest.with_suffix('.png'))
 manifest={'version':1,'warning':'Nominal preview only; physical hue/texture requires panel review.',
  'columns':['A','B','C','A'],'rows':records,'frame_sha256':{str(k):sha(v) for k,v in frames.items()},
  'payload_bytes':len(payload),'payload_sha256':sha(payload),'sampler_codes_sha256':sha(codes),
  'production_color_algorithm_changed':False,'source_hashes':{p:sha((ROOT/p).read_bytes()) for p in INPUTS}}
 dest.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
 hashes=dict(manifest['source_hashes']);hashes['artifacts/color_calibration/green-pair-abc-v1.bin']=sha(payload)
 dest.with_suffix('.sha256').write_text(''.join(h+' '+p+'\n' for p,h in hashes.items()))
 print('Verified baseline, seven deterministic full renders, separate axes, controls, sanitizer sampler and composition.')
 for r in records:print(r['id'],{k:v['native_counts'] for k,v in r['variants'].items()})
 print('Payload',len(payload),sha(payload))
if __name__=='__main__':main()
