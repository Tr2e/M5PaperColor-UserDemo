#!/usr/bin/env python3
"""Render a host-only RGB565 oil preview; it is not an E Ink color simulation."""

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=400)
    parser.add_argument("--height", type=int, default=600)
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0:
        parser.error("width and height must be positive")

    project = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="papercolor-oil-preview-") as temp:
        temporary = Path(temp)
        binary = temporary / "render_ppm"
        subprocess.run(
            ["clang++", "-std=c++17", "-O2", "-I", str(project / "main"),
             str(project / "main/display/papercolor_oil_painter.cpp"),
             str(project / "tools/oil_paint_lab/render_ppm.cpp"), "-o", str(binary)],
            check=True,
        )
        source = Image.open(args.image).convert("RGB")
        source.thumbnail((args.width, args.height), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (args.width, args.height), "white")
        x = (args.width - source.width) // 2
        y = (args.height - source.height) // 2
        frame.paste(source, (x, y))
        source_ppm = temporary / "source.ppm"
        output_ppm = temporary / "output.ppm"
        frame.save(source_ppm)
        subprocess.run(
            [str(binary), str(source_ppm), str(output_ppm), str(x), str(y),
             str(source.width), str(source.height)],
            check=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.open(output_ppm).save(args.output)
    print(f"RGB565 oil preview: {args.output}")


if __name__ == "__main__":
    main()
