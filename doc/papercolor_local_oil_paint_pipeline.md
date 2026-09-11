# PaperColor 本地油画化显示技术设计

## 1. 文档状态

- 状态：编码前技术指导文档
- 日期：2026-09-11
- 适用分支：`feat/papercolor-os`
- 适用设备：M5Stack PaperColor（C151，ESP32-S3，400 x 600 Spectra 6）
- 第一阶段范围：图片浏览器中正在显示的图片，由 PaperColor 本机完成油画化并显示

本文用于指导后续设计、编码、主机测试和真机验收。实现过程中若接口、内存实测或面板行为与本文假设不一致，应先更新本文，再改变实现。

## 2. 目标与范围

### 2.1 目标链路

```text
图片浏览器正在显示的图片
          |
          | 顶部 A 键单击
          v
PaperColor 本地油画化（RGB565）
          |
          v
Spectra 6 调色板量化与误差扩散
          |
          v
六色墨水屏显示
```

这里的“本地”指图像风格化计算全部在 PaperColor 上完成，不依赖手机、服务器或相机端计算。图片来源可以是内部存储、SD 卡或 EzData，但第一轮编码和验收先以本地相册为主。

### 2.2 第一版必须实现

1. 在全屏照片浏览状态下，A 键单击把当前照片转换为油画风格。
2. 油画化发生在 RGB565 源图与 Spectra 6 量化之间。
3. 不修改现有 Spectra 6 LUT、目标颜色、补偿规则和误差扩散参数。
4. 处理失败时保留或恢复原图，不向面板提交半成品。
5. 同一张照片和同一组参数得到确定、可重复的输出。
6. 下一张、上一张、远程新图或旋转发生后，旧照片的效果状态必须失效。

### 2.3 暂不实现

- CamS3、UnitV K210 或其他相机接入。
- PyTorch、神经风格迁移或设备端模型推理。
- 把油画结果保存为新图片文件。
- 多套可编辑风格、画框、滤镜商店或 Web 参数面板。
- 修改 E Ink 波形、刷新时序或显示驱动。
- 为油画效果重新校准 Spectra 6 颜色。

## 3. 已确认的现有代码边界

### 3.1 当前照片在 Canvas 中仍然可用

本地照片由 `PhotoSlideshow::displayPhoto()` 解码到共享的 `hal.Canvas`，随后调用：

```cpp
papercolor_push_canvas(hal.Canvas, 0, 0,
                       PaperColorRenderMode::PhotoBalanced);
```

EzData 照片由 `EzdataPhotoPush::displayPhoto()` 下载、解码到同一 Canvas，再走相同的 `PhotoBalanced` 显示入口。EzData 的压缩图片缓冲会在显示后释放，但解码后的 RGB565 画面仍保留在 Canvas 中。

因此，用户按下效果键时不需要重新读取本地文件，也不需要重新下载 EzData 图片。油画模块可以直接以当前 Canvas 为输入。

### 3.2 Canvas 与显示方向

- 面板物理尺寸为 600 x 400 backing buffer。
- 照片浏览器可以通过 Canvas rotation 提供 400 x 600 等逻辑方向。
- `papercolor_push_canvas()` 在读取 buffer 前临时切换到 rotation 0，读取完成后恢复调用者的 rotation、clip rect 和 scroll rect。
- Canvas 的 16-bit buffer 是 M5Canvas 使用的 byte-swapped RGB565。油画核心若直接访问 `getBuffer()`，必须使用与现有 `papercolor_dither_process_swap565_row()` 相同的字节解释。

### 3.3 现有 Spectra 6 管线

`papercolor_push_canvas()` 已经完成以下工作：

1. 从 RGB565 Canvas 逐行读取输入；
2. 通过当前 32 KiB LUT 求取面板目标；
3. `PhotoBalanced` 使用蛇形 Floyd-Steinberg；
4. 输出黑、白、黄、红、蓝、绿六种原生码；
5. 向面板提交并触发刷新。

油画模块不得复制这套逻辑，也不得先自行量化成六色。唯一正确的组合方式是先改写 RGB565 Canvas，再调用现有 `PhotoBalanced` 管线。

### 3.4 当前按键冲突

当前 `app_manager` 在照片页收到 A click 后直接返回首页。`PhotoSlideshow::handleButtons()` 和 `EzdataPhotoPush::handleButtons()` 内又保留了 A click 切换旋转的逻辑，但通常会被上层导航先消费。

