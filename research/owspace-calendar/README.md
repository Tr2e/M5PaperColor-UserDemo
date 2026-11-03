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

## 复现

在 macOS 上使用系统 Vision 框架和 Python 标准库。无需 App 账号、登录或安装包。

```sh
mkdir -p /tmp/owspace-research
swiftc -O -module-cache-path /tmp/owspace-research/swift-cache research/owspace-calendar/ocr_metadata.swift -o /tmp/owspace-research/ocr_metadata
python3 research/owspace-calendar/index_calendar.py --start 2015-01 --end 2015-12 --commit
python3 research/owspace-calendar/review_year.py 2015
```

每次只处理一年。先保存该年 `years/YYYY-layout.json` 版式分析，再逐月提取，最后执行全年检查；前一年覆盖检查通过后才能开始下一年。默认 3 个工作线程，所有网络请求合计最多每秒 4 次；临时网络错误最多重试 3 次。脚本可中断续跑。`--commit` 只允许在 `codex/owspace-calendar-index-2015-2025` 分支运行，只提交对应月份的数据文件。

原始来源：`https://img.owspace.com/Public/uploads/Download/{YYYY}/{MMDD}.jpg`。
