"""Apply appearance changes to the frozen 2027 preview, never reselect content.

Run after build_preview.py to reproduce the current appearance:
    python tools/tr2e_calendar/editorial_v2/restyle_preview.py

The v1 renderer and device pack remain untouched. The content plan retains its
original hashes; appearance.json records this independent visual revision.
"""
import argparse
import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
import build_preview as b
import render as base

STYLE = 'bottom-aligned-seal-v1'
GAP = 16
SEAL = (316, 546, 364, 568)  # exclusive right/bottom; 48 x 22 px


def binary(im):
    return im.point(lambda p: 255 if p >= 170 else 0)


def render_page(day, record, path):
    spec = copy.deepcopy(base.layout(record))
    # Measure the actual rasterized glyphs, including punctuation and Latin
    # descenders, rather than equating line leading with visible text height.
    quote = Image.new('L', (400, 600), 255)
    qdraw = ImageDraw.Draw(quote)
    for i, line in enumerate(spec['quote_lines']):
        base.draw_text(qdraw, line, 36, i*spec['quote_leading'], 'body', spec['quote_size'], [])
    quote = binary(quote)
    ink = ImageChops.invert(quote).getbbox()
    spec['quote_y'] = spec['footer_top']-GAP-ink[3]
    spec['quote_ink_top'] = spec['quote_y']+ink[1]
    spec['quote_ink_bottom'] = spec['quote_y']+ink[3]
    spec['quote_bottom_gap_px'] = GAP
    spec['appearance'] = STYLE
    # The upper divider follows the paragraph with a stable visible top gap.
    upper_line = spec['quote_ink_top']-16
    assert upper_line > spec['title_y']+len(spec['title_lines'])*38+6

    im = Image.new('L', (400, 600), 255)
    draw = ImageDraw.Draw(im); audit = []
    draw.line((20, 38, 379, 38), fill=0)
    draw.rectangle((20, 94, 379, 579), outline=0, width=2)
    draw.line((250, 50, 250, 80), fill=0)
    md = f'{int(day["date"][5:7])}.{int(day["date"][8:]):02}'
    base.draw_text(draw, md, 20, 49, 'title', 31, audit)
    meta_x = 20+base.width(md, 'title', 31)+10
    base.draw_text(draw, '星期'+'一二三四五六日'[day['weekday']], meta_x, 50, 'sans', 14, audit)
    label = (day.get('solar_term') or '') if day.get('personal') else day.get('display_label') or day.get('solar_term') or ''
    if label:
        base.draw_text(draw, label, meta_x, 70, 'sans', 14, audit)
    for text, y in [(day['date'][:4]+'年', 50), (day['lunar_label'], 70)]:
        base.draw_text(draw, text, 379-base.width(text, 'sans', 14), y, 'sans', 14, audit)
    digits = []
    for char in str(int(day['date'][8:])):
        with Image.open(base.ASSETS/'digits'/f'{char}.png') as src:
            glyph = src.convert('L')
        h = spec['digit_h']; w = round(glyph.width*h/glyph.height)
        digits.append(glyph.resize((w, h), Image.Resampling.LANCZOS))
    x = (400-sum(g.width for g in digits)-8*(len(digits)-1))//2
    for glyph in digits:
        im.paste(glyph, (x, spec['digit_y'])); x += glyph.width+8
    for i, line in enumerate(spec['title_lines']):
        base.draw_text(draw, line, (400-base.width(line,'title',spec['title_size']))/2,
                       spec['title_y']+38*i, 'title', spec['title_size'], audit)
    draw.line((36, upper_line, 363, upper_line), fill=0)
    for i, line in enumerate(spec['quote_lines']):
        base.draw_text(draw, line, 36, spec['quote_y']+i*spec['quote_leading'],
                       'body', spec['quote_size'], audit)
    draw.line((36, spec['footer_top'], 363, spec['footer_top']), fill=0)
    y = spec['footer_top']+9
    footer_audit = []
    for line, size, face in spec['footer']:
        base.draw_text(draw, line, 36, y, face, size, footer_audit); y += size+4
    audit += footer_audit
    for text in audit:
        left, top, right, bottom = text['ink_bounds']
        assert 20 <= left <= right <= 380 and 39 <= top <= bottom <= 578
    for item in footer_audit:
        left, top, right, bottom = item['ink_bounds']
        assert right <= SEAL[0]-12 or bottom <= SEAL[1] or top >= SEAL[3]

    # Clean reversed serif lettering is legible at native e-paper resolution;
    # a small corner radius gives a seal silhouette without a bulky postmark.
    seal = Image.new('L', (48, 22), 255)
    sd = ImageDraw.Draw(seal)
    sd.rounded_rectangle((0, 0, 47, 21), radius=3, fill=0)
    font = base.font('title', 15)
    box = sd.textbbox((0, 0), 'Tr2e', font=font)
    pos = ((48-(box[2]-box[0]))//2-box[0], (22-(box[3]-box[1]))//2-box[1])
    sd.text(pos, 'Tr2e', font=font, fill=255)
    # White reversed strokes use midpoint threshold to keep one-pixel stems.
    seal = seal.point(lambda p:255 if p>=128 else 0)
    im = binary(im)
    im.paste(seal, SEAL[:2])
    actual_ink = ImageChops.invert(im.crop((36,upper_line+1,364,spec['footer_top']))).getbbox()
    actual_bottom = upper_line+1+actual_ink[3]
    assert spec['footer_top']-actual_bottom == GAP
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert('RGB').save(path)
    return dict(date=day['date'], record_id=record['id'], layout_mode=spec['mode'],
                quote_font_px=spec['quote_size'], quote_line_count=len(spec['quote_lines']),
                quote_ink_bottom=actual_bottom, footer_line_y=spec['footer_top'],
                quote_bottom_gap_px=GAP, upper_line_y=upper_line, seal_bounds=list(SEAL),
                image_sha256=b.digest(path), text_preserved=True, bounds_checked=True,
                author_footer_unchanged=True, appearance=STYLE)


def main(out, sample):
    plan_path = out/'2027.json'; plan_hash = b.digest(plan_path)
    plan = b.read(plan_path)
    catalog = {r['id']:r for r in b.read(b.CATALOG)['records']}
    before = b.protected_hashes()
    if sample:
        day = next(d for d in plan['days'] if d['date']==sample)
        print(json.dumps(render_page(day,catalog[day['record_id']],Path('/tmp/tr2e-signature-sample.png')),ensure_ascii=False))
        return
    audits = []
    # Render and verify the complete batch before replacing any visible page.
    with tempfile.TemporaryDirectory(prefix='tr2e-appearance-') as temp:
        for day in plan['days']:
            name = day['date']+'.png'; path = Path(temp)/name
            audit = render_page(day,catalog[day['record_id']],path)
            with Image.open(out/'days'/name) as old, Image.open(path) as new:
                # Header/date/title and the entire author/source footer retain
                # their exact pixels, apart from the explicitly changed seal.
                original_spec=base.layout(catalog[day['record_id']])
                title_end=original_spec['title_y']+len(original_spec['title_lines'])*38+1
                assert ImageChops.difference(old.crop((0,0,400,title_end)),new.crop((0,0,400,title_end))).getbbox() is None
                y = audit['footer_line_y']
                assert ImageChops.difference(old.crop((0,y,SEAL[0],600)),new.crop((0,y,SEAL[0],600))).getbbox() is None
            audits.append(audit)
        assert b.digest(plan_path)==plan_hash and before==b.protected_hashes()
        for day in plan['days']:
            name=day['date']+'.png'
            (out/'days'/name).write_bytes((Path(temp)/name).read_bytes())
    (out/'render_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2)+'\n')
    appearance = dict(version=STYLE, scope='仅样稿，固件未改', signature='Tr2e',
                      seal_size=[48,22],seal_corner_radius=3,seal_font='TR2ESerif-Bold.otf',seal_font_px=15,
                      quote_bottom_gap_px=GAP,verified_days=365,author_footer_pixels_unchanged=True,
                      selection_plan_sha256=plan_hash,protected_files_unchanged=True,
                      sources={str(p.relative_to(b.ROOT)):b.digest(p) for p in [Path(__file__),base.ASSETS/'TR2ESerif-Bold.otf']})
    (out/'appearance.json').write_text(json.dumps(appearance,ensure_ascii=False,indent=2)+'\n')
    page_path=out/'index.html'; page=page_path.read_text()
    match=re.search(r'(<script id="calendar-data" type="application/json">)(.*?)(</script>)',page,re.S)
    data=json.loads(match[2]);data['appearance']=appearance
    for card in data['cards']:
        card['image']=card['image'].split('?')[0]+'?appearance='+STYLE
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    page=page[:match.start(2)]+payload+page[match.end(2):]
    page=re.sub(r'<p id="appearance-note".*?</p>','',page)
    note='<p id="appearance-note" class="sub">签章版：右下角 Tr2e 黑底白字圆角印章；正文实际字形底部至下横线统一留白 16 px。作者行与全年选句保持原样。</p>'
    page=page.replace('<details class="method">',note+'<details class="method">')
    page_path.write_text(page)
    print(json.dumps(appearance,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=b.DEFAULT_OUT)
    parser.add_argument('--sample',help='Render a YYYY-MM-DD sample to /tmp without changing the gallery')
    args=parser.parse_args();main(args.output,args.sample)