后续实现必须让 A 键事件只有一个所有者，不能继续由导航层和照片模块分别解释。

### 3.5 相关现有文件

- `main/apps/app_manager/app_manager.cpp`：页面状态、顶部 A 键和显示活动状态。
- `main/apps/local_photo_slideshow/local_photo_slideshow.cpp`：本地图片选择、解码和全屏显示。
- `main/apps/ezdata_photo_push/ezdata_photo_push.cpp`：EzData 图片下载、解码和全屏显示。
- `main/display/papercolor_lut_display.cpp`：Canvas 到 Spectra 6 的显示适配层。
- `main/display/papercolor_photo_dither.cpp`：照片目标映射和行流式误差扩散。
- `main/display/display_metrics.cpp`：显示耗时与堆内存观测。
- `main/CMakeLists.txt`、`main/Kconfig.projbuild`：源文件、优化级别和功能开关接入点。

## 4. 目标架构

```text
Local Photo / EzData Photo
          |
          | decode + AspectFit
          v
Shared RGB565 Canvas + CurrentPhotoFrame
          |
          | A single click
          v
PhotoEffectController
  |-- snapshot original Canvas to PSRAM
  |-- invoke pure oil-paint core
  |-- rollback on failure
          |
          v
RGB565 oil-paint Canvas
          |
          v
papercolor_push_canvas(PhotoBalanced)
          |
          v
Spectra 6 LUT + Floyd-Steinberg + EPD refresh
```

模块职责：

- 照片来源模块：只负责选图、解码、缩放和登记当前画面。
- `PhotoEffectController`：管理当前照片、原图快照、按键触发、状态和失败恢复。
- `papercolor_oil_painter`：纯 RGB565 图像算法，不访问文件、网络、按键或面板。
- `papercolor_lut_display`：保持现状，负责 Spectra 6 映射、抖动和显示。

## 5. 建议新增模块

### 5.1 文件布局

```text
main/
  apps/
    photo_effects/
      current_photo_frame.h
      photo_effect_controller.h
      photo_effect_controller.cpp
  display/
    papercolor_oil_painter.h
    papercolor_oil_painter.cpp
tools/
  oil_paint_lab/
    run_host_tests.sh
    render_preview.py
    test_papercolor_oil_painter.cpp
```

`papercolor_oil_painter.cpp` 应和现有照片颜色热路径一样使用 `-O2` 单独编译，其余应用继续使用项目默认调试优化级别。

### 5.2 当前照片描述

建议类型：

```cpp
enum class PhotoFrameSource : uint8_t {
    None,
    Local,
    EzData,
};

enum class PhotoEffectState : uint8_t {
    Original,
    RenderingOil,
    Oil,
    RestoringOriginal,
};

struct PhotoRect {
    int32_t x;
    int32_t y;
    int32_t width;
    int32_t height;
};

struct CurrentPhotoFrame {
    bool valid;
    PhotoFrameSource source;
    uint32_t generation;
    uint8_t canvas_rotation;
    PhotoRect logical_content_rect;
    PhotoRect backing_content_rect;
    PhotoEffectState effect_state;
};
```

规则：

- 每次成功解码一张新图片后递增 `generation`。
- `logical_content_rect` 是浏览器计算出的实际图片范围，不包含 AspectFit 白边。
- `backing_content_rect` 在登记时一次性转换为 rotation 0 坐标，算法不在热循环里反复换算。
- 任意新图片、旋转或 Canvas 被其他页面重绘时，旧 context 和原图快照立即失效。

### 5.3 可测试的油画核心接口

```cpp
struct PaperColorOilOptions {
    uint8_t coarse_radius;
    uint8_t medium_radius;
    uint8_t detail_radius;
    uint8_t saturation_percent;
    uint8_t contrast_percent;
    uint32_t seed;
};

struct PaperColorOilStats {
    uint64_t total_us;
    uint32_t coarse_strokes;
    uint32_t medium_strokes;
    uint32_t detail_strokes;
    size_t workspace_bytes;
};

size_t papercolor_oil_workspace_size(int width, int height);

bool papercolor_oil_render_swap565(
    const uint16_t* source,
    uint16_t* destination,
    int width,
    int height,
    int stride,
    const PhotoRect& content_rect,
    const PaperColorOilOptions& options,
    void* workspace,
    size_t workspace_size,
    PaperColorOilStats* stats);
```

