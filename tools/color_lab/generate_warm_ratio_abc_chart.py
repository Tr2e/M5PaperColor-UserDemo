#!/usr/bin/env python3
"""Compose fixed-white patch-14/15 red/yellow ratio A/B/C crops."""
from collections import Counter
import hashlib, json, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ["PRIMARY_WHITE_BUDGET", "PRIMARY_PEAK_PRESERVATION", "EXACT_PIGMENT_ANCHOR",
         "BLUE_SECONDARY_BALANCE", "SECONDARY_WHITE_REDUCTION", "CHROMATIC_EDGE_GUARD",
         "WARM_COMPENSATION_BYPASS", "PURPLE_COMPENSATION_SMOOTH", "CYAN_RATIO_SMOOTH",
         "NATIVE_565_RECONSTRUCTION", "GREEN_PAIR_REFINEMENT", "DEEP_PURPLE_WHITE_REFINEMENT"]
COLORS = {0:(0,0,0), 1:(255,255,255), 2:(255,243,56), 3:(191,0,0),
          5:(100,64,255), 6:(67,138,28)}
NAMES = {0:"black", 1:"white", 2:"yellow", 3:"red", 5:"blue", 6:"green"}
ROWS = [(14,[0,1,2]), (15,[0,1,2]), (13,[0,0,0]), (9,[0,0,0]), (12,[0,0,0]), (16,[0,0,0])]
LABELS = ["14 ORANGE RATIO B:+RED C:-RED", "15 RED ORANGE B:+RED C:-RED",
          "13 WARM YELLOW CONTROL", "09 DEEP PURPLE CONTROL", "12 TEAL CONTROL",
          "16 MAGENTA CONTROL"]
