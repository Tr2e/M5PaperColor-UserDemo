"""Build a self-contained evidence report from reproducible analysis and readings."""
import collections,html,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent;DIR=ROOT/'editorial_thinking'
read=lambda name:json.loads((DIR/name).read_text())
d=read('results.json');coding=read('readings.json');sources=read('sources.json')['sources'];visual=read('visual_checks.json')
prior=json.loads((ROOT/'content_logic_analysis/results.json').read_text())
assert d['source_hashes']==prior['source_hashes'],'Recompute previous evidence before combining changed source records'
raw={r['date']:r for p in sorted((ROOT/'months').glob('*.jsonl')) for r in map(json.loads,p.read_text().splitlines())}
esc=lambda x:html.escape(str(x if x is not None else '—'))
def link(url,label):return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'
def cite(id):
 s=next(s for s in sources if s['id']==id);return link(s['url'],id+' · '+s['title'])
def table(head,rows,raw_html=False):
 cell=str if raw_html else esc
 return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>'
def case(date,heading,analysis,grade='成品解读'):
 r=raw[date]
 return f'<article><span class="badge">{esc(grade)}</span><p class="meta">{esc(date)} · {esc(r.get("author"))}</p><h3>{esc(heading)}</h3><p class="title">{esc(r.get("title"))}</p><p>{esc(analysis)}</p><p class="meta">出处：{esc(r.get("source"))} · {link(r["url"],"原图")}</p></article>'
def pct(a,b):return f'{100*a/b:.1f}%' if b else '—'