接口约束：

- 核心函数内部不做堆分配。
- `source` 和 `destination` 不允许重叠。
- 只写 `content_rect` 内的像素。
- 输入、输出均保持 byte-swapped RGB565。
- 不包含 LUT、六色量化、面板刷新或全局状态。
- 参数非法或 workspace 不足时返回 `false`，不得部分越界写入。

## 6. 油画算法设计

### 6.1 设计原则

油画效果必须为 Spectra 6 的最终表现服务，而不是追求手机屏幕上的高频纹理：

- 优先保留主体轮廓、明暗块和大面积色彩关系。
- 笔触尺度必须明显大于最终抖动点尺度。
- 避免在平坦亮区生成随机细噪声，否则六色误差扩散会将其放大为脏点。
- 不在油画阶段模拟六色颜料；颜色限制统一留给现有显示管线。
- 避免浮点密集算法，优先使用整数、查表和固定大小循环。

### 6.2 V0：可落地算法

第一版采用确定性的多尺度传统绘制，不使用神经网络：

1. **降采样分析**
   - 将实际照片区域按最长边约 300 像素缩小。
   - 使用面积平均或低成本盒式滤波，减少原图噪声。

2. **颜色简化**
   - 对降采样图执行小半径边缘保持平滑。
   - 对局部颜色作温和归并，但仍输出连续 RGB565。
   - 饱和度和对比度调整必须有上限，避免让后续六色投影失控。

3. **方向场**
   - 从亮度图计算 Sobel 梯度。
   - 笔触方向取梯度切线，使笔触沿物体边缘而不是横穿边缘。
   - 低梯度区域使用稳定的默认方向或低频方向扰动。

4. **由粗到细绘制**
   - 粗层：半径约 10 至 16 像素，建立大色块。
   - 中层：半径约 5 至 8 像素，补充主要形状。
   - 细节层：半径约 2 至 4 像素，只在高误差或边缘区域绘制。
   - 每个笔触从源图中心附近采色，以椭圆或短胶囊形状进行 alpha blend。

5. **误差驱动放置**
   - 比较当前绘制结果与目标简化图。
   - 误差低的块跳过，避免每个像素都生成笔触。
   - 每个网格内使用由 `seed` 决定的有限抖动，保证可重复。

6. **边界处理**
   - 所有采样坐标限制在 `content_rect` 内。
   - AspectFit 白边逐字节保持不变。
   - 画面边缘使用 clamp 采样，不访问相邻内存。

### 6.3 与 Stylized Neural Painting 的关系

`jiupinjia/stylized-neural-painting` 的运行方式依赖 PyTorch、神经渲染器和反向优化，不适合作为 ESP32-S3 设备端实现，也不应把模型或训练依赖引入固件。

可借鉴的仅是算法结构思想：

- 从粗到细的笔触层次；
- 以可绘制图元重建目标图像；
- 根据剩余视觉误差增加局部笔触。

正式固件使用独立实现的传统、确定性、定内存算法。

## 7. Canvas、旋转和颜色格式

### 7.1 处理坐标系

油画核心统一处理 rotation 0 backing buffer：

```text
backing width  = 600
backing height = 400
stride         = 600 pixels
```

照片模块完成 AspectFit 后，同时记录逻辑照片矩形和对应的 backing 矩形。效果模块不改变 Canvas rotation，也不修改 clip/scroll 状态。

### 7.2 RGB565 字节序

必须提供单一、经过测试的像素辅助函数：

```cpp
Rgb888 decode_swap565(uint16_t value);
uint16_t encode_swap565(uint8_t r, uint8_t g, uint8_t b);
```

禁止在不同算法阶段各写一套位移和 byte-swap 逻辑。测试向量必须和现有 `papercolor_dither_process_swap565_row()` 的输入解释逐字节一致。

### 7.3 不允许双重量化

油画阶段的目标是新的 RGB565 图像。以下做法均不允许：

- 在油画模块里调用 Spectra 6 LUT；
- 把源图先量化成六色，再进行笔触绘制；
- 将面板上已经显示的六色画面作为效果输入；
- 油画完成后再用另一套调色板预处理。

## 8. 内存方案

以完整 600 x 400 backing buffer 估算：

