import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
TMP=Path('/tmp/owspace-author-audit');p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=9999);p.add_argument('--kind',default='foreign');a=p.parse_args()
rows=json.loads((TMP/f'{a.kind}_review.json').read_text());font=ImageFont.truetype('/tmp/owspace-research/fonts/NotoSansCJKsc-Regular.otf',19)
for start in range(a.start,min(a.end,len(rows)),20):
 im=Image.new('RGB',(1700,1800),'white');draw=ImageDraw.Draw(im)
 for j,r in enumerate(rows[start:start+20]):
  x=j%2*850;y=j//2*180
  draw.text((x+8,y+4),f"{start+j} {r['date']} {r['author']}",fill='black',font=font)
  draw.text((x+8,y+30),(r['author_foreign_name'] or '')[:72],fill='#666',font=font)
  o=json.loads((TMP/'ocr'/f"{r['date']}.json").read_text());src=Image.open(TMP/'images'/f"{r['date']}.jpg").convert('RGB')
  c=src.crop((0,int(src.height*o['top']),src.width,int(src.height*o['bottom'])));scale=min(830/c.width,115/c.height);c=c.resize((int(c.width*scale),int(c.height*scale)),Image.Resampling.LANCZOS);im.paste(c,(x+8,y+58));draw.line((x,y+179,x+850,y+179),fill='#ddd')
 im.save(TMP/'sheets'/f'{a.kind}-{start:04d}.png')
