#!/usr/bin/env python3
"""Exercise the real display adapter with fake M5/ESP I/O and sanitizer checks."""
from pathlib import Path
import subprocess
import tempfile
# Keep this regression independent of uncommitted calibration experiments.
FLAGS = ["PRIMARY_WHITE_BUDGET"]

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='papercolor-home-tests-') as directory:
    tmp=Path(directory)
    # Embedded binary symbols as used by ESP-IDF, supplied from the real LUT.
    (tmp/'lut.S').write_text('.section __TEXT,__const\n.globl _binary_nominal_5bit_lut_start\n.globl _binary_nominal_5bit_lut_end\n_binary_nominal_5bit_lut_start:\n.incbin "'+str(ROOT/'artifacts/color_lut/nominal-5bit.lut')+'"\n_binary_nominal_5bit_lut_end:\n')
    binary=tmp/'test'
    subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-fno-omit-frame-pointer',
        *['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],
        '-DCONFIG_PAPERCOLOR_EXPERIMENTAL_LUT=1',
        '-Itools/color_lab/display_stubs','-Imain','main/display/papercolor_lut.cpp',
        'main/display/papercolor_photo_dither.cpp','main/display/papercolor_lut_display.cpp',
        'tools/color_lab/test_home_photo_pipeline.cpp',str(tmp/'lut.S'),'-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True)
