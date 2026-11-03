#!/usr/bin/env python3
"""Build an offline index document and a compact Word research report."""
from collections import Counter
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
E = lambda value: html.escape(str(value or "—"), quote=True)
FLAG_NAMES = {
    "title_unresolved": "标题未识别", "multiple_title_candidates": "多个标题候选",
    "author_unresolved": "作者未识别", "source_not_detected": "出处未检出",
    "low_ocr_confidence": "OCR低置信度",
}


def load():
    months = {p.stem: [json.loads(x) for x in p.read_text().splitlines()] for p in sorted((ROOT / "months").glob("*.jsonl"))}
    reviews = [json.loads(p.read_text()) for p in sorted((ROOT / "years").glob("*-review.json"))]
    layouts = {int(p.name[:4]): json.loads(p.read_text()) for p in (ROOT / "years").glob("*-layout.json")}
    return months, reviews, layouts


def make_html(months, reviews, layouts):
    rows = [r for month in months.values() for r in month]
    indexed = [r for r in rows if r["status"] == "indexed"]
    missing = sum(r["status"] == "missing_at_tested_url" for r in rows)
    out = ["""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>单向历 2015 至 2025 年历史内容索引</title><style>
body{max-width:1180px;margin:44px auto;padding:0 24px;color:#202020;background:#fff;font:16px/1.75 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}
h1{font-size:32px;line-height:1.4}h2{font-size:25px;margin-top:50px}h3{font-size:20px;margin-top:34px}p{max-width:920px}a{color:#175e86}table{width:100%;border-collapse:collapse;margin:18px 0 30px;font-size:14px;table-layout:fixed}th,td{padding:10px 11px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{background:#f1f3f4;color:#111}tr:nth-child(even){background:#fafafa}.date{width:104px}.title{width:145px}.author{width:180px}.state{width:140px}.muted{color:#626262;font-size:13px}.missing{color:#666}.nav{display:flex;gap:18px;flex-wrap:wrap}input{font:inherit;padding:8px 12px;width:min(460px,90%);border:1px solid #999}button{font:inherit;padding:8px 12px;margin-left:8px}caption{text-align:left;font-weight:600;padding:8px 0}.year{scroll-margin-top:20px}.month{scroll-margin-top:20px}@media print{body{margin:0;padding:0;font-size:10pt}h2{break-before:page}.controls,.nav{display:none}thead{display:table-header-group}tr{break-inside:avoid}a{color:#222;text-decoration:none}table{font-size:8pt}}
</style><main><h1>单向历 2015 至 2025 年历史内容索引</h1>"""]
    out.append(f"<p>按年分析版式、按月整理的历史元数据索引。覆盖 <strong>{len(rows):,}</strong> 个日期，其中 <strong>{len(indexed):,}</strong> 个标准地址返回可识别图片，<strong>{missing}</strong> 个返回 404 或 410。查询日期为 2026 年 11 月 3 日。</p>")
    out.append("<p>本索引收录日期、宜忌短标题、作者、出处和官方图片链接，不收录完整选句。字段为机器提取，尚未逐条人工校对；空值不等同于原图没有该信息。日期来自请求地址，图片内日期尚未逐张确认。链接失效只说明测试的标准地址不可读取。</p>")
    out.append('<nav class="nav">' + ' '.join(f'<a href="#year-{r["year"]}">{r["year"]}</a>' for r in reviews) + '</nav>')
    out.append('<h2>年度覆盖情况</h2><table><thead><tr><th>年份</th><th>日期记录</th><th>图片可读</th><th>标题非空</th><th>作者非空</th><th>出处非空</th><th>地址缺失</th></tr></thead><tbody>')
    for r in reviews:
        out.append('<tr>' + ''.join(f'<td>{v}</td>' for v in [r['year'],r['record_count'],r['status_counts'].get('indexed',0),r['field_counts']['title'],r['field_counts']['author'],r['field_counts']['source'],r['status_counts'].get('missing_at_tested_url',0)]) + '</tr>')
    out.append('</tbody></table><p class="muted">非空字段数反映提取覆盖，不是准确率。同一作者的 OCR 异体和错字未做无依据的合并，不能直接用作精确的作者排名。</p>')
    out.append('<h2>检索索引</h2><div class="controls"><label for="search">搜索日期 标题 作者 出处</label><br><input id="search" placeholder="例如 2020-06 或 卡夫卡"><button id="clear" type="button">清空</button><p id="hits" aria-live="polite"></p></div>')
    for review in reviews:
        year = review['year']
        layout = layouts[year]
        kinds=review['title_kind_counts']
        out.append(f'<section class="year" id="year-{year}"><h2>{year} 年</h2><p>{E(layout["layout"])}</p><p>已识别标题中，宜 {kinds.get("宜",0)} 条，忌 {kinds.get("忌",0)} 条。</p><p class="muted">版式抽查：{E("、".join(layout["sample_dates"]))}。规则：{E(" ".join(layout["rules"]))}</p>')
        for key, batch in months.items():
            if not key.startswith(str(year)):
                continue
            out.append(f'<section class="month"><h3 id="month-{key}">{key}</h3><table><thead><tr><th class="date">日期及原图</th><th class="title">宜忌标题</th><th class="author">作者</th><th>出处</th><th class="state">识别状态</th></tr></thead><tbody>')
            for row in batch:
                status = row['status']
                if status == 'indexed':
                    flags = '；'.join(FLAG_NAMES.get(f,f) for f in row.get('review_flags',[]))
                    state = '样本字段已核对' if row.get('review_status') == 'sample_metadata_verified' else flags or '机器提取 未逐条校对'
                elif status == 'missing_at_tested_url':
                    state = f'标准地址 HTTP {row["http_status"]}'
                else:
                    state = '处理异常 ' + status
                search = ' '.join(str(row.get(k) or '') for k in ['date','title','author','source'])
                out.append(f'<tr class="record" data-search="{E(search.lower())}"><td><a href="{E(row["url"])}" target="_blank" rel="noopener noreferrer">{E(row["date"])}</a></td><td>{E(row.get("title"))}</td><td>{E(row.get("author"))}</td><td>{E(row.get("source"))}</td><td class="muted">{E(state)}</td></tr>')
            out.append('</tbody></table></section>')
        out.append('</section>')
    out.append('''<h2>来源及复核方法</h2><p>数据来源为单向空间公开图片服务器。每条日期链接指向其标准 JPG 地址；索引保存请求状态、图像哈希和检查时间，可与按月 JSONL 数据核对。原图仅用于临时识别，未纳入仓库。</p><p>要分析选材或作者分布，应先逐条核对所用样本的作者与出处。宜忌比例只能描述标题形式，无法单独证明情绪倾向；本索引不包含选句，因此不能据此完成全文语义分析。</p></main><script>
const input=document.querySelector('#search'),records=[...document.querySelectorAll('.record')];
function filter(){let q=input.value.trim().toLowerCase(),n=0;for(const r of records){r.hidden=q&&!r.dataset.search.includes(q);if(!r.hidden)n++}for(const m of document.querySelectorAll('.month'))m.hidden=![...m.querySelectorAll('.record')].some(r=>!r.hidden);for(const y of document.querySelectorAll('.year'))y.hidden=![...y.querySelectorAll('.month')].some(m=>!m.hidden);document.querySelector('#hits').textContent=`显示 ${n.toLocaleString()} 条日期记录`;}
input.addEventListener('input',filter);document.querySelector('#clear').onclick=()=>{input.value='';filter();};filter();
</script></html>''')
    path = OUTPUT / '单向历2015至2025年历史内容索引.html'
    path.write_text(''.join(out), encoding='utf-8')
    return path


