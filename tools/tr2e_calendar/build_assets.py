"""Build small local fonts and the extracted 2020 numeric bitmap prototype.

Requires Pillow, NumPy and fontTools. Inputs are research downloads in --cache.
No full source calendar page is copied into the shipped assets.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
import numpy as np
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,default=Path('/tmp/tr2e-calendar-study'));args=ap.parse_args()
    assets=ROOT/'assets';assets.mkdir(exist_ok=True);(assets/'digits').mkdir(exist_ok=True)
    stats={'source_year':2020,'digit_source':'public calendar images; extracted for this local prototype','cell':[104,144],'ink_height_target':136,'bit_order':'MSB first; 1 means black','digits':[]}
    payload=bytearray();glyphs=[]
    for digit in range(10):
        day=digit if digit else 10;date=f'2020-04-{day:02}'
        path=args.cache/f'{date}.img';im=Image.open(path).convert('L');w,h=im.size
        left,top,right,bottom=int(w*.15),int(h*.23),int(w*.85),int(h*.51)
        crop=im.crop((left,top,right,bottom));ink=np.array(crop)<100
        columns=np.flatnonzero(ink.sum(axis=0)>1)
        runs=np.split(columns,np.where(np.diff(columns)>1)[0]+1)
        selected=runs[-1] if digit==0 else columns
        x0,x1=int(selected.min()),int(selected.max())+1
        crop=crop.crop((x0,0,x1,crop.height));box=ImageOps.invert(crop.point(lambda value:255 if value>=100 else 0)).getbbox()
        master=crop.crop(box);master.save(assets/'digits'/f'{digit}.png')
        height=136;width=round(master.width*height/master.height)
        scaled=master.resize((width,height),Image.Resampling.LANCZOS).point(lambda value:255 if value>=170 else 0).convert('1')
        cell=Image.new('1',(104,144),1);cell.paste(scaled,((104-width)//2,4));glyphs.append(cell)
        packed=np.packbits((np.array(cell)==0).astype(np.uint8),axis=1).tobytes();assert len(packed)==1872;payload.extend(packed)
        stats['digits'].append({'digit':str(digit),'source_date':date,'url':f'https://img.owspace.com/Public/uploads/Download/2020/04{day:02}.jpg','source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_bbox':[left+x0+box[0],top+box[1],left+x0+box[2],top+box[3]],'source_size':list(im.size),'ink_size':list(master.size),'bitmap_ink_width':width})
    (assets/'date_digits_136.bin').write_bytes(payload);stats['bytes']=len(payload)
    (assets/'date_digits.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    # Standard bitmap font, useful independently of any particular device driver.
    lines=['STARTFONT 2.1','FONT -TR2E-CalendarDate-Medium-R-Normal--144-1440-75-75-C-1040-ISO10646-1','SIZE 144 75 75','FONTBOUNDINGBOX 104 144 0 0','STARTPROPERTIES 2','FONT_ASCENT 144','FONT_DESCENT 0','ENDPROPERTIES','CHARS 10']
    for n,cell in enumerate(glyphs):
        lines.extend([f'STARTCHAR digit{n}',f'ENCODING {48+n}','SWIDTH 722 0','DWIDTH 104 0','BBX 104 144 0 0','BITMAP'])
        chunk=payload[n*1872:(n+1)*1872];lines.extend(chunk[y*13:(y+1)*13].hex().upper() for y in range(144));lines.append('ENDCHAR')
    lines.append('ENDFONT');(assets/'TR2E-CalendarDate-136.bdf').write_text('\n'.join(lines)+'\n')
    common=set('TR2E0123456789./— ·《》：年月日周一二三四五六七八九十农历闰初廿正腊冬春夏秋星期生日妻子儿子结婚纪念日内容摘录历史样稿新年岁末迎新元旦情人节妇女节读书劳动儿童国庆除夕春节元宵端午中秋重阳小寒大寒立春雨水惊蛰春分清明谷雨立夏小满芒种夏至小暑大暑立秋处暑白露秋分寒露霜降立冬小雪大雪冬至')
    common.update(chr(c) for c in range(32,127))
    common.update(json.loads((ROOT/'personal_rules.json').read_text()).get('signature','TR2E'))
    calendar_meta=json.loads((assets/'calendar.json').read_text())
    common.update(''.join(calendar_meta['months']+calendar_meta['days']+calendar_meta['terms']))
    chars=set(common);heading_chars=set(common)
    for p in (REPO/'research/owspace-calendar/months').glob('*.jsonl'):
        for row in map(json.loads,p.read_text().splitlines()):
            for key in ('title','excerpt','author','source','author_foreign_name'):chars.update(row.get(key) or '')
            heading_chars.update(row.get('title') or '')
            chars.update(''.join(row.get('author_roles',[])))
    chars.update(chr(c) for c in range(32,127))
    font_specs=[('NotoSerifCJKsc-Regular.otf','TR2ESerif-Regular.otf','TR2E Serif','Regular'),('NotoSerifCJKsc-Bold.otf','TR2ESerif-Bold.otf','TR2E Serif','Bold'),('NotoSansCJKsc-Regular.otf','TR2ESans-Regular.otf','TR2E Sans','Regular'),('Tinos-Regular.ttf','TR2ELatin-Regular.ttf','TR2E Latin','Regular')]
    font_meta=[]
    for src_name,dest_name,family,style in font_specs:
        src=args.cache/'fonts'/src_name
        if not src.exists() and src_name.startswith('NotoSans'):src=Path('/tmp/owspace-research/fonts')/src_name
        font=TTFont(src);options=subset.Options();options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*']
        needed={c for c in chars if ord(c)<0x3000} if 'Latin' in dest_name else common if 'Sans' in dest_name else heading_chars if style=='Bold' else chars
        sub=subset.Subsetter(options=options);sub.populate(text=''.join(sorted(needed)));sub.subset(font)
        # Subset fonts receive project-specific names; upstream licenses remain intact.
        for rec in font['name'].names:
            if rec.nameID in (1,2,3,4,6,16,17):
                value={1:family,2:style,3:family+' '+style+' subset 1',4:family+' '+style,6:family.replace(' ','')+'-'+style,16:family,17:style}[rec.nameID]
                rec.string=value.encode(rec.getEncoding(),errors='replace')
        if 'CFF ' in font:
            top=font['CFF '].cff.topDictIndex[0];top.FamilyName=family;top.FullName=family+' '+style;font['CFF '].cff.fontNames=[family.replace(' ','')+'-'+style]
        font.save(assets/dest_name)
        font_meta.append({'file':dest_name,'source_file':src_name,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'bytes':(assets/dest_name).stat().st_size,'covered_requested_characters':len(set(font.getBestCmap()) & {ord(x) for x in needed}),'requested_characters':len(needed),'codepoints':sorted(font.getBestCmap())})
    shutil.copyfile(args.cache/'fonts/NotoSerif-OFL.txt',assets/'NotoSerif-OFL.txt')
    shutil.copyfile(args.cache/'fonts/NotoSans-OFL.txt',assets/'NotoSans-OFL.txt')
    shutil.copyfile(args.cache/'fonts/Tinos-OFL.txt',assets/'Tinos-OFL.txt')
    for license_name in ('NotoSerif-OFL.txt','NotoSans-OFL.txt','Tinos-OFL.txt'):
        path=assets/license_name;path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    (assets/'font_sources.json').write_text(json.dumps({'fonts':font_meta,'serif_source':'https://github.com/notofonts/noto-cjk/tree/main/Serif/OTF/SimplifiedChinese','sans_source':'https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/SimplifiedChinese','latin_source':'https://github.com/googlefonts/tinos'},ensure_ascii=False,indent=2)+'\n')
    # A compact native-resolution proof of the ten usable glyphs.
    strip=Image.new('RGB',(560,355),'white');draw=ImageDraw.Draw(strip)
    font=ImageFont.truetype(str(assets/'TR2ESans-Regular.otf'),14)
    for n,cell in enumerate(glyphs):
        x=10+(n%5)*110;y=24+(n//5)*172;strip.paste(cell.convert('RGB'),(x,y));draw.text((x+47,y-20),str(n),font=font,fill='black')
    out=REPO/'research/owspace-calendar/typography_2020';out.mkdir(exist_ok=True)
    strip.save(out/'date-glyphs.png')
    if (args.cache/'all-font-scores.json').exists():
        scores=json.loads((args.cache/'all-font-scores.json').read_text())
        (out/'font_comparison.json').write_text(json.dumps({'method':'Thresholded ink IoU after independent ink-box width/height normalization; screening only, not font identification confidence. Variable-font endpoints additionally sampled.','faces_and_variants':len(scores),'scores':scores},ensure_ascii=False,indent=2)+'\n')
    print('digit payload',len(payload),'bytes; font subsets',sum(x['bytes'] for x in font_meta),'bytes')

if __name__=='__main__':main()
