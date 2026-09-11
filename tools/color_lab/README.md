# PaperColor display baseline tools

## 阶段检查点：IMG_9958（2026-09-11）

当前保留的实验基线已完成原生RGB565量化修复和完整24色回归，见
[IMG_9958逐项验收](IMG_9958_REVIEW.md)及[阶段说明](CHECKPOINT_9958.md)。
下一项是11/12绿系的配比与纹理；整体色彩还原尚未完成，人像优化仍在后。

复现当前完整色表使用 `native565-chart-sdkconfig.defaults`；本次不修改默认启动配置。
历史被否决方案的源码、诊断素材及报告一并归档，不能据其存在认定已采用。
旧A/B素材带源码哈希校验，不能直接配合新源码烧录；详见阶段说明。

## 历史进度记录（下列状态不代表当前状态）

最新状态：首页修复用户人工验收通过，校色恢复。[16/20固定白目标配比A/B/C对照](SECONDARY_RATIO_ABC_CHART.md)已烧录，待实拍；正式照片算法及首页修复保持不变。

当前任务：色表调参按用户要求暂停。[首页缩略图/Logo颜色策略修复](HOME_PHOTO_PIPELINE_FIX.md)已烧录，待首页与浏览器实拍复核；保留IMG_9952校色算法。

最新进度：[IMG_9952完整24色回归](IMG_9952_REVIEW.md)通过，保留紫色平滑为实验基线；整体偏色仍未验收，下一轮优先16/20目标混色与白量。

最新实拍：[IMG_9951紫色平滑A/B复核](IMG_9951_REVIEW.md)。过渡改善、控制行保持，暂保留；完整24色与动态照片路径回归待做，整体颜色仍未验收。

当前候选：紫色启用阈值平滑的[同屏渐变 A/B](PURPLE_SMOOTH_AB_CHART.md)。24色色表输出保持 IMG_9949；只在新渐变图中检查过渡效果，数值通过不代表实拍通过。完全紫色旁路仍否决。

The current calibration direction is chart-first, with portrait work deferred.
See `SOURCE_CHART_CALIBRATION.md` for the fixed 24-patch/gray reference, isolated
startup test firmware, and acceptance sequence.

`IMG_9931_REVIEW_AND_FIX.md` records the 24-patch review and the default-off
full-scale primary-peak candidate. Reproduce its archived-baseline A/B with
`python3 tools/color_lab/compare_primary_peak.py`; physical acceptance is pending.

Accepted `21b0370` target-continuity audit (primary white budget enabled):

```bash
python3 tools/color_lab/audit_target_continuity.py
```

This host-only tool scans every RGB565 neighbor, records eight target ramps,
checks portrait pixel distributions, and measures native-code coverage in
uniform frames. It refuses changed baseline color sources. See
`TARGET_CONTINUITY_20260909.md` for findings and limitations; results are nominal
RGB diagnostics, not a physical panel profile or a promoted compensation change.

The firmware emits one `DisplayMetrics` record for every instrumented display
operation. During a serial-capable debug session, capture the output with:

```bash
./tools/idf.sh monitor | tee papercolor-display.log
```

The production firmware exposes a composite USB device: the existing photo
storage volume plus a CDC diagnostics port. Read the last 16 records without
changing the Mac's network connection:

```bash
python3 tools/color_lab/read_display_metrics_usb.py \
  --csv baseline.csv \
  --summary baseline-summary.json
```

The same records are also available over the read-only HTTP fallback:

```text
GET http://<device-address>/api/display/metrics
```

The endpoint is read-only. Records are returned oldest-to-newest and live in
RAM only, so a reboot starts a fresh capture.

Convert the captured records to CSV and a per-source P50/P95 summary:

```bash
python3 tools/color_lab/collect_display_metrics.py papercolor-display.log \
  --csv baseline.csv \
  --summary baseline-summary.json
```

Run the host-side parser tests:

