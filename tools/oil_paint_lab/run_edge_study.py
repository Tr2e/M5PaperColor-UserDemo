#!/usr/bin/env python3
"""Offline, isolated comparison of accepted / background / soft-edge variants.

No downloads, firmware writes, or per-photo tuning. Holdout requires a previously
frozen prototype hash. Output directories may not already contain results.
"""
import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from validate_stacked_batch import normalize, frame, sha
from render_stacked_preview import font

LAB = Path(__file__).resolve().parent
PROJECT = LAB.parents[1]
VARIANTS = {'accepted': (0, 0), 'background': (1, 0), 'soft': (0, 1), 'combined': (1, 1)}


def gradient(picture):
    rgb = np.asarray(picture, dtype=np.int16)
    result = np.zeros(rgb.shape[:2], dtype=np.int16)
    result[:, :-1] = np.abs(rgb[:, 1:] - rgb[:, :-1]).max(axis=2)
    result[:-1] = np.maximum(result[:-1], np.abs(rgb[1:] - rgb[:-1]).max(axis=2))
    return result


def masks(before):
    # Independent source-only diagnostic; no semantic subject/background claim.
    g = gradient(before)
    neighbourhood = np.asarray(Image.fromarray(g.astype(np.uint8)).filter(ImageFilter.MaxFilter(7)))
    return neighbourhood < 12, g >= 40


def metrics(before, after, quiet, edges):
    g = gradient(after)
    error = np.abs(np.asarray(before, dtype=np.int16) - np.asarray(after, dtype=np.int16)).mean(axis=2)
    return {'quiet_pixels': int(quiet.sum()), 'edge_pixels': int(edges.sum()),
            'quiet_gradient_mean': float(g[quiet].mean()) if quiet.any() else None,
            'edge_rgb_mae': float(error[edges].mean()) if edges.any() else None}


