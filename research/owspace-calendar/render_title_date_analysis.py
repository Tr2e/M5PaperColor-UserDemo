"""Render a compact, self-contained evidence report; no media downloads."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'title_date_analysis/results.json').read_text())
esc = lambda x: html.escape(str(x if x is not None else '—'))

def table(head, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>'+esc(x)+'</th>' for x in head) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

parts = ['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单向历：标题与日期的关联分析</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;background:#f7f5ef;color:#252b2b;max-width:1080px;margin:auto;padding:32px 24px;line-height:1.75}h1{font-size:30px;line-height:1.4}h2{margin-top:40px;border-top:1px solid #ccc;padding-top:24px}h3{margin-top:26px}p{max-width:900px}table{border-collapse:collapse;width:100%;background:white;font-size:14px;margin:12px 0}th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #ddd;vertical-align:top}th{background:#e9eee9}.scroll{overflow:auto}a{color:#276a63}.callout{padding:18px 24px;background:#e7eee7;border-left:4px solid #537966}.muted{color:#606b69;font-size:14px}details{background:white;margin:10px 0;padding:12px 16px}summary{cursor:pointer;font-weight:600}.bar{display:inline-block;height:10px;background:#537966;border-radius:2px;vertical-align:middle;margin-right:10px}@media print{body{background:white;padding:0}details{break-inside:avoid}a{color:inherit}}</style>
<h1>单向历：标题与日期的关联分析</h1><p class="muted">2015—2025 · 分析日期：2026-11-03 · 仅分析既有索引的标题与日期，未改动内容记录</p>
<p class="callout"><strong>存在明显的日期主题关联，但没有证据支持一个能从日期直接算出标题的固定公式。</strong><br>最强的线索来自特定节日、纪念日和季节意象；星期、每月第几天对“宜／忌”的解释力较弱。跨年常延续主题，极少复用同一标题。</p>
<h2>样本与方法</h2><p>原表覆盖 4,018 个日期。排除 49 个缺失页面、10 个已知图中日期与文件日期不符的记录，再排除 52 个问答或其他版式页面，共分析 <strong>3,907 个宜忌标题</strong>。节日附录仍列出问答页面，并明确显示无宜忌标题。2015 年和 2025 年等年份存在缺失，年度比例是有效样本比例。</p>
<p>农历节日和节气按<a href="https://www.hko.gov.hk/tc/gts/time/conversion.htm">香港天文台公历与农历对照表</a>对齐，避免把七夕、中秋等错误地固定在公历同一天。标题沿用既有 OCR 字段，本次未逐张复核标题；作者审校不等于标题已完成人工校对。</p>
<h2>1. 节日是最清楚的线索</h2>
''']
parts.append(table(['日期／节日','跨年证据','可支持的判断'],[
('1 月 1 日','10 个有效标题全部为“宜”；宜开始、宜新生、宜希冀、宜小目标','倾向开始、愿景与想象；措辞不固定'),
('12 月 31 日','11/11 为“宜”；宜回首、宜明天、宜翻页、宜再见明天','年末回望和面向明天'),
('除夕／春节','除夕 11/11、春节 10/10 个宜忌标题为“宜”；春节另有 1 个问答页','亲人、团聚、返乡、辞旧迎新'),
('4 月 23 日','11 年中 6 次直接包含“书”或“读”；2018、2019 均为宜翻书','阅读主题高度集中'),
('6 月 1 日','宜单纯、宜尿床、忌老成、宜好奇、忌心机、宜天真、宜玩乐','童真主题，正说与反说并用'),
('七夕','宜缠绵、忌走肾、宜打情骂俏、忌分离、宜琴瑟和鸣、宜彼此支撑','亲密关系主题随农历日期移动'),
('中秋','宜花前月下、宜团圆、宜共此时、宜赏月、宜望月随想','月亮、团聚、思念等主题，但存在例外'),
('5 月 1 日','2017 宜大睡；2018、2019 宜偷懒；2021 宜不劳动；2025 宜劳作','可以顺着节日写，也可以反向表达'),
('12 月 1 日','2018、2019、2021 均为忌歧视','与纪念日议题吻合，是普通日期之外的隐藏线索'),
]))
parts.append('''<p>4 月 23 日为<a href="https://www.unesco.org/en/days/world-book-and-copyright?hub=66691">世界图书与版权日</a>。该日标题命中“书／读”的比例为 6/11（54.5%），全体标题为 32/3,907（0.82%）；去掉该日后为 26/3,896（0.67%）。这里只计算透明的字面命中，未把“神交”“沉浸式体验”等主观判为阅读，也不能用此比例代表全部节日的关联强度。</p>
<p>12 月 1 日是<a href="https://www.unaids.org/en/World_AIDS_Day">世界艾滋病日</a>，其议题包含消除污名与歧视。“忌歧视”的重复与这一议题一致；这是内容关联证据，尚不足以证明编辑的具体意图。</p>
<p>例外同样重要：春节曾出现“宜解除”“宜珍视个人”，2025 年中秋为“忌消沉”。日期主题并不要求每年的标题都直接点明节名；有时需要结合选句理解，本报告未对选句与日期做完整语义标注。</p>
<h2>2. 季节意象存在，但节气并非每天都直译</h2>
<p>包含“夏／暑／纳凉”的 9 个标题全部位于 5—8 月；包含“冬／雪”的 13 个标题全部位于 11—1 月。春秋用词也常落在相应季节，但“青春”“如沐春风”“悲春伤秋”等比喻会造成字面统计误判。因此，这部分说明季节意象的集中分布，不能当成所有标题的自动分类结果。</p>
<p>具体例子：2021-05-05 立夏“宜等待夏天”、2021-08-07 立秋“宜迎秋风”、2022-07-07 小暑“宜纳凉”、2023-09-23 秋分“宜踏秋”、2024-07-22 大暑“宜赏味夏天”、2025-09-23 秋分“宜赏秋色”。而多数年份的夏至、冬至没有直接写“夏”“冬”，关联并非统一硬规则。</p>
<h2>3. 星期与宜忌：有轻微倾向，没有固定排班</h2>''')
parts.append(table(['星期','有效标题数','宜的比例'],[('周'+'一二三四五六日'[r['group']],r['n'],str(r['yi_pct'])+'%') for r in data['weekday']]))
parts.append('''<p>周末“宜”为 71.0%，周一至周五为 66.7%，相差约 4.3 个百分点。星期与宜忌的关联强度很小（Cramér’s V=0.062），逐年也不稳定，不能据此设定“周末一律宜”或“周一固定忌”。此处周末仅指星期六、星期日，未计入法定假日及调休。</p>
<p>年度风格差异更明显：2020 年“宜”占 58.0%，2024 年占 79.9%。这是有效样本的观察结果，可能涉及年度选材或编辑偏好，不能单凭比例确定原因。</p>''')
parts.append(table(['年份','有效标题数','宜的比例'],[(r['group'],r['n'],str(r['yi_pct'])+'%') for r in data['year']]))
parts.append('''<h2>4. 未发现机械循环或固定标题库映射</h2>
<p>将不同年份的同月同日两两比较，共 18,979 对，只有 14 对标题完全相同，占 <strong>0.074%</strong>。随机在各年内打乱标题，平均约出现 3.8 对重复：实际重复确实更集中于同日期，但绝对比例很低。少数重复能指向读书日、劳动节等主题，不能据此预测其余绝大多数标题。</p>
<p>相邻两天“宜／忌”不同的比例为 45.01%，按各年比例随机排布的期望为 42.93%。只有约 2.1 个百分点的差异，并非隔天交替。3,835 个相邻日期对中，还有 1,735 对“宜→宜”和 374 对“忌→忌”。缺失或非宜忌页面之间不作跨页连接，跨年也不连接。</p>
<p>每月第几天、农历初几与宜忌的检验均未给出强证据。不过，本次没有检验干支、生肖、黄历宜忌内容，不能宣称已排除一切传统历法关联。</p>
<h2>可用于理解编排的模型（推测）</h2>
<p class="callout">特殊日期提供主题 → 季节提供生活场景 → 选材转化为简短的情绪或行动提示 → 以“宜／忌”正向或反向表达，并随年度变化措辞。</p>
<p>这一模型能解释“劳动节宜不劳动”“儿童节忌老成”“七夕忌分离”。它是从结果归纳出的工作假设；现有数据无法证明标题和选句谁先确定，也无法还原编辑部流程。若用于复现类似日历，可以把节日视作主题约束，把普通日视作自由选材空间，而不要把日期数字当作标题生成公式。</p>
<h2>逐节日、节气的全部对照</h2><p class="muted">点击展开查看每年标题、作者、出处和原图链接。无标题的问答页面保留作缺失说明。作者和出处只提供核查线索，未用来自动判定主题。</p>''')
for name, rows in data['events'].items():
    yi = sum(r['title_kind']=='宜' for r in rows)
    ji = sum(r['title_kind']=='忌' for r in rows)
    parts.append(f'<details><summary>{esc(name)} · 宜 {yi} / 忌 {ji} / 其他 {len(rows)-yi-ji}</summary><div class="scroll"><table><thead><tr><th>日期</th><th>标题</th><th>作者</th><th>出处</th><th>原图</th></tr></thead><tbody>')
    for r in rows:
        parts.append('<tr>'+''.join('<td>'+esc(r[k])+'</td>' for k in ('date','title','author','source'))+f'<td><a href="{esc(r["url"])}" target="_blank" rel="noopener">查看</a></td></tr>')
    parts.append('</tbody></table></div></details>')
parts.append('<h2>统计口径与复现</h2><p>以下检验均为探索性结果，未作多重比较校正；不应单独以 p&lt;0.05 宣称存在稳定编辑规则。置换在各年内进行，保留每年的宜忌或标题分布；随机种子 20261103。星期、月份、月内日和农历日检验仅检查“宜／忌”，不等价于完整标题语义检验。</p>')
parts.append(table(['检验','Cramér’s V','分年置换 p','置换次数'],[(label,data[k]['cramers_v'],round(data[k]['year_stratified_permutation_p'],5),data[k]['permutations']) for label,k in [('星期→宜忌','weekday_test'),('月份→宜忌','month_test'),('公历日号→宜忌','day_of_month_test'),('农历日号→宜忌','lunar_day_test')]]))
parts.append('''<p>数据和脚本：<a href="../title_date_analysis/results.json">统计结果 JSON</a> · <a href="../title_date_analysis/calendar_reference.json">农历与节气对照</a> · <a href="../analyze_title_dates.py">分析脚本</a> · <a href="../fetch_calendar_reference.py">官方历表获取脚本</a>。分析脚本依赖 NumPy；先获取历表，再运行分析脚本，最后运行 render_title_date_analysis.py 生成本报告。原始月份记录保持不变。</p></html>''')
target = ROOT / 'output/标题与日期关联分析.html'
target.write_text(''.join(parts), encoding='utf-8')
print(target)