| 缓冲 | 格式 | 预算 |
|---|---:|---:|
| 当前 Canvas | RGB565 | 已有 480,000 B |
| 原图快照 | RGB565 / PSRAM | 480,000 B |
| 300 x 200 分析图 | RGB565 / PSRAM | 120,000 B |
| 亮度图 | 8-bit / PSRAM | 60,000 B |
| 方向或梯度图 | 8-bit / PSRAM | 60,000 B |
| 可选块误差 | 8-bit / PSRAM | 不超过 60,000 B |
| PhotoBalanced 行扩散 workspace | 两行 int32 error | 约 14.5 KiB |

预计新增峰值约 675 至 750 KiB；第一版硬门槛为不超过 800 KiB 额外 PSRAM。

分配规则：

1. 在修改 Canvas 前一次性完成所有必需分配。
2. 大缓冲显式使用 `MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT`。
3. 原图快照在油画状态下保留，以便恢复；换图或离开浏览器时释放。
4. 分析和算法 workspace 在油画计算结束后立即释放，再进入面板刷新。
5. 不允许为了效果挤占现有内部 RAM 保留量。
6. 任意分配失败都在 Canvas 未改变时返回失败。

若真机峰值超过预算，按以下顺序降级：

1. 去掉独立块误差图，改为即时计算；
2. 将分析最长边由 300 降到 240；
3. 合并亮度和方向存储；
4. 最后才减少笔触层数。

## 9. `PhotoEffectController` 状态机

```text
NoFrame
   |
   | photo decoded
   v
Original -- A single --> RenderingOil -- success --> Oil
   ^                         |
   |                         | failure
   |                         v
   +------ rollback ------ Original

Oil -- A single --> RestoringOriginal --> Original

Any state -- new photo / rotation / leave viewer --> invalidate + free snapshot
```

控制器职责：

- 验证当前 view 必须是 PHOTO；
- 验证 frame `valid` 且 generation 未改变；
- 设置 `g_effect_in_progress`，暂停轮播和远程画面提交；
- 分配原图快照与 workspace；
- 调用纯油画核心；
- 成功后调用一次 `papercolor_push_canvas(PhotoBalanced)`；
- 失败则恢复 Canvas 并发送失败状态；
- 处理期间忽略重复的效果请求；
- 完成后恢复正常更新并记录活动时间。

第一版可继续在当前 app UI task 中同步执行，避免并发访问 Canvas。未来若实现统一 Display Worker，控制器应作为 display job 的纯处理阶段迁移，油画核心接口不变。

## 10. 按键设计

建议最终映射：

| 页面 | 操作 | 行为 |
|---|---|---|
| HOME | B 单击 | 进入照片浏览器 |
| HOME | C 单击 | 静音切换，保持现状 |
| PHOTO | A 单击 | 原图与油画图切换 |
| PHOTO | A 双击 | 返回首页 |
| PHOTO | B 单击 | 下一张 |
| PHOTO | C 单击 | 上一张 |
| 任意正常页面 | A 持续 5 秒 | Wi-Fi 配置，保持现状 |
| CONFIG | A 单击 | 返回首页，保持现状 |

照片页应使用 M5Unified 的 `wasDecideClickCount()` 和 `getClickCount()` 区分单击与双击，不能在第一次 `wasClicked()` 时立即执行油画，否则双击会先触发一次昂贵的面板刷新。

具体约束：

- A 键只由 `app_manager` 解释；从两个照片模块的 `handleButtons()` 中移除 A 行为。
- 油画处理期间 B/C/A 不改变照片或重复进入算法。
- 双击识别引入的短暂等待可以接受；它远小于 E Ink 刷新时间。
- 现有物理旋转入口不再占用 A 键；旋转继续由已有设置/Web 路径负责。

## 11. 显示提交与失败恢复

成功路径：

```text
allocate snapshot/workspace
  -> copy current backing buffer
  -> render oil RGB565 into Canvas
  -> free temporary analysis workspace
  -> mark render complete
  -> papercolor_push_canvas(PhotoBalanced)
  -> retain original snapshot for toggle
```

失败路径：

```text
allocation failure before Canvas write
  -> return failure, Canvas unchanged, no refresh

algorithm failure after Canvas write
  -> copy snapshot back to Canvas
  -> free temporary buffers
  -> return failure, no panel refresh

panel refresh failure
  -> Canvas state remains known
  -> report display failure
  -> do not discard original snapshot until leaving/toggling
```

