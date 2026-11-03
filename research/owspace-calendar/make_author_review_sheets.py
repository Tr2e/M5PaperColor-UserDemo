"""Render temporary contact sheets of attribution crops for visual QA."""
import argparse,json,math,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent;TMP=Path('/tmp/owspace-author-audit')
p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=9999);args=p.parse_args()
items=json.loads((ROOT/'author_audit/scan.json').read_text())['candidates']
items=[r for r in items if r['reasons']!=['foreign_script_parser_review']]
font=ImageFont.truetype('/tmp/owspace-research/fonts/NotoSansCJKsc-Regular.otf',21)
small=ImageFont.truetype('/tmp/owspace-research/fonts/NotoSansCJKsc-Regular.otf',17)
out=TMP/'sheets';out.mkdir(exist_ok=True)
(TMP/'visual_items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2))
for start in range(args.start,min(args.end,len(items)),10):
    sheet=Image.new('RGB',(1700,1250),'#ffffff');draw=ImageDraw.Draw(sheet)
    for j,row in enumerate(items[start:start+10]):
        x=(j%2)*850;y=(j//2)*250
        draw.text((x+12,y+7),f"{start+j} | {row['date']} | {row.get('author') or '—'}",font=font,fill='black')
        old=row.get('author_foreign_name') or ''
        draw.text((x+12,y+38),old[:70],font=small,fill='#555555')
        meta=TMP/'ocr'/f"{row['date']}.json";image=TMP/'images'/f"{row['date']}.jpg"
        if not meta.exists() or not image.exists():continue
        d=json.loads(meta.read_text());im=Image.open(image).convert('RGB')
        crop=im.crop((0,int(im.height*d['top']),im.width,int(im.height*d['bottom'])))
        if crop.height==0:continue
        crop.thumbnail((820,170))
        # Enlarge small original footers enough to make individual glyphs readable.
        scale=min(820/crop.width,170/crop.height)
        crop=crop.resize((int(crop.width*scale),int(crop.height*scale)),Image.Resampling.LANCZOS)
        sheet.paste(crop,(x+12,y+70))
        draw.line((x,y+248,x+850,y+248),fill='#cccccc')
    name=out/f'authors-{start:04d}.png';sheet.save(name)
print('visual review items',len(items))
