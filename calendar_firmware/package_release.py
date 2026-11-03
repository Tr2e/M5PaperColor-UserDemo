"""Package the independently built app; never erases or flashes a device."""
import hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VERSION='0.1.1'

def main():
    files={
        'bootloader.bin':ROOT/'build/bootloader/bootloader.bin',
        'partition-table.bin':ROOT/'build/partition_table/partition-table.bin',
        'tr2e_calendar.bin':ROOT/'build/tr2e_calendar.bin',
        'README.md':ROOT/'README.md',
        'verification.json':ROOT/'tests/verification.json',
        'build-verification.json':ROOT/'tests/build-verification.json',
    }
    for name in ('NotoSans-OFL.txt','NotoSerif-OFL.txt','Tinos-OFL.txt'):
        files['licenses/'+name]=ROOT.parent/'tools/tr2e_calendar/assets'/name
    assert all(p.is_file() for p in files.values())
    # The pack must be exactly the one exercised by the portable tests.
    verification=json.loads(files['verification.json'].read_text())
    pack=(ROOT/'main/assets/calendar.pack').read_bytes()
    assert verification['pack_sha256']==hashlib.sha256(pack).hexdigest()
    assert pack in files['tr2e_calendar.bin'].read_bytes(),'Rebuild firmware after changing the embedded pack'
    flash='''#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: bash flash.sh /dev/cu.usbmodemXXXX" >&2; exit 1; fi
release_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
flash_python="${TR2E_PYTHON:-python3}"
exec "$flash_python" -m esptool --chip esp32s3 --port "$1" --baud 460800 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 "$release_dir/bootloader.bin" 0x8000 "$release_dir/partition-table.bin" 0x10000 "$release_dir/tr2e_calendar.bin"
'''
    manifest=dict(version=VERSION,target='M5Stack PaperColor ESP32-S3 / 400x600',offsets={'bootloader.bin':'0x0','partition-table.bin':'0x8000','tr2e_calendar.bin':'0x10000'},preserves_nvs=True,preserves_storage=True,physical_device_verified=False,
        files={name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in files.items()},
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'main').glob('*.cpp')})
    release=ROOT/'release';release.mkdir(exist_ok=True)
    path=release/f'tr2e-calendar-{VERSION}.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,p in files.items():archive.write(p,'tr2e-calendar-'+VERSION+'/'+name)
        archive.writestr('tr2e-calendar-'+VERSION+'/flash.sh',flash)
        archive.writestr('tr2e-calendar-'+VERSION+'/manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    manifest['package']=dict(file=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (release/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(path);print(manifest['package'])

if __name__=='__main__':main()
