#!/usr/bin/env python3
"""Sanitized photo, RGB565 and home-adapter checks for deep-purple candidate."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FLAGS = [
    "PRIMARY_WHITE_BUDGET", "PRIMARY_PEAK_PRESERVATION", "EXACT_PIGMENT_ANCHOR",
    "BLUE_SECONDARY_BALANCE", "SECONDARY_WHITE_REDUCTION", "CHROMATIC_EDGE_GUARD",
    "WARM_COMPENSATION_BYPASS", "PURPLE_COMPENSATION_SMOOTH", "CYAN_RATIO_SMOOTH",
    "NATIVE_565_RECONSTRUCTION", "GREEN_PAIR_REFINEMENT",
    "DEEP_PURPLE_WHITE_REFINEMENT",
]


def main():
    defines = ["-DCONFIG_PAPERCOLOR_EXPERIMENTAL_LUT=1"] + [
        "-DCONFIG_PAPERCOLOR_" + flag + "=1" for flag in FLAGS]
    common = ["c++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
              "-fsanitize=address,undefined", "-fno-omit-frame-pointer", *defines]
    with tempfile.TemporaryDirectory(prefix="papercolor-deep-purple-tests-") as directory:
        temporary = Path(directory)
        photo = temporary / "photo"
        subprocess.run([
            *common, "-Imain", "main/display/papercolor_lut.cpp",
            "main/display/papercolor_photo_dither.cpp", "tools/color_lab/test_papercolor_lut.cpp",
            "-o", str(photo),
        ], cwd=ROOT, check=True)
        subprocess.run([str(photo), "artifacts/color_lut/nominal-5bit.lut"], cwd=ROOT, check=True)
        print("sanitized photo pipeline, both filters and RGB565 inputs: pass", flush=True)

        native = temporary / "native565"
        subprocess.run([
            *common, "-Imain", "main/display/papercolor_lut.cpp",
            "tools/color_lab/test_native565.cpp", "-o", str(native),
        ], cwd=ROOT, check=True)
        subprocess.run([str(native), "artifacts/color_lut/nominal-5bit.lut"], cwd=ROOT, check=True)
        print("sanitized native RGB565 reconstruction cells: pass", flush=True)

        assembly = temporary / "lut.S"
        assembly.write_text(
            '.section __TEXT,__const\n.globl _binary_nominal_5bit_lut_start\n'
            '.globl _binary_nominal_5bit_lut_end\n_binary_nominal_5bit_lut_start:\n'
            '.incbin "' + str(ROOT / "artifacts/color_lut/nominal-5bit.lut") + '"\n'
            '_binary_nominal_5bit_lut_end:\n')
        home = temporary / "home"
        subprocess.run([
            *common, "-Itools/color_lab/display_stubs", "-Imain",
            "main/display/papercolor_lut.cpp", "main/display/papercolor_photo_dither.cpp",
            "main/display/papercolor_lut_display.cpp",
            "tools/color_lab/test_home_photo_pipeline.cpp", str(assembly), "-o", str(home),
        ], cwd=ROOT, check=True)
        subprocess.run([str(home)], cwd=ROOT, check=True)
        print("sanitized real home display adapter: pass", flush=True)


if __name__ == "__main__":
    main()