```bash
python3 -m unittest discover -s tools/color_lab -p 'test_*.py'
./tools/color_lab/run_host_tests.sh
```

Generate the nominal 32 KiB perceptual LUT:

```bash
python3 tools/color_lab/generate_lut.py \
  tools/color_lab/profiles/nominal.json \
  --output artifacts/color_lut/nominal-5bit.lut \
  --metadata artifacts/color_lut/nominal-5bit.json
```

Compare it with the current RGB-nearest-color baseline on the complete 5-bit
grid:

```bash
python3 tools/color_lab/evaluate_lut.py \
  tools/color_lab/profiles/nominal.json \
  artifacts/color_lut/nominal-5bit.lut \
  --output artifacts/color_lut/nominal-evaluation.json
```

The nominal profile reproduces the current M5GFX palette as a controlled
reference. The evaluation above proves the algorithm and packing pipeline, not
the appearance of the physical panel. Color-improvement claims must use a new profile populated from
measured panel patches; changing the distance metric alone is not considered
calibration.

Firmware integration is guarded by
`CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT` and defaults to off. Enable it only for
controlled A/B builds. The disabled path calls the existing `pushSprite()`
implementation and does not change page rendering.

The enabled build exposes four internal render modes without changing the web
page: `legacy` is the exact upstream path, `ui` is perceptual nearest-color,
`photo-balanced` is serpentine Floyd-Steinberg, and `photo-detail` is
serpentine Burkes. Full-screen local and EZData photos currently select
`photo-balanced`; home, QR, and other UI screens remain in `ui` mode. Both
photo modes in the currently accepted repair use signed Q4 nominal sRGB error
diffusion, constrained gamut targets and a 32-entry target cache (384 bytes in
the state). The two scanline buffers use 14,496 bytes at the 600-pixel unrotated
Canvas backing width. This is not yet a measured linear-light mixing model.
The workspace uses internal RAM only when a 96 KiB reserve and a
large-enough contiguous block remain; otherwise it falls back to PSRAM, and it
is released before the physical panel refresh begins.

The M5Canvas byte-swapped RGB565 fast path is tested against the RGB888 path
for byte-identical native-color output. Only the two measured per-pixel source
files are compiled with `-O2`; the rest of the application keeps the project's
debuggable `-Og` profile. On the C151 sample, the latest calibration-chart
`photo-balanced` preparation time is 1,009,798 us; the full display call took
17,659,355 us. `panel_us` includes preparation and must not be added to it.
Earlier timings belong to earlier variants/images, not same-image A/B evidence.

Build the enabled variant in an independent directory:

```bash
./tools/idf.sh \
  -B build-lut \
  -D SDKCONFIG=build-lut/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/lut-sdkconfig.defaults' \
  build
```

For a device that already contains photos, flash only the app target so the
FAT storage partition is not rewritten:

```bash
./tools/idf.sh -B build-lut -p /dev/cu.usbmodemXXXX app-flash
```

The current `panel_us` value includes color quantization, SPI transfer, power
sequencing and the physical BUSY interval. Splitting those phases requires the
planned, reproducible M5GFX fork; this first instrumentation step deliberately
does not modify the detached upstream submodule.

Experimental firmware also includes a `PaperColorPipeline` line in the USB
metrics response. Its `prepare_us` measures scanline read, quantization and
the pre-refresh image transfer, while `workspace_bytes` records the temporary
dither memory. The physical refresh remains part of `panel_us`.

### IMG_9932 全色表与边缘复查

见 [24 项检查和根因修复](IMG_9932_REVIEW_AND_FIX.md)。本轮对完整填充区
（含第一行/列）比较峰值候选与精确颜料边界保护，机器结果保存在
`artifacts/color_calibration/exact-pigment-comparison.json`。

```sh
python3 tools/color_lab/compare_exact_pigment.py
```

