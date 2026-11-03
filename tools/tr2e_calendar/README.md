# Tr2e 离线日历原型

固定400×600竖屏。当前为电脑端生成器，未接入设备的RTC日历应用，也未烧录硬件。落款最终为 `Tr2e`，14px，右下角。内部身份仍使用TR2E。个人日期只影响选句，不显示生日或纪念日标签。

## 运行

Python 3.10+；选排只需标准库，渲染另需Pillow。以下命令从仓库根目录运行，均无需联网：

```sh
python3 tools/tr2e_calendar/planner.py --year 2027
python3 tools/tr2e_calendar/render.py --plan artifacts/tr2e_calendar_400x600/2027.json --date 2027-06-21 --output artifacts/tr2e_calendar_400x600/2027-06-21.png
python3 -m unittest discover -s tools/tr2e_calendar -p 'test_*.py' -v
python3 tools/tr2e_calendar/build_report.py
```

仓库附有2026年计划及10张样稿。年度文件已存在且不同则拒绝覆盖；正式使用后应保留年度文件及使用历史，修改配置只对新计划生效。不要通过删除现用计划来重新抽签。

## 规则和数据

- `personal_rules.json`：三个人日期、岁末年初和春节窗口、各农历节日内容池、落款。池中的ID是历史来源日期。特殊日期内部最高优先级；画面仅显示正常节气。
- `assets/catalog.json`：从既有月度JSONL导出，不改原始摘抄。含作者、出处、标签、来源哈希与选句去重组。普通主题为启发式标签；已有人工摘抄仍可能含OCR错误，不能称为全库校勘完成。
- `assets/calendar.bin/json`：香港天文台1901—2100年UTC+8离线表。除夕为春节前一天，闰月不重复触发节日，夏至不硬编码月日。
- `planner.py`：先保留稀缺/特殊日期，再排普通日期。规范化选句与高相似句共用内容组，同一年每组和每个完整标题最多一次；不足时报错。现有作者生卒日只使用之前核实的26个身份。
- `render.py`：保留原文与作者/出处，按内容长度切换留白和字号，不做截断；日期母版来自2020年4月1—10日。历史日期与显示日期始终分开。

PNG为RGB格式，像素只有黑白，兼容既有PNG显示路径。`.bin`为400×600、逐行、每字节高位在前、1为黑，无文件头，共30,000字节。`.layout.json`记录布局、原始文字、显示标签和字面边界。

## 资源重建

已有资源可直接离线使用。仅在重建研究输入时联网：

```sh
python3 tools/tr2e_calendar/fetch_references.py --cache /tmp/tr2e-calendar-study
python3 tools/tr2e_calendar/build_calendar.py --cache /tmp/tr2e-calendar-study/calendars
python3 tools/tr2e_calendar/build_catalog.py
# build_assets另需Pillow、NumPy、fontTools
python3 tools/tr2e_calendar/build_assets.py --cache /tmp/tr2e-calendar-study
```

字体子集使用Noto Serif/Sans CJK与Tinos，均重命名为项目字体并保留OFL授权。字体来源、原文件哈希与字符覆盖位于 `assets/font_sources.json`。数学中点U+22C5在渲染时使用居中点字形；原始数据不替换该字符。数字点阵为本地研究提取，只包含0—9；它不代表已经识别出原版字体。

## PaperColor接入

现有 `main/apps/app_server/app_server.cpp` 提供 `/api/photos/upload`，multipart字段 `file`，`action=upload_display` 可显示PNG。此原型没有自动向设备上传或烧录。

后续固件需提供日历入口、RTC日期驱动、离线资源与年度计划存储、跨年处理、断电恢复与屏幕刷新。部署方案应先确定设备端排版或预渲染方式，再做内存、笔画与刷新效果验证。仅把PNG上传到照片应用，不等于设备已具备自动万年历功能。