在效果计算开始后若 EzData 收到新图，只记录 pending update；当前处理完成或取消后再显示最新图。禁止网络任务直接改写正在处理的 Canvas。

## 12. 性能与可观测性

复用现有 `DisplayMetricsTrace`，新增 `source=oil_photo`，至少记录：

- 原图快照耗时；
- 分析图生成耗时；
- 粗、中、细三层耗时和笔触数；
- 油画算法总耗时；
- 进入 Spectra 6 管线前的 PSRAM/内部 RAM；
- `PhotoBalanced` prepare 时间；
- 面板刷新时间；
- 成功、失败和失败阶段。

第一版性能门槛：

- 600 x 400 油画计算不超过 5 秒，不含 E Ink 物理刷新；
- 目标值为 3 秒以内，最终以真机测量决定；
- 额外 PSRAM 峰值不超过 800 KiB；
- 算法期间不得触发任务看门狗；长循环需按实测决定是否周期性让出调度；
- 20 次原图/油画切换后 free heap 不持续下降。

## 13. 分阶段编码计划

### Phase 0：基线与契约

任务：

- 固定 6 至 12 张本地测试图，覆盖人像、风景、绿植、天空、暖色、暗部、细节和白边。
- 记录当前原图 `PhotoBalanced` 输出和显示指标。
- 增加本文定义的状态、矩形和统计接口，但不改变实际显示行为。

验收：

- 固件构建通过；
- 本地/EzData 原图输出不变；
- 能记录每次成功显示的当前 frame 和 backing content rect。

### Phase 1：纯油画核心与主机预览

任务：

- 实现 RGB565 encode/decode 公共辅助函数。
- 实现 `papercolor_oil_workspace_size()`。
- 实现降采样、亮度/方向场和三层笔触。
- 建立 host preview，把 RGB565 结果导出为 PNG，仅用于观察算法，不参与固件路径。

验收：

- ASan/UBSan 通过；
- 相同输入和 seed 输出逐字节一致；
- 矩形外像素不变；
- 横竖图均不越界；
- 视觉上已经形成可辨认的大、中、小笔触，而非单纯马赛克或模糊。

### Phase 2：本地相册集成

任务：

- 本地照片解码成功后登记 `CurrentPhotoFrame`。
- 实现 `PhotoEffectController` 的 snapshot、油画化、回滚和恢复原图。
- 将 A 键单击接到效果控制器，处理现有 A 键冲突。
- 油画完成后复用现有 `PhotoBalanced` 显示入口。

验收：

- 当前正在看的图片被处理，不跳图、不重新扫描后误选其他索引；
- A 单击出现油画结果，再次单击恢复原图；
- B/C 换图后不会错误恢复上一张图片；
- JPG、PNG、BMP 和两个方向通过；
- 不改变 LUT 和抖动回归结果。

### Phase 3：Spectra 6 实机调优

任务：

- 对比主机 RGB565 预览、六色软件预览和实体屏。
- 只调整油画参数：笔触半径、层数、误差阈值、饱和度和对比度。
- 重点检查人脸、天空、白墙和暗部是否因笔触生成额外污染点。

验收：

- 油画效果在实体屏上可辨认；
- 主体轮廓没有被粗笔触破坏；
- 亮区没有明显新增红/蓝/绿脏点；
- 性能、内存和稳定性达到第 12 节门槛。

### Phase 4：EzData 与异步更新

任务：

- EzData 解码成功后登记同一 `CurrentPhotoFrame`。
- 效果直接处理当前 Canvas，不重新下载图片。
- 油画处理中收到的新图采用 pending/replace-latest 语义。

验收：

- 断网后，已经显示在 Canvas 上的当前图仍可油画化和恢复；
- 新图不会在处理过程中撕裂 Canvas；
- 本地和 EzData 对相同 RGB565 输入产生相同油画输出。

### Phase 5：文档、默认参数与发布准备

任务：

- 固定 `OilPaintOptions` 默认值和版本号。
- 增加默认关闭的 `PAPERCOLOR_OIL_PAINT` Kconfig，依赖 `PAPERCOLOR_EXPERIMENTAL_LUT`。
- 更新 README 的照片页按键说明。
- 保存代表性 golden outputs、性能报告和真机照片。

验收：

