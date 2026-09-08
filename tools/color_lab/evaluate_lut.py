#!/usr/bin/env python3
"""Compare a PaperColor LUT with the current RGB-nearest-color baseline."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from generate_lut import LUT_EDGE, LUT_SIZE, delta_e_2000, expand_5bit, load_profile, srgb_to_lab


def percentile(sorted_values: list[float], percent: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    position = (len(sorted_values) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "mean": sum(ordered) / len(ordered),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "max": ordered[-1],
    }


def evaluate(profile: dict[str, object], lut: bytes) -> dict[str, object]:
    if len(lut) != LUT_SIZE:
        raise ValueError(f"LUT must contain exactly {LUT_SIZE} bytes")

    colors = profile["colors"]
    palette = [
        {
            "native": int(color["native"]),
            "rgb": tuple(int(channel) for channel in color["rgb"]),
            "lab": srgb_to_lab(color["rgb"]),
        }
        for color in colors
    ]
    palette_by_native = {entry["native"]: entry for entry in palette}
    unknown_codes = sorted(set(lut) - set(palette_by_native))
    if unknown_codes:
        raise ValueError(f"LUT contains native codes absent from profile: {unknown_codes}")

    baseline_errors: list[float] = []
    lut_errors: list[float] = []
    wins = ties = losses = disagreements = 0
    offset = 0
    for red5 in range(LUT_EDGE):
        red = expand_5bit(red5)
        for green5 in range(LUT_EDGE):
            green = expand_5bit(green5)
            for blue5 in range(LUT_EDGE):
                rgb = (red, green, expand_5bit(blue5))
                lab = srgb_to_lab(rgb)
                baseline = min(
                    palette,
                    key=lambda entry: sum((a - b) ** 2 for a, b in zip(rgb, entry["rgb"])),
                )
                selected = palette_by_native[lut[offset]]
                baseline_error = delta_e_2000(lab, baseline["lab"])
                lut_error = delta_e_2000(lab, selected["lab"])
                baseline_errors.append(baseline_error)
                lut_errors.append(lut_error)
                disagreements += baseline["native"] != selected["native"]
                if lut_error < baseline_error - 1e-12:
                    wins += 1
                elif lut_error > baseline_error + 1e-12:
                    losses += 1
                else:
                    ties += 1
                offset += 1

    baseline_summary = summarize(baseline_errors)
    lut_summary = summarize(lut_errors)
    mean_reduction = baseline_summary["mean"] - lut_summary["mean"]
    return {
        "schema_version": 1,
        "sample_space": f"expanded {LUT_EDGE}x{LUT_EDGE}x{LUT_EDGE} sRGB grid",
        "sample_count": LUT_SIZE,
        "baseline": "RGB squared Euclidean nearest palette color",
        "candidate": "5-bit CIEDE2000 LUT",
        "metric": "CIEDE2000 against nominal profile",
        "baseline_delta_e": baseline_summary,
        "candidate_delta_e": lut_summary,
        "mean_delta_e_reduction": mean_reduction,
        "mean_delta_e_reduction_percent": 100.0 * mean_reduction / baseline_summary["mean"],
        "mapping_disagreements": disagreements,
        "candidate_wins": wins,
        "ties": ties,
        "candidate_losses": losses,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("lut", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = evaluate(load_profile(args.profile), args.lut.read_bytes())
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
