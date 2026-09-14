#!/usr/bin/env python3
"""Validate the built photo filesystem and prepare an offline flash ZIP. Never flashes."""
import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build_dir', type=Path)
    parser.add_argument('--idf-path', type=Path, required=True)
    parser.add_argument('--idf-python', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    build = args.build_dir.resolve()
    config = (build / 'config/sdkconfig.h').read_text()
    for flag in ('PAPERCOLOR_OIL_PAINT', 'PAPERCOLOR_OIL_PAINT_STACKED'):
        if f'#define CONFIG_{flag} 1\n' not in config:
            raise RuntimeError('Missing accepted renderer flag: ' + flag)
    info = json.loads((build / 'flasher_args.json').read_text())
    for relative in ('main/display/papercolor_stacked_painter.cpp', 'main/display/papercolor_stacked_painter.h',
                     'main/display/papercolor_oil_painter.cpp', 'main/apps/photo_effects/photo_effect_controller.cpp',
                     'main/CMakeLists.txt', 'main/Kconfig.projbuild', 'CMakeLists.txt',
                     'tools/oil_paint_lab/oil-paint-sdkconfig.defaults'):
        if (project / relative).stat().st_mtime_ns > (build / 'paper_color.bin').stat().st_mtime_ns:
            raise RuntimeError('Build is older than source; rebuild first: ' + relative)
    if info['extra_esptool_args']['chip'] != 'esp32s3':
        raise RuntimeError('Wrong chip')
    if info['flash_files'].get('0xa00000') != 'storage.bin':
        raise RuntimeError('Photo filesystem absent or partition layout changed')
    photo_dir = project / 'main/apps/local_photo_slideshow/images'
    golden = json.loads((project / 'artifacts/oil_paint_optimized/results.json').read_text())
    for sample in golden['samples']:
        if digest(photo_dir / (str(sample['photo_id']) + '.jpg')) != sample['source_sha256']:
            raise RuntimeError('Bundled photo differs from accepted source: ' + sample['id'])
    # Parse the actual generated wear-levelled FAT image with ESP-IDF's tool.
    with tempfile.TemporaryDirectory(prefix='papercolor-fat-check-') as temporary:
        # Preserve the venv entry point; resolving its symlink bypasses its packages.
        subprocess.run([str(args.idf_python.absolute()), str(args.idf_path.resolve() / 'components/fatfs/fatfsparse.py'),
                        str(build / 'storage.bin'), '--wl-layer', 'enabled', '--long-name-support'],
                       cwd=temporary, check=True)
        extracted = {p.name.casefold(): p for p in Path(temporary).rglob('*') if p.is_file()}
        assets = []
        for path in sorted(photo_dir.iterdir()):
            if not path.is_file() or path.name.startswith('.'):
                continue
            actual = extracted.get(path.name.casefold())
            if actual is None or digest(actual) != digest(path):
                raise RuntimeError('FAT content missing/mismatched: ' + path.name)
            assets.append(dict(name=path.name, size=path.stat().st_size, sha256=digest(path)))
    files = []
    for offset, relative in info['flash_files'].items():
        source = (build / relative).resolve()
        source.relative_to(build)  # Reject unexpected external paths.
        files.append(dict(offset=offset, file=relative, size=source.stat().st_size, sha256=digest(source)))
    if (build / 'storage.bin').stat().st_size != 0x600000:
        raise RuntimeError('Unexpected FAT partition size')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
    changed = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=project, text=True).strip()
    manifest = dict(git_revision=revision, tracked_worktree_dirty=bool(changed), chip='esp32s3',
                    renderer_source_sha256=digest(project / 'main/display/papercolor_stacked_painter.cpp'),
                    sdkconfig_sha256=digest(build / 'sdkconfig'), flash_files=files, filesystem_assets=assets,
                    validation='Actual storage.bin extracted and all 13 photos plus SOURCES.TXT verified byte-for-byte',
                    device_tested=False, flashed=False)
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    (build / 'flash-bundle-manifest.json').write_text(text)
    readme = '''PaperColor stacked-brush firmware + validation photographs

PREPARATION ONLY: no physical-device test or flashing has been performed.
WARNING: full flashing overwrites the internal photo filesystem (0xA00000,
6 MiB). Back up the device's existing photos before flashing. NVS is not
included. Do not erase the whole flash. SD card files are not included.

Unzip into an empty directory. With the ESP-IDF 5.5 Python environment active,
replace PORT with the actual connected PaperColor serial port and run:

python -m esptool --chip esp32s3 -p PORT -b 460800 --before default_reset --after hard_reset write_flash @flash_args

This package was built with ESP-IDF 5.5.4 / esptool 4.12.0. Never run this command
against an unidentified device. For app-only updates that retain old photos,
use idf.py app-flash from the matching project/build directory instead.

Use internal storage (remove SD if its gallery is selected). Open a photo,
single-click the top button for local oil painting; click again to restore.
The nine new JPEG filenames correspond to the IDs in SOURCES.TXT; the existing
four built-in PNGs are preserved. Oil painting occurs on-device, not pre-baked.
See flash-bundle-manifest.json for offsets, exact bytes and checksums.
'''
    archive = build / 'papercolor-stacked-ready.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for item in files:
            package.write(build / item['file'], item['file'])
        package.write(build / 'flash_args', 'flash_args')
        package.write(build / 'flasher_args.json', 'flasher_args.json')
        package.writestr('flash-bundle-manifest.json', text)
        package.writestr('README.txt', readme)
        package.write(photo_dir / 'SOURCES.TXT', 'SOURCES.TXT')
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError('ZIP integrity failure')
    print('PASS: actual FAT image contains all 13 photos + attribution, exact source checksums')
    print(archive)
    print('SHA256:', digest(archive))


if __name__ == '__main__':
    main()
