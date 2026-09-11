#!/usr/bin/env python3
"""Sanitized baseline/candidate photo regressions and independent cyan invariants."""
from pathlib import Path
import subprocess
import tempfile
from compare_cyan_ratio import FLAGS
ROOT=Path(__file__).resolve().parents[2]
def main():
    with tempfile.TemporaryDirectory(prefix='papercolor-cyan-tests-') as directory:
        for enabled in (False,True):
            for kind in ('papercolor_lut','warm_targets','purple_smooth_targets','cyan_ratio_targets'):
                if not enabled and kind!='papercolor_lut':continue
                sources=['main/display/papercolor_lut.cpp','tools/color_lab/test_'+kind+'.cpp']
                if kind=='papercolor_lut':sources.append('main/display/papercolor_photo_dither.cpp')
                binary=str(Path(directory)/(str(enabled)+'-'+kind))
                subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    *['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],
                    '-DCONFIG_PAPERCOLOR_CYAN_RATIO_SMOOTH='+str(int(enabled)),
                    '-Imain',*sources,'-o',binary],cwd=ROOT,check=True)
                subprocess.run([binary,'artifacts/color_lut/nominal-5bit.lut'],cwd=ROOT,check=True)
                print('candidate' if enabled else 'baseline',kind,'pass',flush=True)
if __name__=='__main__':main()
