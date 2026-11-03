# -*- coding: utf-8 -*-
"""Render the author audit without copying any quotation bodies."""
import html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;A=ROOT/'author_audit';E=lambda s:html.escape(str(s if s is not None else '—'))
def build():
 s=json.loads((A/'summary.json').read_text());changes=json.loads((A/'changes.json').read_text());v=json.loads((A/'visual_decisions.json').read_text());f=json.loads((A/'foreign_decisions.json').read_text());d={k:{**v.get(k,{}),**f.get(k,{})} for k in v.keys()|f.keys()}
 out=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单向历作者姓名核对清单</title><style>body{font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#202b35;max-width:1200px;margin:36px auto;padding:0 22px;overflow-wrap:anywhere}h1{font-size:30px}h2{margin-top:38px}a{color:#145b89}table{border-collapse:collapse;width:100%;font-size:14px;min-width:740px}td,th{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dde3e7;overflow-wrap:anywhere}th{background:#edf2f5}.wrap{overflow:auto}input{font:inherit;padding:9px;width:min(520px,90%)}.note{color:#53606c}.pill{display:inline-block;background:#edf2f5;padding:6px 12px;margin:4px}.issue{background:#fff3db}small{color:#53606c}button{font:inherit;padding:9px;margin-left:8px}</style><main><h1>单向历作者姓名核对清单</h1><p>2015—2025 年 · 2026 年 11 月 3 日核对</p><p><a href="单向历2015至2025年历史内容索引.html">打开修正后的完整统计表</a></p>''']
 for label,key in [('日期记录扫描','date_records_scanned'),('原有不同署名','distinct_original_author_values'),('原图署名区重新识别','original_image_regions_reprocessed'),('逐图目视复核记录','visually_reviewed_records'),('发生修正的日期','changed_records'),('中文／主署名修正','changed_author_fields'),('外文署名修正','changed_foreign_name_fields')]:out.append(f'<span class="pill">{label} <b>{s[key]:,}</b></span>')
 out.append(f'<p>主署名和外文署名的修正次数可重叠，同一天只计一条修正记录。全部 {s["protected_records_verified"]:,} 条记录的选句、职业、出处、标题、日期及其他非姓名字段已通过逐条哈希校验，内容保持原样。</p><h2>核对范围与规则</h2><p>先扫描所有已有作者值，筛选错字、乱码、职业混入、缺失缩写、多作者粘连等问题；再重新读取原图署名区，对可疑差异逐图核对。外文同时使用多语种和拉丁语种 OCR 比对，未出现字符差异的记录保留原值。该部分属于机器比对，不能算作逐图目视核验。</p><p>按原图恢复韩文、日文、俄文、希腊文等字符。不根据熟悉程度统一所有译名，不根据书名猜补未署名的作者。原图自身存在错拼或中外文冲突时保留其印刷署名，单独标记；核对结果用于订正 OCR，不代表已完成作者身份考证。</p>')
 out.append('<h2>原图署名问题与未确定项</h2><div class="wrap"><table><thead><tr><th>日期／原图</th><th>当前署名</th><th>说明</th></tr></thead><tbody>')
 for date in sorted(set(s['source_conflicts']+s['source_suspected_errors'])):
  r=d[date];url=f'https://img.owspace.com/Public/uploads/Download/{date[:4]}/{date[5:7]}{date[8:]}.jpg'
  # Resolve missing unchanged fields from the preserved baseline.
  base=next(x for x in json.loads((A/'baseline.json').read_text()) if x['date']==date)
  name=r.get('author',base.get('author'));foreign=r.get('author_foreign_name',base.get('author_foreign_name'))
  out.append(f'<tr class="issue"><td><a href="{url}">{date}</a></td><td>{E(name)}<br><small>{E(foreign)}</small></td><td>{E(r["note"])}</td></tr>')
 out.append('</tbody></table></div><h2>逐条修改清单</h2><p class="note">仅列实际改动；未改变的目视复核结果保存在 author_audit/visual_decisions.json 与 foreign_decisions.json。每项均可点击原图核验。</p><label for="q">搜索日期、原名或修正后的姓名</label><p><input id="q" placeholder="例如 韩江、茅盾、한강"><button id="clear">清空</button></p><p id="count" aria-live="polite"></p><div class="wrap"><table><thead><tr><th style="width:110px">日期／原图</th><th>修改前</th><th>修改后</th><th>核对说明</th></tr></thead><tbody>')
 for c in changes:
  old=[];new=[]
  for k,x in c['changes'].items():
   label='主署名' if k=='author' else '外文';old.append(f'<small>{label}</small><br>{E(x["before"])}');new.append(f'<small>{label}</small><br>{E(x["after"])}')
  out.append(f'<tr class="change"><td><a href="{E(c["url"])}">{c["date"]}</a></td><td>'+ '<br>'.join(old)+'</td><td>'+'<br>'.join(new)+f'</td><td>{E(c["note"])}</td></tr>')
 out.append('''</tbody></table></div><h2>追溯与校验</h2><p>本轮基线为 Git 提交 <code>'''+E(s['baseline_commit'])+'''</code>。修正按月份提交；每条记录保留修改前后值和原图 SHA-256。重新读取的原图哈希均与原始采集一致。未把原图图片或新引文加入仓库。</p><p class="note">本清单只核对作者字段。原统计表的日期错配标记继续保留；存在译名变体、笔名、同名或演员／角色署名时，进行作者频次统计前仍需确定统计口径。</p></main><script>const q=document.querySelector('#q'),rows=[...document.querySelectorAll('.change')];function filter(){let n=0;for(const r of rows){r.hidden=!r.textContent.toLowerCase().includes(q.value.trim().toLowerCase());if(!r.hidden)n++}document.querySelector('#count').textContent=`显示 ${n} 条修正记录`}q.oninput=filter;document.querySelector('#clear').onclick=()=>{q.value='';filter()};filter();</script></html>''')
 p=ROOT/'output'/'作者姓名核对清单.html';p.write_text(''.join(out));print(p)
if __name__=='__main__':build()