def strip(sample, pictures, labels):
    canvas = Image.new('RGB', (24 + 624 * len(pictures), 490), '#f3f1ed')
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 8), sample['id'] + ' · ' + sample['label'], font=font(21), fill='#222222')
    for i, (picture, label) in enumerate(zip(pictures, labels)):
        draw.text((24 + 624 * i, 40), label, font=font(17), fill='#555555')
        canvas.paste(frame(picture), (24 + 624 * i, 72))
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--suite', choices=('develop', 'holdout'), default='develop')
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--expected-prototype', help='SHA-256 frozen before rendering holdouts')
    args = parser.parse_args()
    prototype = LAB / 'render_edge_study_ppm.cpp'
    accepted = LAB / 'render_stacked_ppm.cpp'
    core = PROJECT / 'main/display/papercolor_oil_painter.cpp'
    prototype_hash = sha(prototype)
    if args.suite == 'holdout' and not args.expected_prototype:
        parser.error('holdout requires --expected-prototype from the completed development run')
    if args.expected_prototype and args.expected_prototype != prototype_hash:
        parser.error('prototype changed after freeze')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('output must be empty or new; preserve earlier evidence')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = LAB / ('validation_samples.json' if args.suite == 'develop' else 'edge_study_holdout.json')
    sources = args.sources or PROJECT / 'main/apps/local_photo_slideshow/images'
    samples = json.loads(manifest.read_text())
    results, sheets, cards, commands = [], {}, [], {}
    with tempfile.TemporaryDirectory(prefix='papercolor-edges-') as temporary:
        work = Path(temporary)
        common = ['clang++', '-std=c++17', '-O2', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror',
                  '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                  '-I', str(PROJECT / 'main'), str(core)]
        for name, (background, soft) in VARIANTS.items():
            commands[name] = common + [str(prototype), '-DPAINT_BACKGROUND_CONTROL=' + str(background),
                                     '-DPAINT_SOFT_EDGES=' + str(soft), '-o', str(work / name)]
            subprocess.run(commands[name], check=True)
        commands['original'] = common + [str(accepted), '-o', str(work / 'original')]
        subprocess.run(commands['original'], check=True)
        for sample in samples:
            source = sources / (str(sample['photo_id']) + '.jpg')
            before = normalize(source)
            before.save(work / 'input.ppm')
            folder = args.output / sample['id']
            folder.mkdir()
            before.save(folder / 'before.png')
            quiet, edges = masks(before)
            mask = np.zeros((before.height, before.width, 3), dtype=np.uint8)
            mask[quiet] = (40, 160, 200)
            mask[edges] = (255, 170, 40)
            Image.fromarray(mask).save(folder / 'diagnostic-mask.png')
            images, records = {}, {}
            original = subprocess.run([str(work / 'original'), str(work / 'input.ppm'), str(work / 'original.ppm')],
                                      check=True, capture_output=True, text=True)
            for name in VARIANTS:
                logs, pixels = [], []
                for repeat in range(2):
                    output = work / (name + '.ppm')
                    result = subprocess.run([str(work / name), str(work / 'input.ppm'), str(output)],
                                            check=True, capture_output=True, text=True)
                    logs.append(result.stderr)
                    pixels.append(output.read_bytes())
                if pixels[0] != pixels[1] or logs[0] != logs[1]:
                    raise RuntimeError('nondeterministic: ' + sample['id'] + '/' + name)
                if name == 'accepted' and (pixels[0] != (work / 'original.ppm').read_bytes() or logs[0] != original.stderr):
                    raise RuntimeError('switches-off diverges from accepted source')
                with Image.open(output) as rendered:
                    images[name] = rendered.convert('RGB')
                if images[name].size != before.size:
                    raise RuntimeError('dimension mismatch')
                if name == 'accepted' and args.suite == 'develop':
                    golden = PROJECT / 'artifacts/oil_paint_optimized' / sample['id']
                    for file, current in [('before.png', before), ('after.png', images[name])]:
                        with Image.open(golden / file) as old:
                            if old.size != current.size or old.convert('RGB').tobytes() != current.tobytes():
                                raise RuntimeError('accepted golden mismatch: ' + sample['id'])
                images[name].save(folder / (name + '.png'))
                records[name] = dict(metrics(before, images[name], quiet, edges),
                                     strokes=sum(map(int, re.findall(r'strokes=(\d+)', logs[0]))),
                                     stats=logs[0].strip().splitlines(), deterministic=True, sanitizer_runs=2,
                                     output_sha256=sha(folder / (name + '.png')))
            comparison = strip(sample, [before, images['accepted'], images['combined']],
                               ['原图 / RGB565', '已验收版', '实验版 / 平静区域 + 柔边'])
            comparison.save(folder / 'comparison.png')
            strip(sample, [images[n] for n in VARIANTS],
                  ['已验收版', '仅平静区域控制', '仅柔边', '两项同时启用']).save(folder / 'ablation.png')
            sheets.setdefault(sample['category'], []).append(comparison)
            record = dict(sample, source_sha256=sha(source), content_size=list(before.size),
                          quiet_map_payload_bytes=((before.width + 2) // 3) * ((before.height + 2) // 3),
                          source_metrics=metrics(before, before, quiet, edges), variants=records)
            results.append(record)
            print(sample['id'], {n: r['strokes'] for n, r in records.items()}, flush=True)
            cards.append('<section><h2>' + html.escape(sample['id'] + ' · ' + sample['label']) + '</h2>'
                         f'<a href="{sample["id"]}/comparison.png"><img src="{sample["id"]}/comparison.png" alt="原图、已验收版、实验版"></a>'
                         f'<details><summary>四组开关对照</summary><img src="{sample["id"]}/ablation.png" alt="四组开关对照"></details>'
                         f'<p>Photo: <a href="{html.escape(sample["source"])}">{html.escape(sample["author"])}</a></p></section>')
    for category, items in sheets.items():
        sheet = Image.new('RGB', (items[0].width, 490 * len(items)), '#f3f1ed')
        for i, item in enumerate(items):
            sheet.paste(item, (0, 490 * i))
        sheet.save(args.output / (category + '.png'))
    metadata = dict(suite=args.suite, prototype_sha256=prototype_hash, accepted_sha256=sha(accepted),
                    core_sha256=sha(core), harness_sha256=sha(Path(__file__)), manifest_sha256=sha(manifest),
                    compiler=subprocess.check_output(['clang++', '--version'], text=True).strip(),
                    commands=commands, samples=results, freeze_check=args.expected_prototype,
                    stage='Host RGB565 only; no firmware, six-color, real-time, power or aesthetic acceptance claim',
                    metrics='Source-only masks: max 7x7 RGB neighbour gradient <12 for quiet; gradient >=40 for edges. '
                            'Quiet gradient and edge RGB MAE are diagnostics, not artistic quality scores.')
    (args.output / 'results.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>PaperColor 边缘实验</title>'
        '<style>body{font:16px system-ui;background:#f3f1ed;color:#222;max-width:1896px;margin:32px auto;padding:0 20px}'
        'img{width:100%;height:auto}section{margin:40px 0}a{color:#285a70}p{line-height:1.7}</style>'
        '<h1>PaperColor · 平静区域与柔边实验 / ' + args.suite + '</h1>'
        '<p>每行：RGB565 原图 → 已验收算法 → 两项实验。下拉可看单项开关。统一参数、不裁脸、不逐图调参。'
        '这些是实际 C++ 输出；不含六色量化或真实屏幕模拟。已验收固件未修改。'
        '局部平静不等于背景，运行成功也不等于审美验收。</p>'
        '<p><a href="results.json">校验值与运行记录</a> · <a href="https://www.pexels.com/license/">照片许可</a></p>'
        + ''.join(cards) + '</html>')


if __name__ == '__main__':
    main()
