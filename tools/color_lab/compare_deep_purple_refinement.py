#!/usr/bin/env python3
"""Audit the IMG_9961 patch-09 B production candidate."""
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
    "NATIVE_565_RECONSTRUCTION", "GREEN_PAIR_REFINEMENT",
]
NAMES = {0: "black", 1: "white", 2: "yellow", 3: "red", 5: "blue", 6: "green"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def weights(points):
    matrix = np.array([[255, 255, 255], [191, 0, 0], [100, 64, 255]], dtype=float).T
    return np.asarray(points) @ np.linalg.inv(matrix).T


def main():
    source = ROOT / "artifacts/color_calibration/papercolor-calibration-v1.png"
    chart = Image.open(source).convert("RGB")
    spec = json.loads(source.with_suffix(".json").read_text())
    report = {
        "baseline": "IMG_9960 green-pair candidate",
        "candidate": "IMG_9961 patch-09 B continuous deep-purple white refinement",
        "source_sha256": sha(source.read_bytes()),
        "production_color_algorithm_changed": True,
        "variants": {},
    }
    frames = {}
    targets = {}
    rows = None
    with tempfile.TemporaryDirectory(prefix="papercolor-deep-purple-") as directory:
        directory = Path(directory)
        for enabled in (False, True):
            name = "candidate" if enabled else "baseline"
            defines = [f"-DCONFIG_PAPERCOLOR_{flag}=1" for flag in FLAGS]
            defines.append(f"-DCONFIG_PAPERCOLOR_DEEP_PURPLE_WHITE_REFINEMENT={int(enabled)}")
            frame_binary = directory / f"{name}-frame"
            target_binary = directory / f"{name}-targets"
            subprocess.run([
                "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", *defines,
                "-Imain", "main/display/papercolor_lut.cpp",
                "main/display/papercolor_photo_dither.cpp", "tools/color_lab/probe_frame.cpp",
                "-o", str(frame_binary),
            ], cwd=ROOT, check=True)
            subprocess.run([
                "c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", *defines,
                "-Imain", "main/display/papercolor_lut.cpp", "tools/color_lab/probe_targets.cpp",
                "-o", str(target_binary),
            ], cwd=ROOT, check=True)
            raw = subprocess.run(
                [str(frame_binary), "artifacts/color_lut/nominal-5bit.lut"], cwd=ROOT,
                input=chart.tobytes(), capture_output=True, check=True).stdout
            repeat = subprocess.run(
                [str(frame_binary), "artifacts/color_lut/nominal-5bit.lut"], cwd=ROOT,
                input=chart.tobytes(), capture_output=True, check=True).stdout
            assert raw == repeat and len(raw) == 240000 and set(raw) <= set(NAMES)
            frames[name] = np.frombuffer(raw, np.uint8).reshape(600, 400)
            target_csv = subprocess.run(
                [str(target_binary)], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            rows = list(csv.DictReader(io.StringIO(target_csv)))
            targets[name] = np.array(
                [[float(row[f"target_{channel}"]) for channel in "rgb"] for row in rows])
            rgb = np.asarray(chart)
            result = {"frame_sha256": sha(raw), "patches": []}
            for patch in spec["patches"]:
                x0, y0, x1, y1 = patch["rect_xyxy"]
                fill = np.all(rgb[y0:y1, x0:x1] == patch["rgb"], axis=2)
                counts = Counter(frames[name][y0:y1, x0:x1][fill])
                result["patches"].append({
                    "id": patch["id"],
                    "native_counts": {NAMES[code]: int(counts[code]) for code in NAMES},
                })
            report["variants"][name] = result

    assert report["variants"]["baseline"]["frame_sha256"] == (
        "7943d33235ac6f12fb74d762343af215adab36ff7cc928ad9f5e7e4422dbb7d6")
    before, after = targets["baseline"], targets["candidate"]
    changed = np.any(before != after, axis=1)
    indices = np.arange(65536)
    masks = np.array([int(row["mask"]) for row in rows])
    patch_indices = {}
    patch_targets = {}
    for patch in spec["patches"]:
        red, green, blue = patch["rgb"]
        index = (red >> 3) << 11 | (green >> 2) << 5 | (blue >> 3)
        patch_indices[patch["id"]] = index
        patch_targets[str(patch["id"])] = {
            "baseline": before[index].tolist(), "candidate": after[index].tolist()}
        if patch["id"] != 9:
            assert np.array_equal(before[index], after[index]), patch["id"]
    patch9 = patch_indices[9]
    assert np.all(masks[changed] == masks[patch9])
    before_weights = weights([before[patch9]])[0]
    after_weights = weights([after[patch9]])[0]
    assert abs(after_weights[0] - before_weights[0] * 0.5) < 0.001
    assert abs(after_weights[1] / after_weights[2] - before_weights[1] / before_weights[2]) < 0.001
    assert abs(after_weights.sum() - before_weights.sum()) < 0.001

    old_steps = []
    new_steps = []
    edge_pairs = []
    for step, valid in ((2048, (indices >> 11) < 31),
                        (32, ((indices >> 5) & 63) < 63),
                        (1, (indices & 31) < 31)):
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
            (edge_pairs[index], float(old_steps[index]), float(new_steps[index]))
            for index in introduced[np.argsort(new_steps[introduced])[-12:]]])
    assert not len(introduced)
    assert new_steps.max() <= old_steps.max() + 0.1

    baseline_patches = report["variants"]["baseline"]["patches"]
    candidate_patches = report["variants"]["candidate"]["patches"]
    changed_patches = [old["id"] for old, new in zip(baseline_patches, candidate_patches)
                       if old["native_counts"] != new["native_counts"]]
    changed_indices = indices[changed]
    changed_rgb = np.column_stack((
        ((changed_indices >> 11) << 3) | (changed_indices >> 13),
        ((((changed_indices >> 5) & 63) << 2) | ((changed_indices >> 9) & 3)),
        ((changed_indices & 31) << 3) | ((changed_indices & 31) >> 2),
    ))
    report["checks"] = {
        "targets_scanned": 65536, "changed_targets": int(changed.sum()),
        "changed_masks": sorted(set(masks[changed].tolist())),
        "neighbor_edges": int(len(old_steps)),
        "old_max_neighbor_step": float(old_steps.max()),
        "new_max_neighbor_step": float(new_steps.max()),
        "new_edges_from_at_most_30_to_over_30": 0,
        "changed_chart_patches": changed_patches,
        "changed_chart_pixels": int(np.sum(frames["baseline"] != frames["candidate"])),
        "changed_source_rgb_bounds": {
            "minimum": changed_rgb.min(axis=0).tolist(),
            "maximum": changed_rgb.max(axis=0).tolist(),
        },
        "maximum_target_delta": float(np.linalg.norm(after[changed] - before[changed], axis=1).max()),
        "patch_targets": patch_targets,
        "patch09_weights_before_after": [before_weights.tolist(), after_weights.tolist()],
    }
    destination = ROOT / "artifacts/color_calibration/deep-purple-refinement-comparison.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["checks"], indent=2))
    for old, new in zip(baseline_patches, candidate_patches):
        if old["native_counts"] != new["native_counts"]:
            print(old["id"], old["native_counts"], "->", new["native_counts"])


if __name__ == "__main__":
    main()
