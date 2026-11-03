"""Optional research/build inputs. Daily planning and rendering never call this."""
import argparse,hashlib,json,time,urllib.request
from pathlib import Path

FONTS={
    'NotoSerifCJKsc-Regular.otf':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf',
    'NotoSerifCJKsc-Bold.otf':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Bold.otf',
    'NotoSansCJKsc-Regular.otf':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
    'NotoSerif-OFL.txt':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/LICENSE',
    'NotoSans-OFL.txt':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE',
    'Tinos-Regular.ttf':'https://raw.githubusercontent.com/google/fonts/main/ofl/tinos/Tinos-Regular.ttf',
    'Tinos-OFL.txt':'https://raw.githubusercontent.com/googlefonts/tinos/main/OFL.txt',
}
DATES=sorted({*(f'2020-{m:02}-15' for m in range(1,13)),*(f'2020-04-{d:02}' for d in range(1,11)),*(f'2020-10-{d:02}' for d in range(18,24)),*['2020-01-01','2020-01-02','2020-01-31','2020-02-01','2020-02-29','2020-07-01','2020-07-02','2020-08-30','2020-12-31']})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,default=Path('/tmp/tr2e-calendar-study'));args=ap.parse_args()
    (args.cache/'fonts').mkdir(parents=True,exist_ok=True)
    items=[(args.cache/(date+'.img'),f'https://img.owspace.com/Public/uploads/Download/2020/{date[5:7]}{date[8:]}.jpg') for date in DATES]
    items += [(args.cache/'fonts'/name,url) for name,url in FONTS.items()]
    manifest=[]
    for path,url in items:
        if not path.exists():
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url,timeout=45) as response:data=response.read()
                    path.write_bytes(data);break
                except Exception:
                    if attempt==3:raise
                    time.sleep(attempt+1)
        manifest.append(dict(file=str(path.relative_to(args.cache)),url=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (args.cache/'reference_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(len(items),'cached build inputs')

if __name__=='__main__':main()
