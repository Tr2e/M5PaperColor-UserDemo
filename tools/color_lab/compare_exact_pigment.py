#!/usr/bin/env python3
"""Full-fill and edge regression for IMG_9932; counts are not colorimetry."""
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
NAMES = {0: 'black', 1: 'white', 2: 'yellow', 3: 'red', 5: 'blue', 6: 'green'}
PEAK_FRAME_SHA = 'a8639c251613efe1ffd027a8fd04664c46e10626f83fe6918d4f466a316e3370'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    chart_path = ROOT / 'artifacts/color_calibration/papercolor-calibration-v1.png'
    chart = Image.open(chart_path).convert('RGB')
    spec = json.loads(chart_path.with_suffix('.json').read_text())
    pixels = list(chart.getdata())
    report = {'baseline': 'saved primary-peak-chart-candidate policy',
              'candidate': 'same target policy plus exact chromatic pigment anchor',
              'source_sha256': digest(chart_path.read_bytes()),
              'warning': 'Native output counts, not measured physical RGB or Delta-E.',
              'source_hashes': {p: digest((ROOT / p).read_bytes()) for p in (
                  'main/display/papercolor_photo_dither.cpp', 'main/display/papercolor_gamut.h',
                  'tools/color_lab/probe_frame.cpp', 'artifacts/color_lut/nominal-5bit.lut')},
              'patches': [], 'controls': {}, 'ramps': {}}
    with tempfile.TemporaryDirectory(prefix='papercolor-anchor-ab-') as tmp:
        binaries = []
        for enabled in (False, True):
            binary = str(Path(tmp) / ('anchor' if enabled else 'peak'))
            subprocess.run(['c++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                '-DCONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET=1',
                '-DCONFIG_PAPERCOLOR_PRIMARY_PEAK_PRESERVATION=1',
                '-DCONFIG_PAPERCOLOR_EXACT_PIGMENT_ANCHOR=' + str(int(enabled)),
                '-I' + str(ROOT / 'main'), str(ROOT / 'main/display/papercolor_photo_dither.cpp'),
                str(ROOT / 'main/display/papercolor_lut.cpp'),
                str(ROOT / 'tools/color_lab/probe_frame.cpp'), '-o', binary], check=True)
            binaries.append(binary)
        def render(image):
            result = []
            for binary in binaries:
                data = subprocess.run([binary, str(ROOT / 'artifacts/color_lut/nominal-5bit.lut')],
                    input=image.tobytes(), capture_output=True, check=True).stdout
                assert len(data) == 240000 and set(data) <= set(NAMES)
                result.append(data)
            return result
        before, after = render(chart)
        assert digest(before) == PEAK_FRAME_SHA, 'Off variant must reproduce the flashed candidate'
        assert render(chart) == [before, after], 'Determinism'
        report['frame_sha256'] = {'before': digest(before), 'after': digest(after)}
        report['changed_pixels'] = sum(a != b for a,b in zip(before,after))
        for patch in spec['patches']:
            x0,y0,x1,y1 = patch['rect_xyxy']
            # Include the first/last fill rows and columns; match source pixels
            # to exclude the outline. Black outline equals black fill by design.
            indices = [y*400+x for y in range(y0,y1) for x in range(x0,x1)
                       if pixels[y*400+x] == tuple(patch['rgb'])]
            row = {'id': patch['id'], 'name': patch['name'], 'source_rgb': patch['rgb'],
                   'fill_pixels': len(indices), 'changed_pixels': sum(before[i]!=after[i] for i in indices)}
            for name,frame in [('before',before),('after',after)]:
                counts = Counter(frame[i] for i in indices)
                row[name] = {NAMES[c]: counts[c] for c in NAMES}
            if patch['id'] == 19:
                dots = [[i%400,i//400] for i in indices if before[i] != 5]
                assert len(dots) == 12 and all(x == 205 for x,y in dots)
                assert all(after[i] == 5 for i in indices)
                row['before_foreign_dot_coordinates'] = dots
            if patch['id'] in (1,2,5,7,8):
                assert row['before'] == row['after']
            if patch['id'] >= 21:
                assert {after[i] for i in indices} <= {0,1}
            # Absorbing boundary residual may shift phase, but must not shift
            # a mixed patch's coverage materially (1 percentage point guard).
            assert max(abs(row['after'][n]-row['before'][n])/len(indices) for n in NAMES.values()) < .01
            report['patches'].append(row)
        controls = {'red':(255,0,0), 'green':(0,255,0), 'blue':(0,0,255),
                    'native_blue':(100,64,255), 'near_native_red':(191,0,0),
                    'near_native_green':(67,138,28), 'near_native_yellow':(255,243,56),
                    'magenta':(255,0,255), 'cyan':(0,255,255), 'pale_red':(255,160,160),
                    'gray96':(96,96,96)}
        for name,rgb in controls.items():
            a,b = render(Image.new('RGB',(400,600),rgb))
            assert a == b, name
            report['controls'][name] = {'identical': True, 'sha256':digest(a)}
        ramps = {'blue_black':((0,0,255),(0,0,0)), 'blue_white':((0,0,255),(255,255,255)),
                 'blue_cyan':((0,0,255),(0,255,255)), 'blue_magenta':((0,0,255),(255,0,255)),
                 'red_white':((255,0,0),(255,255,255)), 'neutral':((0,0,0),(255,255,255))}
        for name,(start,end) in ramps.items():
            image = Image.new('RGB',(400,600))
            image.putdata([tuple(round(a+(b-a)*x/399) for a,b in zip(start,end))
                           for y in range(600) for x in range(400)])
            a,b = render(image)
            max_delta = 0
            for x0 in range(0,400,25):
                ca,cb = (Counter(data[y*400+x] for y in range(32,568) for x in range(x0,x0+25)) for data in (a,b))
                max_delta = max(max_delta, max(abs(ca[c]-cb[c])/13400 for c in NAMES))
            assert max_delta < .01, name
            if name == 'neutral': assert a == b and set(b) <= {0,1}
            report['ramps'][name] = {'changed_pixels':sum(x!=y for x,y in zip(a,b)),
                                    'max_coverage_delta':max_delta}
    dest = ROOT / 'artifacts/color_calibration/exact-pigment-comparison.json'
    dest.write_text(json.dumps(report,indent=2)+'\n')
    for p in report['patches']:
        print(f"{p['id']:02} {p['name']}: {p['before']} -> {p['after']}; changed={p['changed_pixels']}")
    print(json.dumps(report['ramps'],indent=2))
    print(dest)

if __name__ == '__main__':
    main()
