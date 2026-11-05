"""Six small 1-bit, code-rendered signature studies. No calendar edits.

The HTML composes each new signature with the existing 400x600 layout, keeping
the full-year pages, selection plan, and firmware byte-for-byte unchanged.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops
import build_preview as b
import render as base

OUT=b.ROOT/'artifacts/tr2e_signature_studies'
VARIANTS=[
 ('A','书末署名','疏朗的衬线字，配一条短线。像书页末尾的私人落款。','最轻，接近日历本身的文字气质。'),
 ('B','细框藏书印','白底细框与日签边框呼应，留下清楚的归属标记。','适合想保留“盖章感”，又不希望太重。'),
 ('C','开放角标','只保留对角的两处边角，让字标与纸面之间有呼吸。','推荐：有辨识度，也能融入细线与留白。'),
 ('D','椭圆书印','纤细的椭圆围住署名，带一点旧书藏章的温和感。','轮廓柔和，比矩形更有手工印记的感觉。'),
 ('E','双行方印','将 Tr／2e 排成两行，收进小方框，像一枚简洁私印。','印章感最强，字标的存在感也更明确。'),
 ('F','轻邮戳','圆形邮戳配两道短波纹，像给这一页留下寄出的印记。','更有叙事趣味，装饰性也更明显。'),
]
DATES=['2027-01-09','2027-08-08','2027-12-30']


def centered(draw,text,size,cx,cy,bold=False,tracking=0):
    f=base.font('title' if bold else 'body',size)
    w=sum(f.getlength(c) for c in text)+tracking*(len(text)-1)
    box=f.getbbox(text)
    x=cx-w/2;y=cy-(box[3]-box[1])/2-box[1]
    for c in text:
        draw.text((round(x),round(y)),c,font=f,fill=0)
        x+=f.getlength(c)+tracking


def signature(code):
    # Patch occupies x=300..364, y=530..569, safely to the right of the
    # unchanged author/source column (whose maximum line width is 256 px).
    im=Image.new('L',(65,40),255);d=ImageDraw.Draw(im)
    if code=='A':
        centered(d,'Tr2e',15,42,25,tracking=.6)
        d.line((37,36,47,36),fill=0)
    elif code=='B':
        d.rectangle((11,15,63,37),outline=0,width=1)
        centered(d,'Tr2e',14,37,26,tracking=.4)
    elif code=='C':
        d.line([(18,23),(18,15),(27,15)],fill=0,width=1)
        d.line([(54,37),(63,37),(63,29)],fill=0,width=1)
        centered(d,'Tr2e',14,41,26,tracking=.3)
    elif code=='D':
        d.ellipse((8,10,63,37),outline=0,width=1)
        centered(d,'Tr2e',14,36,24,tracking=.3)
    elif code=='E':
        d.rectangle((28,2,63,37),outline=0,width=1)
        centered(d,'Tr',14,46,12,bold=True,tracking=1)
        centered(d,'2e',14,46,27,bold=True,tracking=1)
    elif code=='F':
        d.ellipse((28,2,63,37),outline=0,width=1)
        centered(d,'Tr2e',12,46,20)
        # Two small cancellation waves; keep a visible gap before the circle.
        for y in (15,23):
            d.line([(5,y),(9,y-2),(13,y-2),(18,y+2),(22,y+2),(25,y)],fill=0,width=1)
    else:
        raise ValueError(code)
    return im.point(lambda p:255 if p>=160 else 0).convert('RGB')


def main():
    OUT.mkdir(exist_ok=True)
    before={str(p):b.digest(p) for p in [b.DEFAULT_OUT/'2027.json',b.DEFAULT_OUT/'index.html',*sorted((b.DEFAULT_OUT/'days').glob('*.png'))]}
    rows=[]
    for code,name,desc,note in VARIANTS:
        im=signature(code);im.save(OUT/f'{code}.png')
        bounds=ImageChops.invert(im.convert('L')).getbbox()
        assert bounds and bounds[0]>=0 and bounds[2]<=65 and bounds[3]<=40
        rows.append(dict(code=code,name=name,description=desc,note=note,patch=f'{code}.png',ink_bounds=list(bounds)))
    data=dict(variants=rows,dates=DATES,source='../tr2e_calendar_2027_editorial_v2_1/days/',patch_box=[300,530,365,570])
    template=(Path(__file__).parent/'signature_studies.html').read_text()
    (OUT/'index.html').write_text(template.replace('__STUDIES__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')))
    assert before=={p:b.digest(Path(p)) for p in before}
    (OUT/'manifest.json').write_text(json.dumps(dict(**data,existing_calendar_unchanged=True,resolution=[400,600],signature='Tr2e'),ensure_ascii=False,indent=2)+'\n')
    print(OUT/'index.html')


if __name__=='__main__':main()
