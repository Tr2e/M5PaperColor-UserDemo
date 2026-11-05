"""Frozen 2027 editorial experiment. Does not write any firmware/pack/v1 files.

Run from any directory with Python + Pillow. All inputs and output assets are
local; the gallery has no runtime dependency on a server or network.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / 'research/owspace-calendar'))
from calendar_data import Calendar
from render import layout, render, width
from content_analysis_author_dates import AUTHORS

CATALOG = HERE.parent / 'assets/catalog.json'
HISTORY = ROOT / 'artifacts/tr2e_calendar_400x600/2026.json'
DEFAULT_OUT = ROOT / 'artifacts/tr2e_calendar_2027_editorial_v2_1'
THEME_NOTES = {
    '相伴与体谅': '从人与人的具体联系进入，让体谅与关心有落点。',
    '亲密与欣赏': '给亲密和欣赏保留空间，不要求关系必须完美。',
    '松弛与日常': '把注意力放回身体、日常和节奏，给生活留一点余地。',
    '自我与边界': '留意自己的感受与选择，也容纳复杂和不确定。',
    '行动与希望': '保留尝试和向前的可能，不以必然成功作为安慰。',
    '阅读与表达': '借文字、记忆或想象，多看见一层生活。',
    '感官与自然': '从感官、自然或好奇出发，把目光移向身边。',
}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC', s).lower() if c.isalnum())


ALIASES = {norm(alias): a['name'] for a in AUTHORS for alias in a['aliases']}
# Matching for cadence only; source attribution and typography stay untouched.
ALIASES.update({norm(x): y for y, xs in {
    '几米': ['几米', '幾米'], 'J.D.塞林格': ['J.D.塞林格', 'J·D·塞林格'],
    '约翰·凯奇': ['约翰·凯奇', '约翰-凯奇'],
}.items() for x in xs})


def author_key(r):
    return norm(ALIASES.get(norm(r['author']), r['author']))


def season(d):
    # Broad meteorological reading context, not a claim about local weather.
    m = int(d['date'][5:7])
    return '冬' if m in (12, 1, 2) else '春' if m <= 5 else '夏' if m <= 8 else '秋'


def context_fits(r, d, rules):
    flags = set(r['editorial']['context_flags'])
    warm = any(a <= d['date'] <= b for a, b in rules['warm_windows'])
    child = any(a <= d['date'] <= b for a, b in rules['child_windows'])
    return not ((warm and flags-{'成人亲密'}) or (child and '成人亲密' in flags))


def anniversary(r, d):
    name = ALIASES.get(norm(r['author']))
    for a in AUTHORS:
        if a['name'] != name:
            continue
        for key, label in [('birth', '生日'), ('death', '忌日')]:
            if a[key] and a[key][5:] == d['date'][5:]:
                return dict(kind=label, name=name, date=a[key], sources=a['sources'], note=a['note'])
    return None


def protected_hashes():
    """Compare before/after bytes, including the released pack and v1 plans."""
    paths = [HISTORY, HERE.parent/'planner.py', HERE.parent/'personal_rules.json',
             HERE.parent/'render.py', CATALOG]
    paths += list((ROOT/'calendar_firmware/main').rglob('*'))
    paths += list((ROOT/'calendar_firmware/release').glob('*'))
    paths += list((ROOT/'artifacts/tr2e_calendar_400x600').glob('*.json'))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths)) if p.is_file()}


def prepare():
    rules = read(HERE/'rules_2027.json')
    curation = read(HERE/'curation.json')
    catalog = {r['id']: r for r in read(CATALOG)['records']}
    history = read(HISTORY)['days']
    old_groups = {d['content_group'] for d in history}
    old_titles = {d['title_key'] for d in history}
    pool, omitted = {}, []
    for meta in curation['reviewed']:
        r = catalog[meta['record_id']]
        if not r['eligible'] or r['content_group'] in old_groups or r['title_key'] in old_titles:
            omitted.append(dict(record_id=r['id'], reason='2026已使用或原库不可用'))
            continue
        try:
            spec = layout(r)
        except ValueError as exc:
            omitted.append(dict(record_id=r['id'], reason=str(exc)))
            continue
        pool[r['id']] = dict(r, editorial=meta, layout_mode=spec['mode'])
    return rules, curation, catalog, pool, history, omitted


def make_plan():
    rules, curation, catalog, pool, history, omitted = prepare()
    days = Calendar().year(rules['year'])
    anchors = {a['date']: a for a in rules['anchors']}
    by_date = {d['date']: d for d in days}
    chosen, groups, titles = {}, set(), set()
    authors = collections.Counter()

    def put(date, rid):
        r = pool[rid]
        if r['content_group'] in groups or r['title_key'] in titles:
            raise ValueError(f'Duplicate anchor/selection {date}: {rid}')
        chosen[date] = r
        groups.add(r['content_group']); titles.add(r['title_key'])
        authors[author_key(r)] += 1

    for date, a in anchors.items():
        if a['record_id'] not in pool:
            raise ValueError(f'Anchor excluded by review/history/layout: {date} {a}')
        if not context_fits(pool[a['record_id']], by_date[date], rules):
            raise ValueError(f'Anchor context mismatch: {date}')
        put(date, a['record_id'])
    if max(authors.values()) > 5:
        raise ValueError('Anchor author concentration exceeds limit')

    weights = rules['weights']
    ordinals = {d['date']: dt.date.fromisoformat(d['date']).toordinal() for d in days}

    def score(r, d):
        date = d['date']; meta = r['editorial']; key = author_key(r)
        value = int(hashlib.sha256((rules['seed']+date+r['id']).encode()).hexdigest()[:8], 16)/2**32*15
        if meta['theme'] in rules['monthly_lenses'][str(int(date[5:7]))]:
            value += weights['monthly_lens']
        if season(d) in meta['seasons']:
            value += weights['season_fit']
        ann = anniversary(r, d)
        if ann:
            value += weights['birthday'] if ann['kind'] == '生日' else weights['death_anniversary']
        value += authors[key]*weights['author_count']
        for other_date, other in chosen.items():
            distance = abs(ordinals[date]-ordinals[other_date])
            if distance <= 21 and author_key(other) == key:
                value += weights['same_author_21_days']
            if distance <= 3 and other['editorial']['theme'] == meta['theme']:
                value += weights['same_theme_previous'] if distance == 1 else weights['same_theme_last_3']
            if distance == 1 and meta['tone'] == other['editorial']['tone'] == '沉思':
                value += weights['both_reflective']
        prev = [chosen.get((dt.date.fromisoformat(date)-dt.timedelta(days=i)).isoformat()) for i in (1, 2, 3)]
        if all(x and x['kind'] == r['kind'] for x in prev):
            value += weights['same_kind_last_3']
        return value

    for d in days:
        if d['date'] in chosen:
            continue
        available = [r for r in pool.values() if r['content_group'] not in groups
                     and r['title_key'] not in titles and authors[author_key(r)] < 5
                     and context_fits(r, d, rules)
                     and (not r['editorial']['seasons'] or season(d) in r['editorial']['seasons'])]
        if not available:
            raise ValueError(f'No candidate meets hard rules on {d["date"]}; do not silently relax')
        best = max(available, key=lambda r: (score(r, d), r['id']))
        put(d['date'], best['id'])

    output = []
    for i, d in enumerate(days):
        date = d['date']; r = chosen[date]; m = r['editorial']; a = anchors.get(date)
        ann = anniversary(r, d)
        label = a['label'] if a else (d['solar_term'] or '')
        reason = a['reason'] if a else THEME_NOTES[m['theme']]
        if not a:
            if ann:
                reason = f'{ann["name"]}{ann["kind"]}提供日期线索；'+reason
            elif d['solar_term']:
                reason = '保留节气标识；本条按普通日阅读取向安排，不把节气强解为选句本意。'+reason
            elif m['theme'] in rules['monthly_lenses'][str(int(date[5:7]))]:
                reason += '与本月的阅读视角相合；并非该日期的历史事件。'
            else:
                reason += '作为本月主线以外的一次换气；不声称与该日期有史实关联。'
        output.append(dict(d, record_id=r['id'], content_group=r['content_group'], title_key=r['title_key'],
                           display_label=label, personal=bool(a and a['private']),
                           theme=m['theme'], tone=m['tone'], relation=m['relation'],
                           context_flags=m['context_flags'],
                           selection_reason=reason, arrangement='逐日审定的锚点' if a else '主题与相邻阅读节奏评分',
                           anniversary=ann, review=m['review']))
    inputs = [CATALOG, HISTORY, HERE/'curation.json', HERE/'rules_2027.json',
              HERE/'build_preview.py', HERE/'gallery.html', HERE.parent/'render.py',
              HERE.parent/'assets/calendar.bin', ROOT/'research/owspace-calendar/content_analysis_author_dates.py']
    return dict(schema=2, status='draft-not-firmware', version=rules['version'], year=2027,
                theme=rules['theme'], timezone='Asia/Shanghai', signature='Tr2e',
                inputs={str(p.relative_to(ROOT)): digest(p) for p in inputs},
                pool_size=len(pool), omitted_candidates=omitted,
                days=output), catalog


def verify(plan, catalog):
    days = plan['days']; history = read(HISTORY)['days']
    assert [d['date'] for d in days] == [d['date'] for d in Calendar().year(2027)]
    for d in days:
        r = catalog[d['record_id']]
        assert (d['content_group'], d['title_key']) == (r['content_group'], r['title_key'])
        actual = Calendar().day(d['date'])
        assert all(d[k] == v for k, v in actual.items())
    assert len({d['content_group'] for d in days}) == 365
    assert len({d['title_key'] for d in days}) == 365
    assert not ({d['content_group'] for d in days} & {d['content_group'] for d in history})
    assert not ({d['title_key'] for d in days} & {d['title_key'] for d in history})
    assert len({norm(catalog[d['record_id']]['excerpt']) for d in days}) == 365
    assert not ({norm(catalog[d['record_id']]['excerpt']) for d in days} &
                {norm(catalog[d['record_id']]['excerpt']) for d in history})
    counts = collections.Counter(author_key(catalog[d['record_id']]) for d in days)
    assert max(counts.values()) <= 5
    rules, _, _, pool, _, _ = prepare()
    assert all(context_fits(pool[d['record_id']], d, rules) for d in days)
    lunar_expected = {'02-06': (1, 1), '02-20': (1, 15), '06-09': (5, 5),
                      '08-08': (7, 7), '09-15': (8, 15), '10-08': (9, 9)}
    by_date = {d['date']: d for d in days}
    for md, pair in lunar_expected.items():
        d = by_date['2027-'+md]
        assert (d['lunar_month'], d['lunar_day']) == pair and not d['leap_month']
    assert by_date['2027-06-21']['solar_term'] == '夏至'
    assert by_date['2027-08-08']['display_label'] == '七夕·立秋'
    assert by_date['2027-10-08']['display_label'] == '重阳·寒露'
    assert [d['date'] for d in days if d['personal']] == ['2027-05-08', '2027-06-21', '2027-11-11']
    near = []
    for i, d in enumerate(days):
        for e in days[max(0, i-21):i]:
            if author_key(catalog[d['record_id']]) == author_key(catalog[e['record_id']]):
                near.append([e['date'], d['date'], catalog[d['record_id']]['author']])
    return dict(days=365, unique_groups=365, unique_titles=365, repeat_groups_vs_2026=0,
                repeat_titles_vs_2026=0, max_author_count=max(counts.values()),
                normalized_author_keys=len(counts), author_pairs_within_21_days=near,
                kind_counts=dict(collections.Counter(catalog[d['record_id']]['kind'] for d in days)),
                themes=dict(collections.Counter(d['theme'] for d in days)),
                tones=dict(collections.Counter(d['tone'] for d in days)),
                lunar_and_personal_dates_checked=True,
                source_note='对既有文本做语义通读筛选；本次没有把365张原图逐一重新OCR。作者统计使用有限别名表，不代表完整权威人名消歧。')


def build(out):
    before = protected_hashes()
    plan, catalog = make_plan()
    result = verify(plan, catalog)
    # Refuse accidental mutation of a previously generated draft.
    payload = json.dumps(plan, ensure_ascii=False, indent=2)+'\n'
    plan_path = out/'2027.json'
    if plan_path.exists() and plan_path.read_text() != payload:
        raise SystemExit('Existing draft differs. Choose another --output directory; preserve the reviewed draft.')
    out.mkdir(parents=True, exist_ok=True)
    (out/'days').mkdir(exist_ok=True)
    cards, audits = [], []
    with tempfile.TemporaryDirectory(prefix='tr2e-preview-') as temp:
        for d in plan['days']:
            r = catalog[d['record_id']]
            p = Path(temp)/(d['date']+'.png')
            audit = render(d, r, p, signature='Tr2e')
            spec = audit['layout']
            assert ''.join(spec['quote_lines']) == r['excerpt'].replace('\n', '')
            assert ''.join(spec['title_lines']) == r['title']
            # Keep approved author line and foreign-name typography.
            expected_author = ' · '.join(filter(None, ['、'.join(r['roles']), r['author']]))
            author_lines = [(t, s, f) for t, s, f in spec['footer'] if s == 13]
            assert ''.join(t for t, _, _ in author_lines) == expected_author
            assert all(f == 'body' for _, _, f in author_lines)
            assert ''.join(t for t, s, f in spec['footer'] if s == 11 and f == 'body') == r['foreign_name']
            label = audit['event_label']
            assert not any(s in label for s in ['生日', '纪念', '结婚', '妻子', '儿子'])
            if label:
                assert 20+width(f"{int(d['date'][5:7])}.{int(d['date'][8:]):02}", 'title', 31)+10+width(label,'sans',14) < 250
            shutil.copyfile(p, out/'days'/p.name)
            audits.append(dict(date=d['date'], record_id=r['id'], layout_mode=spec['mode'],
                               quote_font_px=spec['quote_size'], quote_line_count=len(spec['quote_lines']),
                               image_sha256=digest(p), text_preserved=True, bounds_checked=True))
            cards.append(dict(date=d['date'], weekday='星期'+'一二三四五六日'[d['weekday']],
                              lunar=d['lunar_label'], label=label, title=r['title'], excerpt=r['excerpt'],
                              author=r['author'], source=r['source'], source_date=r['source_date'],
                              theme=d['theme'], tone=d['tone'], relation=d['relation'], reason=d['selection_reason'],
                              arrangement=d['arrangement'], anniversary=d['anniversary'],
                              image='days/'+p.name, mode=spec['mode']))
            p.unlink(); p.with_suffix('.bin').unlink(); p.with_suffix('.layout.json').unlink()
    result['layout_modes'] = dict(collections.Counter(x['layout_mode'] for x in audits))
    result['all_365_full_text_and_bounds_checked'] = True
    result['protected_files_unchanged'] = before == protected_hashes()
    assert result['protected_files_unchanged']
    result['protected_sha256'] = before
    template = (HERE/'gallery.html').read_text()
    data = json.dumps(dict(plan={k: plan[k] for k in ['year','theme','version','pool_size']},
                           stats={k: v for k,v in result.items() if k!='protected_sha256'}, cards=cards), ensure_ascii=False).replace('<','\\u003c')
    gallery = template.replace('__CALENDAR_DATA__', data)
    (out/'index.html').write_text(gallery)
    plan_path.write_text(payload)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/'render_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='protected_sha256'},ensure_ascii=False,indent=2))
    print(out/'index.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.output.resolve())
