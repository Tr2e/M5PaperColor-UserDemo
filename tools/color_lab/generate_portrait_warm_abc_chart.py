#!/usr/bin/env python3
"""Compose Kodak-04 crops for a low-chroma warm yellow-to-red A/B/C."""
from collections import Counter
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FLAGS = [
    "PRIMARY_WHITE_BUDGET", "PRIMARY_PEAK_PRESERVATION", "EXACT_PIGMENT_ANCHOR",
    "BLUE_SECONDARY_BALANCE", "SECONDARY_WHITE_REDUCTION", "CHROMATIC_EDGE_GUARD",
    "WARM_COMPENSATION_BYPASS", "PURPLE_COMPENSATION_SMOOTH", "CYAN_RATIO_SMOOTH",
    "NATIVE_565_RECONSTRUCTION", "GREEN_PAIR_REFINEMENT",
    "DEEP_PURPLE_WHITE_REFINEMENT", "WARM_RATIO_REFINEMENT", "PHOTO_BURKES",
]
COLORS = {0: (0, 0, 0), 1: (255, 255, 255), 2: (255, 243, 56),
          3: (191, 0, 0), 5: (100, 64, 255), 6: (67, 138, 28)}
NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red",
         5: "blue", 6: "green"}
CROPS = [
    ("eye_upper_face", 151, 180, 239, 260),
    ("cheek_mouth", 161, 310, 249, 390),
    ("neck_chest", 236, 430, 324, 510),
    ("red_hat_control", 146, 20, 234, 100),
    ("pink_fabric_control", 296, 150, 384, 230),
]
INPUTS = [
    "main/display/papercolor_photo_dither.cpp",
    "main/display/papercolor_photo_dither.h",
    "main/display/papercolor_gamut.h",
    "main/display/papercolor_warm_ratio_refinement.h",
    "main/display/papercolor_portrait_warm_refinement.h",
    "main/display/papercolor_portrait_warm_abc_chart.h",
    "main/display/papercolor_portrait_warm_abc_chart.cpp",
    "tools/color_lab/portrait_warm_probe.h",
    "tools/color_lab/probe_frame_mode.cpp",
    "tools/color_lab/probe_portrait_warm_abc_chart.cpp",
    "tools/color_lab/generate_portrait_warm_abc_chart.py",
    "artifacts/color_lut/nominal-5bit.lut",
    "artifacts/color_calibration/kodim04.png",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    source_image = Image.open(ROOT / "artifacts/color_calibration/kodim04.png").convert("RGB")
    source_image = source_image.resize((400, 600), Image.Resampling.BILINEAR)
    source = (ROOT / "main/display/papercolor_photo_dither.cpp").read_text()
    needle = "        cached.edge_pigment = 0;"
    assert source.count(needle) == 1
    modified = '#include "portrait_warm_probe.h"\n' + source.replace(
        needle,
        "        p = papercolor_diagnostic::portrait_warm_target("
        "original, p, PAPERCOLOR_DIAGNOSTIC_PORTRAIT_WARM_MODE);\n" + needle)

    frames = {}
    crops = {}
    records = []
    payload = bytearray()
    with tempfile.TemporaryDirectory(prefix="papercolor-portrait-warm-") as directory:
        temporary = Path(directory)
        implementation = temporary / "diagnostic.cpp"
        implementation.write_text(modified)
        for mode in range(3):
            binary = temporary / f"render-{mode}"
            subprocess.run([
                "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                *["-DCONFIG_PAPERCOLOR_" + flag + "=1" for flag in FLAGS],
                f"-DPAPERCOLOR_DIAGNOSTIC_PORTRAIT_WARM_MODE={mode}",
                "-I" + str(ROOT / "main"), "-I" + str(ROOT / "tools/color_lab"),
                str(implementation), str(ROOT / "main/display/papercolor_lut.cpp"),
                str(ROOT / "tools/color_lab/probe_frame_mode.cpp"), "-o", str(binary),
            ], check=True)

            def render():
                return subprocess.run(
                    [str(binary), str(ROOT / "artifacts/color_lut/nominal-5bit.lut"), "burkes"],
                    input=source_image.tobytes(), capture_output=True, check=True).stdout

            frame = render()
            assert len(frame) == 240000 and set(frame) <= set(COLORS)
            assert render() == frame
            frames[mode] = frame

        assert len({sha(frame) for frame in frames.values()}) == 3
        for row, (name, x0, y0, x1, y1) in enumerate(CROPS):
            record = {"name": name, "rect_xyxy": [x0, y0, x1, y1], "variants": {}}
            for mode in range(3):
                frame = frames[mode]
                crop = bytes(frame[y * 400 + x]
                             for y in range(y0, y1) for x in range(x0, x1))
                crops[row, mode] = crop
                payload.extend((crop[index] << 4) | crop[index + 1]
                               for index in range(0, len(crop), 2))
                count = Counter(crop)
                record["variants"]["ABC"[mode]] = {
                    "mode": mode, "crop_sha256": sha(crop),
                    "native_counts": {NAMES[code]: count[code] for code in COLORS},
                }
            records.append(record)
        assert len(payload) == 52800
        packed = temporary / "portrait-warm-abca-v2.bin"
        packed.write_bytes(payload)
        sampler = temporary / "sampler"
        subprocess.run([
            "c++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-I" + str(ROOT / "main"),
            str(ROOT / "tools/color_lab/probe_portrait_warm_abc_chart.cpp"),
            "-o", str(sampler),
        ], check=True)
        codes = subprocess.run([str(sampler), str(packed)], capture_output=True,
                               check=True).stdout

    assert len(codes) == 240000 and set(codes) <= set(COLORS) | {255}
    expected = bytearray([255]) * 240000
    for row in range(5):
        for column, variant in enumerate((0, 1, 2, 0)):
            crop = crops[row, variant]
            for y in range(80):
                start = (82 + row * 96 + y) * 400 + 12 + column * 96
                expected[start:start + 88] = crop[y * 88:(y + 1) * 88]
    assert codes == expected

    image = Image.new("RGB", (400, 600), "white")
    image.putdata([COLORS.get(code, (255, 255, 255)) for code in codes])
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 10)
    big = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 20)
    draw.text((8, 6), "PORTRAIT WARM A/B/C/A", font=big, fill="black")
    draw.text((8, 28), "A NOW    B +RED 1/16    C +RED 1/8", font=font, fill="black")
    draw.text((8, 42), "yellow->red; black/white/color total fixed", font=font, fill="black")
    for column, label in enumerate("ABCA"):
        draw.text((52 + column * 96, 58), label, font=font, fill="black")
    labels = ["EYE / UPPER FACE", "CHEEK / MOUTH", "NECK / CHEST",
              "RED HAT CONTROL", "PINK FABRIC CONTROL"]
    for row, label in enumerate(labels):
        draw.text((8, 71 + row * 96), label, font=font, fill="black")
    draw.text((8, 568), "Compare skin cast; guard teeth/hat/fabric", font=font, fill="black")
    draw.text((8, 582), "Keep full panel visible. Button A: home", font=font, fill="black")

    destination = ROOT / "artifacts/color_calibration/portrait-warm-abca-v2"
    destination.with_suffix(".bin").write_bytes(payload)
    image.save(destination.with_suffix(".png"))
    manifest = {
        "version": 1,
        "warning": "Nominal preview only; physical hue and texture require panel review.",
        "source_resize": "Pillow bilinear 512x768 to 400x600 for same-screen relative A/B/C only",
        "columns": ["A", "B", "C", "A"], "rows": records,
        "frame_sha256": {str(mode): sha(frame) for mode, frame in frames.items()},
        "payload_bytes": len(payload), "payload_sha256": sha(payload),
        "sampler_codes_sha256": sha(codes),
        "production_color_algorithm_changed": False,
        "source_hashes": {path: sha((ROOT / path).read_bytes()) for path in INPUTS},
    }
    destination.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    hashes = dict(manifest["source_hashes"])
    hashes["artifacts/color_calibration/portrait-warm-abca-v2.bin"] = sha(payload)
    destination.with_suffix(".sha256").write_text(
        "".join(digest + " " + path + "\n" for path, digest in hashes.items()))
    print("Verified three deterministic full Burkes renders, sampler and composition.")
    for record in records:
        print(record["name"], {key: value["native_counts"]
              for key, value in record["variants"].items()})
    print("Frames", {mode: sha(frame) for mode, frame in frames.items()})
    print("Payload", len(payload), sha(payload))


if __name__ == "__main__":
    main()
