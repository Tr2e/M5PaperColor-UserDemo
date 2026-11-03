"""Offline 400 x 600 monochrome renderer. Requires Pillow, never network access.

PNG is RGB for the existing PaperColor PNG loader. The companion framebuffer is
1 bpp, row-major, MSB first, 1 = black (30,000 bytes, no header).
"""
import argparse,functools,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from calendar_data import Calendar
from planner import load_inputs

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets'
NO_START=set('，。！？；：、）》」』】”’…,.!?;:)]')
NO_END=set('（《「『【“‘([')
FILES={'body':'TR2ESerif-Regular.otf','title':'TR2ESerif-Bold.otf','sans':'TR2ESans-Regular.otf','latin':'TR2ELatin-Regular.ttf'}

@functools.lru_cache(None)
def coverage():
    return {r['file']:set(r['codepoints']) for r in json.loads((ASSETS/'font_sources.json').read_text())['fonts']}

@functools.lru_cache(None)
def font(style,size):return ImageFont.truetype(str(ASSETS/FILES[style]),size)

@functools.lru_cache(None)
def face(char,style,size):
    # The mathematical middle dot is rendered with the same centered dot shape;
    # original Unicode remains unchanged in the catalog and layout audit.
    glyph='·' if char=='⋅' else char
    for candidate in (style,'body','latin'):
        if ord(glyph) in coverage()[FILES[candidate]]:
            f=font(candidate,size);return glyph,f,f.getlength(glyph)
    raise ValueError(f'Missing glyph U+{ord(char):04X} {char!r}')

def width(text,style,size):return sum(face(c,style,size)[2] for c in text)

def wrap(text,style,size,max_width):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for char in paragraph:
            if line and width(line+char,style,size)>max_width:
                # Reserve room for closing punctuation instead of hanging it
                # outside the frame or starting a line with it.
                if char in NO_START or line[-1] in NO_END:
                    carry=line[-1];line=line[:-1]
                    lines.append(line);line=carry+char
                else:lines.append(line);line=char
            else:line+=char
        lines.append(line)
    return lines

def draw_text(draw,text,x,y,style,size,audit):
    x0=x;ink=[]
    for char in text:
        glyph,f,advance=face(char,style,size)
        # E-ink has an integer pixel grid; keep the host preview and the
        # firmware bitmap atlas aligned, including mixed Latin/CJK headings.
        pixel_x=int(x)
        box=draw.textbbox((pixel_x,y+size),glyph,font=f,anchor='ls')
        if not char.isspace():ink.append(box)
        draw.text((pixel_x,y+size),glyph,font=f,fill=0,anchor='ls');x+=advance
    bounds=[min(b[0] for b in ink),min(b[1] for b in ink),max(b[2] for b in ink),max(b[3] for b in ink)] if ink else [x0,y,x0,y]
    audit.append(dict(text=text,x=round(x0,2),y=y,width=round(x-x0,2),font_px=size,style=style,ink_bounds=bounds))

def layout(record):
    footer=[]
    identity=' · '.join(filter(None,['、'.join(record['roles']),record['author']]))
    for text,size in ((identity,13),(record['foreign_name'],11),('《'+record['source']+'》' if record['source'] else '',12)):
        if text:footer.extend((line,size) for line in wrap(text,'body',size,256))
    footer_height=sum(size+4 for _,size in footer)
    footer_top=568-footer_height-9
    title_size=30
    title_lines=wrap(record['title'],'title',title_size,324)
    # Preserve the 2020 whitespace when possible; move the body up for longer
    # excerpts. Text is neither truncated nor summarized to fit the screen.
    modes=[('standard',155,136,335,428,22,29),('balanced',139,124,301,378,21,28),
           ('long',128,124,280,348,19,25),('long-small',128,124,280,348,18,24),
           ('compact',122,106,250,312,18,24)]
    for name,digit_y,digit_h,title_y,quote_y,size,leading in modes:
        actual_quote_y=max(quote_y,title_y+len(title_lines)*38+24)
        lines=wrap(record['excerpt'],'body',size,328)
        if actual_quote_y+len(lines)*leading<=footer_top-12 and len(title_lines)<=2:
            return dict(mode=name,digit_y=digit_y,digit_h=digit_h,title_y=title_y,title_lines=title_lines,title_size=title_size,quote_y=actual_quote_y,quote_size=size,quote_leading=leading,quote_lines=lines,footer_top=footer_top,footer=footer)
    raise ValueError(f'Content does not fit without truncation: {record["id"]}')

