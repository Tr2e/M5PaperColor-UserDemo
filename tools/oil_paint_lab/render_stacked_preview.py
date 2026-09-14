#!/usr/bin/env python3
"""Run the stacked-brush C++ prototype and save reproducible RGB565 comparisons."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for path in ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def comparison(left, right, left_label, right_label, output):
    width, height = left.size
    sheet = Image.new('RGB', (width * 2 + 72, height + 114), '#f3f1ed')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 16), left_label, fill='#262626', font=font(22))
    draw.text((width + 48, 16), right_label, fill='#262626', font=font(22))
    sheet.paste(left, (24, 56))
    sheet.paste(right, (width + 48, 56))
    draw.text((24, height + 77), '600 x 400 | C++ algorithm | RGB565 before six-color conversion',
              fill='#555555', font=font(16))
    sheet.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--rotate-clockwise', type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    prototype = project / 'tools/oil_paint_lab/render_stacked_ppm.cpp'
    core = project / 'main/display/papercolor_oil_painter.cpp'
    before = Image.open(args.source).convert('RGB')
    if args.rotate_clockwise:
        before = before.rotate(-args.rotate_clockwise, expand=True)
    before.thumbnail((600, 400), Image.Resampling.LANCZOS)
    frame = Image.new('RGB', (600, 400), 'white')
    frame.paste(before, ((600 - before.width) // 2, (400 - before.height) // 2))
    pixels = bytearray(frame.tobytes())
    for i in range(0, len(pixels), 3):
        r, g, b = pixels[i] >> 3, pixels[i + 1] >> 2, pixels[i + 2] >> 3
        pixels[i:i + 3] = bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
    before = Image.frombytes('RGB', frame.size, bytes(pixels))
    with tempfile.TemporaryDirectory(prefix='papercolor-brush-') as temporary:
        temporary = Path(temporary)
        binary = temporary / 'render'
        command = ['clang++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror']
        if args.sanitize:
            command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        command += ['-I', str(project / 'main'), str(core), str(prototype), '-o', str(binary)]
        subprocess.run(command, check=True)
        before.save(temporary / 'input.ppm')
        result = subprocess.run([str(binary), str(temporary / 'input.ppm'), str(temporary / 'out.ppm')],
                                check=True, capture_output=True, text=True)
        # Replay the same compiled algorithm, checking byte-for-byte determinism.
        subprocess.run([str(binary), str(temporary / 'input.ppm'), str(temporary / 'repeat.ppm')],
                       check=True, capture_output=True)
        assert (temporary / 'repeat.ppm').read_bytes() == (temporary / 'out.ppm').read_bytes()
        after = Image.open(temporary / 'out.ppm').convert('RGB')
        after.load()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    before.save(args.output_dir / 'before.png')
    after.save(args.output_dir / 'after.png')
    comparison(before, after, '原图 / RGB565', '优化笔触 / 纯算法试验版',
               args.output_dir / 'source-comparison.png')
    if args.baseline:
        baseline = Image.open(args.baseline).convert('RGB')
        if baseline.size != before.size:
            parser.error('baseline must have the same 600x400 dimensions')
        comparison(baseline, after, '上一版 / 切角色块', '本轮优化 / 笔触试验版',
                   args.output_dir / 'brush-comparison.png')
    metadata = {
        'source': str(args.source), 'clockwise_rotation': args.rotate_clockwise,
        'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'prototype_sha256': hashlib.sha256(prototype.read_bytes()).hexdigest(),
        'color_helpers_sha256': hashlib.sha256(core.read_bytes()).hexdigest(),
        'resolution': list(before.size), 'stats': result.stderr.strip().splitlines(),
        'sanitizers': args.sanitize, 'deterministic_replay': True,
        'stage': 'Host prototype RGB565; no six-color conversion or firmware integration',
    }
    (args.output_dir / 'render.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))
    print(args.output_dir / 'brush-comparison.png' if args.baseline else args.output_dir / 'source-comparison.png')


if __name__ == '__main__':
    main()
