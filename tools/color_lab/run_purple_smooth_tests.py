#!/usr/bin/env python3
"""Sanitized legacy/candidate regressions, including a legacy negative control."""
from pathlib import Path
import subprocess
import tempfile

from compare_purple_smooth import FLAGS

ROOT = Path(__file__).resolve().parents[2]

def main():
    flags = ['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS]
    with tempfile.TemporaryDirectory(prefix='papercolor-purple-tests-') as directory:
        for name, extra in [('legacy', []), ('smooth', ['-DCONFIG_PAPERCOLOR_PURPLE_COMPENSATION_SMOOTH=1'])]:
            for kind in ['papercolor_lut', 'warm_targets', 'purple_smooth_targets']:
                if name == 'legacy' and kind == 'warm_targets':
                    continue
                binary = str(Path(directory)/(name+'-'+kind))
                sources = ['main/display/papercolor_lut.cpp', 'tools/color_lab/test_'+kind+'.cpp']
                if kind == 'papercolor_lut':
                    sources.append('main/display/papercolor_photo_dither.cpp')
                subprocess.run(['c++', '-std=c++17', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                                *flags, *extra, '-Imain', *sources, '-o', binary], cwd=ROOT, check=True)
                result = subprocess.run([binary, 'artifacts/color_lut/nominal-5bit.lut'],
                                        cwd=ROOT, capture_output=True, text=True)
                negative = name == 'legacy' and kind == 'purple_smooth_targets'
                if negative:
                    assert result.returncode != 0 and 'squared<96*96' in result.stderr, result.stderr
                    print('legacy negative control detects original threshold jump: pass', flush=True)
                else:
                    assert result.returncode == 0, result.stdout+result.stderr
                    print(name, kind, result.stdout, flush=True)

if __name__ == '__main__':
    main()
