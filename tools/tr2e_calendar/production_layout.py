"""Device layout matching the approved 2027 A-signature preview.

Keep legacy renderer/preview inputs frozen. Pack generation and its reference
renderer use these shared metrics and the exact reviewed signature bitmap.
"""
import copy
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
import render as base

ROOT=Path(__file__).resolve().parent
SIGNATURE=ROOT.parents[1]/'artifacts/tr2e_signature_studies/A.png'
GAP=16
TITLE_GAP=20

def ink_bounds(lines,style,size,leading):
    mask=Image.new('L',(400,600),255);draw=ImageDraw.Draw(mask)
    for i,line in enumerate(lines):base.draw_text(draw,line,36,i*leading,style,size,[])
    return ImageChops.invert(mask.point(lambda p:255 if p>=170 else 0)).getbbox()

def layout(record):
    s=copy.deepcopy(base.layout(record))
    ink=ink_bounds(s['quote_lines'],'body',s['quote_size'],s['quote_leading'])
    s['quote_y']=s['footer_top']-GAP-ink[3]
    s['quote_ink_top']=s['quote_y']+ink[1]
    s['quote_ink_bottom']=s['quote_y']+ink[3]
    s['upper_line']=s['quote_ink_top']-16
    title=ink_bounds(s['title_lines'],'title',s['title_size'],38)
    s['title_y']=s['upper_line']-TITLE_GAP-title[3]
    s['title_ink_top']=s['title_y']+title[1]
    available=s['title_ink_top']-96
    s['digit_h']=min(184,round(available*.65),available-48)
    if s['digit_h']<72:raise ValueError(f'Insufficient date space: {record["id"]}')
    s['digit_y']=96+round((available-s['digit_h'])*.55)
    assert s['quote_ink_bottom']+GAP==s['footer_top']
    assert s['title_y']+title[3]+TITLE_GAP==s['upper_line']
    assert ''.join(s['quote_lines'])==record['excerpt'].replace('\n','')
    return s

def render(day,record,target):
    s=layout(record);im=Image.new('L',(400,600),255);draw=ImageDraw.Draw(im);audit=[]
    draw.line((20,38,379,38),fill=0)
    draw.rectangle((20,94,379,579),outline=0,width=2)
    draw.line((250,50,250,80),fill=0)
    md=f'{int(day["date"][5:7])}.{int(day["date"][8:]):02}'
    base.draw_text(draw,md,20,49,'title',31,audit)
    meta_x=20+base.width(md,'title',31)+10
    base.draw_text(draw,'星期'+'一二三四五六日'[day['weekday']],meta_x,50,'sans',14,audit)
    label=day['display_label']
    if label:
        assert meta_x+base.width(label,'sans',14)<250
        base.draw_text(draw,label,meta_x,70,'sans',14,audit)
    for text,y in ((day['date'][:4]+'年',50),(day['lunar_label'],70)):
        base.draw_text(draw,text,379-base.width(text,'sans',14),y,'sans',14,audit)
    digits=[]
    for char in str(int(day['date'][8:])):
        with Image.open(base.ASSETS/'digits'/f'{char}.png') as src:im_digit=src.convert('L')
        h=s['digit_h'];w=round(im_digit.width*h/im_digit.height)
        digits.append(im_digit.resize((w,h),Image.Resampling.LANCZOS))
    x=(400-sum(g.width for g in digits)-8*(len(digits)-1))//2
    for g in digits:im.paste(g,(x,s['digit_y']));x+=g.width+8
    for i,line in enumerate(s['title_lines']):
        base.draw_text(draw,line,(400-base.width(line,'title',s['title_size']))/2,s['title_y']+38*i,'title',s['title_size'],audit)
    draw.line((36,s['upper_line'],363,s['upper_line']),fill=0)
    for i,line in enumerate(s['quote_lines']):base.draw_text(draw,line,36,s['quote_y']+i*s['quote_leading'],'body',s['quote_size'],audit)
    draw.line((36,s['footer_top'],363,s['footer_top']),fill=0)
    y=s['footer_top']+9
    for line,size,style in s['footer']:base.draw_text(draw,line,36,y,style,size,audit);y+=size+4
    for item in audit:
        left,top,right,bottom=item['ink_bounds']
        assert 20<=left<=right<=380 and 39<=top<=bottom<=578,item
    im=im.point(lambda p:255 if p>=170 else 0)
    with Image.open(SIGNATURE) as patch:
        mark=patch.convert('L')
        # Glyphs contribute black ink only. An entry with a one-line author
        # footer can place its divider behind the bitmap's white top padding;
        # that padding must not erase the divider.
        im.paste(mark,(300,530),ImageChops.invert(mark))
    target=Path(target);im.convert('RGB').save(target)
    bits=bytes(v^255 for v in im.convert('1').tobytes())
    target.with_suffix('.bin').write_bytes(bits)
    return s