def render(day,record,target,signature=None):
    rules=json.loads((ROOT/'personal_rules.json').read_text())
    signature=signature if signature is not None else rules.get('signature',rules['owner_id'])
    spec=layout(record);im=Image.new('L',(400,600),255);draw=ImageDraw.Draw(im);audit=[]
    draw.line((20,38,379,38),fill=0,width=1)
    draw.rectangle((20,94,379,579),outline=0,width=2)
    draw.line((250,50,250,80),fill=0,width=1)
    md=f'{int(day["date"][5:7])}.{int(day["date"][8:]):02}'
    draw_text(draw,md,20,49,'title',31,audit)
    draw_text(draw,'星期'+'一二三四五六日'[day['weekday']],112,50,'sans',13,audit)
    label=(day.get('solar_term') or '') if day.get('personal') else day.get('display_label',day.get('event_label')) or day.get('solar_term') or ''
    if label:draw_text(draw,label,112,70,'sans',13,audit)
    for text,y in ((day['date'][:4]+'年',50),(day['lunar_label'],70)):
        draw_text(draw,text,379-width(text,'sans',13),y,'sans',13,audit)
    digits=[]
    for char in str(int(day['date'][8:])):
        glyph=Image.open(ASSETS/'digits'/f'{char}.png').convert('L')
        h=spec['digit_h'];w=round(glyph.width*h/glyph.height)
        digits.append(glyph.resize((w,h),Image.Resampling.LANCZOS))
    total=sum(g.width for g in digits)+8*(len(digits)-1);x=(400-total)//2
    for glyph in digits:im.paste(glyph,(x,spec['digit_y']));x+=glyph.width+8
    for i,line in enumerate(spec['title_lines']):
        draw_text(draw,line,(400-width(line,'title',spec['title_size']))/2,spec['title_y']+38*i,'title',spec['title_size'],audit)
    draw.line((36,spec['quote_y']-15,363,spec['quote_y']-15),fill=0,width=1)
    for i,line in enumerate(spec['quote_lines']):draw_text(draw,line,36,spec['quote_y']+i*spec['quote_leading'],'body',spec['quote_size'],audit)
    draw.line((36,spec['footer_top'],363,spec['footer_top']),fill=0,width=1)
    y=spec['footer_top']+9
    for line,size in spec['footer']:draw_text(draw,line,36,y,'body',size,audit);y+=size+4
    draw_text(draw,signature,364-width(signature,'body',14),552,'body',14,audit)
    for item in audit:
        left,top,right,bottom=item['ink_bounds']
        if left<20 or right>380 or top<39 or bottom>578:raise ValueError(f'Text bounds failure: {item}')
    binary=im.point(lambda p:255 if p>=170 else 0).convert('1')
    target.parent.mkdir(parents=True,exist_ok=True);binary.convert('RGB').save(target)
    payload=bytes(b^255 for b in binary.tobytes());assert len(payload)==30000
    target.with_suffix('.bin').write_bytes(payload)
    result=dict(display_date=day['date'],source_date=record['source_date'],record_id=record['id'],event_label=label,owner_id=rules['owner_id'],signature=signature,resolution=[400,600],layout=spec,text=audit,framebuffer_bytes=len(payload),original_text_preserved=True)
    target.with_suffix('.layout.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path);ap.add_argument('--date',required=True);ap.add_argument('--historical',action='store_true');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    catalog,rules,_=load_inputs();by_id={r['id']:r for r in catalog['records']}
    if args.historical:day=Calendar().day(args.date);record=by_id[args.date]
    else:
        if not args.plan:ap.error('--plan is required unless --historical')
        plan=json.loads(args.plan.read_text());day=next(d for d in plan['days'] if d['date']==args.date);record=by_id[day['record_id']]
    print(json.dumps(render(day,record,args.output)['layout'],ensure_ascii=False))

if __name__=='__main__':main()