p=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单向历编辑如何思考：从制作证言到成品验证</title>
<style>:root{--ink:#26352e;--muted:#637067;--line:#cdd3c8;--paper:#f5f3eb;--green:#e5ebdf}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.85 system-ui,-apple-system,sans-serif}main{max-width:1160px;margin:auto;padding:50px 30px 80px}h1{font-size:40px;line-height:1.3;letter-spacing:-1px;max-width:900px}h2{font-size:26px;line-height:1.5;margin:50px 0 20px;padding-top:22px;border-top:1px solid var(--line)}h3{font-size:19px;line-height:1.55}p{max-width:980px}a{color:#285e4a;text-underline-offset:3px}.meta{font-size:13px;color:var(--muted)}.lead{font-size:21px;line-height:1.8}.callout{background:var(--green);border-left:4px solid #607a59;padding:20px 26px;margin:24px 0}.limit{background:#eee5d4;padding:16px 22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}article{background:#fffef9;border:1px solid var(--line);padding:20px 23px}article p{margin:10px 0}.title{font-family:serif;font-size:24px;font-weight:bold}.badge{font-size:12px;display:inline-block;padding:2px 9px;background:var(--green);border-radius:3px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;background:#fffef9}th,td{padding:11px 13px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:var(--green);white-space:nowrap}details{padding:12px 18px;margin:12px 0;border:1px solid var(--line);background:#fffef9}summary{cursor:pointer;font-weight:600}blockquote{margin:12px 0;padding:12px 18px;background:#f3f4ee;border-left:3px solid #879480;color:#536056}nav{display:flex;gap:10px 22px;flex-wrap:wrap;margin:24px 0}nav a{font-size:14px}.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.flow div{padding:16px 18px;background:var(--green)}.flow b{display:block}input,select{font:inherit;border:1px solid #a8b4a1;background:white;padding:9px 12px;max-width:100%}.filter{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:18px 0}.bar{display:inline-block;height:9px;background:#668260;vertical-align:middle;margin-right:7px}.num{font-variant-numeric:tabular-nums;white-space:nowrap}code{font-size:13px;background:#e9ecdf;padding:2px 5px}.mini{font-size:13px}.visnote{border-left:3px solid #998354;padding-left:12px}@media(max-width:600px){main{padding:24px 16px}h1{font-size:30px}h2{font-size:23px}.lead{font-size:19px}}@media print{body{background:white}main{padding:0}nav,.filter{display:none}article,details{break-inside:avoid}a{color:inherit}}</style>
<main><p class="meta">研究日期 2026-11-05 · 2015—2025 公开日签索引 · 本地离线报告</p><h1>单向历的编辑，<br>可能在为“这一天”考虑什么？</h1>
<p class="lead">最值得学习的不是给每个日期找一个名人，而是把一段文学表达，变成读者今天可以使用的一种看法。</p>
<p>这一次把制作团队的公开说明、全量统计、固定抽样阅读及原图复核放在一起。能确认的制作事实、能观察到的成品规律、我们的解释，以及未来日历的设计建议，分别标明。不会把反推结果写成编辑本人未公开的心理活动。</p>
<nav><a href="#findings">主要发现</a><a href="#process">制作证言</a><a href="#years">年度变化</a><a href="#bridge">标题如何工作</a><a href="#dates">日期如何选材</a><a href="#boundary">年界与春节</a><a href="#rhythm">前后日节奏</a><a href="#design">用于 Tr2e</a><a href="#samples">66页阅读记录</a><a href="#method">方法与证据</a></nav>
<div class="callout"><strong>更接近证据的工作模型：</strong>年度关注与读者处境 → 确定需要照顾的日期 → 挑选有独立表达力的句子 → 用标题改变阅读角度 → 复核整年安排。<br>其中2018版的流程有编辑自述；跨年度延伸及“读者处境”的细分，是结合其他公开说明与成品作出的解释。</div>
<h2 id="findings">先看这次新增的判断</h2>
''']
p.append(table(['判断','证据强度','实际含义'],[
 ('2018版确实先处理特殊日子，再配句、拟宜忌，最后调整顺序','编辑本人自述','此前仅能从成品推测的部分，现在有适用该版本的过程证据。'),
 ('年份会改变选材重点，而不只是更换365条名言','制作说明＋年度结构','2022音乐、2023问题页与后续更长的标题，不能压成一套永久不变的风格。'),
 ('标题常给读者一种许可或提醒，而非给选句写摘要','固定66页的解释性阅读＋重复选句对照','同一句话可因读者处境不同而换宜忌；不能把宜当积极情绪标签。'),
 ('节日吻合可以隐藏在身体经验、书名或作品人物中','跨年案例＋8张原图核验','春节的消食、冬至的作品名、作者忌日的酒，都比关键词匹配多一步。'),
 ('年界有明显倾向，但13天连续正能量不是已证实原规则','窗口统计＋反例','元旦、除夕、跨年是强提示；外围日子仍留有幽默、反思与提醒。'),
 ('未检出稳定的相邻作者、词汇主题、长短句轮换','月内置换对照，4项检验','不能把我们希望的舒适节奏说成已破解的编辑排班。'),
]))
p.append(f'<p class="meta">本次样本：4,018个日期 → 排除49个缺失地址与10个已知错图 → 3,959个有效页面；标题与摘录同时可用的宜忌页为{d["counts"]["normal_pairs"]:,}页。50个问答页单列；另4页属于其他版式或缺标题／摘录。2015与2025不是完整覆盖年份。</p>')

p.append('<h2 id="process">制作证言：流程证据比猜测更有分量</h2><p>以下每条都限定适用年份。公开自述可能简化实际工作，也不能证明所有版本的纸质日历与公开日签内容一致。</p>')
for s in sources:
 p.append(f'<article><p class="meta">{esc(s["id"])} · {esc(s["publication_date"] or "发布日期未可靠确认")}</p><h3>{link(s["url"],s["title"])}</h3><p>{esc(s["finding"])}</p><p class="meta">适用范围：{esc(s["scope"])}<br>访问情况：{esc(s["access"])}</p></article>')
p.append('''<p class="limit">需要收回此前一种过于保守的说法：现在不能再笼统地说“完全无法知道先选句还是先拟标题”。2018版已经有明确自述；其他年份是否采用同样顺序，仍不能自动确认。</p>
<h2 id="years">年度主题会改变材料：不能只学习一个平均年份</h2>
<p>公开叙述与既有数据可以相互核对。2022年的音乐相关署名明显增加；2023年恰有50个问答页，之后标题正文的长度中位数从约2字变为4字。它们支持年度表达方式会变化，但无法单凭数据把变化归因于某位编辑或某件社会事件。</p>''')
p.append(table(['年份','有效页','音乐相关署名¹','问答页','宜／可用配对','标题正文中位字数','重复标题组²'],[(x['year'],x['pages'],f'{x["music_role_pages"]} / {x["pages"]}（{pct(x["music_role_pages"],x["pages"])}）',x['question_pages'],f'{x["yi"]}/{x["normal_pairs"]}',int(x['title_median']),x['repeat_title_groups']) for x in d['annual']]))
p.append('''<p class="meta">¹ 音乐相关署名由职业字段包含音乐、歌手、乐队、词作等词识别，既非精确歌曲数，也非全面体裁分类；早年职业字段缺失较多。2022有356/365页提供职业字段，命中94页，与访谈方向一致，不能拿94和100余首直接判谁错。² 去标点后的完整标题重复组，只统计标题与摘录均可用的页面，组内可能不止2页。</p>
<p>历史成品并未实行所有年份标题绝不重复：2019年有36组，2022年为0组。已存摘录也有少量同年重复。因此我们设定的“年内内容与标题不重复”，是为个人使用增加的约束，并非照搬了一条已证实的原编辑制度。</p>
<p>2023年的50个问题页分布在一周七天，星期一10页、星期六10页，其余曜日也有；相邻问题页间隔2—17天，没有固定周更位置。约50页不能被直接解释成“一周一个、固定星期日”。问题页摘录在当前索引中为空，本次未对这些问答的具体语义作全量分析。</p>
<h2 id="bridge">标题真正增加了什么：把作品中的表达接到生活里</h2>
<p>我们新增66页固定抽样阅读：每年分成6个两月区间，每区间随机取1个正常页，先固定日期，再判读。分类是本助手的解释，不是编辑认可的答案；主类用于导航，实际可兼具多种关系。全部逐条记录在后文。</p>''')
counts=collections.Counter(r['relation'] for r in coding['records'])
descriptions={
 '直述概括':'提炼已有主张，读者较容易直接看出逻辑。',
 '反向提醒':'从困境、危险或反例提出别陷入什么，不等于选句本身负面。',
 '场景转译':'把文学、哲学或电影里的表达接到返工、散步、交往等具体场景。',
 '双关反讽':'在字面／比喻或宏大／日常之间制造错位，让人会心一笑。',
 '情绪许可':'允许自己疲惫、怀旧、暂停或无所事事；陪伴不只有鼓励奋斗。',
 '意象联想':'保留风、名字、凝视等意象，留给读者补足含义，解释不一定唯一。'}
p.append(table(['主导读法','本样本页数','标题提供的增量'],[(c,counts[c],descriptions[c]) for c in coding['categories']]))
p.append('<p class="meta">页数只描述这66页的单次模型编码，不据此推算全库比例或声称独立人工校验准确率。</p><div class="grid">')
p.append(case('2021-08-21','借现代动作说古老问题','王尔德谈模仿他人的思想和生活，标题却用电脑操作“复制粘贴”。编辑增加的是读者熟悉的动作词；若只寻找书中同词，就会错过它。'))
p.append(case('2023-12-27','陪伴有时是替人松一口气','闭眼听讲的幽默辩解，与“放过自己”接在一起。临近年末，它没有催促完成目标，而是容纳疲惫；这是一种解释，不是已核实的当日意图。','原图核验＋解读'))
p.append(case('2024-01-13','积极不等于提高效率','“无所事事”在传统劝勉里可能被视为消极，这里却是在为无聊和生命经验留空间。只用正负词典筛选，会把这类关怀误删。'))
p.append(case('2020-01-15','宜也可以容纳低落','正文承认热情熄灭，标题选择怀旧。宜是阅读姿态，不是整段文字的情绪分数。'))
p.append('</div><h3>同一句话可以被放在得失的不同一侧</h3><p>2018-05-26“忌挥霍”和2019-11-23“宜释然”使用同一条已存摘录，署名分别为张悬、焦安溥。前者可理解为面对所得要珍惜，后者可理解为面对失去要放下。此处只比较相同摘录的阅读角度，不用署名变体判断引用真伪。以此前全库去标点分组计，64组相同摘录中59组换过标题，27组换过宜忌；不能把标题视为选句唯一正确的标签。</p>')

p.append('''<h2 id="dates">日期提供的是进入内容的路径，不是唯一答案</h2>
<div class="flow"><div><b>公共日历</b>节庆、节气、纪念议题</div><div><b>文化关联</b>作者、作品、人物与纪念口径</div><div><b>生活经验</b>返工、饮食、寒冷、想念、休息</div><div><b>读者处境</b>需要被提醒、被允许、被看见的事情</div></div>
<p>前两类通常可核事实；后两类更依赖语义判断。一个日期可能有多条路径，应该保留多种解释及证据等级，而非一找到生日就停止理解选句。</p><div class="grid">''')
p.append(case('2018-02-16','春节也可以谈“消化世界”','原图明确写春节。标题用节日饮食经验作入口，正文谈独处与精神消化；它没有直接写家人或团聚，却与日子的生活场景贴合。','原图明确日期＋解读'))
p.append(case('2018-12-22','日期线索可能放在出处里','当天冬至，出处也叫《冬至》，标题则是宜出神。只分析宜忌标题会把这条关联漏掉；作品名相同本身也不能证明作品创作日。'))
p.append(case('2022-07-02','作者纪念不规定情绪','原图直接写海明威逝世纪念日，并使用肖像。标题与酒的选句有双关关联；这是纪念排期的直接成品证据，且并非哀悼口吻。','原图明确纪念标记'))
p.append(case('2022-04-22','公共议题通过感官出现','原图标注世界地球日。页面用聆听与守护的歌词回应，而不是把环保写成一条知识定义；这条路径同时兼容当年的音乐选材。','原图明确日期＋解读'))
p.append('</div><h3>作者日期：已有证据，仍不能当总开关</h3>')
a=prior['author_dates']
p.append(f'<p>沿用上一轮已核验的{a["checked_identities"]}位作者证据，覆盖{a["covered_pages"]}条署名记录，有{a["strict_matched_pages"]}页与生卒月日精确对应：生日{a["birth_pages"]}页、忌日{a["death_pages"]}页。作者对象是定向选择的，不能把这一比例外推给全部3,959页。完整传记链接及莎士比亚历法、张爱玲发现日期等口径见{link("内容编排规律分析.html#anniversary","上一轮作者证据表")}。</p>')
p.append('''<p>同一批26位作者在不同年份的命中也不稳定：2016有20/29条署名记录对应生卒日，2018为1/20，2023为2/30。该对比说明至少不能假定这批作者每年固定出现；样本本身偏向跨年复现作者，不能据此估算各年全部纪念页比例。</p>
<p>2017-01-28同时是春节和叶芝忌日，当天“宜迎新”能兼容两条解释。2016、2017年4月28日的《辛德勒的名单》，更可能通过作品人物辛德勒的生日关联，而不是署名导演；这类路径已有外部传记依据，详见上一轮报告。不能把作品人物生日写进导演的生平字段。</p>
<p>2025年中秋的“忌消沉”选句谈用阅读抵抗消沉，没有直接出现月亮或团圆。这是节日主题并非每年硬绑定的反例。我们可以为个人日历提高节日贴合度，但应把它标为自己的偏好。</p>
<h2 id="boundary">年末年初：强日期、弱窗口，多种照顾方式</h2>
<p>本次先写明两组词表，再检查不同宽度的窗口：“更新与时间”包括开始、未来、告别、回首等13个词；“亲密与家庭”包括爱人、家人、团聚、思念等14个词。它们只是透明的字面指标，既不是情绪模型，也覆盖不了消食式双关。</p>''')
labels={'gregorian_new_year_3day':'12/31—1/2','gregorian_new_year_13day':'12/26—1/7','lunar_new_year_3day':'除夕—正月初二','lunar_new_year_10day':'春节前3天—正月初七'}
p.append(table(['窗口','词表命中／样本','窗口外命中率','宜／样本','分年置换 p / BH q'],[(labels[k],f'{v["hits"]}/{v["n"]}（{pct(v["hits"],v["n"])}）',pct(v['outside_hits'],v['outside_n']),f'{v["yi"]}/{v["n"]}',f'{v["p"]:.4f} / {v["bh_q"]:.4f}') for k,v in d['windows'].items()]))
p.append('''<p>公历年界词汇在紧邻日期最集中，窗口扩大后被稀释，但仍高于窗口外。春节的短窗口未显示这套家庭词表明显富集，扩大到10天后仅有较弱信号。这不否认春节编排：原图中的“消化世界”就说明，词表会漏掉重要联系。观察到窗口效应也不能精确还原编辑采用的起止日。</p>
<p>尤其不能把“12/26—1/7”当作已发现的原始硬规则：135个可用页面中96页为宜，仍有39页为忌。这个范围是我们个人日历采用并在本次检查的窗口，不是由数据唯一推导出的最佳窗口；宜也不等于积极情绪。</p>
<div class="grid">''')
p.append(case('2020-12-31','收尾：先承认失去与牵挂','“宜回首”搭配怀念具体之人的表达。年末的照顾可以是允许回望，而不是马上要求振奋。'))
p.append(case('2021-01-01','开篇：把不可能留给希望','“宜希冀”搭配毛姆笔下近乎不可能的信念，可读作允许想象。并不是一条提高完成率的计划建议。'))
p.append(case('2024-12-31','过渡：保留另一种人生的想象','“宜想象对岸”将当前生活与其他可能并置，起承接和打开空间的作用。'))
p.append(case('2025-01-01','开始：先改变看时间的方式','“宜异想天开”配米兰达·裘丽的文字，开篇无需直说新年。它与当年时间主题相容，但不能证明该句为主题专门找到。'))
p.append('</div><h3>连续一周不必编成一条励志曲线</h3>')
p.append(table(['2023年末日期','标题','一种可能的阅读功能'],[(date,raw[date]['title'],reading) for date,reading in [('2023-12-26','挡住外界评判'),('2023-12-27','允许疲惫与幽默'),('2023-12-28','暂时抽身'),('2023-12-29','提醒别靠侥幸'),('2023-12-30','珍惜持续的爱'),('2023-12-31','转向明天')]]))
p.append('<p class="meta">这一段是为展示复杂性选取的案例，不是随机样本；可以读出情绪变化，但不能把读出的顺序宣称为编辑刻意写好的连续剧情。</p>')

p.append('''<h2 id="rhythm">前后日的节奏：这次专门检查了“不成立”的猜想</h2>
<p>将正常宜忌页在同一年、同一月内部打乱2,000次，保留每月作者频数、文本长度分布、词汇比例及缺失日期位置。只比较真实相邻日期，不跨缺页或跨年接线。这样可以检验实际排列是否超出当月素材本身就会产生的分散程度。</p>''')
names={'adjacent_same_author':'相邻日同作者对数','within_7_days_same_author':'相隔1—7天的同作者对数','adjacent_lexical_jaccard':'相邻日8类词汇标记Jaccard均值','adjacent_excerpt_length_difference':'相邻摘录长度差绝对值均值'}
p.append(table(['指标','实际','打乱均值','打乱结果中间95%范围','双侧 p / BH q'],[(names[k],f'{v["observed"]:.4f}',f'{v["null_mean"]:.4f}',f'{v["null_95_interval"][0]:.4f}—{v["null_95_interval"][1]:.4f}',f'{v["p"]:.4f} / {v["bh_q"]:.4f}') for k,v in d['rhythm']['tests'].items()]))
p.append(f'<p>共{d["rhythm"]["pairs"]:,}对真实相邻日与{d["rhythm"]["within_7_pairs"]:,}对相隔1—7天的页面。当前没有足够证据认定存在固定的局部作者轮换、词汇主题接力或长短句交替。匿名、佚名和空署名不当作同一个作者；仅26位已核验作者的别名作分析层归并，未清洗的其他别名仍可能低估重复。</p>')
p.append('''<p class="limit">这里没有“证明编辑不调整顺序”。编辑自述确实有调整环节；检验只是没有在这几项粗指标中检出稳定痕迹。词汇重合不等于语义相似，摘录长度也不等于印刷原文长度；弱而灵活的审美判断可能不被这些指标捕获。</p>
<h2 id="design">对 Tr2e 的启发：先补语义证据，再改选排权重</h2>
<p>现有固件按固定年度安排离线运行，能保证确定性、年内去重和特殊日期优先。此次只提交研究结果，不改动已发布固件或已锁定年度的安排。下面是下一版设计建议，不是原编辑算法的“复原代码”。</p>''')
p.append(table(['现有做法／潜在误差','建议补充','为什么'],[
 ('依靠少量关键词寻找节日、季节内容','保留标题＋选句＋出处的完整关系，增添“日常场景”和“标题如何回应选句”标注','消食、复制粘贴、返工等转译会被主题词漏掉。'),
 ('找到作者生日或忌日便大幅加分','先确认日期证据与人物身份，再检查内容是否适合读者这一天','生日只提供候选，不能替代内容适配；作品人物与导演要分开。'),
 ('年末年初统一积极池','把回望、告别、宽慰、打开可能分开，并保留幽默与适度提醒','避免连续多日像同一种励志标语；外围窗口可以柔和过渡。'),
 ('用宜／忌当正负标签','分别标注正文情绪、标题态度、对读者的作用','宜怀旧可能低落，忌薄情可能在维护关系。'),
 ('把14天作者间隔等规则称作历史规律','继续作为我们自己的阅读舒适度偏好，并允许显式解释','本次统计没有证明原版存在固定的14天门槛。'),
 ('每年只轮换条目','可在未来未锁定年份选一个轻量关注方向，并设置软比例','年度主题能让材料变化有理由；不能借此强行改动已运行的年份。'),
 ('遇到模糊语义也打确定标签','记录不确定、OCR疑点与原图核验状态；优先核对高优先级候选','少量错误字段可能让整个解释方向发生变化。'),
]))
p.append('''<p>对于你的三个私人日期，重点仍是选句的关系：夏至偏共同生活与长久相伴；11月11日偏好奇、玩乐和成长，不让购物节含义盖过去；5月8日偏欣赏一个具体的人、自由与祝福。仅有“爱”字还不够，例如强调为爱情抛开朋友或吞噬式关系的句子，未必适合这些日子。私人含义继续只用于内部甄选。</p>
<p>可为每个候选保留四项可审查的说明：<strong>为什么适合这个日期、为什么适合这位读者、标题如何改变选句的读法、有哪些不宜使用的场景</strong>。运行时只查预编译结果，仍可完全离线；丰富语义并不要求把模型放进设备。</p>
<h2 id="samples">66页固定样本：逐条看我们如何解释</h2>
<p>保留既有excerpt字段，不静默校正文本。8张原图核验结果另行提示；未逐张核验的页面，理解仍可能受截断、OCR或上下文缺失影响。研究分类是可修改的读法。</p>
<div class="filter"><input id="query" type="search" placeholder="搜索日期、标题、作者或解读" aria-label="搜索阅读样本"><select id="relation" aria-label="筛选读法"><option value="">全部读法</option>''')
p.extend(f'<option>{esc(c)}</option>' for c in coding['categories'])
p.append('</select><span id="count" class="meta">66 / 66 页</span></div><div id="samples-list">')
vmap={v['date']:v for v in visual};bycode={r['date']:r for r in coding['records']}
for r in d['semantic_sample']:
 c=bycode[r['date']];p.append(f'<details class="sample" data-relation="{esc(c["relation"])}"><summary>{esc(r["date"])} · {esc(r["title"])} · {esc(c["relation"])}</summary><p class="meta">署名：{esc(r["author"])} · 出处：{esc(r["source"])}</p><blockquote>{esc(r["excerpt"])}</blockquote><p>{esc(c["reason"])}</p>')
 if r['date'] in vmap:p.append(f'<p class="visnote">原图复核：{esc(vmap[r["date"]]["finding"])}</p>')
 p.append(f'<p>{link(r["url"],"打开原图")}</p></details>')
p.append('</div><h2 id="method">方法、未解决的问题与可复查文件</h2>')
p.append('''<p>统计单位是公开图片地址对应的既有索引记录，不是确认完整的App数据库，也不是每一个纸质版本。排除规则与前两轮一致；跨日作者比较新增对匿名署名的排除。之前报告的3,907个标题包含2条没有excerpt的记录，本轮配对统计为3,905，因此相邻对数也从3,835降至3,831。不同分析分母不混用。</p>
<p>置换种子固定20261105，每项2,000次；节日窗口以年内打乱作比较，节奏以年＋月内打乱作比较。两组各4项分别用Benjamini–Hochberg校正；探索性分析、词表与窗口经过研究者选择，校正不能消除这些选择偏差。报告中的95%范围是置换结果的中间范围，不是效果估计的置信区间。</p>
<p>农历来自已校验的本地历表，春节按非闰正月初一，除夕按春节前一天，避免固定为腊月三十。未核查传统黄历宜忌、干支、法定调休表，也未作全体作者生卒日普查。标题短小与词汇相似度均不等于语义或情绪标签。</p>
<p>66页抽样每年每两月取1页，2015年前两个月仅从可用页面抽取；它不是从完整4018天均匀抽样，也没有独立第二标注员。用于展示机制和发现反例，不给分类结果加虚假的精确置信度。重点案例另行选择，与随机样本明确分开。</p>
<p>8张临时原图的SHA-256均与既有索引一致。原图还显示，有的疑似错字本来就印在图上：2017-09-10的“蒙味”、2023-12-27的“聚中”均不能径直认定是OCR错误。本轮记录问题，但不改写月份源记录。图片仅临时核验，不加入仓库。</p>
<p>下一步最有价值的工作是给将来高优先级使用的候选补做完整语义标注与原图核验，再用一个尚未锁定的年份对比新旧方案；不是继续增加无依据的日期硬规则。</p>
<p>本地证据：<a href="../editorial_thinking/results.json">全量统计与66页样本</a> · <a href="../editorial_thinking/readings.json">逐条读法</a> · <a href="../editorial_thinking/sources.json">公开制作证言</a> · <a href="../editorial_thinking/visual_checks.json">8张原图核验</a> · <a href="../analyze_editorial_thinking.py">统计脚本</a> · <a href="../editorial_thinking/code_readings.py">标注脚本</a> · <a href="../render_editorial_thinking.py">报告生成器</a></p>
<p>前期研究：<a href="标题与日期关联分析.html">标题与日期</a> · <a href="内容编排规律分析.html">标题、选句与作者生卒日</a> · <a href="2020排版与Tr2e离线日历研究.html">2020版式及离线原型</a></p>
<p class="meta">复现顺序：analyze_editorial_thinking.py → editorial_thinking/code_readings.py → render_editorial_thinking.py。Python运行环境需NumPy；不联网、不改变源数据、不重新生成设备年度计划。</p>
</main><script>const cards=[...document.querySelectorAll('.sample')];const query=document.getElementById('query'),relation=document.getElementById('relation');function filter(){const q=query.value.trim().toLowerCase();let n=0;for(const card of cards){const show=(!relation.value||card.dataset.relation===relation.value)&&(!q||card.textContent.toLowerCase().includes(q));card.hidden=!show;if(show)n++;}document.getElementById('count').textContent=n+' / '+cards.length+' 页';}query.addEventListener('input',filter);relation.addEventListener('change',filter);</script></html>''')
target=ROOT/'output/编辑思考逻辑深度研究.html'
target.write_text('\n'.join(p),encoding='utf-8');print(target)
