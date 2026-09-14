# PaperColor 本地油画化：功能分支实施与验收

日期：2026-09-14

功能分支：`codex/local-oil-paint`

基线：`feat/papercolor-os` 的 `e4fd821`

状态：离线实现候选；主机测试和功能开/关两套构建已通过，尚未实机验收，不得合入 OS 分支。

## 1. 当前有效的处理链

```text
照片浏览器当前画面
  -> M5Canvas RGB565 backing buffer
  -> PaperColor 本地油画核心（仅修改 RGB565）
  -> M5Canvas::pushSprite()
  -> M5GFX Panel_ED2208 官方 Spectra 6 颜色转换与抖动
  -> 墨水屏
```

2026-09-14 的 OS 已回退实验 LUT/`PhotoBalanced` 管线。此功能不依赖它们，不修改 `Panel_ED2208`，也不添加第二套六色量化。`PAPERCOLOR_OIL_PAINT` 默认关闭，开启时仅增加上游 RGB565 油画阶段。相机、神经网络推理、图片保存均不在此分支范围。

## 2. 当前实现文件

| 文件 | 职责 |
|---|---|
| `main/display/papercolor_oil_painter.h/.cpp` | 无设备依赖的确定性 RGB565 油画核心 |
| `main/apps/photo_effects/photo_frame_geometry.h` | 逻辑照片矩形转 Canvas backing 坐标 |
| `main/apps/photo_effects/photo_effect_controller.h/.cpp` | 当前照片登记、PSRAM 原图快照、切换和失败回滚 |
| `main/apps/app_manager/app_manager.cpp` | A 键单/双击状态机、Canvas 操作互斥入口 |
| `main/apps/local_photo_slideshow/local_photo_slideshow.cpp` | 本地照片解码后登记当前画面 |
| `main/apps/ezdata_photo_push/ezdata_photo_push.cpp` | EzData 照片解码后登记当前画面 |
| `main/Kconfig.projbuild`、`main/CMakeLists.txt` | 默认关闭的功能开关与独立优化编译 |
| `tools/oil_paint_lab/` | ASan/UBSan 主机测试与 RGB565 预览 |

## 3. 状态与按键契约

照片成功解码后，来源模块登记当前照片实际可见矩形、Canvas rotation、backing 尺寸和 generation。新照片开始覆盖 Canvas、返回首页、进入 Wi-Fi 配置或切换方向时，必须使旧登记与快照失效。

启用功能时：

| 位置 | 操作 | 行为 |
|---|---|---|
| 照片页 | A 单击 | 原图与油画图切换 |
| 照片页 | A 双击 | 返回 OS 首页 |
| 照片页 | B / C | 下一张 / 上一张 |
| 照片页 | A 持续 5 秒 | 现有 Wi-Fi 配置入口 |
| 配置页 | A 单击 | 返回首页 |

单击通过 M5Unified 的 `wasSingleClicked()` 延迟确认，避免双击时先耗费一次完整 E Ink 刷新。A 键只由 `app_manager` 解释；两个照片模块在功能开启时不再消费 A 键。功能关闭时保留原有按键逻辑和构建路径。

网页本地图片显示及网页模式切换通过效果控制器的 Canvas claim 与油画处理互斥；UI task 的自动轮播与照片页显示也使用同一 claim。此前项目其他显示入口的全局并发模型并未在本分支重构为 Display Worker，因此真机压力测试仍是合入前置条件。

## 4. 纯算法契约

`papercolor_oil_render_swap565()` 接受分离的 source/destination、完整 backing 尺寸、stride、照片矩形、参数和调用者提供的 workspace。RGB565 按 M5Canvas 的 byte-swapped 内存格式解释。函数不读写文件、不访问面板、不分配堆内存，不接触六色码。

实现步骤：