`exact-pigment-chart-sdkconfig.defaults` 为独立候选配置，默认不开启。
镜像位于 `.cache/firmware/exact-pigment-chart-candidate/`；已仅烧录 PaperColor 应用分区并校验通过，IMG_9933 边缘修复实拍通过。

[IMG_9933 逐项验收与优化清单](IMG_9933_REVIEW.md)：蓝块边缘修复通过；24 色块的源色/目标/原生码比例归因已记录，下一步优先洋红、浅紫、青蓝和青色。

### 洋红/青色混色比例候选

[候选说明与全 24 块对照](SECONDARY_BALANCE_CANDIDATE.md)：
`PAPERCOLOR_BLUE_SECONDARY_BALANCE` 默认关闭，保持旧目标的黑白覆盖系数，
只调整红蓝/绿蓝彩色份额；不是实测 profile，已烧录且数据校验通过，尚待实拍验收。

```sh
python3 tools/color_lab/compare_secondary_balance.py
```

需要 Pillow 和 numpy。配置为 `secondary-balance-chart-sdkconfig.defaults`。

[IMG_9934 实拍验收](IMG_9934_REVIEW.md)：混色候选部分色相方向改善，整体尚未达标；10/20 纹理代价及全部 24 项状态已记录。

### 同屏混色比例对照

[40 格对照图说明](MIX_RATIO_CHART.md)：独立改变红蓝/绿蓝比例与白色份额，
输出已知原生色码。`mix-ratio-chart-sdkconfig.defaults` 切换诊断启动图，
不修改 IMG_9934 照片算法。预览和数量表在 `artifacts/color_calibration/mix-ratio-v1.png/.json`；
预览只是标称颜色，不是屏幕模拟。

```sh
python3 tools/color_lab/generate_mix_chart_preview.py
```

[IMG_9936 混色图验收](IMG_9936_REVIEW.md)：40 格相对比较已记录，下一轮固定彩色比、单独验证白色份额；诊断显示成功不等于整体校色完成。

### 温和减白候选

[完整色表候选与风险记录](SECONDARY_WHITE_CANDIDATE.md)：固定 IMG_9934 彩色相对份额，
温和减少高饱和红蓝/绿蓝混色的白色份额，默认关闭；已烧录并校验通过。
10 号边缘新增稀疏码和可能变暗的风险已列入验收。

```sh
python3 tools/color_lab/compare_secondary_white.py
```

[IMG_9937 完整验收与边缘根因](IMG_9937_REVIEW.md)：19纯蓝保护保持，16/17/20减白还原收益未确认，10左缘点列可见。未改候选代码的完整渲染追踪复现10白+1黑，下一步单独处理近两彩色连线目标的边缘残差；当前候选未提升为校色基准。

### 两彩色连线目标边缘保护

[边缘修复候选与完整验证](CHROMATIC_EDGE_CANDIDATE.md)：仅拦截不相容的黑白选码，
10号离线白10/黑1归零；目标映射不变，15个均匀控制场和12/16条渐变逐字节一致。
其余渐变的相位变化仍需实拍验收。独立固件已仅烧录PaperColor应用分区，数据校验通过。

```sh
python3 tools/color_lab/compare_chromatic_edge.py
```

配置 `chromatic-edge-chart-sdkconfig.defaults`，回退与当前设备状态见根目录 TODO。

[IMG_9938 全24项验收](IMG_9938_REVIEW.md)：10号左缘点列消失，19纯蓝及红绿保护保持；边缘修复通过，16/17/20灰暗及暖色混色继续待办。本轮USB设备在查询前已不在枚举中，没有新增耗时记录。

### 同屏照片算法减白 A/B

[ABBA诊断图与拍摄说明](WHITE_AB_CHART.md)：实际PhotoBalanced完整源图预渲染，
固定彩色比和边缘保护，只切换减白；B复现IMG_9938，24格保持原始网点。
同字母重复格完全相同，便于检查局部照明。默认关闭，已仅烧录PaperColor应用分区，数据校验通过，IMG_9942已完成同屏判读。