- 功能关闭时，现有固件行为和输出保持不变；
- 功能开启时，完整构建、host tests 和真机冒烟均通过；
- 文档、默认配置和实际按键行为一致。

## 14. 测试计划

### 14.1 纯算法测试

- 1 x 1、窄行、窄列和最大画面尺寸。
- 全黑、全白、六种标称原生色、灰阶渐变、彩色渐变和棋盘格。
- 非零 stride、非全屏 rect 和贴近四条边的 rect。
- 非法尺寸、空指针、workspace 少 1 字节等拒绝路径。
- 相同 seed 确定性与不同 seed 的受控差异。
- source buffer 只读性和 rect 外 destination 不变。

### 14.2 管线测试

- 真实油画核心后链接真实 `papercolor_photo_dither.cpp`。
- 验证顺序为 `oil RGB565 -> PhotoBalanced`，而不是相反。
- 所有最终 code 都在有效六色索引范围内。
- 油画开关关闭时，原图输出与当前 golden hash 相同。
- 油画开关开启时，输出稳定且与油画 RGB565 输入对应。

### 14.3 控制器测试

- 无当前照片时按 A 不刷新。
- 重复 A 请求不会重入。
- 分配失败不改变 Canvas。
- 算法中途失败完整回滚。
- 换图、旋转、回首页会释放快照并递增 generation。
- 旧 generation 的完成事件不能覆盖新图片。

### 14.4 真机测试矩阵

| 维度 | 覆盖项 |
|---|---|
| 来源 | Internal、SD、EzData |
| 格式 | JPEG、PNG、BMP |
| 方向 | 横屏、竖屏 |
| 内容 | 人像、风景、绿植、天空、暖色、暗部、白底 |
| 操作 | 油画、恢复、上一张、下一张、回首页、Wi-Fi 配置 |
| 压力 | 连续切换 20 次、自动轮播碰撞、EzData 新图碰撞 |

## 15. 完成定义

第一版只有同时满足以下条件才视为完成：

1. A 单击处理的是屏幕当前图片，第一张和切换后的图片均正确。
2. 油画化完全离线，在 PaperColor 上执行。
3. 油画算法输出 RGB565，随后只调用现有 `PhotoBalanced` 完成六色量化与抖动。
4. 原有 Spectra 6 校色源码、LUT 和参数没有因该功能被修改。
5. 所有分配失败和算法失败路径都能安全恢复。
6. 主机 sanitizer、确定性、边界和真实抖动管线测试通过。
7. 真机额外 PSRAM、计算耗时和 20 次稳定性达到预算。
8. 至少一组人像和一组风景在实体屏上被确认具有明确、可接受的油画观感。

## 16. 风险与决策规则

### 风险 1：效果看起来像马赛克或模糊

处理原则：先改进方向场和误差驱动笔触，不通过增加随机噪点制造“纹理”。

### 风险 2：六色显示吃掉细笔触

处理原则：增大中、细层笔触尺度并提高结构对比，不绕过或修改 Spectra 6 调色板。

### 风险 3：亮区出现污染色

处理原则：限制油画阶段的饱和度提升和颜色扰动，比较油画前后的 RGB565 输入；只有确认问题属于现有量化策略时，才另立校色任务。

### 风险 4：PSRAM 碎片或峰值过高

处理原则：进入效果前一次性分配，使用固定 workspace，按第 8 节顺序降级，不在热循环中反复 malloc/free。

### 风险 5：按键和异步图片更新竞争

处理原则：Canvas 仍由 UI/display 单一任务拥有；异步来源只提交 pending 状态，不能直接覆盖处理中画面。

### 风险 6：编码时与当前校色工作冲突

处理原则：新增功能保持独立文件和默认关闭的 feature flag；不重写 `papercolor_photo_dither.cpp`，不改变当前 LUT、补偿函数或校色诊断资源。

## 17. 建议的首个编码里程碑

第一个可提交里程碑只包含：

1. `CurrentPhotoFrame` 登记；
2. 纯 C++ `papercolor_oil_painter`；
3. host preview 与 sanitizer 测试；
4. 本地相册 A 单击触发；
5. 复用现有 `PhotoBalanced` 输出；
6. feature flag 默认关闭。

该里程碑不接相机、不接 EzData 异步更新、不调 Spectra 6 校色。先确认“当前照片 -> 本地油画化 -> 六色显示”闭环和实体观感，再进入后续扩展。
