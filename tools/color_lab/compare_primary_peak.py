#!/usr/bin/env python3
"""Controlled chart A/B against archived 21b0370; no physical-color claims.

Requires Pillow. Builds the actual old and new renderers independently, records
all 24 patches, checks protected uniform fields, ramps and RGB565 target edges.
"""
import csv
import hashlib
import io
import json
import math
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red", 5: "blue", 6: "green"}
FILES = ["papercolor_photo_dither.cpp", "papercolor_photo_dither.h",
         "papercolor_lut.cpp", "papercolor_lut.h", "papercolor_gamut.h"]


def build(folder, name, includes, source, probe, peak=False):
    binary = folder / (name + "-probe")
    subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-DCONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1",
                    *(["-DCONFIG_PAPERCOLOR_PRIMARY_PEAK_PRESERVATION=1"] if peak else []),
                    "-I" + str(includes), *([str(source)] if source else []),
                    str(includes / "display/papercolor_lut.cpp"), str(probe),
                    "-o", str(binary)], check=True)
    return binary


def main():
    chart_path = ROOT / "artifacts/color_calibration/papercolor-calibration-v1.png"
    chart = Image.open(chart_path).convert("RGB")
    spec = json.loads(chart_path.with_suffix(".json").read_text())
    baseline_hash = json.loads((ROOT / "artifacts/color_calibration/source-chart-baseline-21b0370.json").read_text())["frame_sha256"]
    report = {"baseline": "21b0370 + primary white budget", "candidate": "continuous full-scale primary peak",
              "warning": "Native-code counts and nominal RGB target steps only; not measured color accuracy or Delta-E.",
              "source_sha256": hashlib.sha256(chart_path.read_bytes()).hexdigest(),
              "candidate_source_sha256": {f: hashlib.sha256((ROOT / "main/display" / f).read_bytes()).hexdigest() for f in FILES},
              "variants": {}}
    traces = {}
    frames = {}
    with tempfile.TemporaryDirectory(prefix="papercolor-peak-ab-") as directory:
        folder = Path(directory)
        old = folder / "baseline/main/display"
        old.mkdir(parents=True)
        for f in FILES:
            data = subprocess.run(["git", "show", "21b0370:main/display/" + f], cwd=ROOT,
                                  capture_output=True, check=True).stdout
            (old / f).write_bytes(data)
        for name, includes, peak in [("baseline", old.parent, False), ("candidate", ROOT / "main", True)]:
            binary = build(folder, name, includes, includes / "display/papercolor_photo_dither.cpp",
                           ROOT / "tools/color_lab/probe_frame.cpp", peak)
            def render(image):
                data = subprocess.run([str(binary), str(ROOT / "artifacts/color_lut/nominal-5bit.lut")],
                                      input=image.tobytes(), capture_output=True, check=True).stdout
                assert len(data) == 240000 and set(data) <= set(NAMES)
                return data
            frame = render(chart)
            assert render(chart) == frame
            frames[name] = frame
            result = {"frame_sha256": hashlib.sha256(frame).hexdigest(), "patches": [], "uniform": {}, "ramps": {}}
            for p in spec["patches"]:
                x0, y0, x1, y1 = p["sample_xyxy"]
                indices = [y * 400 + x for y in range(y0, y1) for x in range(x0, x1)]
                counts = Counter(frame[i] for i in indices)
                result["patches"].append({"name": p["name"], "source_rgb": p["rgb"],
                    "native_percent": {NAMES[c]: round(counts[c] * 100 / len(indices), 4) for c in NAMES},
                    "changed_pixels_vs_baseline": sum(frame[i] != frames["baseline"][i] for i in indices)})
            controls = {"red": (255,0,0), "green": (0,255,0), "blue": (0,0,255),
                        "magenta": (255,0,255), "cyan": (0,255,255), "gray96": (96,96,96),
                        "native_blue": (100,64,255), "pale_red": (255,160,160)}
            for key, rgb in controls.items():
                data = render(Image.new("RGB", (400,600), rgb))
                counts = Counter(data)
                result["uniform"][key] = {"frame_sha256": hashlib.sha256(data).hexdigest(),
                    "native_percent": {NAMES[c]: round(counts[c] * 100 / len(data), 4) for c in NAMES}}
            ramps = {"blue_to_black": ((0,0,255),(0,0,0)), "blue_to_white": ((0,0,255),(255,255,255)),
                     "blue_to_cyan": ((0,0,255),(0,255,255)), "blue_to_magenta": ((0,0,255),(255,0,255)),
                     "red_to_white": ((255,0,0),(255,255,255)), "neutral": ((0,0,0),(255,255,255))}
            for key, (a,b) in ramps.items():
                image = Image.new("RGB", (400,600))
                image.putdata([tuple(round(u+(v-u)*x/399) for u,v in zip(a,b)) for y in range(600) for x in range(400)])
                data = render(image)
                if key == "neutral": assert set(data) <= {0,1}
                result["ramps"][key] = {"frame_sha256": hashlib.sha256(data).hexdigest(), "bins": []}
                for x0 in range(0,400,25):
                    counts=Counter(data[y*400+x] for y in range(32,568) for x in range(x0,x0+25))
                    result["ramps"][key]["bins"].append({NAMES[c]: round(counts[c]/13400,6) for c in NAMES})
                if key in ("blue_to_white", "red_to_white", "neutral"):
                    whites=[r["white"] for r in result["ramps"][key]["bins"]]
                    assert all(a <= b + .01 for a,b in zip(whites,whites[1:])), key
            trace = build(folder, name+"-trace", includes, None,
                          ROOT / "tools/color_lab/probe_targets.cpp", peak)
            output = subprocess.run([str(trace)], capture_output=True, text=True, check=True).stdout
            traces[name] = list(csv.DictReader(io.StringIO(output)))
            assert len(traces[name]) == 65536
            report["variants"][name] = result
    assert report["variants"]["baseline"]["frame_sha256"] == baseline_hash
    base, candidate = (report["variants"][k] for k in ("baseline", "candidate"))
    for key in ("red", "green", "magenta", "cyan", "gray96", "native_blue", "pale_red"):
        assert base["uniform"][key] == candidate["uniform"][key], key
    assert candidate["uniform"]["blue"]["native_percent"]["blue"] == 100
    for key in ("red_to_white", "neutral"):
        assert base["ramps"][key] == candidate["ramps"][key], key
    def target(row): return tuple(float(row["target_"+c]) for c in "rgb")
    original = [target(r) for r in traces["baseline"]]
    fixed = [target(r) for r in traces["candidate"]]
    edges = []
    for i, (a,b) in enumerate(zip(original,fixed)):
        r,g,bl = (int(traces["candidate"][i][c]) for c in "rgb")
        # Unaffected source hues keep exactly the accepted quantized target.
        if bl <= max(r,g): assert a == b
        if a != b:
            assert b[2] >= a[2] and b[2] <= bl + .0625
        for step, allowed in [(2048,(i>>11)<31),(32,((i>>5)&63)<63),(1,(i&31)<31)]:
            if allowed:
                edges.append((math.dist(a,original[i+step]),math.dist(b,fixed[i+step]),i,i+step))
    assert len(edges) == 191488
    worst = max(edges,key=lambda e:e[1]-e[0])
    # Guard against the ~77-unit seam in the rejected hard sector-only prototype.
    assert worst[1]-worst[0] < 8.1
    report["continuity"] = {"edges": len(edges),
        "baseline_max_step": max(e[0] for e in edges), "candidate_max_step": max(e[1] for e in edges),
        "max_step_increase": worst[1]-worst[0],
        "new_steps_over_30": sum(a<=30 and b>30 for a,b,_,_ in edges),
        "note": "30 is a diagnostic ranking threshold, not a perceptual threshold. Legacy compensation seams remain."}
    dest=ROOT / "artifacts/color_calibration/primary-peak-comparison.json"
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(dest)
    print(json.dumps(report["continuity"],indent=2))
    print("Protected uniform colors and red/neutral ramps: byte-identical")
    print("Pure blue:",base["uniform"]["blue"]["native_percent"],"->",candidate["uniform"]["blue"]["native_percent"])


if __name__ == "__main__":
    main()
