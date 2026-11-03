"""Build a local evidence report from existing text and checked biographies."""
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'content_logic_analysis/results.json').read_text())
raw={r['date']:r for p in sorted((ROOT/'months').glob('*.jsonl')) for r in map(json.loads,p.read_text().splitlines())}
esc=lambda x:html.escape(str(x if x is not None else '—'))
link=lambda url,label:f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'
def table(head,rows,raw_html=False):
    cell=(lambda x:str(x)) if raw_html else esc
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def record(r):
    return [r['date'],r.get('title') or '无宜忌标题',r.get('author'),r.get('source')]
def excerpt_card(date,comment):
    r=raw[date]
    return f'<article><p class="eyebrow">{esc(date)} · {esc(r["author"])}</p><h3>{esc(r["title"])}</h3><blockquote>{esc(r.get("excerpt"))}</blockquote><p>{esc(comment)}</p><p class="muted">出处：{esc(r.get("source"))} · {link(r["url"],"原图")}</p></article>'

p=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单向历内容编排：日期、作者、选句与标题</title><style>
body{font-family:system-ui,-apple-system,sans-serif;line-height:1.8;background:#f5f3ed;color:#27312e;max-width:1120px;margin:auto;padding:32px 24px}h1{font-size:32px;line-height:1.4}h2{font-size:24px;border-top:1px solid #c7cec5;padding-top:26px;margin-top:40px}h3{font-size:19px;line-height:1.5;margin:6px 0 12px}a{color:#286b63}p{max-width:940px}.muted,.eyebrow{color:#65736b;font-size:14px}.callout{padding:20px 26px;background:#e5ece2;border-left:4px solid #66845d}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}article{padding:20px;background:white;border:1px solid #dce1d8;border-radius:7px}blockquote{margin:12px 0;padding:10px 16px;border-left:3px solid #aaa;color:#536258;background:#fafaf7}table{width:100%;border-collapse:collapse;background:white;font-size:14px;margin:14px 0}th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid #e0e4dc}th{background:#e5ece2}.scroll{overflow:auto}details{background:white;padding:12px 18px;margin:12px 0}summary{cursor:pointer;font-weight:600}.flow{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.flow>div{background:#e5ece2;padding:16px 20px;flex:1;min-width:190px}.flow b{display:block}.warn{background:#fff2db;padding:14px 20px}code{font-size:13px}nav{display:flex;gap:20px;flex-wrap:wrap}@media print{body{background:white;padding:0}.cards{display:block}article{break-inside:avoid}details{break-inside:avoid}}</style>
<h1>单向历内容编排：日期、作者、选句与标题</h1><p class="muted">2015—2025 · 2026-11-03 · 基于既有统计表的全量结构筛查、44 条语义样本判读、26 位作者的定向传记核验</p>
<nav><a href="#title">标题与选句</a><a href="#anniversary">作者生卒日</a><a href="#combined">多种日期关联</a><a href="#evidence">核验明细</a><a href="#limits">方法与限制</a></nav>
<p class="callout"><strong>新增结论：作者的生日、忌日确实参与了排期；标题则常常为选句提供一个当代、日常、带态度的阅读角度。</strong><br>同一句摘录可以换标题甚至换宜忌；同一作者纪念日可以换选句和主题。更符合证据的模型是“日期关联限定部分选材范围，选句提供文学内容，标题完成语境转接”。具体先选作者、先选句还是先拟标题，仍无法由成品确定。</p>
''']
c=d['counts']; a=d['author_dates']; lex=d['lexical']; dup=d['repeated_excerpts']; rec=d['author_recurrence']
p.append(table(['检查层次','范围','主要结果'],[
    ('标题与摘录',f'{c["title_excerpt_pairs"]:,} 组',f'去掉宜忌前缀后，标题完整文字出现在摘录中的有 {lex["exact_body_in_excerpt"]} 组'),
    ('相同摘录对照',f'{dup["groups"]} 组，{dup["records"]} 个页面',f'{dup["changed_title_groups"]} 组标题不同，{dup["changed_polarity_groups"]} 组宜忌有变化'),
    ('跨年作者复现',f'{rec["credited_pages"]:,} 个有署名的页面',f'同月同日的跨年比较中，{rec["same_author_pairs"]} 对为同一作者字符串；分年打乱后平均 {rec["shuffled_mean"]} 对'),
    ('生卒日核验',f'{a["checked_identities"]} 位作者、{a["covered_pages"]} 条署名记录',f'{a["strict_matched_pages"]} 个页面日期匹配：生日 {a["birth_pages"]}、忌日 {a["death_pages"]}；另有 3 条传统或发现日期纪念记录单列'),
]))
p.append('''<h2 id="title">标题通常是对选句的解释、回应或生活化改写</h2>
<p>把“宜／忌”去掉，并去除标点后，标题剩余文字完整出现在摘录里的只有 101/3,905（2.59%）；与摘录至少共享连续两个字的为 297/3,905（7.61%）。分年随机打乱标题与摘录后，相应平均数仅为 2.27 和 12.47。这说明两者有明显联系，但不能靠“找相同词”解释大多数配对。</p>
<p>这不是说其余 97.41% 都完全没有字面关系：既有 excerpt 可能只是选句的一部分，OCR 也会漏字错字。这里测量的是既有字段中的严格字面重合。下面用可读实例解释不同关系。</p><div class="cards">''')
p.append(excerpt_card('2017-11-16','直接提词：把选句反复出现的“写诗”抽为当天可做的动作。'))
p.append(excerpt_card('2015-08-16','情绪概括：选句叙述一次意识到爱情的经历，标题把它压缩成一种感受。'))
p.append(excerpt_card('2017-08-16','反向提醒：选句主张保留可能性，标题把同一立场反写为“不要绝对化”。“忌”不代表选句在说负面的话。'))
p.append(excerpt_card('2018-02-15','场景化改写：除夕不眠的古诗被接到现代抢红包的生活场景。标题中的红包并非从摘录直接提取。'))
p.append(excerpt_card('2021-02-15','修辞回应：诗句表达求而不得的爱，标题用“忌自怜”回应这种情绪，形成评论关系。'))
p.append(excerpt_card('2019-11-16','当代语言转译：把与猫建立信任的描述，转换成读者熟悉的“吸猫”。不据此核定原书出处是否准确。'))
p.append('''</div><p>固定选取每年 2、5、8、11 月中间一条有效记录，共判读 44 条：4 条因明显 OCR 问题暂不分类，其余主要关系分别为直接提词 4、情绪概括 10、反向提醒 13、场景化改写 7、修辞回应 6。类别可重叠，这里只记录主要关系；判读由模型完成，不是人工标准答案，也不能把样本比例推算到全体。</p>
<h3>最有力的对照：同一句摘录，换一种标题</h3>''')
chosen=[('2015-02-27','2018-06-15','从对失约者的责备，切换到对等待者的理解。'),('2016-03-25','2021-04-01','“宜欺骗”与“忌真话”字面方向相反，却都在突出艺术与谎言的关系。'),('2016-08-24','2019-12-27','从“葛优躺”的具体生活姿态，换成避免过度思考的提醒。'),('2021-07-10','2025-07-10','同一作者生日、同一摘录，可以从“大吃大喝”换成更概括的“犒劳自己”。')]
for x,y,comment in chosen:
    r,s=raw[x],raw[y]
    p.append(f'<article><h3>{esc(r["author"])}：{esc(r["title"])} → {esc(s["title"])}</h3><blockquote>{esc(r["excerpt"])}</blockquote><p>{esc(x)} · {link(r["url"],r["title"])}<br>{esc(y)} · {link(s["url"],s["title"])}</p><p>{esc(comment)}</p></article>')
p.append('''<p>64 组相同摘录中，59 组换过标题、27 组换过宜忌。这是同一摘录不唯一决定标题的直接证据。相同指去标点后的既有 excerpt 相同，不保证印刷全文完全一样；个别组署名不同，也不能借重复统计确认引用归属。</p>
<h2 id="anniversary">生日、忌日确实是排期线索</h2>
<p>全量筛查首先按原始作者字符串检查跨年同月同日复现，得到 72 组重复“作者＋月日”，共 125 对同作者比较；在每年内部随机打乱作者，平均只有 14.7 对，约相差 8.5 倍。此对照保留了年度作者出现频次，支持作者与日期存在关联，但本身不能说明关联一定是生卒日。</p>
<p>随后对重复明显、出现较多以及用于反例的 26 位作者查阅传记资料，并只在分析层归并已确认的姓名变体。找到 94 个精确月日匹配的页面，其中 63 个为生日、31 个为忌日；另有 3 个传统纪念或发现日期记录单列。生日并不规定必须用“宜”：例如鲍勃·迪伦的生日既有“忌正统”，也有“宜随风”。</p>''')
focus=['鲍勃·迪伦','川端康成','张爱玲','王小波','沈从文','简·奥斯汀','约翰·济慈','马塞尔·普鲁斯特','今敏','威廉·莎士比亚']
tab=[]
for name in focus:
    person=next(x for x in a['identities'] if x['name']==name)
    for kind,tag in [('birth','生日'),('death','忌日')]:
        matches=[r for r in a['matches'] if r['identity']==name and r['kind']==kind]
        if matches:tab.append([esc(name),esc(tag+' '+person[kind][5:]),esc('、'.join(r['date'][:4] for r in matches)),esc('；'.join(r['title'] or '问答页' for r in matches)),link(person['sources'][0],'生平依据')])
p.append(table(['作者','对应日期','命中年份','当天标题','外部证据'],tab,True))
p.append('''<p class="warn">这 26 位是定向选择的核验对象，不是随机抽样。94/305 不能用来宣称全部日历约 31% 按作者生卒日编排。全表尚有大量作者的生卒日未核验；“未命中”只表示当前证据表未匹配，不表示该日没有纪念含义。</p>
<h2 id="combined">日期可以连接作者，也可以连接作品主题和作品中的人物</h2>
<h3>同一句话，可以走两条不同的日期路径</h3>
<p>德彪西的同一句摘录，2016-03-25 配“宜欺骗”，这一天与其忌日对应；2021-04-01 配“忌真话”，则与愚人节的话题吻合。因此，不能只给一句话绑定一个日期，也不能只查作者生日。德彪西生卒日见<a href="https://catalogue.bnf.fr/ark%3A/12148/cb13893072d">法国国家图书馆权威记录</a>。</p>
<h3>作品中人物的生日：4 月 28 日的《辛德勒的名单》</h3>
<p>2016-04-28“忌滥用”和 2017-04-28“宜慈悲”都署名史蒂文·斯皮尔伯格，来源为《辛德勒的名单》。4 月 28 日与电影所写人物奥斯卡·辛德勒的生日一致，依据为<a href="https://encyclopedia.ushmm.org/content/en/article/oskar-schindler">美国大屠杀纪念馆的人物资料</a>。这支持“通过作品人物关联日期”的解释，而不能把日期误记为署名导演的生日。</p>
<h3>议题选择作者：12 月 1 日的苏珊·桑塔格</h3>
<p>2018、2021 年 12 月 1 日均出现桑塔格的《疾病的隐喻》，标题均为“忌歧视”，摘录谈疾病妖魔化与归咎患者。这与<a href="https://www.unaids.org/en/World_AIDS_Day">世界艾滋病日</a>的议题吻合。她的生卒日期是 1 月 16 日与 12 月 28 日（<a href="https://susansontag.com/SusanSontag/index.shtml">作者官网</a>），所以该组重复不能归为生卒纪念。</p>
<h3>两种线索可以重合：春节与叶芝忌日</h3>
<p>2017-01-28 是春节，也是叶芝忌日的月日。当天署名“叶芝”，标题“宜迎新”。这提供了同时满足节日与作者纪念的实例，但不能确定编辑当时优先考虑哪条线索。农历日期来自<a href="https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2017c.txt">香港天文台 2017 年历表</a>，生卒日来自<a href="https://www.nobelprize.org/laureate/593">诺贝尔奖官网</a>。</p>
<h3>历法口径必须保留：莎士比亚 4 月 23 日与 5 月 3 日</h3>
<p>2017、2021、2022 年的 5 月 3 日都出现莎士比亚。<a href="https://www.folger.edu/blogs/shakespeare-and-beyond/shakespeare-and-cervantes-400-years/">福尔杰莎士比亚图书馆</a>明确解释：其逝世的儒略历 4 月 23 日，对应公历 5 月 3 日。2016-04-23 也出现莎士比亚，可同时关联传统忌日和读书日。我们保留两种口径，不把传统上推定的生日当作已知精确生日。</p>
<h2>更符合现有证据的编排模型</h2>
<div class="flow"><div><b>日期提供选材线索</b>节日／节气／生卒纪念／作品人物纪念／普通生活场景</div><div><b>选句承载文学内容</b>作者与作品范围、思想或情绪、意象、场景、值得回应的困境</div><div><b>标题提供阅读角度</b>提词、概括、反向提醒、现代生活转译、幽默或反讽</div></div>
<p>“宜／忌”不是作者对当天运势的判断，也不必等于选句的表面情绪。它更像面向读者的一句行动或态度提示：宜做什么，或不宜陷入什么。一个消极场景可以导出积极建议，一个积极主张也可以改写成“忌”的提醒。</p>
<p>这是一套可以解释成品的模型，不是已证实的内部生产流程。现有数据能确认组合关系与重复模式，不能确认谁先选题、是否有固定编辑排期表、是否使用算法，也不能据此复原每一页的意图。</p>
<h2 id="evidence">可复查的作者证据表</h2>
<p class="muted">每位作者列出核验口径、外部依据和全部精确匹配记录。问答页面计入作者日期分析，但不计入标题—摘录配对。</p>''')
for person in a['identities']:
    matches=[r for r in a['matches'] if r['identity']==person['name']]
    special=[r for r in a['special_memorial_dates'] if r['identity']==person['name']]
    p.append(f'<details><summary>{esc(person["name"])} · 精确匹配 {len(matches)} 条 · 其他纪念口径 {len(special)} 条</summary>')
    p.append(f'<p>已核验生日：{esc(person["birth"])}；已核验忌日：{esc(person["death"])}。空项表示未录入或不适用。</p><p>{esc(person["note"])}</p>')
    p.append('<p>依据：'+' · '.join(link(url,f'资料 {i+1}') for i,url in enumerate(person['sources']))+'</p>')
    p.append('<p class="muted">分析采用的姓名形式：'+esc('、'.join(person['aliases']))+'</p>')
    p.append(table(['日期','类型','标题','原署名','出处','原图'],[[esc(r['date']),esc('生日' if r['kind']=='birth' else '忌日'),esc(r['title']),esc(r['author']),esc(r['source']),link(r['url'],'查看')] for r in matches],True))
    if special:p.append(table(['日期','口径','标题'],[(r['date'],r['kind'],r['title']) for r in special]))
    p.append('</details>')
p.append('<h2>44 条固定样本的逐条判读</h2><p class="muted">摘录显示原字段，不静默改错字；不确定项保留。以下为模型判读，可据原图和上下文修订。</p>')
for r in d['semantic_sample']['records']:
    p.append(f'<details><summary>{esc(r["date"])} · {esc(r["title"])} · {esc(r["relation"])}</summary><blockquote>{esc(r["excerpt"])}</blockquote><p>{esc(r["author"])} · {esc(r["source"])}</p><p>{esc(r["reason"])}</p><p>{link(r["url"],"原图")}</p></details>')
p.append('<h2>64 组相同摘录的标题对照</h2><p class="muted">仅按既有摘录去标点后的文本相等分组，不作引用真伪与作者归属判断。全部组均列出，便于检查反例。</p>')
for group in dup['details']:
    rows=group['records']
    p.append('<details><summary>'+esc(' / '.join(r['title'] for r in rows))+'</summary><blockquote>'+esc(group['excerpt'])+'</blockquote>')
    p.append(table(['日期','标题','署名','出处'],[record(r) for r in rows]))
    p.append('</details>')
p.append('<h2>跨年同日作者复现：全量筛查清单</h2><p>共 72 组。以下只是候选规律，不应把未核验条目自动标为生日或忌日。</p>')
p.append(table(['原署名','月日','年份','标题'],[(g['author'],g['md'],'、'.join(r['date'][:4] for r in g['records']),'；'.join(r['title'] or '问答页' for r in g['records'])) for g in rec['groups']]))
p.append('''<h2 id="limits">方法、数据质量与边界</h2>
<p>原始 4,018 条记录排除 49 个缺失地址及 10 个已知日期错配，剩 3,959 页。作者复现分析使用其中 3,917 个有署名页面；标题—摘录分析使用 3,905 个具备宜忌标题和非空 excerpt 的页面，比上一份标题报告少 2 个无摘录记录。共出现 2,027 个不同作者字符串，尚未对所有字符串统一人物身份。</p>
<p>本次全量完成了字面关联、摘录重复和作者同日复现筛查；语义关系采用 44 条固定样本，生卒日采用 26 位定向作者核验。不能把这些不同层次都描述为“全量人工核验”。其他作者未核实，资料缺项、别名漏合并、历法差异、署名角色等都可能使现有匹配数低估。</p>
<p>明显 OCR 问题仍会影响语义分析，例如 2015-02-23 的标题和 2022 年部分样本。还有相同摘录但不同署名的组，需要单独核对引用归属。本次未把推测写回原表，也未通过常识补齐损坏选句。现有摘录不一定等于整页全文，文学作品中的角色话语也不等于作者本人的观点。</p>
<p>置换对照均保留每年的记录和频次，并在年内打乱：标题与摘录 1,000 次；作者与日期 2,000 次；随机种子 20261103。作者同日复现的探索性置换 p≈0.00050，但关联的大小和具体传记证据比单一 p 值更重要。生卒日样本是事后定向核验，不据其命中比例进行总体推断。</p>
<p>复现文件：<a href="../content_logic_analysis/results.json">统计结果、原文件哈希和明细</a> · <a href="../content_analysis_author_dates.py">作者日期与证据表</a> · <a href="../analyze_content_logic.py">分析脚本</a> · <a href="../render_content_logic_analysis.py">报告生成脚本</a>。先用带 NumPy 的 Python 运行分析脚本，再运行报告生成脚本。全部月份原始记录保持不变。</p>
<p>前一份研究：<a href="标题与日期关联分析.html">标题与日期关联分析</a>。</p></html>''')
target=ROOT/'output/内容编排规律分析.html'
target.write_text(''.join(p),encoding='utf-8')
print(target)
