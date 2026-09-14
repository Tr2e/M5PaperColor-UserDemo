#!/usr/bin/env python3
"""Audit the IMG_9959 green-pair B/B/B production candidate."""
import csv
import hashlib
import io
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FLAGS = [
    "PRIMARY_WHITE_BUDGET", "PRIMARY_PEAK_PRESERVATION", "EXACT_PIGMENT_ANCHOR",
    "BLUE_SECONDARY_BALANCE", "SECONDARY_WHITE_REDUCTION", "CHROMATIC_EDGE_GUARD",
    "WARM_COMPENSATION_BYPASS", "PURPLE_COMPENSATION_SMOOTH", "CYAN_RATIO_SMOOTH",
    "NATIVE_565_RECONSTRUCTION",
]
NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red", 5: "blue", 6: "green"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pigment_weights(points, first, second):
    matrix = np.array([[255, 255, 255], first, second], dtype=float).T
    return np.asarray(points) @ np.linalg.inv(matrix).T


def main():
    source = ROOT / "artifacts/color_calibration/papercolor-calibration-v1.png"
    chart = Image.open(source).convert("RGB")
    spec = json.loads(source.with_suffix(".json").read_text())
    report = {
        "baseline": "IMG_9958 accepted experimental baseline",
        "candidate": "IMG_9959 B/B/B continuous green-pair refinement",
        "source_sha256": sha(source.read_bytes()),
        "production_color_algorithm_changed": True,
        "variants": {},
    }
    frames = {}
    targets = {}
    with tempfile.TemporaryDirectory(prefix="papercolor-green-pair-refinement-") as directory:
        directory = Path(directory)
        for enabled in (False, True):
            name = "candidate" if enabled else "baseline"
            defines = [f"-DCONFIG_PAPERCOLOR_{flag}=1" for flag in FLAGS]
            defines.append(f"-DCONFIG_PAPERCOLOR_GREEN_PAIR_REFINEMENT={int(enabled)}")
            frame_bin = directory / f"{name}-frame"
            target_bin = directory / f"{name}-targets"
            subprocess.run([
                "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", *defines,
                "-Imain", "main/display/papercolor_lut.cpp",
                "main/display/papercolor_photo_dither.cpp", "tools/color_lab/probe_frame.cpp",
                "-o", str(frame_bin),
            ], cwd=ROOT, check=True)
            subprocess.run([
                "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", *defines,
                "-Imain", "main/display/papercolor_lut.cpp", "tools/color_lab/probe_targets.cpp",
                "-o", str(target_bin),
            ], cwd=ROOT, check=True)
            raw = subprocess.run(
                [str(frame_bin), "artifacts/color_lut/nominal-5bit.lut"],
                cwd=ROOT, input=chart.tobytes(), capture_output=True, check=True).stdout
            repeat = subprocess.run(
                [str(frame_bin), "artifacts/color_lut/nominal-5bit.lut"],
                cwd=ROOT, input=chart.tobytes(), capture_output=True, check=True).stdout
            assert raw == repeat and len(raw) == 240000 and set(raw) <= set(NAMES)
            frames[name] = np.frombuffer(raw, np.uint8).reshape(600, 400)
            target_csv = subprocess.run(
                [str(target_bin)], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            rows = list(csv.DictReader(io.StringIO(target_csv)))
            targets[name] = np.array(
                [[float(row[f"target_{channel}"]) for channel in "rgb"] for row in rows])
            result = {"frame_sha256": sha(raw), "patches": []}
            rgb = np.asarray(chart)
            for patch in spec["patches"]:
                x0, y0, x1, y1 = patch["rect_xyxy"]
                fill = np.all(rgb[y0:y1, x0:x1] == patch["rgb"], axis=2)
                values = frames[name][y0:y1, x0:x1][fill]
                counts = Counter(values)
                result["patches"].append({
                    "id": patch["id"],
                    "native_counts": {NAMES[code]: int(counts[code]) for code in NAMES},
                })
            report["variants"][name] = result

    assert report["variants"]["baseline"]["frame_sha256"] == (
        "61b7a31855ef42f920eb37fdadd4b0f6925995c1a2be5fc6c16fad42edc6b2f1"
    )
    before, after = targets["baseline"], targets["candidate"]
    changed = np.any(before != after, axis=1)
    indices = np.arange(65536)
    masks = np.array([int(row["mask"]) for row in rows])
    assert np.all(np.isin(masks[changed], [71, 99]))

    patch_targets = {}
    for patch in spec["patches"]:
        red, green, blue = patch["rgb"]
        index = (red >> 3) << 11 | (green >> 2) << 5 | (blue >> 3)
        patch_targets[str(patch["id"])] = {
            "baseline": before[index].tolist(),
            "candidate": after[index].tolist(),
        }
        if patch["id"] not in (11, 12):
            assert np.array_equal(before[index], after[index]), patch["id"]

    lime_index = (156 >> 3) << 11 | (255 >> 2) << 5
    lime_before = pigment_weights([before[lime_index]], [67, 138, 28], [255, 243, 56])[0]
    lime_after = pigment_weights([after[lime_index]], [67, 138, 28], [255, 243, 56])[0]
    assert abs(lime_after[0] - lime_before[0]) < 0.001
    assert abs(lime_after.sum() - lime_before.sum()) < 0.001
    assert abs((lime_after[1] - lime_before[1]) - 0.0625 * lime_before[1:].sum()) < 0.001

    teal_index = (49 >> 3) << 11 | (154 >> 2) << 5 | (99 >> 3)
    teal_before = pigment_weights([before[teal_index]], [67, 138, 28], [100, 64, 255])[0]
    teal_after = pigment_weights([after[teal_index]], [67, 138, 28], [100, 64, 255])[0]
    assert abs(teal_after.sum() - teal_before.sum()) < 0.001
    assert abs(teal_after[0] - teal_before[0] * 0.6) < 0.001
    expected_green = teal_before[1] - 0.0625 * teal_before[1:].sum()
    ratio_green = expected_green / teal_before[1:].sum()
    assert abs(teal_after[1] / teal_after[1:].sum() - ratio_green) < 0.001

    old_steps = []
    new_steps = []
    edge_pairs = []
    for step, valid in (
        (2048, (indices >> 11) < 31),
        (32, ((indices >> 5) & 63) < 63),
        (1, (indices & 31) < 31),
    ):
        left = indices[valid]
        right = left + step
        old_steps.extend(np.linalg.norm(before[left] - before[right], axis=1))
        new_steps.extend(np.linalg.norm(after[left] - after[right], axis=1))
        edge_pairs.extend(zip(left.tolist(), right.tolist()))
    old_steps = np.asarray(old_steps)
    new_steps = np.asarray(new_steps)
    introduced = np.where((old_steps <= 30.0) & (new_steps > 30.0))[0]
    if len(introduced):
        print("introduced_edges", len(introduced))
        print("worst_introduced", [
            (int(index), edge_pairs[index], before[edge_pairs[index][0]].tolist(),
             before[edge_pairs[index][1]].tolist(), after[edge_pairs[index][0]].tolist(),
             after[edge_pairs[index][1]].tolist(), float(old_steps[index]),
             float(new_steps[index]))
            for index in introduced[np.argsort(new_steps[introduced])[-12:]]
        ])
    assert not np.any((old_steps <= 30.0) & (new_steps > 30.0))
    assert new_steps.max() <= old_steps.max() + 0.1

    base_patches = report["variants"]["baseline"]["patches"]
    new_patches = report["variants"]["candidate"]["patches"]
    changed_patches = [
        old["id"] for old, new in zip(base_patches, new_patches)
        if old["native_counts"] != new["native_counts"]
    ]
    report["checks"] = {
        "targets_scanned": 65536,
        "changed_targets": int(changed.sum()),
        "neighbor_edges": int(len(old_steps)),
        "old_max_neighbor_step": float(old_steps.max()),
        "new_max_neighbor_step": float(new_steps.max()),
        "new_edges_from_at_most_30_to_over_30": 0,
        "changed_chart_patches": changed_patches,
        "changed_chart_pixels": int(np.sum(frames["baseline"] != frames["candidate"])),
        "patch_targets": patch_targets,
        "lime_weights_before_after": [lime_before.tolist(), lime_after.tolist()],
        "teal_weights_before_after": [teal_before.tolist(), teal_after.tolist()],
    }
    destination = ROOT / "artifacts/color_calibration/green-pair-refinement-comparison.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["checks"], indent=2))
    for old, new in zip(base_patches, new_patches):
        if old["native_counts"] != new["native_counts"]:
            print(old["id"], old["native_counts"], "->", new["native_counts"])


if __name__ == "__main__":
    main()
