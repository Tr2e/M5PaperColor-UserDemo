#!/usr/bin/env python3
"""Compare full-chart pigment coverage after selecting Burkes for photos."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FLAGS = [
    "PRIMARY_WHITE_BUDGET", "PRIMARY_PEAK_PRESERVATION", "EXACT_PIGMENT_ANCHOR",
    "BLUE_SECONDARY_BALANCE", "SECONDARY_WHITE_REDUCTION", "CHROMATIC_EDGE_GUARD",
    "WARM_COMPENSATION_BYPASS", "PURPLE_COMPENSATION_SMOOTH", "CYAN_RATIO_SMOOTH",
    "NATIVE_565_RECONSTRUCTION", "GREEN_PAIR_REFINEMENT",
    "DEEP_PURPLE_WHITE_REFINEMENT", "WARM_RATIO_REFINEMENT",
]
CODE_NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red", 5: "blue", 6: "green"}
EXPECTED_FRAMES = {
    "floyd_steinberg": "42407c96d85fd2e70fba200c4485ae4339397a13c02f4ad378c68e22e1231a67",
    "burkes": "d0f71129301d96d340d84e6f084cf7f4e30d8371cab63e2c4b62108291cb16a4",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def counts(data):
    count = Counter(data)
    return {name: count[code] for code, name in CODE_NAMES.items()}


def main():
    chart_path = ROOT / "artifacts/color_calibration/papercolor-calibration-v1.png"
    spec_path = ROOT / "artifacts/color_calibration/papercolor-calibration-v1.json"
    chart = Image.open(chart_path).convert("RGB")
    spec = json.loads(spec_path.read_text())
    defines = ["-DCONFIG_PAPERCOLOR_" + flag + "=1" for flag in FLAGS]
    with tempfile.TemporaryDirectory(prefix="papercolor-burkes-compare-") as directory:
        binary = Path(directory) / "render"
        subprocess.run([
            "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", *defines,
            "-Imain", "main/display/papercolor_lut.cpp",
            "main/display/papercolor_photo_dither.cpp", "tools/color_lab/probe_frame_mode.cpp",
            "-o", str(binary),
        ], cwd=ROOT, check=True)
        frames = {}
        for name, mode in (("floyd_steinberg", "fs"), ("burkes", "burkes")):
            def render():
                return subprocess.run(
                    [str(binary), "artifacts/color_lut/nominal-5bit.lut", mode],
                    cwd=ROOT, input=chart.tobytes(), capture_output=True, check=True).stdout
            first = render()
            assert len(first) == 400 * 600 and render() == first
            assert set(first) <= set(CODE_NAMES)
            assert digest(first) == EXPECTED_FRAMES[name]
            frames[name] = first

    rows = []
    maximum_patch_code_delta = 0
    for patch in spec["patches"]:
        x0, y0, x1, y1 = patch["rect_xyxy"]
        variants = {}
        patch_counts = {}
        for name, frame in frames.items():
            crop = bytes(frame[y * 400 + x] for y in range(y0 + 1, y1 - 1)
                         for x in range(x0 + 1, x1 - 1))
            patch_counts[name] = counts(crop)
            variants[name] = {"sha256": digest(crop), "native_counts": patch_counts[name]}
        delta = {name: patch_counts["burkes"][name] - patch_counts["floyd_steinberg"][name]
                 for name in CODE_NAMES.values()}
        maximum_patch_code_delta = max(maximum_patch_code_delta,
                                       *(abs(value) for value in delta.values()))
        rows.append({"id": patch["id"], "name": patch["name"],
                     "source_rgb": patch["rgb"], "variants": variants,
                     "burkes_minus_floyd_steinberg": delta})

    changed = sum(a != b for a, b in zip(frames["floyd_steinberg"], frames["burkes"]))
    neutral_ids = {21, 22, 23, 24}
    neutral_chromatic = 0
    for row in rows:
        if row["id"] in neutral_ids:
            neutral_chromatic += sum(row["variants"]["burkes"]["native_counts"][name]
                                     for name in ("yellow", "red", "blue", "green"))
    report = {
        "decision": "select Burkes for PhotoBalanced and home photo regions",
        "source_photo": "IMG_9967.HEIC",
        "target_mapping_changed": False,
        "full_frame": {
            "pixels": 240000,
            "changed_pixels": changed,
            "changed_percent": changed * 100.0 / 240000,
            "sha256": {name: digest(frame) for name, frame in frames.items()},
            "native_counts": {name: counts(frame) for name, frame in frames.items()},
        },
        "maximum_absolute_native_count_delta_in_one_patch": maximum_patch_code_delta,
        "burkes_neutral_patch_chromatic_codes": neutral_chromatic,
        "patches": rows,
    }
    destination = ROOT / "artifacts/color_calibration/burkes-photo-adoption-comparison.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "full_frame": report["full_frame"],
        "maximum_absolute_native_count_delta_in_one_patch": maximum_patch_code_delta,
        "burkes_neutral_patch_chromatic_codes": neutral_chromatic,
        "report": str(destination.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
