"""Inventory all author fields and queue questionable names for image review."""
from collections import Counter,defaultdict
import hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'author_audit';OUT.mkdir(exist_ok=True)
rows=[json.loads(line) for p in sorted((ROOT/'months').glob('*.jsonl')) for line in p.read_text().splitlines()]
names=defaultdict(list)
for r in rows:
    if r.get('author'):names[r['author']].append(r['date'])
manual_indices=[24,61,62,91,117,132,150,156,172,173,188,199,206,254,257,279,362,363,379,380,391,411,423,427,438,477,534,544,554,557,568,580,617,641,645,646,653,657,658,664,672,675,677,695,750,782,791,797,814,873,876,891,903,908,914,915,918,924,926,929,932,942,943,984,986,994,996,998,1011,1027,1050,1071,1084,1085,1088,1091,1092,1094,1101,1113,1131,1176,1209,1227,1242,1255,1260,1262,1272,1276,1309,1314,1321,1333,1373,1375,1377,1397,1403,1412,1418,1423,1426,1429,1435,1438,1451,1456,1457,1463,1466,1471,1478,1481,1484,1489,1491,1513,1514,1518,1527,1539,1541,1547,1556,1562,1563,1567,1589,1592,1604,1618,1633,1634,1639,1645,1654,1668,1675,1678,1681,1685,1690,1694,1702,1747,1750,1757,1766,1770,1776,1777,1781,1798,1805,1806,1814,1828,1840,1845,1850,1853,1867,1870,1880,1888,1895,1898,1902,1903,1905,1906,1908,1915,1920,1921,1930,1933,1934,1939,1940,1941,1945,1965,1966,1969,1971,1976,1977,1978,1981,1983,1985,1986,1989,1998,1999,2005,2007,2009,2022,2025,2028,2031,2041,2042,2043,2046,2047,2048,2050,2053,2058,2059,2065,2066,2072,2074,2077,2079,2084,2086,2087,2089,2093,2102,2103,2106,2110,2111,2114,2118,2121,2122,2129,2133,2134,2136,2137,2138,2144,2145,2151,2153,2156,2158,2159,2162,2164,2170,2182,2183]
inventory=list(names)
manual_names={inventory[i] for i in manual_indices}
baseline=[];candidates=[]
for r in rows:
    protected={k:v for k,v in r.items() if k not in ('author','author_foreign_name','review_flags','metadata_edits','author_name_audit')}
    baseline.append({'date':r['date'],'protected_sha256':hashlib.sha256(json.dumps(protected,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'author':r.get('author'),'author_foreign_name':r.get('author_foreign_name')})
    if r['status']!='indexed':continue
    a=r.get('author') or '';reasons=[]
    if not a:reasons.append('missing_author')
    if a in manual_names:reasons.append('inventory_name_anomaly')
    if re.search(r'[,，；;《》〈〉（）()\d【】\[\]：:|×]',a):reasons.append('mixed_name_or_metadata')
    if a.startswith(('·','作者','之','作，','电影','美剧','日剧','敬手','编刷','导潢','作冢')):reasons.append('prefix_or_role_contamination')
    if re.search(r'兙|呇|剞|刟|0替|丕台|天猫|單向|出浓郁|主导人物',a):reasons.append('script_or_banner_contamination')
    if r.get('author_foreign_name'):reasons.append('foreign_script_parser_review')
    if reasons:candidates.append({k:r.get(k) for k in ('date','url','image_sha256','author','author_foreign_name','author_roles','layout_variant')}|{'reasons':reasons})
summary={'baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'date_records_scanned':len(rows),'indexed_records':sum(r['status']=='indexed' for r in rows),'unique_author_values':len(names),'candidates':len(candidates),'reason_counts':dict(Counter(reason for r in candidates for reason in r['reasons']))}
for name,data in [('scan',{'summary':summary,'candidates':candidates}),('baseline',baseline),('name_inventory',[{'author':a,'dates':dates} for a,dates in names.items()])]:
    p=OUT/f'{name}.json'
    if p.exists():raise SystemExit(f'Refusing to replace existing audit baseline: {p}')
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
