#!/usr/bin/env python3
"""Generate a 5-bit RGB-to-native-color LUT using CIEDE2000."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable


LUT_BITS = 5
LUT_EDGE = 1 << LUT_BITS
LUT_SIZE = LUT_EDGE**3
D65 = (0.95047, 1.0, 1.08883)


def srgb_to_lab(rgb: Iterable[int]) -> tuple[float, float, float]:
    values = []
    for value in rgb:
        channel = value / 255.0
        values.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = values
    x = red * 0.4124564 + green * 0.3575761 + blue * 0.1804375
    y = red * 0.2126729 + green * 0.7151522 + blue * 0.0721750
    z = red * 0.0193339 + green * 0.1191920 + blue * 0.9503041

    def lab_f(value: float) -> float:
        delta = 6.0 / 29.0
        return value ** (1.0 / 3.0) if value > delta**3 else value / (3.0 * delta**2) + 4.0 / 29.0

    fx, fy, fz = lab_f(x / D65[0]), lab_f(y / D65[1]), lab_f(z / D65[2])
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def delta_e_2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    g = 0.5 * (1.0 - math.sqrt(c_bar**7 / (c_bar**7 + 25.0**7)))
    a1_prime = (1.0 + g) * a1
    a2_prime = (1.0 + g) * a2
    c1_prime = math.hypot(a1_prime, b1)
    c2_prime = math.hypot(a2_prime, b2)

    def hue(a: float, b: float) -> float:
        angle = math.degrees(math.atan2(b, a))
        return angle + 360.0 if angle < 0.0 else angle

    h1_prime = hue(a1_prime, b1) if c1_prime else 0.0
    h2_prime = hue(a2_prime, b2) if c2_prime else 0.0
    delta_l_prime = l2 - l1
    delta_c_prime = c2_prime - c1_prime
    hue_delta = h2_prime - h1_prime
    if c1_prime * c2_prime == 0.0:
        delta_h_prime = 0.0
    elif abs(hue_delta) <= 180.0:
        delta_h_prime = hue_delta
    elif hue_delta > 180.0:
        delta_h_prime = hue_delta - 360.0
    else:
        delta_h_prime = hue_delta + 360.0
    delta_h_term = 2.0 * math.sqrt(c1_prime * c2_prime) * math.sin(math.radians(delta_h_prime / 2.0))

    l_bar_prime = (l1 + l2) / 2.0
    c_bar_prime = (c1_prime + c2_prime) / 2.0
    if c1_prime * c2_prime == 0.0:
        h_bar_prime = h1_prime + h2_prime
    elif abs(h1_prime - h2_prime) <= 180.0:
        h_bar_prime = (h1_prime + h2_prime) / 2.0
    elif h1_prime + h2_prime < 360.0:
        h_bar_prime = (h1_prime + h2_prime + 360.0) / 2.0
    else:
        h_bar_prime = (h1_prime + h2_prime - 360.0) / 2.0

    t = (
        1.0
        - 0.17 * math.cos(math.radians(h_bar_prime - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * h_bar_prime))
        + 0.32 * math.cos(math.radians(3.0 * h_bar_prime + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * h_bar_prime - 63.0))
    )
    delta_theta = 30.0 * math.exp(-((h_bar_prime - 275.0) / 25.0) ** 2)
    r_c = 2.0 * math.sqrt(c_bar_prime**7 / (c_bar_prime**7 + 25.0**7))
    s_l = 1.0 + 0.015 * (l_bar_prime - 50.0) ** 2 / math.sqrt(20.0 + (l_bar_prime - 50.0) ** 2)
    s_c = 1.0 + 0.045 * c_bar_prime
    s_h = 1.0 + 0.015 * c_bar_prime * t
    r_t = -math.sin(math.radians(2.0 * delta_theta)) * r_c

    l_term = delta_l_prime / s_l
    c_term = delta_c_prime / s_c
    h_term = delta_h_term / s_h
    return math.sqrt(l_term**2 + c_term**2 + h_term**2 + r_t * c_term * h_term)


def load_profile(path: Path) -> dict[str, object]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("grid_bits") != LUT_BITS:
        raise ValueError(f"grid_bits must be {LUT_BITS}")
    colors = profile.get("colors")
    if not isinstance(colors, list) or len(colors) != 6:
        raise ValueError("profile must contain exactly six colors")
    native_codes: set[int] = set()
    for color in colors:
        if not isinstance(color, dict):
            raise ValueError("each color must be an object")
        native = color.get("native")
        rgb = color.get("rgb")
        if not isinstance(native, int) or not 0 <= native <= 0xF or native in native_codes:
            raise ValueError("native color codes must be unique 4-bit integers")
        if not isinstance(rgb, list) or len(rgb) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in rgb):
            raise ValueError("rgb values must contain three bytes")
        native_codes.add(native)
    return profile


def expand_5bit(value: int) -> int:
    return (value << 3) | (value >> 2)


def generate_lut(profile: dict[str, object]) -> bytes:
    colors = profile["colors"]
    palette = [(int(color["native"]), srgb_to_lab(color["rgb"])) for color in colors]
    lut = bytearray(LUT_SIZE)
    offset = 0
    for red5 in range(LUT_EDGE):
        red = expand_5bit(red5)
        for green5 in range(LUT_EDGE):
            green = expand_5bit(green5)
            for blue5 in range(LUT_EDGE):
                lab = srgb_to_lab((red, green, expand_5bit(blue5)))
                lut[offset] = min(palette, key=lambda entry: delta_e_2000(lab, entry[1]))[0]
                offset += 1
    return bytes(lut)


def metadata(profile_path: Path, profile: dict[str, object], lut: bytes) -> dict[str, object]:
    counts = Counter(lut)
    return {
        "schema_version": 1,
        "profile": profile.get("name", profile_path.stem),
        "profile_path": str(profile_path),
        "grid_bits": LUT_BITS,
        "size_bytes": len(lut),
        "distance": "CIEDE2000",
        "sha256": hashlib.sha256(lut).hexdigest(),
        "native_code_counts": {str(code): counts[code] for code in sorted(counts)},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    lut = generate_lut(profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(lut)
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(metadata(args.profile, profile, lut), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
