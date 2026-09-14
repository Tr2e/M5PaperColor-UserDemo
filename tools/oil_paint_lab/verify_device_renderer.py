#!/usr/bin/env python3
"""Run the firmware core on all accepted RGB565 inputs and verify exact pixels."""
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
from validate_stacked_batch import sha

project = Path(__file__).resolve().parents[2]
golden = project / 'artifacts/oil_paint_optimized'
output = project / 'artifacts/oil_paint_device'
output.mkdir(parents=True, exist_ok=True)
records = []
with tempfile.TemporaryDirectory(prefix='papercolor-device-') as folder:
    folder = Path(folder)
    binary = folder / 'render'
    sources = [project / 'main/display/papercolor_oil_painter.cpp',
               project / 'main/display/papercolor_stacked_painter.cpp',
               Path(__file__).with_name('render_device_ppm.cpp')]
    command = ['clang++', '-std=c++17', '-O2', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(project / 'main'),
               *map(str, sources), '-o', str(binary)]
    subprocess.run(command, check=True)
    for sample in json.loads((golden / 'results.json').read_text())['samples']:
        with Image.open(golden / sample['id'] / 'before.png') as before:
            before.save(folder / 'input.ppm')
        results = []
        for run in range(2):
            result = subprocess.run([str(binary), str(folder / 'input.ppm'), str(folder / 'out.ppm')],
                                    capture_output=True, text=True, check=True)
            results.append((folder / 'out.ppm').read_bytes())
        assert results[0] == results[1], sample['id']
        with Image.open(folder / 'out.ppm') as after, Image.open(golden / sample['id'] / 'after.png') as expected:
            assert after.size == expected.size and after.tobytes() == expected.tobytes(), 'Pixels differ: ' + sample['id']
            after.save(output / (sample['id'] + '.png'))
        records.append(dict(id=sample['id'], exact_match=True, deterministic=True, sanitizer_runs=2, stats=result.stderr.splitlines()))
        print(sample['id'], 'exact match', result.stderr.strip().splitlines()[-1], flush=True)
    report = dict(command=command, device_source_sha256=sha(sources[1]),
                  golden_results_sha256=sha(golden / 'results.json'), samples=records,
                  scope='Host execution of firmware core; not physical device verification')
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: all 9 firmware-core outputs match accepted host pixels, twice, under ASan/UBSan')
