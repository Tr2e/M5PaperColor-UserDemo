#!/usr/bin/env python3
"""Audit native-cell reconstruction using real targets and full photo frames."""
import csv,io,json,hashlib,subprocess,tempfile
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image
from compare_cyan_ratio import FLAGS as CYAN_FLAGS, NAMES
ROOT=Path(__file__).resolve().parents[2]
FLAGS=CYAN_FLAGS+['CYAN_RATIO_SMOOTH']
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    chart=Image.open(ROOT/'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB')
    spec=json.loads((ROOT/'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
    native={2:(255,243,56),3:(191,0,0),5:(100,64,255),6:(67,138,28)}
    pack=lambda rgb:(rgb[0]>>3)<<11|(rgb[1]>>2)<<5|(rgb[2]>>3)
    cells={pack(rgb):code for code,rgb in native.items()}
    controls={p['name']:p['rgb'] for p in spec['patches'] if p['id'] not in (3,4,5,6)}
    ramps={}
    for code,color in native.items():
        for channel in range(3):
            a=list(color);b=list(color);a[channel]=max(0,a[channel]-24);b[channel]=min(255,b[channel]+24)
            ramps[f'native{code}_channel{channel}']=(a,b)
    frames={};targets={};rgb888={};results={}
    with tempfile.TemporaryDirectory(prefix='native565-audit-') as directory:
        tmp=Path(directory);probe=(ROOT/'tools/color_lab/probe_targets.cpp').read_text()
        (tmp/'targets.cpp').write_text(probe)
        # The second probe always supplies ordinary bit-expanded RGB888;
        # only the RGB565 adapter may select a different representative.
        (tmp/'rgb888.cpp').write_text(probe.replace('Swap565Source{&swapped}.sample(0, rgb);','(void)swapped; rgb[0]=((packed>>11)<<3)|(packed>>13); rgb[1]=(((packed>>5)&63)<<2)|((packed>>9)&3); rgb[2]=((packed&31)<<3)|((packed&31)>>2);'))
        for enabled,name in [(False,'baseline'),(True,'candidate')]:
            flags=['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS]+['-DCONFIG_PAPERCOLOR_NATIVE_565_RECONSTRUCTION='+str(int(enabled))]
            for kind in ('frame','targets','rgb888'):
                sources=[ROOT/'main/display/papercolor_lut.cpp']
                sources+=([ROOT/'main/display/papercolor_photo_dither.cpp',ROOT/'tools/color_lab/probe_frame.cpp'] if kind=='frame' else [tmp/(kind+'.cpp')])
                subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*flags,'-I'+str(ROOT/'main'),*map(str,sources),'-o',str(tmp/(name+kind))],check=True)
            out=subprocess.check_output([str(tmp/(name+'targets'))],text=True)
            rows=list(csv.DictReader(io.StringIO(out)));targets[name]=np.array([[float(r['target_'+c]) for c in 'rgb'] for r in rows])
            rgb888[name]=subprocess.check_output([str(tmp/(name+'rgb888'))])
            def render(im):
                data=subprocess.run([str(tmp/(name+'frame')),str(ROOT/'artifacts/color_lut/nominal-5bit.lut')],input=im.tobytes(),capture_output=True,check=True).stdout
                assert len(data)==240000 and set(data)<=set(NAMES)
                return data
            data=render(chart);assert render(chart)==data;frames[name]=np.frombuffer(data,np.uint8).reshape(600,400)
            result={'frame_sha256':sha(data),'patches':[],'uniform':{},'ramps':{}}
            for p in spec['patches']:
                x0,y0,x1,y1=p['rect_xyxy'];crop=frames[name][y0:y1,x0:x1];cnt=Counter(crop[1:-1,1:-1].ravel())
                result['patches'].append({'id':p['id'],'crop_sha256':sha(crop.tobytes()),'native_counts':{NAMES[k]:int(cnt[k]) for k in NAMES}})
            for key,color in controls.items():result['uniform'][key]=sha(render(Image.new('RGB',(400,600),tuple(color))))
            for key,(a,b) in ramps.items():
                line=[tuple(round(u+(v-u)*x/399) for u,v in zip(a,b)) for x in range(400)]
                im=Image.new('RGB',(400,600));im.putdata(line*600);codes=np.frombuffer(render(im),np.uint8).reshape(600,400)
                result['ramps'][key]={'sha256':sha(codes.tobytes()),'counts':{NAMES[k]:int(np.sum(codes==k)) for k in NAMES}}
            results[name]=result
    old=json.loads((ROOT/'artifacts/color_calibration/cyan-ratio-comparison.json').read_text())
    assert results['baseline']['frame_sha256']==old['variants']['candidate']['frame_sha256']
    assert rgb888['baseline']==rgb888['candidate'],'RGB888 target mapping must remain identical'
    assert results['baseline']['uniform']==results['candidate']['uniform']
    a,b=targets['baseline'],targets['candidate'];changed=np.where(np.any(a!=b,axis=1))[0]
    assert set(changed)<=set(cells)
    for key,code in cells.items():assert np.array_equal(b[key],native[code]),(key,b[key])
    for pid,code in [(3,2),(4,3),(5,5),(6,6)]:assert results['candidate']['patches'][pid-1]['native_counts'][NAMES[code]]==4128
    index=np.arange(65536);steps=[[],[]];affected=[];details=[]
    for delta,valid in [(2048,(index>>11)<31),(32,((index>>5)&63)<63),(1,(index&31)<31)]:
        i=index[valid];j=i+delta;touch=np.isin(i,changed)|np.isin(j,changed)
        for arr,collection in zip((a,b),steps):collection.extend(np.linalg.norm(arr[i]-arr[j],axis=1))
        affected.extend(touch)
    u,v=map(np.array,steps);touch=np.array(affected)
    assert not np.any((u<=30)&(v>30))
    assert max(v[touch])<30
    report={'baseline':'IMG_9957 cyan smooth','candidate':'native RGB565-cell representative reconstruction','warning':'Nominal targets, not measured physical colors. RGB565 cell collisions are unavoidable; neighboring cells are not snapped.','variants':results,'checks':{'changed_target_keys':changed.tolist(),'native_cells':cells,'rgb888_all_65536_targets_identical':True,'protected_uniform_frames':len(controls),'neighbor_edges':len(u),'old_max':float(max(u)),'new_max':float(max(v)),'affected_old_max':float(max(u[touch])),'affected_new_max':float(max(v[touch])),'new_edges_over_30':int(sum((u<=30)&(v>30))),'changed_frame_pixels':int(np.sum(frames['baseline']!=frames['candidate']))},'source_hashes':{}}
    for path in ['main/display/papercolor_photo_dither.cpp','main/display/papercolor_photo_dither.h','main/display/papercolor_gamut.h','main/display/papercolor_cyan_ratio.h','main/display/papercolor_lut.cpp','tools/color_lab/probe_targets.cpp','tools/color_lab/probe_frame.cpp','tools/color_lab/compare_native565.py','artifacts/color_lut/nominal-5bit.lut']:
        report['source_hashes'][path]=sha((ROOT/path).read_bytes())
    dest=ROOT/'artifacts/color_calibration/native565-comparison.json';dest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['checks'],indent=2))
    for x,y in zip(results['baseline']['patches'],results['candidate']['patches']):
        if x!=y:print(x['id'],x['native_counts'],'->',y['native_counts'])
if __name__=='__main__':main()
