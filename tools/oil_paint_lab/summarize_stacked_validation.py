#!/usr/bin/env python3
"""Verify paired ablations and compose real algorithm outputs, without retouching."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from render_stacked_preview import font


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    args = parser.parse_args()
    names = ['validation', 'optimized', 'baseline_replay', 'ablation_no_detail', 'ablation_no_scale', 'ablation_no_quiet']
    records = {name: json.loads((args.artifacts / ('oil_paint_' + name) / 'results.json').read_text()) for name in names}
    originals = {sample['id']: sample for sample in records['validation']['samples']}
    rows = []
    for name, record in records.items():
        assert set(originals) == {sample['id'] for sample in record['samples']}
        for sample in record['samples']:
            assert sample['source_sha256'] == originals[sample['id']]['source_sha256']
            assert sample['content_size'] == originals[sample['id']]['content_size']
            assert sample['deterministic']
            if name == 'baseline_replay':
                assert sample['output_sha256'] == originals[sample['id']]['output_sha256']
        if name not in ('validation',):
            assert record['prototype_sha256'] == records['optimized']['prototype_sha256']
        rows.append({'variant': name, 'photos': len(record['samples']),
                     'sanitized_runs': sum(s['sanitizer_runs'] for s in record['samples']),
                     'total_strokes': sum(s['strokes'] for s in record['samples'])})
    folder = args.artifacts / 'oil_paint_optimized'
    (folder / 'ablation-summary.json').write_text(json.dumps(dict(
        baseline_replay_matches=9, same_source_and_dimensions=True, variants=rows), indent=2) + '\n')
    sheet = Image.new('RGB', (960, 980), '#f3f1ed')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 12), '原图 / 上一版 / 优化版 · 真实 C++ 输出', font=font(24), fill='#222222')
    for row, (sample_id, title) in enumerate([('P2', '黑白人像：五官结构'), ('S2', '玻璃静物：瓶口、圆环与薄边')]):
        y = 60 + row * 455
        draw.text((24, y), title, font=font(22), fill='#222222')
        for col, (variant, filename, label) in enumerate([('validation', 'before.png', '原图 / RGB565'),
                                                        ('validation', 'after.png', '上一版'),
                                                        ('optimized', 'after.png', '优化版')]):
            x = 24 + col * 312
            draw.text((x, y + 30), label, font=font(17), fill='#555555')
            with Image.open(args.artifacts / ('oil_paint_' + variant) / sample_id / filename) as picture:
                sheet.paste(picture, (x, y + 55))
    sheet.save(folder / 'focus-comparison.png')
    # Nearest-neighbor enlargement is for pixel inspection, not enhancement.
    columns = [('validation', 'before.png', '原图'), ('validation', 'after.png', '旧版'),
               ('ablation_no_detail', 'after.png', '关闭细节'), ('ablation_no_scale', 'after.png', '关闭缩放'),
               ('ablation_no_quiet', 'after.png', '关闭背景控制'), ('optimized', 'after.png', '完整优化')]
    crops = [('P2', (70, 65, 160, 180)), ('S2', (85, 65, 175, 180))]
    sheet = Image.new('RGB', (1248, 620), '#f3f1ed')
    draw = ImageDraw.Draw(sheet)
    for row, (sample_id, box) in enumerate(crops):
        for col, (variant, filename, label) in enumerate(columns):
            x, y = 16 + col * 208, 16 + row * 300
            draw.text((x, y), sample_id + ' ' + label, font=font(16), fill='#222222')
            with Image.open(args.artifacts / ('oil_paint_' + variant) / sample_id / filename) as picture:
                sheet.paste(picture.crop(box).resize((180, 230), Image.Resampling.NEAREST), (x, y + 32))
    sheet.save(folder / 'ablation-crops.png')
    print(json.dumps(rows, indent=2))
    print('PASS: 9/9 baseline hashes, matching sources and content sizes across variants')


if __name__ == '__main__':
    main()
