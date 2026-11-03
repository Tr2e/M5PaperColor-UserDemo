"""Refresh only the small-text subset, without original calendar image inputs.

Usage: python build_small_font.py /path/to/NotoSansCJKsc-Regular.otf
Requires fontTools; the source font remains outside the repository.
"""
import hashlib,json,sys
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

def main(source):
    assets=Path(__file__).resolve().parent/'assets'
    metadata=json.loads((assets/'font_sources.json').read_text())
    entry=next(f for f in metadata['fonts'] if f['file']=='TR2ESans-Regular.otf')
    needed=set(entry['codepoints'])
    catalog=json.loads((assets/'catalog.json').read_text())
    for record in catalog['records']:
        for field in ('author','foreign_name','source'):
            needed.update(map(ord,record[field]))
        needed.update(map(ord,''.join(record['roles'])))
    needed.update(map(ord,'、 ·《》'))
    font=TTFont(source);options=subset.Options()
    options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*']
    cutter=subset.Subsetter(options=options);cutter.populate(unicodes=needed);cutter.subset(font)
    names={1:'TR2E Sans',2:'Regular',3:'TR2E Sans Regular subset 2',4:'TR2E Sans Regular',6:'TR2ESans-Regular',16:'TR2E Sans',17:'Regular'}
    for record in font['name'].names:
        if record.nameID in names:record.string=names[record.nameID].encode(record.getEncoding(),errors='replace')
    top=font['CFF '].cff.topDictIndex[0];top.FamilyName='TR2E Sans';top.FullName='TR2E Sans Regular'
    font['CFF '].cff.fontNames=['TR2ESans-Regular']
    target=assets/entry['file'];font.save(target)
    entry.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bytes=target.stat().st_size,
                 covered_requested_characters=len(needed&set(font.getBestCmap())),requested_characters=len(needed),codepoints=sorted(font.getBestCmap()))
    (assets/'font_sources.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(f'{target.name}: {target.stat().st_size} bytes; {len(font.getBestCmap())} characters')

if __name__=='__main__':main(Path(sys.argv[1]))
