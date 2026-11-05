"""Apply the chosen A wordmark without reflowing the frozen yearly pages.

This appearance-only step follows the existing page renderer. All pixels
outside the signature patch are checked before publishing the complete batch.
The selected bitmap comes from the reviewed design studies.
"""
import json
import re
import tempfile
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw
import build_preview as b

OUT=b.DEFAULT_OUT
STUDIES=b.ROOT/'artifacts/tr2e_signature_studies'
BOX=(300,530,365,570)
VARIANT='A'
NAME='书末署名'
VERSION='balanced-stack-signature-A-v1'


def main():
    before=b.protected_hashes()
    plan_hash=b.digest(OUT/'2027.json')
    audits=b.read(OUT/'render_audit.json')
    assert len(audits)==365
    with Image.open(STUDIES/f'{VARIANT}.png') as src:
        patch=src.convert('RGB')
    assert patch.size==(BOX[2]-BOX[0],BOX[3]-BOX[1])
    assert set(patch.convert('L').tobytes())<={0,255}
    old_hashes={a['date']:b.digest(OUT/'days'/(a['date']+'.png')) for a in audits}
    with tempfile.TemporaryDirectory(prefix='tr2e-signature-choice-') as tmp:
        for audit in audits:
            assert audit['quote_bottom_gap_px']==16 and audit['title_bottom_gap_px']==20
            assert audit['footer_line_y']<BOX[1]
            path=OUT/'days'/(audit['date']+'.png')
            with Image.open(path) as src:
                original=src.convert('RGB')
            im=original.copy();im.paste(patch,BOX[:2])
            diff=ImageChops.difference(im,original)
            ImageDraw.Draw(diff).rectangle((BOX[0],BOX[1],BOX[2]-1,BOX[3]-1),fill=0)
            assert diff.getbbox() is None
            assert ImageChops.difference(im.crop((0,0,300,600)),original.crop((0,0,300,600))).getbbox() is None
            im.save(Path(tmp)/path.name)
            audit.update(image_sha256=b.digest(Path(tmp)/path.name),appearance=VERSION,
                         signature_variant=VARIANT,signature_name=NAME,
                         signature_patch_bounds=list(BOX),signature_ink_bounds=[325,549,359,567],
                         outside_signature_pixels_unchanged=True)
            audit.pop('seal_bounds',None)
        assert before==b.protected_hashes() and plan_hash==b.digest(OUT/'2027.json')
        for audit in audits:
            path=OUT/'days'/(audit['date']+'.png')
            assert b.digest(path)==old_hashes[audit['date']]
            path.write_bytes((Path(tmp)/path.name).read_bytes())
    (OUT/'render_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2)+'\n')
    appearance=b.read(OUT/'appearance.json')
    appearance={k:v for k,v in appearance.items() if not k.startswith('seal_')}
    appearance.update(version=VERSION,signature_variant=VARIANT,signature_name=NAME,
                      signature_font='TR2ESerif-Regular.otf',signature_font_px=15,
                      signature_tracking_px=.6,signature_patch_bounds=list(BOX),
                      outside_signature_pixels_unchanged=True,verified_days=365)
    appearance['sources'][str(Path(__file__).relative_to(b.ROOT))]=b.digest(Path(__file__))
    appearance['sources'][str((STUDIES/'A.png').relative_to(b.ROOT))]=b.digest(STUDIES/'A.png')
    (OUT/'appearance.json').write_text(json.dumps(appearance,ensure_ascii=False,indent=2)+'\n')
    page_path=OUT/'index.html';page=page_path.read_text()
    match=re.search(r'(<script id="calendar-data" type="application/json">)(.*?)(</script>)',page,re.S)
    data=json.loads(match[2]);data['appearance']=appearance
    for card in data['cards']:
        card['image']=card['image'].split('?')[0]+'?appearance='+VERSION
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    page=page[:match.start(2)]+payload+page[match.end(2):]
    note='<p id="appearance-note" class="sub">已采用 A「书末署名」：Tr2e 字下短线。数字、标题、正文和作者行的位置保持原样；正文下边距 16 px、标题至上横线 20 px。仅更新样稿，固件未改。</p>'
    page=re.sub(r'<p id="appearance-note".*?</p>',note,page)
    page_path.write_text(page)
    assert before==b.protected_hashes() and plan_hash==b.digest(OUT/'2027.json')
    print(json.dumps(dict(days=365,variant=VARIANT,name=NAME,outside_signature_pixels_unchanged=True,
                          plan_unchanged=True,firmware_unchanged=True),ensure_ascii=False))


if __name__=='__main__':main()
