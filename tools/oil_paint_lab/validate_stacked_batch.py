#!/usr/bin/env python3
"""Reproducible nine-photo visual check of the current host C++ prototype.

Sources must already be downloaded; this script does not access the network.
Fit the whole photograph into a 600x400 viewer, render only its content rectangle,
then add untouched white margins. No per-photo parameter tuning or face cropping.
"""
import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from render_stacked_preview import font


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(path):
    with Image.open(path) as source:
        picture = ImageOps.exif_transpose(source).convert('RGB')
    picture.thumbnail((600, 400), Image.Resampling.LANCZOS)
    pixels = bytearray(picture.tobytes())
    for i in range(0, len(pixels), 3):
        r, g, b = pixels[i] >> 3, pixels[i + 1] >> 2, pixels[i + 2] >> 3
        pixels[i:i + 3] = bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
    return Image.frombytes('RGB', picture.size, bytes(pixels))


def frame(picture):
    result = Image.new('RGB', (600, 400), 'white')
    result.paste(picture, ((600-picture.width)//2, (400-picture.height)//2))
    return result


def pair(before, after, sample, left_label='原图 / RGB565'):
    sheet = Image.new('RGB', (1272, 496), '#f3f1ed')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 10), sample['id'] + '  ' + sample['label'], font=font(22), fill='#222222')
    draw.text((24, 42), left_label, font=font(17), fill='#555555')
    draw.text((648, 42), '堆叠笔触 / 统一规则', font=font(17), fill='#555555')
    sheet.paste(frame(before), (24, 72))
    sheet.paste(frame(after), (648, 72))
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--sources', type=Path, help='Existing photo directory; defaults to bundled firmware photos')
    parser.add_argument('--baseline', type=Path, help='Previous batch; preserve it and compare identical normalized inputs')
    parser.add_argument('--disable', action='append', choices=('detail', 'scale', 'quiet'), default=[],
                        help='Compile-time ablation; may be repeated')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    manifest = Path(__file__).with_name('validation_samples.json')
    samples = json.loads(manifest.read_text())
    prototype = Path(__file__).with_name('render_stacked_ppm.cpp')
    core = project / 'main/display/papercolor_oil_painter.cpp'
    args.output.mkdir(parents=True, exist_ok=True)
    if args.baseline and args.baseline.resolve() == args.output.resolve():
        parser.error('output must not overwrite the baseline')
    results, sheets, cards = [], {}, []
    with tempfile.TemporaryDirectory(prefix='papercolor-nine-') as temporary:
        temporary = Path(temporary)
        binary = temporary / 'render'
        command = ['clang++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-fno-omit-frame-pointer', '-I', str(project / 'main'),
                   str(core), str(prototype), '-o', str(binary)]
        command += ['-DPAINT_' + feature.upper() + '=0' for feature in args.disable]
        subprocess.run(command, check=True)
        for sample in samples:
            source = (args.sources or project / 'main/apps/local_photo_slideshow/images') / (str(sample['photo_id']) + '.jpg')
            before = normalize(source)
            before.save(temporary / 'input.ppm')
            runs = []
            for name in ('out', 'repeat'):
                runs.append(subprocess.run([str(binary), str(temporary / 'input.ppm'),
                                            str(temporary / (name + '.ppm'))],
                                           check=True, capture_output=True, text=True))
            if (temporary / 'out.ppm').read_bytes() != (temporary / 'repeat.ppm').read_bytes():
                raise RuntimeError('Nondeterministic output: ' + sample['id'])
            with Image.open(temporary / 'out.ppm') as rendered:
                after = rendered.convert('RGB')
            if after.size != before.size:
                raise RuntimeError('Wrong output dimensions: ' + sample['id'])
            folder = args.output / sample['id']
            folder.mkdir(exist_ok=True)
            before.save(folder / 'before.png')
            after.save(folder / 'after.png')
            sheet = pair(before, after, sample)
            sheet.save(folder / 'comparison.png')
            if args.baseline:
                with Image.open(args.baseline / sample['id'] / 'before.png') as previous_input:
                    if previous_input.size != before.size or previous_input.convert('RGB').tobytes() != before.tobytes():
                        raise RuntimeError('Baseline input mismatch: ' + sample['id'])
                with Image.open(args.baseline / sample['id'] / 'after.png') as previous_output:
                    if previous_output.size != after.size:
                        raise RuntimeError('Baseline output dimension mismatch: ' + sample['id'])
                    sheet = pair(previous_output.convert('RGB'), after, sample, '上一版 / 固定粗笔触')
                sheet.save(folder / 'baseline-comparison.png')
            sheets.setdefault(sample['category'], []).append(sheet)
            result = dict(sample, content_size=list(before.size), source_sha256=sha(source),
                          output_sha256=sha(folder / 'after.png'), deterministic=True,
                          sanitizer_runs=2, stats=runs[0].stderr.strip().splitlines(),
                          strokes=sum(map(int, re.findall(r'strokes=(\d+)', runs[0].stderr))),
                          actual_radii=list(map(int, re.findall(r'radius=(\d+)', runs[0].stderr))),
                          download_url=f"https://images.pexels.com/photos/{sample['photo_id']}/pexels-photo-{sample['photo_id']}.jpeg?auto=compress&cs=tinysrgb&w=1200")
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            comparison_name = 'baseline-comparison.png' if args.baseline else 'comparison.png'
            cards.append(f'<section><h2>{html.escape(sample["id"] + " · " + sample["label"])}</h2>'
                         f'<a href="{sample["id"]}/{comparison_name}"><img src="{sample["id"]}/{comparison_name}" alt="Algorithm comparison"></a>'
                         f'<details><summary>查看原图与本版</summary>'
                         f'<a href="{sample["id"]}/comparison.png"><img src="{sample["id"]}/comparison.png" alt="Before and after"></a>'
                         '</details>'
                         f'<p>Photo: <a href="{html.escape(sample["source"])}">{html.escape(sample["author"])}</a> · '
                         f'content {before.width}×{before.height} · {result["strokes"]} strokes · ASan/UBSan + deterministic replay passed</p></section>')
    for category, items in sheets.items():
        sheet = Image.new('RGB', (1272, 76 + 496 * len(items)), '#f3f1ed')
        draw = ImageDraw.Draw(sheet)
        draw.text((24, 14), category.upper() + '  /  3 photos', font=font(25), fill='#222222')
        draw.text((24, 48), 'Host C++ / RGB565 / no six-color conversion / no per-photo tuning', font=font(15), fill='#555555')
        for i, item in enumerate(items):
            sheet.paste(item, (0, 76 + i * 496))
        sheet.save(args.output / (category + '.png'))
    metadata = dict(prototype_sha256=sha(prototype), color_helpers_sha256=sha(core),
                    harness_sha256=sha(Path(__file__)),
                    manifest_sha256=sha(manifest), command=command,
                    compiler=subprocess.check_output(['clang++', '--version'], text=True).strip(),
                    viewer_size=[600, 400], normalization='EXIF transpose; contain, no crop; RGB565; paint content only',
                    disabled_features=args.disable, baseline=str(args.baseline) if args.baseline else None,
                    baseline_results_sha256=sha(args.baseline / 'results.json') if args.baseline else None,
                    radii='See per-sample actual_radii', seed='0x5041494e',
                    stage='Host visual prototype, not firmware or Spectra 6', samples=results)
    (args.output / 'results.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>PaperColor 九图验证</title>'
        '<style>body{background:#f3f1ed;color:#222;font:16px system-ui;max-width:1272px;margin:40px auto;padding:0 20px}img{width:100%;height:auto}section{margin:40px 0}a{color:#285a70}p{line-height:1.7}</style>'
        '<h1>PaperColor · 九图统一规则验证</h1><p>主图左侧：' + ('上一版' if args.baseline else 'RGB565 原图') +
        '；右侧：当前 C++ 堆叠笔触原型。可展开原图对比。完整构图适配 600×400 横屏，仅处理照片区域；'
        '未接入六色量化、抖动或固件。竖图因此可用像素更少。运行成功不等于审美或人脸保真通过。</p>'
        '<p><a href="results.json">运行记录、校验值与参数</a> · <a href="https://www.pexels.com/license/">照片使用许可</a></p>'
        + ''.join(cards) + '</html>')


if __name__ == '__main__':
    main()
