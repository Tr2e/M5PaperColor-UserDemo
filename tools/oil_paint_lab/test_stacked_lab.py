#!/usr/bin/env python3
"""Sanitized CLI and invariant tests for the host-only stacked brush renderer."""
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def main():
    project = Path(__file__).resolve().parents[2]
    cases = 0
    with tempfile.TemporaryDirectory(prefix='papercolor-lab-test-') as directory:
        directory = Path(directory)
        binary = directory / 'render'
        subprocess.run(['clang++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                        '-fno-omit-frame-pointer', '-I', str(project / 'main'),
                        str(project / 'main/display/papercolor_oil_painter.cpp'),
                        str(Path(__file__).with_name('render_stacked_ppm.cpp')), '-o', str(binary)], check=True)
        for size in [(1, 1), (1, 37), (37, 1), (2, 2), (7, 11), (267, 400), (600, 400), (400, 600), (600, 600)]:
            for color in [(0, 0, 0), (255, 255, 255), (99, 130, 181)]:
                before = Image.new('RGB', size, color)
                before.save(directory / 'input.ppm')
                outputs = []
                for name in ['out', 'repeat']:
                    result = subprocess.run([str(binary), str(directory / 'input.ppm'), str(directory / (name + '.ppm'))],
                                            check=True, capture_output=True, text=True)
                    for layer, radius, strokes, candidates, budget in re.findall(
                            r'layer=(\d+) radius=(\d+) strokes=(\d+) candidates=(\d+) budget=(\d+)', result.stderr):
                        assert int(radius) >= 1
                        assert int(strokes) <= min(int(candidates), int(budget))
                        if int(layer) >= 3:
                            assert int(budget) <= max(1, size[0] * size[1] // (85 if int(layer) == 3 else 110))
                    outputs.append((directory / (name + '.ppm')).read_bytes())
                assert outputs[0] == outputs[1]
                with Image.open(directory / 'out.ppm') as after:
                    assert after.size == size
                    # A flat field must stay flat, including black/white endpoints.
                    assert len(set(after.getdata())) == 1
                    assert max(abs(a-b) for a, b in zip(after.getpixel((0, 0)), color)) <= 7
                cases += 1
        # Structured, deterministic stress input includes high-frequency edges.
        for size in [(31, 29), (267, 400), (400, 600)]:
            before = Image.new('RGB', size)
            before.putdata([((x * 17 + y * 3) % 256, (x ^ y) % 256, 255 if x % 7 == 0 else 0)
                            for y in range(size[1]) for x in range(size[0])])
            before.save(directory / 'input.ppm')
            subprocess.run([str(binary), str(directory / 'input.ppm'), str(directory / 'out.ppm')], check=True, capture_output=True)
            with Image.open(directory / 'out.ppm') as after:
                assert after.size == size
            cases += 1
        for data in [b'', b'P3\n1 1\n255\n0 0 0', b'P6\n0 1\n255\n', b'P6\n-1 1\n255\n',
                     b'P6\n601 1\n255\n', b'P6\n1 601\n255\n', b'P6\n1 1\n256\nabc', b'P6\n1 1\n255\nx']:
            (directory / 'bad.ppm').write_bytes(data)
            result = subprocess.run([str(binary), str(directory / 'bad.ppm'), str(directory / 'rejected.ppm')], capture_output=True)
            assert result.returncode == 2
            assert not (directory / 'rejected.ppm').exists()
            cases += 1
    print(f'PASS: {cases} cases, ASan/UBSan, flat fields, dimensions, budgets, deterministic replays, malformed inputs')


if __name__ == '__main__':
    main()
