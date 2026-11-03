"""Compile editorial rules and glyphs into one immutable, offline firmware pack.

No full-page images, network, external fonts or yearly download on the device.
2026 is pinned to the approved plan; subsequent years use rolling history.
"""
import argparse,datetime as dt,hashlib,json,struct,zlib
from pathlib import Path
from PIL import Image,ImageDraw
from planner import load_inputs,plan_year
from render import layout,face,width,ASSETS
from calendar_data import Calendar

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
OUT=REPO/'calendar_firmware/main/assets'
HEIGHTS=[136,124,112,106]

def build(first=2026,last=2099,cache=None):
    catalog,rules,_=load_inputs();records=[r for r in catalog['records'] if r['eligible']];ids={r['id']:i for i,r in enumerate(records)}
    key=hashlib.sha256((ROOT/'planner.py').read_bytes()+(ROOT/'personal_rules.json').read_bytes()+(ASSETS/'catalog.json').read_bytes()).hexdigest()
    if cache:cache.mkdir(parents=True,exist_ok=True)
    history=[];overlap=[]
    for year in range(first,last+1):
        p=cache/f'{key}-{year}.json' if cache else None
        if year==2026:plan=json.loads((REPO/'artifacts/tr2e_calendar_400x600/2026.json').read_text())
        elif p and p.exists():plan=json.loads(p.read_text())
        else:
            plan=plan_year(year,catalog,rules,history)
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
        codes=[glyph(c,style,size) for c in text];assert len(codes)<256
        return struct.pack('<hhBB',round(x*64),y,size,len(codes))+struct.pack('<'+'H'*len(codes),*codes)

    bodies=[]
    for r in records:
        s=layout(r);lines=[]
        for i,text in enumerate(s['title_lines']):lines.append(line(text,(400-width(text,'title',s['title_size']))/2,s['title_y']+38*i,'title',s['title_size']))
        for i,text in enumerate(s['quote_lines']):lines.append(line(text,36,s['quote_y']+i*s['quote_leading'],'body',s['quote_size']))
        y=s['footer_top']+9
        for text,size,style in s['footer']:lines.append(line(text,36,y,style,size));y+=size+4
        signature=rules['signature'];lines.append(line(signature,364-width(signature,'body',14),552,'body',14))
        bodies.append(struct.pack('<IHHHHH',dt.date.fromisoformat(r['source_date']).toordinal(),s['digit_y'],HEIGHTS.index(s['digit_h']),s['quote_y']-15,s['footer_top'],len(lines))+b''.join(lines))
    cal=Calendar();labels=sorted({d['display_label'] for p in history for d in p['days']})
    texts=[(c,'title',31) for c in '0123456789.']+[(c,'sans',14) for c in '0123456789年']
    texts += [('星期'+c,'sans',14) for c in '一二三四五六日']
    texts += [(s,'sans',14) for s in cal.meta['months']+cal.meta['days']+['闰']+labels]
    strings=[]
    for text,style,size in texts:
        codes=[glyph(c,style,size) for c in text];strings.append(struct.pack('<H',len(codes))+struct.pack('<'+'H'*len(codes),*codes))
    big=[]
    for height in HEIGHTS:
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
    record_table=table(bodies);text_table=table(strings);big_table=add(struct.pack('<40H',*big))
    days=[]
    for plan in history:
        for d in plan['days']:
            lunar=d['lunar_month']|(d['lunar_day']<<4)|(int(d['leap_month'])<<9)
            days.append(struct.pack('<HHH',ids[d['record_id']],lunar,72+labels.index(d['display_label'])))
    day_table=add(b''.join(days))
    struct.pack_into('<8s16I',blob,0,b'TR2EPK02',len(blob),0,dt.date(first,1,1).toordinal(),len(days),len(glyphs),len(records),glyph_table,record_table,day_table,text_table,len(strings),big_table,first,last,2,0)
    struct.pack_into('<I',blob,12,zlib.crc32(blob))
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'calendar.pack').write_bytes(blob)
    summary=dict(schema=2,first_year=first,last_year=last,days=len(days),records=len(records),glyphs=len(glyphs),bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),planner_input=key,signature=rules['signature'],ordinary_group_cooldown_years=5,ordinary_title_cooldown_years=2,max_adjacent_overlap=max(x['repeated_from_previous'] for x in overlap),overlap=overlap,record_ids=[r['id'] for r in records],note='Immutable compiled annual assignments; same civil date always selects the same source. Special-date pools may repeat across years; each adjacent pair must be at least 95% distinct. Calendar range limited to RX8130 years 2026-2099.')
    (OUT/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(f'pack: {len(blob):,} bytes; {len(glyphs)} glyphs',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--last-year',type=int,default=2099);ap.add_argument('--cache',type=Path,default=Path('/tmp/tr2e-device-plans'));args=ap.parse_args();build(last=args.last_year,cache=args.cache)
