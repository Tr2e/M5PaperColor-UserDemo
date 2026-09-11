#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
from compare_native565 import FLAGS
ROOT=Path(__file__).resolve().parents[2]
def main():
 with tempfile.TemporaryDirectory(prefix='native565-tests-') as directory:
  for enabled in (False,True):
   for kind in ('papercolor_lut','native565'):
    files=['main/display/papercolor_lut.cpp','tools/color_lab/test_'+kind+'.cpp']
    if kind=='papercolor_lut':files.append('main/display/papercolor_photo_dither.cpp')
    binary=str(Path(directory)/(str(enabled)+kind))
    subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*['-DCONFIG_PAPERCOLOR_'+f+'=1' for f in FLAGS],'-DCONFIG_PAPERCOLOR_NATIVE_565_RECONSTRUCTION='+str(int(enabled)),'-Imain',*files,'-o',binary],cwd=ROOT,check=True)
    result=subprocess.run([binary,'artifacts/color_lut/nominal-5bit.lut'],cwd=ROOT,capture_output=True,text=True)
    if not enabled and kind=='native565':assert result.returncode!=0 and 'actual[c]==expected[c]' in result.stderr;print('baseline negative control detects incorrect native representative: pass',flush=True)
    else:
     assert result.returncode==0,result.stdout+result.stderr
     print(enabled,kind,result.stdout,flush=True)
if __name__=='__main__':main()