def make_docx(months, reviews, layouts):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(.75)
    sec.left_margin = sec.right_margin = Inches(.8)
    for style in doc.styles:
        if style.type not in (1,2):
            continue
        style.font.name='Noto Sans CJK SC';style.font.color.rgb=RGBColor(0,0,0)
        fonts=style.element.get_or_add_rPr().rFonts
        for attr in list(fonts.attrib):
            del fonts.attrib[attr]
        for attr in ['ascii','hAnsi','cs','eastAsia']:
            fonts.set(qn('w:'+attr),'Noto Sans CJK SC')
        for border in list(style.element.iter(qn('w:pBdr'))):
            border.getparent().remove(border)
    doc.styles['Normal'].font.size=Pt(10)
    doc.styles['Normal'].paragraph_format.space_after=Pt(7)
    doc.styles['Normal'].paragraph_format.line_spacing=1.15
    doc.styles['Title'].font.size=Pt(24)
    doc.styles['Heading 1'].font.size=Pt(16)
    doc.styles['Heading 2'].font.size=Pt(12)
    doc.add_paragraph('单向历历史内容索引研究报告',style='Title')
    doc.add_paragraph('2015 至 2025 年',style='Subtitle')
    total=sum(r['record_count'] for r in reviews)
    available=sum(r['status_counts'].get('indexed',0) for r in reviews)
    missing=sum(r['status_counts'].get('missing_at_tested_url',0) for r in reviews)
    doc.add_paragraph(f'本研究按年分析日历版式，再按月提取日期、宜忌短标题、作者与出处，并附官方图片链接。共检查 {total:,} 个日期，取得 {available:,} 个可读取页面，另有 {missing} 个标准地址返回 404 或 410。完整逐日记录见同目录的离线 HTML 索引文档。')
    doc.add_paragraph('索引不含完整选句。所有自动识别字段均需核对原图后用于严谨统计；字段非空率不等于识别准确率。检查日期为 2026 年 11 月 3 日。')
    doc.add_heading('年度覆盖情况',level=1)
    table=doc.add_table(rows=1, cols=6)
    for c,t in zip(table.rows[0].cells,['年份','日期数','图片可读','标题','作者','出处']): c.text=t
    for r in reviews:
        for c,v in zip(table.add_row().cells,[r['year'],r['record_count'],r['status_counts'].get('indexed',0),r['field_counts']['title'],r['field_counts']['author'],r['field_counts']['source']]): c.text=str(v)
    for i,row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(4)
                p.paragraph_format.space_before=Pt(4)
                for run in p.runs:run.font.size=Pt(9)
            if i==0:
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F2F3F5');cell._tc.get_or_add_tcPr().append(shade)
    doc.add_paragraph('表中标题、作者和出处列均为非空字段数。原图未署名、识别遗漏和规则无法判断，都可能造成空值。',style='Caption')
    doc.add_page_break()
    doc.add_heading('提取方法与使用边界',level=1)
    paragraphs=[
      ('逐年定位','先查看当年跨季度样本，记录标题与页脚的位置。版式规则单独保存，完成本年覆盖检查后才进入下一年。'),
      ('逐月保存','每月按真实日历生成全部日期，逐日查询标准图片地址。成功、缺失和错误均保留记录，每月单独提交。网络异常与图片缺失分别记录。'),
      ('书目拆分','从标题区域提取以宜或忌开头的短标题，从对应年份的署名区域拆分作者与书名。职业前缀可以缺省，同排多个 OCR 片段按位置合并。'),
      ('原图链接','每条记录保存官方地址、HTTP 状态、检查时间和图像 SHA-256。临时图像在识别后删除，不把原图或完整选句加入资料集。'),
      ('人工核对','本报告完成日期覆盖与字段结构检查，没有逐条确认四千余张图片的文字。尤其是罕见人名、外文、书名号和相近汉字，仍可能误识。低置信度标记用于优先复核，未标记不代表无误。'),
      ('缺失的含义','标准地址返回 404 或 410，不等于当日没有发行。地址可能变化，也可能是图片未上传。作者或出处空白也不能直接断言原图没有署名。'),
      ('统计解释','日期由 URL 推导，尚未逐张核对图内日期。作者分布应先校正异体、错字和译名；宜忌比例仅描述标题形式，不是情感分类或编辑决策的证据。')]
    for title,text in paragraphs:
        doc.add_heading(title,level=2);doc.add_paragraph(text)
    doc.add_page_break()
    doc.add_heading('年度版式变化',level=1)
    for year in range(2015,2021):
        if year in layouts:
            doc.add_heading(f'{year} 年',level=2)
            doc.add_paragraph(layouts[year]['layout'])
    doc.add_page_break()
    doc.add_heading('年度版式变化续',level=1)
    for year in range(2021,2026):
        if year in layouts:
            doc.add_heading(f'{year} 年',level=2)
            doc.add_paragraph(layouts[year]['layout'])
    doc.add_heading('后续内容编排研究',level=1)
    doc.add_paragraph('本索引可支持按日期寻找样本、核查作者与作品的出现频率，以及比较标题形式。研究节日关联、情绪节奏、标题与引文的关系时，需要逐页阅读原图并建立经过核对的分析样本，不能仅凭版式或标题推断内部编辑流程。')
    doc.add_paragraph('来源：单向空间公开图片服务器 https://img.owspace.com/Public/uploads/Download/ 。逐日链接及机器识别状态见离线索引。')
    path=OUTPUT/'单向历历史内容索引研究报告.docx'
    doc.save(path)
    return path


if __name__ == '__main__':
    OUTPUT.mkdir(exist_ok=True)
    data=load()
    print(make_html(*data))
    print(make_docx(*data))
