#!/usr/bin/env python3
"""Host CLI timing only; never extrapolate these milliseconds to ESP32-S3."""
import argparse
import json
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image
from run_edge_study import LAB, PROJECT, VARIANTS, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('runs', type=Path, nargs='+', help='Completed run directories containing results.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; preserve previous measurement')
    prototype = LAB / 'render_edge_study_ppm.cpp'
    entries = []
    for run in args.runs:
        metadata = json.loads((run / 'results.json').read_text())
        if metadata['prototype_sha256'] != sha(prototype):
            parser.error('run does not match current prototype')
        entries.extend((run, s) for s in metadata['samples'])
    commands, records = {}, []
    with tempfile.TemporaryDirectory(prefix='papercolor-edge-bench-') as directory:
        work = Path(directory)
        for name, (background, soft) in VARIANTS.items():
            commands[name] = ['clang++', '-std=c++17', '-O2', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror',
                              '-I', str(PROJECT / 'main'), str(PROJECT / 'main/display/papercolor_oil_painter.cpp'),
                              str(prototype), '-DPAINT_BACKGROUND_CONTROL=' + str(background),
                              '-DPAINT_SOFT_EDGES=' + str(soft), '-o', str(work / name)]
            subprocess.run(commands[name], check=True)
        for run, sample in entries:
            folder = run / sample['id']
            with Image.open(folder / 'before.png') as before:
                before.save(work / 'input.ppm')
            expected = {}
            for name in VARIANTS:
                with Image.open(folder / (name + '.png')) as picture:
                    expected[name] = (picture.size, picture.convert('RGB').tobytes())
            times = {name: [] for name in VARIANTS}
            for iteration in range(4):
                names = list(VARIANTS)
                names = names[iteration:] + names[:iteration]
                for name in names:
                    start = time.perf_counter()
                    subprocess.run([str(work / name), str(work / 'input.ppm'), str(work / 'output.ppm')],
                                   check=True, capture_output=True)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    with Image.open(work / 'output.ppm') as picture:
                        if (picture.size, picture.convert('RGB').tobytes()) != expected[name]:
                            raise RuntimeError('release/sanitized pixels differ')
                    if iteration:
                        times[name].append(elapsed_ms)
            medians = {name: statistics.median(values) for name, values in times.items()}
            records.append(dict(id=sample['id'], measured_ms=times, median_ms=medians,
                                combined_vs_accepted=medians['combined'] / medians['accepted'],
                                release_matches_sanitized=True))
            print(sample['id'], {n: round(t, 1) for n, t in medians.items()}, flush=True)
    result = dict(platform=platform.platform(), machine=platform.machine(), commands=commands,
                  prototype_sha256=sha(prototype), harness_sha256=sha(Path(__file__)),
                  input_runs={str(run): sha(run / 'results.json') for run in args.runs}, samples=records,
                  method='1 discarded warm-up + 3 interleaved CLI wall times per image/variant; includes process and PPM I/O. '
                         'No sanitizers in timed binaries. Every render checked against sanitized golden pixels. '
                         'Host diagnostics only, not ESP32 performance, power, or latency predictions.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
