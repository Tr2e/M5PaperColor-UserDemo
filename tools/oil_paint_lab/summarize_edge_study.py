#!/usr/bin/env python3
"""Summarize the frozen study without rerendering or changing its algorithm."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from run_edge_study import PROJECT, VARIANTS, sha
from render_stacked_preview import font


def main():
    root = PROJECT / 'artifacts/oil_paint_edge_study'
    freeze = json.loads((root / 'freeze.json').read_text())
    reports = {suite: json.loads((root / suite / 'results.json').read_text())
               for suite in ('develop_v2', 'holdout')}
    benchmark = json.loads((root / 'benchmark.json').read_text())
    expected_hash = freeze['prototype_sha256']
    if any(r['prototype_sha256'] != expected_hash for r in [*reports.values(), benchmark]):
        raise RuntimeError('mixed prototype revisions')
    if reports['holdout']['freeze_check'] != expected_hash:
        raise RuntimeError('holdout was not run against the frozen prototype')
    for suite, report in reports.items():
        for sample in report['samples']:
            for name, record in sample['variants'].items():
                if sha(root / suite / sample['id'] / (name + '.png')) != record['output_sha256']:
                    raise RuntimeError('output image changed after measurement')
    summary = {'prototype_sha256': expected_hash, 'suites': {}}
    for suite, report in reports.items():
        samples = report['samples']
        totals = {name: sum(s['variants'][name]['strokes'] for s in samples) for name in VARIANTS}
        summary['suites'][suite] = dict(
            stroke_totals=totals,
            combined_stroke_change_percent=100 * (totals['combined'] / totals['accepted'] - 1),
            quiet_gradient_improved=sum(s['variants']['combined']['quiet_gradient_mean'] <
                                        s['variants']['accepted']['quiet_gradient_mean'] for s in samples),
            image_count=len(samples),
            largest_edge_mae_increase=max(s['variants']['combined']['edge_rgb_mae'] -
                                          s['variants']['accepted']['edge_rgb_mae'] for s in samples))
    for name in VARIANTS:
        total = sum(s['median_ms'][name] for s in benchmark['samples'])
        summary.setdefault('host_sum_of_image_medians_ms', {})[name] = total
    summary['host_combined_vs_accepted'] = (summary['host_sum_of_image_medians_ms']['combined'] /
                                          summary['host_sum_of_image_medians_ms']['accepted'])
    (root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    # Post-run explanatory ROIs, explicitly not masks used for tuning/scoring.
    rois = [
        ('develop_v2', 'L2', (25, 0, 295, 170), '天空：减少抢眼的背景笔触'),
        ('develop_v2', 'S1', (5, 0, 260, 145), '幕布：稍收敛，仍保留宽色块'),
        ('develop_v2', 'L3', (40, 0, 260, 145), '雾区：仍有块面和细碎色阶'),
        ('holdout', 'H2', (180, 80, 380, 240), '新照片：五官保留，但色面仍硬')]
    sheet = Image.new('RGB', (1248, 60 + 310 * len(rois)), '#f3f1ed')
    draw = ImageDraw.Draw(sheet)
    for i, text in enumerate(['原图局部 / RGB565', '已验收版局部', '实验版局部']):
        draw.text((24 + 408 * i, 14), text, font=font(20), fill='#333333')
    for row, (suite, sample, box, label) in enumerate(rois):
        y = 60 + row * 310
        draw.text((24, y), sample + ' · ' + label, font=font(18), fill='#333333')
        for column, name in enumerate(['before', 'accepted', 'combined']):
            with Image.open(root / suite / sample / (name + '.png')) as picture:
                if not (0 <= box[0] < box[2] <= picture.width and 0 <= box[1] < box[3] <= picture.height):
                    raise RuntimeError('ROI outside content')
                crop = picture.crop(box)
                crop.thumbnail((384, 260), Image.Resampling.NEAREST)
                # Consistent enlargement, no sharpening or photometric edits.
                scale = min(384 / crop.width, 260 / crop.height)
                crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.NEAREST)
                sheet.paste(crop, (24 + column * 408, y + 32))
    sheet.save(root / 'focus.png')
    (root / 'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PaperColor 离线柔边实验</title>
<style>body{font:17px system-ui;max-width:1248px;margin:40px auto;padding:0 20px;background:#f3f1ed;color:#222;line-height:1.7}img{width:100%;height:auto}a{color:#285a70}</style>
<h1>PaperColor · 背景与柔边实验</h1>
<p>结论：局部改善，尚不足以默认替换已验收版。天空、幕布有所收敛；雾区色阶带和低反差五官没有解决。所有图是实际 C++ 算法输出，未使用 AI 生成或后期修图。</p>
<p><a href="develop_v2/index.html">九张开发回归图：原图 / 已验收 / 实验 + 四组消融</a><br>
<a href="holdout/index.html">三张新照片：冻结参数后验证</a><br>
<a href="../../doc/papercolor_stacked_brush_edge_study.md">技术记录与限制</a> ·
<a href="summary.json">指标摘要</a> · <a href="benchmark.json">主机计时</a></p>
<p>以下局部包含改善与遗留问题。裁切仅用于看清差异，不是算法输入，也未用于指标评分。全图见上述图册。</p>
<img src="focus.png" alt="原图、已验收版、实验版的四组局部对比">
<p>这是 RGB565 阶段，不是 Spectra 6 实屏效果。四组测试均可复现且通过 ASan/UBSan，但不代表审美验收。
主机计时包含进程启动和文件读写，不能推算设备耗时。固件、烧录包和 OS 分支未更改。</p>
<p>实验过程：<a href="develop/index.html">第一轮（未采用）</a> → <a href="develop_v2/index.html">第二轮</a> →
<a href="freeze.json">冻结</a> → <a href="holdout/index.html">新图验证</a>。照片来源与作者见各图册。</p></html>''')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
