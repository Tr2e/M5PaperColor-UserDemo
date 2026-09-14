#!/usr/bin/env python3
"""Compose same-target Floyd-Steinberg/Burkes neutral texture crops."""
from collections import Counter
import hashlib, json, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
FLAGS=["PRIMARY_WHITE_BUDGET","PRIMARY_PEAK_PRESERVATION","EXACT_PIGMENT_ANCHOR",
 "BLUE_SECONDARY_BALANCE","SECONDARY_WHITE_REDUCTION","CHROMATIC_EDGE_GUARD",
 "WARM_COMPENSATION_BYPASS","PURPLE_COMPENSATION_SMOOTH","CYAN_RATIO_SMOOTH",
 "NATIVE_565_RECONSTRUCTION","GREEN_PAIR_REFINEMENT","DEEP_PURPLE_WHITE_REFINEMENT",
 "WARM_RATIO_REFINEMENT"]
COLORS={0:(0,0,0),1:(255,255,255),2:(255,243,56),3:(191,0,0),5:(100,64,255),6:(67,138,28)}
NAMES={0:"black",1:"white",2:"yellow",3:"red",5:"blue",6:"green"}
ROWS=[21,22,23,24,16,14]
LABELS=["21 GRAY 32","22 GRAY 96","23 GRAY 160","24 GRAY 224","16 MAGENTA GUARD","14 ORANGE GUARD"]
INPUTS=["main/display/papercolor_photo_dither.cpp","main/display/papercolor_photo_dither.h",
 "main/display/papercolor_gamut.h","main/display/papercolor_cyan_ratio.h",
 "main/display/papercolor_green_pair_refinement.h","main/display/papercolor_deep_purple_refinement.h",
 "main/display/papercolor_warm_ratio_refinement.h","main/display/papercolor_lut.cpp",
 "main/display/papercolor_neutral_dither_ab_chart.h","main/display/papercolor_neutral_dither_ab_chart.cpp",
 "tools/color_lab/probe_frame_mode.cpp","tools/color_lab/probe_neutral_dither_ab_chart.cpp",
 "tools/color_lab/generate_neutral_dither_ab_chart.py","artifacts/color_lut/nominal-5bit.lut",
 "artifacts/color_calibration/papercolor-calibration-v1.png","artifacts/color_calibration/papercolor-calibration-v1.json"]
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
 chart=Image.open(ROOT/"artifacts/color_calibration/papercolor-calibration-v1.png").convert("RGB")
 spec=json.loads((ROOT/"artifacts/color_calibration/papercolor-calibration-v1.json").read_text())
 patches={p["id"]:p for p in spec["patches"]}; frames={}; crops={}; records=[]; payload=bytearray()
 with tempfile.TemporaryDirectory(prefix="papercolor-neutral-dither-") as directory:
  binary=Path(directory)/"render"
  subprocess.run(["c++","-std=c++17","-O2","-Wall","-Wextra","-Werror",
   *["-DCONFIG_PAPERCOLOR_"+f+"=1" for f in FLAGS],"-Imain",
   "main/display/papercolor_lut.cpp","main/display/papercolor_photo_dither.cpp",
   "tools/color_lab/probe_frame_mode.cpp","-o",str(binary)],cwd=ROOT,check=True)
  for variant,mode in enumerate(("fs","burkes")):
   def render(): return subprocess.run([str(binary),"artifacts/color_lut/nominal-5bit.lut",mode],cwd=ROOT,
      input=chart.tobytes(),capture_output=True,check=True).stdout
   frame=render(); assert len(frame)==240000 and set(frame)<=set(COLORS) and render()==frame;frames[variant]=frame
  assert sha(frames[0])=="42407c96d85fd2e70fba200c4485ae4339397a13c02f4ad378c68e22e1231a67"
  for row,pid in enumerate(ROWS):
   p=patches[pid];x0,y0,x1,y1=p["rect_xyxy"];assert(x1-x0,y1-y0)==(88,50)
   rec={"id":pid,"name":p["name"],"source_rgb":p["rgb"],"variants":{}}
   for variant,name in enumerate(("A_FS","B_BURKES")):
    frame=frames[variant];crop=bytes(frame[y*400+x] for y in range(y0,y1) for x in range(x0,x1));crops[row,variant]=crop
    payload.extend((crop[i]<<4)|crop[i+1] for i in range(0,len(crop),2))
    count=Counter(frame[y*400+x] for y in range(y0+1,y1-1) for x in range(x0+1,x1-1))
    rec["variants"][name]={"crop_sha256":sha(crop),"native_counts":{NAMES[k]:count[k] for k in COLORS}}
   assert crops[row,0]!=crops[row,1];records.append(rec)
  assert len(payload)==26400
  packed=Path(directory)/"payload.bin";packed.write_bytes(payload);sampler=Path(directory)/"sampler"
  subprocess.run(["c++","-std=c++17","-O1","-g","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",
   "-fno-omit-frame-pointer","-Imain","tools/color_lab/probe_neutral_dither_ab_chart.cpp","-o",str(sampler)],cwd=ROOT,check=True)
  codes=subprocess.run([str(sampler),str(packed)],capture_output=True,check=True).stdout
 assert len(codes)==240000 and set(codes)<=set(COLORS)|{255}
 expected=bytearray([255])*240000
 for i,code in enumerate([0,1,2,3,5,6]):
  for y in range(52,72):
   for x in range(12+64*i,68+64*i):expected[y*400+x]=code
 for row in range(6):
  for col,variant in enumerate((0,1,1,0)):
   crop=crops[row,variant]
   for y in range(50):
    start=(118+74*row+y)*400+12+96*col;expected[start:start+88]=crop[y*88:(y+1)*88]
 assert codes==expected
 image=Image.new("RGB",(400,600),"white");image.putdata([COLORS.get(c,(255,255,255)) for c in codes])
 draw=ImageDraw.Draw(image);font=ImageFont.truetype("/System/Library/Fonts/Menlo.ttc",10);big=ImageFont.truetype("/System/Library/Fonts/Menlo.ttc",20)
 draw.text((12,8),"NEUTRAL DITHER A/B",font=big,fill="black");draw.text((12,30),"A: FLOYD-STEINBERG   B: BURKES",font=font,fill="black")
 for i,name in enumerate(["BLACK","WHITE","YELLOW","RED","BLUE","GREEN"]):draw.text((12+i*64,42),name,font=font,fill="black");draw.rectangle((11+i*64,51,68+i*64,72),outline="black")
 for col,name in enumerate("ABBA"):draw.text((52+96*col,84),name,font=font,fill="black")
 for row,label in enumerate(LABELS):draw.text((12,103+74*row),label,font=font,fill="black")
 draw.text((12,552),"Same targets; compare grain, bands and tone",font=font,fill="black");draw.text((12,566),"Color guards: reject visible hue regression",font=font,fill="black");draw.text((12,582),"Keep whole chart visible. Button A: home",font=font,fill="black")
 for x in(2,392):
  for y in(2,592):draw.rectangle((x,y,x+5,y+5),fill="black")
 dest=ROOT/"artifacts/color_calibration/neutral-dither-ab-v1";dest.with_suffix(".bin").write_bytes(payload);image.save(dest.with_suffix(".png"))
 manifest={"version":1,"warning":"Nominal preview only; physical texture requires panel review.","columns":["A_FS","B_BURKES","B_BURKES","A_FS"],"rows":records,
  "frame_sha256":{"A_FS":sha(frames[0]),"B_BURKES":sha(frames[1])},"payload_bytes":len(payload),"payload_sha256":sha(payload),
  "sampler_codes_sha256":sha(codes),"production_color_algorithm_changed":False,"source_hashes":{p:sha((ROOT/p).read_bytes()) for p in INPUTS}}
 dest.with_suffix(".json").write_text(json.dumps(manifest,indent=2)+"\n")
 hashes=dict(manifest["source_hashes"]);hashes["artifacts/color_calibration/neutral-dither-ab-v1.bin"]=sha(payload)
 dest.with_suffix(".sha256").write_text("".join(v+" "+k+"\n" for k,v in hashes.items()))
 print("Verified deterministic FS/Burkes full frames, sanitizer sampler and independent composition.")
 for r in records:print(r["id"],{k:v["native_counts"] for k,v in r["variants"].items()})
 print("Payload",len(payload),sha(payload),"frames",manifest["frame_sha256"])
if __name__=="__main__":main()
