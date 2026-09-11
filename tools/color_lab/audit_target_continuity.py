#!/usr/bin/env python3
"""Audit accepted RGB565 targets; never changes firmware or a physical profile.

Requires Pillow. Compiles the real firmware helpers with the accepted white
budget enabled, scans every adjacent RGB565 color, and reports nominal target
steps separately from native-code proportions. The uncompensated column is an
attribution experiment, not a proposed replacement renderer.
"""
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "artifacts/color_calibration/target-continuity-21b0370.json"
NATIVE = {0: (0, 0, 0), 1: (255, 255, 255), 2: (255, 243, 56),
          3: (191, 0, 0), 5: (100, 64, 255), 6: (67, 138, 28)}
NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red", 5: "blue", 6: "green"}


def compile_probe(folder, name, sources):
    binary = Path(folder) / name
    subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-DCONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1",
                    "-I" + str(ROOT / "main"),
                    *[str(ROOT / s) for s in sources],
                    str(ROOT / "main/display/papercolor_lut.cpp"),
                    "-o", str(binary)], check=True)
    return binary


def packed(rgb):
    r, g, b = rgb
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


def summary(values):
    values = sorted(values)
    return {"count": len(values), "mean": round(sum(values) / len(values), 4),
            "p95": round(values[math.ceil(len(values) * .95) - 1], 4),
            "max": round(values[-1], 4),
            "over_30": sum(v > 30 for v in values)} if values else {"count": 0}


