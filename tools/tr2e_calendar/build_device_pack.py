"""Compile editorial rules and glyphs into one immutable, offline firmware pack.

No full-page images, network, external fonts or yearly download on the device.
2026 and 2027 are pinned to approved plans; later years use editorial v3 history.
"""
import argparse,datetime as dt,hashlib,json,struct,zlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
from planner import load_inputs
from production_planner import plan_year,input_key,FROZEN
from production_layout import layout,SIGNATURE
from render import face,width,draw_text,ASSETS
from calendar_data import Calendar

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
OUT=REPO/'calendar_firmware/main/assets'

def build(first=2026,last=2099,cache=None):
    catalog,rules,_=load_inputs()
    key=input_key()
    if cache:cache.mkdir(parents=True,exist_ok=True)
    history=[];overlap=[]
    for year in range(first,last+1):
        p=cache/f'{key}-{year}.json' if cache else None
        if year in FROZEN:plan=json.loads(FROZEN[year].read_text())
        elif p and p.exists():plan=json.loads(p.read_text())
        else:
            plan=plan_year(year,history)
            if p:p.write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':')))
        groups={d['content_group'] for d in plan['days']};titles={d['title_key'] for d in plan['days']}
        expected=(dt.date(year+1,1,1)-dt.date(year,1,1)).days
        assert len(groups)==len(titles)==len(plan['days'])==expected,year
        if history:
            previous={d['content_group'] for d in history[-1]['days']};common=groups&previous
            assert len(common)/expected<=.05,(year,len(common),'adjacent-year repeat budget exceeded')
            overlap.append(dict(year=year,repeated_from_previous=len(common),days=expected))
        history.append(plan)
        print(f'planned {year}: {len(groups)} unique, adjacent overlap {overlap[-1]["repeated_from_previous"] if overlap else 0}',flush=True)

    selected={d['record_id'] for plan in history for d in plan['days']}
    records=[r for r in catalog['records'] if r['id'] in selected];ids={r['id']:i for i,r in enumerate(records)}
    specs={r['id']:layout(r) for r in records};heights=sorted({s['digit_h'] for s in specs.values()})
    glyphs=[];glyph_index={}
    def glyph(char,style,size):
        ch,f,advance=face(char,style,size);key=(str(f.path),size,ch)
        if key not in glyph_index:
            left,top,right,bottom=f.getbbox(ch,anchor='ls');w=max(1,right-left);h=max(1,bottom-top)
            im=Image.new('L',(w,h),255);ImageDraw.Draw(im).text((-left,-top),ch,font=f,anchor='ls',fill=0)
            bits=im.point(lambda v:255 if v>=170 else 0).convert('1')
            glyph_index[key]=len(glyphs);glyphs.append((w,h,left,top,round(advance*64),bytes(b^255 for b in bits.tobytes())))
        return glyph_index[key]

    def line(text,x,y,style,size):
        codes=[glyph(c,style,size) for c in text]
        # Pillow accumulates antialias coverage when adjacent Latin glyphs
        # touch. Independent 1-bit glyphs can miss 1-2 black pixels (notably in
        # author credits). Store only those sparse additions as a zero-advance
        # glyph, keeping the exact approved line and all positions unchanged.
        reference=Image.new('L',(400,96),255)
        draw_text(ImageDraw.Draw(reference),text,x,48-size,style,size,[])
        expected=ImageChops.invert(reference.point(lambda v:255 if v>=170 else 0))
        composed=Image.new('L',(400,96),0);pen=int(x*64)
        for code in codes:
            w,h,left,top,advance,bits=glyphs[code]
            mask=Image.frombytes('1',(w,h),bits).convert('L')
            composed.paste(255,((pen>>6)+left,48+top),mask);pen+=advance
        assert ImageChops.subtract(composed,expected).getbbox() is None,(text,x,'unexpected extra ink')
        missing=ImageChops.subtract(expected,composed);box=missing.getbbox()
        if box:
            patch=missing.crop(box).convert('1');w,h=patch.size
            item=(w,h,box[0]-(pen>>6),box[1]-48,0,patch.tobytes())
            correction=('line-coverage',item)
            if correction not in glyph_index:
                glyph_index[correction]=len(glyphs);glyphs.append(item)
            codes.append(glyph_index[correction])
        assert len(codes)<256
        return struct.pack('<hhBB',int(x*64),y,size,len(codes))+struct.pack('<'+'H'*len(codes),*codes)

    with Image.open(SIGNATURE) as source:signature=source.convert('1')
    signature_id=len(glyphs)
    glyphs.append((signature.width,signature.height,0,0,signature.width*64,bytes(v^255 for v in signature.tobytes())))
    bodies=[]
    for r in records:
        s=specs[r['id']];lines=[]
        for i,text in enumerate(s['title_lines']):lines.append(line(text,(400-width(text,'title',s['title_size']))/2,s['title_y']+38*i,'title',s['title_size']))
        for i,text in enumerate(s['quote_lines']):lines.append(line(text,36,s['quote_y']+i*s['quote_leading'],'body',s['quote_size']))
        y=s['footer_top']+9
        for text,size,style in s['footer']:lines.append(line(text,36,y,style,size));y+=size+4
        # The approved A design is a single exact 1-bit glyph: lettering plus
        # its short underline; no firmware font approximation or author reflow.
        lines.append(struct.pack('<hhBBH',300*64,530,0,1,signature_id))
        bodies.append(struct.pack('<IHHHHH',dt.date.fromisoformat(r['source_date']).toordinal(),s['digit_y'],heights.index(s['digit_h']),s['upper_line'],s['footer_top'],len(lines))+b''.join(lines))
    cal=Calendar();labels=sorted({d['display_label'] for p in history for d in p['days']})
    texts=[(c,'title',31) for c in '0123456789.']+[(c,'sans',14) for c in '0123456789年']
    texts += [('星期'+c,'sans',14) for c in '一二三四五六日']
    texts += [(s,'sans',14) for s in cal.meta['months']+cal.meta['days']+['闰']+labels]
    strings=[]
    for text,style,size in texts:
        codes=[glyph(c,style,size) for c in text];strings.append(struct.pack('<H',len(codes))+struct.pack('<'+'H'*len(codes),*codes))
    big=[]
    for height in heights:
        for n in range(10):
            im=Image.open(ASSETS/'digits'/f'{n}.png').convert('L');w=round(im.width*height/im.height)
            bits=im.resize((w,height),Image.Resampling.LANCZOS).point(lambda v:255 if v>=170 else 0).convert('1')
            big.append(len(glyphs));glyphs.append((w,height,0,0,w*64,bytes(b^255 for b in bits.tobytes())))
    assert len(glyphs)<65535 and len(records)<65535
    blob=bytearray(72)
    def add(data):offset=len(blob);blob.extend(data);return offset
    glyph_table=add(bytes(16*len(glyphs)))
    for i,(w,h,left,top,advance,bits) in enumerate(glyphs):
        offset=add(bits);struct.pack_into('<IHHhhHH',blob,glyph_table+i*16,offset,w,h,left,top,advance,0)
    def table(items):
        offset=add(bytes(4*(len(items)+1)))
        for i,data in enumerate(items):struct.pack_into('<I',blob,offset+4*i,add(data))
        struct.pack_into('<I',blob,offset+4*len(items),len(blob));return offset
    record_table=table(bodies);text_table=table(strings);big_table=add(struct.pack('<'+'H'*len(big),*big))
    days=[]
    for plan in history:
        for d in plan['days']:
            lunar=d['lunar_month']|(d['lunar_day']<<4)|(int(d['leap_month'])<<9)
            days.append(struct.pack('<HHH',ids[d['record_id']],lunar,72+labels.index(d['display_label'])))
    day_table=add(b''.join(days))
    struct.pack_into('<8s16I',blob,0,b'TR2EPK03',len(blob),0,dt.date(first,1,1).toordinal(),len(days),len(glyphs),len(records),glyph_table,record_table,day_table,text_table,len(strings),big_table,first,last,3,len(heights))
    struct.pack_into('<I',blob,12,zlib.crc32(blob))
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'calendar.pack').write_bytes(blob)
    summary=dict(schema=3,first_year=first,last_year=last,days=len(days),records=len(records),glyphs=len(glyphs),bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),planner_input=key,signature=rules['signature'],signature_variant='A',signature_sha256=hashlib.sha256(SIGNATURE.read_bytes()).hexdigest(),digit_heights=heights,labels=labels,frozen_plans={str(y):hashlib.sha256(p.read_bytes()).hexdigest() for y,p in FROZEN.items()},quote_bottom_gap_px=16,title_to_divider_gap_px=20,ordinary_group_cooldown_years=5,ordinary_title_cooldown_years=2,max_adjacent_overlap=max((x['repeated_from_previous'] for x in overlap),default=0),overlap=overlap,record_ids=[r['id'] for r in records],note='Editorial v3: 2026 and 2027 frozen; later years use phased calendar context, reviewed pair metadata and explicitly identified legacy tags. Special-date pools rotate; adjacent years at least 95% distinct. Runtime is an offline date lookup for 2026-2099.')
    (OUT/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(f'pack: {len(blob):,} bytes; {len(glyphs)} glyphs',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--last-year',type=int,default=2099);ap.add_argument('--cache',type=Path,default=Path('/tmp/tr2e-device-plans'));args=ap.parse_args();build(last=args.last_year,cache=args.cache)