BASELINE_SHA256 = "72db7bef3746af85f7f8d647899bd4f610351d5d21eaaf8ce69e4d6f08477cfc"
INPUTS = ["main/display/papercolor_photo_dither.cpp", "main/display/papercolor_photo_dither.h",
          "main/display/papercolor_gamut.h", "main/display/papercolor_cyan_ratio.h",
          "main/display/papercolor_green_pair_refinement.h",
          "main/display/papercolor_deep_purple_refinement.h", "main/display/papercolor_lut.cpp",
          "main/display/papercolor_warm_ratio_abc_chart.h",
          "main/display/papercolor_warm_ratio_abc_chart.cpp", "tools/color_lab/warm_ratio_probe.h",
          "tools/color_lab/generate_warm_ratio_abc_chart.py", "tools/color_lab/probe_frame.cpp",
          "tools/color_lab/probe_warm_ratio_abc_chart.cpp", "artifacts/color_lut/nominal-5bit.lut",
          "artifacts/color_calibration/papercolor-calibration-v1.png",
          "artifacts/color_calibration/papercolor-calibration-v1.json"]
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    chart = Image.open(ROOT / "artifacts/color_calibration/papercolor-calibration-v1.png").convert("RGB")
    spec = json.loads((ROOT / "artifacts/color_calibration/papercolor-calibration-v1.json").read_text())
    patches = {patch["id"]:patch for patch in spec["patches"]}
    source = (ROOT / "main/display/papercolor_photo_dither.cpp").read_text()
    needle = "        cached.edge_pigment = 0;"
    assert source.count(needle) == 1
    modified = "#include \"warm_ratio_probe.h\"\n" + source.replace(
        needle, "        p = papercolor_diagnostic::warm_ratio_target(original, p, "
                "PAPERCOLOR_DIAGNOSTIC_WARM_RATIO_MODE);\n" + needle)
    frames, crops, records, payload = {}, {}, [], bytearray()
    with tempfile.TemporaryDirectory(prefix="papercolor-warm-ratio-") as directory:
        tmp = Path(directory); implementation = tmp / "diagnostic.cpp"; implementation.write_text(modified)
        for mode in range(3):
            binary = tmp / f"render-{mode}"
            subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                *["-DCONFIG_PAPERCOLOR_" + flag + "=1" for flag in FLAGS],
                f"-DPAPERCOLOR_DIAGNOSTIC_WARM_RATIO_MODE={mode}",
                "-I" + str(ROOT / "main"), "-I" + str(ROOT / "tools/color_lab"),
                str(implementation), str(ROOT / "main/display/papercolor_lut.cpp"),
                str(ROOT / "tools/color_lab/probe_frame.cpp"), "-o", str(binary)], check=True)
            def render():
                return subprocess.run([str(binary), str(ROOT / "artifacts/color_lut/nominal-5bit.lut")],
                                      input=chart.tobytes(), capture_output=True, check=True).stdout
            frame = render(); assert len(frame) == 240000 and set(frame) <= set(COLORS); assert render() == frame
            frames[mode] = frame
        assert sha(frames[0]) == BASELINE_SHA256
        for row, (patch_id, modes) in enumerate(ROWS):
            patch = patches[patch_id]; x0,y0,x1,y1 = patch["rect_xyxy"]
            assert (x1-x0,y1-y0) == (88,50)
            record = {"id":patch_id,"name":patch["name"],"source_rgb":patch["rgb"],"modes":modes,"variants":{}}
            for variant, mode in enumerate(modes):
                frame = frames[mode]
                crop = bytes(frame[y*400+x] for y in range(y0,y1) for x in range(x0,x1))
                crops[row,variant] = crop
                payload.extend((crop[index]<<4)|crop[index+1] for index in range(0,len(crop),2))
                count = Counter(frame[y*400+x] for y in range(y0+1,y1-1) for x in range(x0+1,x1-1))
                record["variants"]["ABC"[variant]] = {"mode":mode,"crop_sha256":sha(crop),
                    "native_counts":{NAMES[code]:count[code] for code in COLORS}}
            if row < 2: assert len({crops[row,v] for v in range(3)}) == 3
            else: assert crops[row,0] == crops[row,1] == crops[row,2]
            records.append(record)
        assert len(payload) == 39600
        packed = tmp / "warm-ratio-abc-v1.bin"; packed.write_bytes(payload)
        sampler = tmp / "sampler"
        subprocess.run(["c++","-std=c++17","-O1","-g","-Wall","-Wextra","-Werror",
            "-fsanitize=address,undefined","-fno-omit-frame-pointer","-I"+str(ROOT/"main"),
            str(ROOT/"tools/color_lab/probe_warm_ratio_abc_chart.cpp"),"-o",str(sampler)],check=True)
        codes = subprocess.run([str(sampler),str(packed)],capture_output=True,check=True).stdout
    assert len(codes)==240000 and set(codes)<=set(COLORS)|{255}
    expected=bytearray([255])*240000
    for index,code in enumerate([0,1,2,3,5,6]):
        for y in range(52,72):
            for x in range(12+64*index,68+64*index): expected[y*400+x]=code
    for row in range(6):
        for column,variant in enumerate((0,1,2,0)):
            crop=crops[row,variant]
            for y in range(50):
                start=(118+74*row+y)*400+12+96*column
                expected[start:start+88]=crop[y*88:(y+1)*88]
    assert codes==expected
    image=Image.new("RGB",(400,600),"white"); image.putdata([COLORS.get(code,(255,255,255)) for code in codes])
    draw=ImageDraw.Draw(image); font=ImageFont.truetype("/System/Library/Fonts/Menlo.ttc",10); big=ImageFont.truetype("/System/Library/Fonts/Menlo.ttc",20)
    draw.text((12,8),"WARM RATIO A/B/C",font=big,fill="black"); draw.text((12,30),"A: NOW   B: +RED   C: -RED",font=font,fill="black")
    for index,name in enumerate(["BLACK","WHITE","YELLOW","RED","BLUE","GREEN"]):
        draw.text((12+index*64,42),name,font=font,fill="black"); draw.rectangle((11+index*64,51,68+index*64,72),outline="black")
    for column,name in enumerate("ABCA"): draw.text((52+96*column,84),name,font=font,fill="black")
    for row,label in enumerate(LABELS): draw.text((12,103+74*row),label,font=font,fill="black")
    draw.text((12,552),"Rows 14/15: fixed white and color total",font=font,fill="black")
    draw.text((12,566),"Compare hue, brightness, dots and grain",font=font,fill="black")
    draw.text((12,582),"Keep whole chart visible. Button A: home",font=font,fill="black")
    for x in (2,392):
        for y in (2,592): draw.rectangle((x,y,x+5,y+5),fill="black")
    destination=ROOT/"artifacts/color_calibration/warm-ratio-abc-v1"
    destination.with_suffix(".bin").write_bytes(payload); image.save(destination.with_suffix(".png"))
    manifest={"version":1,"warning":"Nominal preview only; physical hue and texture require panel review.",
        "columns":["A","B","C","A"],"rows":records,"frame_sha256":{str(k):sha(v) for k,v in frames.items()},
        "payload_bytes":len(payload),"payload_sha256":sha(payload),"sampler_codes_sha256":sha(codes),
        "production_color_algorithm_changed":False,"source_hashes":{path:sha((ROOT/path).read_bytes()) for path in INPUTS}}
    destination.with_suffix(".json").write_text(json.dumps(manifest,indent=2)+"\n")
    hashes=dict(manifest["source_hashes"]); hashes["artifacts/color_calibration/warm-ratio-abc-v1.bin"]=sha(payload)
    destination.with_suffix(".sha256").write_text("".join(digest+" "+path+"\n" for path,digest in hashes.items()))
    print("Verified baseline, three deterministic full renders, controls, sanitizer sampler and composition.")
    for record in records: print(record["id"],{key:value["native_counts"] for key,value in record["variants"].items()})
    print("Payload",len(payload),sha(payload))


if __name__ == "__main__": main()