```sh
python3 tools/color_lab/generate_white_ab_chart.py
```

产物 `artifacts/color_calibration/white-ab-v1.*`，预览仅为标称RGB，不模拟实物。
配置 `white-ab-chart-sdkconfig.defaults`；构建时自动拒绝失配的源码和预渲染素材。

[IMG_9942 同屏A/B判读](IMG_9942_REVIEW.md)：16/20减白有有限观感收益且伴随变沉，17差异弱；暂留当前幅度，不继续加大。边缘保护保持，整体校色未完成，下一步单独检查暖色旧补偿。

### 暖色旧补偿旁路候选

[原因、完整验证与风险](WARM_BYPASS_CANDIDATE.md)：默认关闭，只跳过带两个硬阈值的
红黄源补偿。14白码约5.84%→11.31%，需实拍判断提亮与变灰的取舍；其他颜色目标保持。
已烧录并完成IMG_9944完整24色表复核，颜色收益尚未通过验收。旧ABBA素材不刷新，回退用缓存镜像。

```sh
python3 tools/color_lab/compare_warm_bypass.py
```

配置 `warm-bypass-chart-sdkconfig.defaults`；当前stopwatch也处于下载模式，务必按精确PaperColor身份操作。

[IMG_9944 全24项复核](IMG_9944_REVIEW.md)：10/19边缘保护保持，14仍为高反差黄褐织纹，
暖色旁路的颜色收益尚未通过实拍验收；下一步优先同屏暖色A/B。USB色表显示成功，当前候选仅作实验对照。

### 暖色同屏照片A/B

[诊断说明与验证](WARM_AB_CHART.md)：A旧暖色补偿、B当前旁路，每行A/B/B/A；
六行14/13/15/10/19/22，以真实整图渲染后裁块，其他减白/配比/边缘保护固定。
独立素材 `warm-ab-v1.*` 和固件已烧录PaperColor，IMG_9946完成同屏判读；旧减白ABBA不覆盖。

```sh
python3 tools/color_lab/generate_warm_ab_chart.py
```

配置 `warm-ab-chart-sdkconfig.defaults`。预览仅标称RGB，实物需同屏拍摄判断。

[IMG_9946 暖色同屏判读](IMG_9946_REVIEW.md)：B略浅、纹理反差稍弱，暂留旁路及连续性修复，
不继续加白；两版亮橙还原仍未通过。13/15及边缘/灰阶控制保持，下一步分别审查蓝紫/青蓝旧补偿。

### 蓝紫旧补偿旁路候选

[原因、两处分支审查和测试口径](PURPLE_BYPASS_CANDIDATE.md)：保留青蓝压暗，仅旁路
旧蓝紫增红；消除该分支目标突变，但09/18增加黑色、17减少白色，必须检查过暗/偏蓝。
完整色表候选已实拍，IMG_9947蓝紫色相验收不通过；已回退IMG_9944镜像，身份与写入哈希校验通过。

```sh
python3 tools/color_lab/audit_blue_compensation.py
python3 tools/color_lab/compare_purple_bypass.py
```

审查使用保存的上一版源码做隔离消融，比较工具验证当前真实候选；配置为
`purple-bypass-chart-sdkconfig.defaults`，旧AB素材与镜像继续独立保留。

[IMG_9947 全24项复核与回退](IMG_9947_REVIEW.md)：09/18偏蓝黑、17转灰蓝，完全旁路不采用；
恢复暖色旁路基线，再研究保留紫色观感的连续映射。设备已回退，stopwatch未操作。

[IMG_9949 回退实拍验收](IMG_9949_REVIEW.md)：09/17/18已恢复上一版紫色表现，10/19边缘与暖色/灰阶保护保持；
回退通过，整体校色未完成。下一步研究保留紫色观感的阈值平滑，不重复烧录同版。