1. 对实际照片区域降采样至最长边 300 像素，五点均值抑制输入噪声。
2. 从亮度图提取 Sobel 方向场；笔触沿边缘切线排列。
3. 用平滑的分析图建立画面底层，并保留少量原图细节。
4. 绘制粗、中、细三层椭圆笔触；细层集中在有梯度的区域。
5. 使用固定 xorshift seed，保证相同输入、参数和方向产生相同输出。

默认参数：粗/中/细半径 `14/7/3`，饱和度和对比度均 `108%`。这只是主机预览候选值，不是已实机验收的最终视觉参数。

参数或工作区不合法时，在写 destination 之前返回 `false`；算法开始写 destination 之后不再有失败路径。效果控制器仍保留完整原图快照，用于异常回滚和第二次单击恢复。

## 5. 内存与性能

600 × 400 × 2 字节的 RGB565 原图快照为 480,000 B。最长边 300 的分析图最多 90,000 像素，每像素 2 字节颜色、1 字节亮度、1 字节方向/梯度，总 workspace 最多 360,000 B；对于 400 × 600 的整屏照片实际为 300 × 200 × 4 = 240,000 B。常见 600 × 400 的额外 PSRAM 峰值因此约 720,000 B，低于 800 KiB 的设计门槛。

所有大缓冲在修改 Canvas 前一次性从 PSRAM 申请。分析 workspace 在 `pushSprite()` 前释放；原图快照保留到恢复原图、换图或退出照片页。分配失败时 Canvas 不变且不刷新屏幕。`DisplayMetricsTrace("oil_photo")` 与油画笔触/计算耗时日志分开记录，不能把约 15–30 秒的面板物理刷新计入“算法耗时”。

目标：真机油画计算 ≤5 秒，期望 ≤3 秒；连续 20 次切换后 free heap 不持续下降。这些数字必须在设备回来后测量，目前只能验证算法复杂度、主机耗时和内存上界。

## 6. 离线验证

主机测试：

```bash
bash tools/oil_paint_lab/run_host_tests.sh
```

已通过，覆盖 RGB565 字节序、四种 rotation 的照片矩形、非法参数/不足工作区/重叠输入、矩形外像素保持、确定性、1 × 1 边界和 600 × 400 整帧。使用 ASan/UBSan。

RGB565 预览（不是实体六色墨水屏模拟）：

```bash
python3 tools/oil_paint_lab/render_preview.py \
  artifacts/color_calibration/kodim04.png /private/tmp/papercolor-oil-preview.png
```

开启功能的 ESP-IDF 构建：

```bash
./tools/idf.sh -B /private/tmp/papercolor-oil-build \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/oil_paint_lab/oil-paint-sdkconfig.defaults' build
```

已完成开启与默认关闭两套 ESP-IDF 构建；关闭配置的编译清单不包含油画核心和控制器。`kodim04.png` 的主机 RGB565 预览已生成并人工查看，但不代表实体六色显示效果。不得在无设备时运行 `flash`。

## 7. 仍待完成的真机验收

1. 确认实际 Canvas 为 600 × 400 byte-swapped RGB565，四种 rotation 下的可见照片区域正确，白边不被笔触污染。
2. 检查内部存储/SD/EzData 的 JPG、PNG、BMP，以及网页选中的当前图。
3. 观察 A 单击、双击、5 秒长按与 B/C 导航是否互不冲突；尤其测试面板刷新期间再次按键。
4. 验证油画图与原图切换、换图后旧快照释放、断网后的 EzData 当前图仍可本地油画化。
5. 对固定人像、风景、天空和白底样本作实体屏对比，检查肤色层次、主体边界及脏点。
6. 实测算法耗时、额外 PSRAM、最大连续块和 20 次重复后的内存稳定性。
7. 压力测试网页显示/模式切换、自动轮播与按钮交错时不出现 Canvas 撕裂或错误照片。

没有实体屏观察、性能数据与按键实测前，当前分支只能称为“离线实现候选”，不能宣称视觉效果和产品体验已通过，也不应合入 `feat/papercolor-os`。
