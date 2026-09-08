#!/usr/bin/env python3
"""Offline A/B of the current firmware and a host-only white-budget candidate.

Requires Pillow; writes numeric evidence only, never modifies firmware or photos.
"""
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
from collections import Counter
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
COLORS = {0: 'black', 1: 'white', 2: 'yellow', 3: 'red', 5: 'blue', 6: 'green'}


def main():
    chart = Image.open(ROOT / 'artifacts/color_calibration/papercolor-calibration-v1.png').convert('RGB')
    spec = json.loads((ROOT / 'artifacts/color_calibration/papercolor-calibration-v1.json').read_text())
    report = {'warning': 'Nominal-code proportions, not measured color accuracy.', 'variants': {}}
    baseline_codes = None
    with tempfile.TemporaryDirectory(prefix='papercolor-white-budget-') as folder:
        for name, source in [('baseline', 'main/display/papercolor_photo_dither.cpp'),
                             ('white_budget', 'tools/color_lab/white_budget_candidate.cpp'),
                             ('primary_budget', 'tools/color_lab/primary_budget_candidate.cpp'),
                             ('primary_firmware', 'main/display/papercolor_photo_dither.cpp')]:
            binary = str(Path(folder) / name)
            defines = ['-DCONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1'] if name == 'primary_firmware' else []
            subprocess.run(['c++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', *defines,
                            '-I' + str(ROOT / 'main'), str(ROOT / source),
                            str(ROOT / 'main/display/papercolor_lut.cpp'),
                            str(ROOT / 'tools/color_lab/probe_frame.cpp'), '-o', binary], check=True)

            def render(image):
                data = subprocess.run([binary, str(ROOT / 'artifacts/color_lut/nominal-5bit.lut')],
                                      input=image.tobytes(), capture_output=True, check=True).stdout
                assert len(data) == 400 * 600 and set(data) <= set(COLORS)
                return data

            codes = render(chart)
            assert codes == render(chart), 'non-deterministic frame'
            if name == 'baseline':
                baseline_codes = codes
            patches = []
            for patch in spec['patches']:
                x0, y0, x1, y1 = patch['sample_xyxy']
                counts = Counter(codes[y * 400 + x] for y in range(y0, y1) for x in range(x0, x1))
                total = sum(counts.values())
                changed = sum(codes[y * 400 + x] != baseline_codes[y * 400 + x]
                              for y in range(y0, y1) for x in range(x0, x1))
                patches.append({'name': patch['name'], 'rgb': patch['rgb'],
                                'changed_pixels_vs_baseline': changed, 'sample_pixels': total,
                                'percent': {COLORS[c]: round(counts[c] * 100 / total, 3) for c in COLORS}})

            # Whole-frame transitions retain accumulated errors across strips.
            # Row groups: red->white, red->black, gray->white. All 256 levels.
            ramp = Image.new('RGB', (400, 600))
            ramp.putdata([(255, x * 255 // 399, x * 255 // 399) if y < 200 else
                          (x * 255 // 399, 0, 0) if y < 400 else
                          (x * 255 // 399,) * 3 for y in range(600) for x in range(400)])
            ramp_codes = render(ramp)
            assert all(c in (0, 1) for c in ramp_codes[400 * 400:]), 'gray pigment contamination'
            bins = []
            for x0 in range(0, 400, 25):
                counts = Counter(ramp_codes[y * 400 + x] for y in range(20, 180)
                                 for x in range(x0, x0 + 25))
                bins.append(round(counts[1] / 40, 3))
            assert all(a <= b + 2 for a, b in zip(bins, bins[1:])), 'large pink-ramp reversal'
            report['variants'][name] = {'patches': patches, 'red_to_white_white_percent': bins,
                                         'gray_contamination': False, 'deterministic': True,
                                         'frame_sha256': hashlib.sha256(codes).hexdigest(),
                                         'ramp_sha256': hashlib.sha256(ramp_codes).hexdigest()}
    assert report['variants']['primary_budget'] == report['variants']['primary_firmware'], 'firmware port differs'
    for patch in report['variants']['primary_firmware']['patches']:
        if patch['name'] in ('COLOR.PURPLE', 'COLOR.CYAN', 'MAGENTA', 'CYAN') or patch['name'].startswith('GRAY.'):
            assert patch['changed_pixels_vs_baseline'] == 0, f"protected chart sample changed: {patch['name']}"
    destination = ROOT / 'artifacts/color_calibration/white-budget-comparison.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    for name, result in report['variants'].items():
        print(name)
        for patch in result['patches']:
            if patch['name'] in ('RED', 'MAGENTA', 'CYAN', 'COLOR.PURPLE', 'COLOR.CYAN', 'GRAY.96'):
                print(patch['name'], patch['percent'])
        print('red-to-white white fraction:', result['red_to_white_white_percent'])
    print(destination)


if __name__ == '__main__':
    main()
