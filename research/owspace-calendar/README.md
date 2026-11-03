# 单向历历史内容索引

覆盖日期范围为 2015-01-01 至 2025-12-31，共 4,018 个日期。索引按月份保存并提交，内容包括日期、宜忌短标题、作者、出处、作者角色和官方图片链接。不收录完整选句，也不归档原图。

## 数据与可信度

- `months/YYYY-MM.jsonl`：每个日期一条记录，包括失败日期。
- 日期由请求 URL 生成；尚未逐张核对图片内日期，不等于已经验证图片日期。
- `indexed` 表示资源可读取且 OCR 已运行，不代表字段全部正确。
- `missing_at_tested_url` 仅表示该日期的标准 JPG 地址返回 404 或 410，不能推断当天未出版。
- `source_not_detected` 包含原图未注明出处和 OCR 漏识别两种可能。
- 所有自动识别记录标为未人工核验。置信度是 OCR 引擎的启发式分数，不能当作准确率。
- 字段为空时不猜测补全；图像 SHA-256 可用于检查重复资源，但不存储图像。
- 临时图片用于本地 OCR，处理结束立即删除。引文正文不序列化，不保存 OCR 全文。
- `sample_metadata_verified` 表示该日期的标题、作者、出处已对照原图核对；人工修正前的值保留在 `metadata_edits` 和 Git 历史中。
- 2023 年的 `reader_question` 页面没有宜忌标题，使用 `title_kind: 问答` 和空标题，不将其计作标题漏识别。
- 标准地址虽以 `.jpg` 结尾，也可能返回 PNG；实际格式由文件签名判断。
- 全部 4,018 个日期中有 3,969 个可读地址、49 个标准地址缺失；另有 10 个可读地址返回其他日期的图片，已人工核验并标记。字段计数包含这些实际返回值，不能直接按网址日期进行内容研究。
- 2024 年额外核查图内月份，2025 年核查月份与日号；2024 年日号被标题切开，机器读数不可靠，未用于自动判断。`image_date_ocr` 为机器候选，`date_verification` 为人工结论，发生冲突时以人工结论为准。

## 阅读结果

- `output/单向历2015至2025年历史内容索引.html`：离线检索全部日期，按年、月浏览，打开官方原图复核。
- `output/单向历历史内容索引研究报告.docx`：覆盖情况、方法、年度版式变化及内容编排观察。
- `years/YYYY-layout.json` 与 `years/YYYY-review.json`：年度规则、覆盖审查、缺失记录与待复核字段数量。
- `verified_samples.json`：逐张查看过的样本字段，不代表全量准确率。
- `verified_dates.json`：人工核对的图内日期；`output/collection-audit.json`：全量覆盖、字段数量、日期冲突和月文件哈希。

范围是公开图片服务器的日期索引，不是 App 数据库备份；没有证明 App 与公开服务器的历史内容完全一致，也没有验证 App 是否停止维护。2015 年的标准地址可用范围与请求范围不同，详情见年度审查。完整选句和较长正文不在本次资料集中。

## 复现

在 macOS 上使用系统 Vision 框架和 Python 标准库。无需 App 账号、登录或安装包。

```sh
mkdir -p /tmp/owspace-research
swiftc -O -module-cache-path /tmp/owspace-research/swift-cache research/owspace-calendar/ocr_metadata.swift -o /tmp/owspace-research/ocr_metadata
python3 research/owspace-calendar/index_calendar.py --start 2015-01 --end 2015-12 --commit
python3 research/owspace-calendar/apply_verified.py 2015 --commit
python3 research/owspace-calendar/tidy_roles.py 2015 --commit
python3 research/owspace-calendar/review_year.py 2015
```

每次只处理一年。先保存该年 `years/YYYY-layout.json` 版式分析，再逐月提取，最后执行全年检查；前一年覆盖检查通过后才能开始下一年。默认 3 个工作线程，所有网络请求合计最多每秒 4 次；临时网络错误最多重试 3 次。脚本可中断续跑。`--commit` 只允许在 `codex/owspace-calendar-index-2015-2025` 分支运行，只提交对应月份的数据文件。

原始来源：`https://img.owspace.com/Public/uploads/Download/{YYYY}/{MMDD}.jpg`。

`build_documents.py` 依赖 python-docx，用于重新生成 HTML 与 Word 报告。Word 文档使用 Noto Sans CJK SC；重新渲染时需准备该字体。`test_metadata.py` 覆盖书目拆分的典型错误，`qa_index.cjs` 使用 Playwright 与 Chrome 验证检索和页面布局。