def main():
    baseline_sources = ["main/display/papercolor_photo_dither.cpp", "main/display/papercolor_gamut.h",
                        "main/display/papercolor_lut.cpp", "main/display/papercolor_photo_dither.h",
                        "main/display/papercolor_lut.h", "artifacts/color_lut/nominal-5bit.lut"]
    for source in baseline_sources:
        baseline = subprocess.run(["git", "show", "21b0370:" + source], cwd=ROOT,
                                  check=True, capture_output=True).stdout
        if baseline != (ROOT / source).read_bytes():
            raise RuntimeError(f"{source} differs from 21b0370; use a separate candidate audit")
    sources = [*baseline_sources,
               "tools/color_lab/probe_targets.cpp", "tools/color_lab/probe_frame.cpp",
               "tools/color_lab/audit_target_continuity.py", "artifacts/color_calibration/kodim04.png"]
    report = {
        "baseline": "21b0370 + CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1",
        "warning": "Euclidean steps in nominal gamma-encoded RGB; not Delta-E, physical color accuracy, or panel simulation. 30 is an audit ranking threshold, not a visibility threshold.",
        "source_sha256": {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources},
        "ablation": "Remove only source compensation, preserving the selected hull, primary white budget and Q4 rounding; diagnostic targets only.",
    }
    with tempfile.TemporaryDirectory(prefix="papercolor-continuity-") as folder:
        probe = compile_probe(folder, "targets", ["tools/color_lab/probe_targets.cpp"])
        output = subprocess.run([str(probe)], check=True, capture_output=True, text=True).stdout
        rows = []
        for row in csv.DictReader(io.StringIO(output)):
            def vector(prefix):
                return tuple(float(row[prefix + c]) for c in "rgb")
            rows.append({"rgb": vector(""), "mask": int(row["mask"]),
                         "compensated": vector("comp_"), "target": vector("target_"),
                         "uncompensated": vector("uncompensated_")})
            assert int(row["rgb565"]) == len(rows) - 1
        assert len(rows) == 65536
        assert all(packed(tuple(int(v) for v in r["rgb"])) == i for i, r in enumerate(rows))
        edges = defaultdict(list)
        incident = set()
        for i, a in enumerate(rows):
            for step, allowed in [(2048, (i >> 11) < 31),
                                  (32, ((i >> 5) & 63) < 63), (1, (i & 31) < 31)]:
                if not allowed:
                    continue
                b = rows[i + step]
                distance = math.dist(a["target"], b["target"])
                uncompensated = math.dist(a["uncompensated"], b["uncompensated"])
                group = ("mask_change" if a["mask"] != b["mask"] else
                         "compensation_on_off" if (a["rgb"] != a["compensated"]) !=
                         (b["rgb"] != b["compensated"]) else "same_mask_same_compensation_state")
                edges[group].append((distance, uncompensated, i, i + step))
                if distance > 30:
                    incident.update((i, i + step))
        def edge_record(edge):
            distance, uncompensated, i, j = edge
            return {"source_step": math.dist(rows[i]["rgb"], rows[j]["rgb"]),
                    "target_step": round(distance, 4),
                    "uncompensated_target_step": round(uncompensated, 4),
                    "a": rows[i], "b": rows[j]}
        report["grid"] = {
            group: {"accepted": summary([e[0] for e in items]),
                    "uncompensated": summary([e[1] for e in items]),
                    "largest_steps": [edge_record(e) for e in sorted(items, reverse=True)[:5]]}
            for group, items in edges.items()}
        assert sum(len(e) for e in edges.values()) == 2 * 31 * 64 * 32 + 63 * 32 * 32

        ramps = {
            "red_to_white": ((255, 0, 0), (255, 255, 255)),
            "black_to_red": ((0, 0, 0), (255, 0, 0)),
            "neutral": ((0, 0, 0), (255, 255, 255)),
            "cheek_direction": ((0, 0, 0), (255, 201, 170)),
            "purple_compensation_boundary": ((0, 73, 255), (255, 73, 255)),
            "warm_compensation_boundary": ((100, 120, 64), (255, 120, 64)),
            "near_neutral_mid": ((150, 150, 150), (182, 150, 150)),
            "near_neutral_light": ((200, 200, 200), (232, 200, 200)),
        }
        report["ramps"] = {}
        ramp_csv = io.StringIO()
        writer = csv.writer(ramp_csv)
        writer.writerow(["ramp", "step", "source_r", "source_g", "source_b", "mask",
                         "target_r", "target_g", "target_b", "uncompensated_r",
                         "uncompensated_g", "uncompensated_b"])
        for name, (start, end) in ramps.items():
            ids = []
            for t in range(256):
                source = tuple(round(a + (b - a) * t / 255) for a, b in zip(start, end))
                i = packed(source)
                ids.append(i)
                writer.writerow([name, t, *source, rows[i]["mask"], *rows[i]["target"],
                                 *rows[i]["uncompensated"]])
            steps = [(math.dist(rows[a]["target"], rows[b]["target"]),
                      math.dist(rows[a]["uncompensated"], rows[b]["uncompensated"]), a, b)
                     for a, b in zip(ids, ids[1:])]
            report["ramps"][name] = {
                "start": start, "end": end, "steps": 256,
                "accepted": summary([e[0] for e in steps]),
                "uncompensated": summary([e[1] for e in steps]),
                "largest_step": edge_record(max(steps)),
            }
        (DEST.parent / "target-continuity-ramps-21b0370.csv").write_text(ramp_csv.getvalue())

        photo = Image.open(ROOT / "artifacts/color_calibration/kodim04.png").convert("RGB")
        # Hand-selected rectangles, not semantic skin segmentation. Analyze the
        # original pixel distribution; no claim to match the M5 PNG resampler.
        regions = {"whole_original": (0, 0, 512, 768), "cheek_sample": (140, 365, 190, 435),
                   "shoulder_sample": (350, 610, 445, 700), "hat_sample": (130, 60, 380, 155),
                   "pink_fabric_sample": (410, 450, 490, 535)}
        report["portrait_sampling"] = "Original 512x768 pixels, RGB565 quantized, no resizing; rectangular samples are not semantic masks or the exact device framebuffer. Neighbor incidence denotes risk near a synthetic boundary, not observed image banding."
        report["portrait"] = {}
        for name, box in regions.items():
            crop = photo.crop(box)
            ids = [packed(p) for p in crop.getdata()]
            total = len(ids)
            histogram = Counter(ids)
            report["portrait"][name] = {
                "xyxy": box, "pixels": total,
                "mask_percent": {str(m): round(n * 100 / total, 4) for m, n in
                                 sorted(Counter(rows[i]["mask"] for i in ids).items())},
                "source_compensation_percent": round(sum(rows[i]["rgb"] != rows[i]["compensated"]
                                                         for i in ids) * 100 / total, 4),
                "incident_to_grid_step_over_30_percent": round(sum(i in incident for i in ids) * 100 / total, 4),
                "compensation_target_displacement": summary([
                    math.dist(rows[i]["target"], rows[i]["uncompensated"]) for i in ids]),
                "most_frequent_colors": [{"count": n, **rows[i]} for i, n in histogram.most_common(3)],
            }

        frame_probe = compile_probe(folder, "frame", ["tools/color_lab/probe_frame.cpp",
                                                       "main/display/papercolor_photo_dither.cpp"])
        samples = {}
        # Worst boundaries plus fixed neutral/red/pink controls and actual cheek.
        selected = {"pure_red": (255, 0, 0), "pale_red": (255, 160, 160),
                    "gray": (96, 96, 96), "magenta": (255, 0, 255), "cyan": (0, 255, 255)}
        for group, items in edges.items():
            for label, index in zip(("a", "b"), max(items)[2:]):
                selected[group + "_" + label] = tuple(int(v) for v in rows[index]["rgb"])
        selected["frequent_cheek"] = tuple(int(v) for v in
            report["portrait"]["cheek_sample"]["most_frequent_colors"][0]["rgb"])
        for name, rgb in selected.items():
            data = subprocess.run([str(frame_probe), str(ROOT / "artifacts/color_lut/nominal-5bit.lut")],
                                  input=bytes(rgb) * (400 * 600), capture_output=True, check=True).stdout
            assert len(data) == 400 * 600 and set(data) <= set(NATIVE)
            counts = Counter(data[y * 400 + x] for y in range(32, 568) for x in range(32, 368))
            total = sum(counts.values())
            mean = [sum(NATIVE[c][k] * n for c, n in counts.items()) / total for k in range(3)]
            target = rows[packed(rgb)]["target"]
            samples[name] = {"source": rgb, "target": target,
                             "interior_xyxy": [32, 32, 368, 568],
                             "native_percent": {NAMES[c]: round(counts[c] * 100 / total, 4) for c in NATIVE},
                             "nominal_mean": mean, "nominal_mean_target_distance": math.dist(mean, target),
                             "frame_sha256": hashlib.sha256(data).hexdigest()}
        assert samples["pure_red"]["native_percent"]["red"] == 100
        assert sum(samples["gray"]["native_percent"][NAMES[c]] for c in (2, 3, 5, 6)) == 0
        assert samples["pale_red"]["native_percent"]["white"] > 0
        # Check that the independently counted native-code mean follows the
        # inspected target; boundary jumps must not be a trace-only artifact.
        assert all(s["nominal_mean_target_distance"] < 1 for s in samples.values())
        report["uniform_frames"] = samples
    DEST.write_text(json.dumps(report, indent=2) + "\n")
    print(DEST)
    for group, result in report["grid"].items():
        print(group, result["accepted"])
    for name, result in report["portrait"].items():
        print(name, "compensated %", result["source_compensation_percent"],
              "near boundary %", result["incident_to_grid_step_over_30_percent"])


if __name__ == "__main__":
    main()
