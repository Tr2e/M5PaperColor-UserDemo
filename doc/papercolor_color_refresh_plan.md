# PaperColor 色彩与刷新优化行动计划

## 1. 范围与结论

基线分支：`feat/papercolor-os`

基线提交：`c6d9cbfec68a0b8159c89e804be17a0db65530cf`

目标分为两个独立指标：

1. 提高照片、插画和 UI 在 ED2208-DOA / EL040EF1 六色面板上的颜色真实性。
2. 降低用户从发出操作到看到稳定画面的等待，并减少不必要的完整刷新。

已经确认的硬件边界：

- 面板只有黑、白、黄、红、蓝、绿六种原生墨水状态。
- 面板资料给出的 25 摄氏度典型更新时间约为 12 秒；M5Stack 给出的设备实际范围约为 15 到 30 秒。
- 当前 `epd_fastest`、`epd_fast`、`epd_text`、`epd_quality` 只切换 RGB 到六色的量化/抖动函数，最终发送的刷新命令和面板波形相同。
- 当前驱动即使收到局部矩形，也会发送全部 400 x 600 像素并启动完整刷新。因此现阶段不能把 `setClipRect()` 视为硬件局部刷新。
- 不采用未知来源的波形数据，不调整 VCOM、高压或刷新脉冲。自定义快速波形只在 M5Stack/E Ink 提供与该批次面板匹配的正式数据后单独立项。

预期结果：色彩可以获得明显提升；处理和软件开销可以缩短；单次物理波形时间不会因图像 LUT 获得数量级改善。

## 2. 方案 CR 结论

### P0：BUSY 超时与官方刷新范围冲突，且错误被忽略

当前 `_wait_busy()` 默认 20 秒超时，而 M5Stack 给出的实际刷新范围可到 30 秒。`_turn_on_display()` 对 POWER_ON、DISPLAY_REFRESH 和 POWER_OFF 的等待都忽略返回值。刷新超过 20 秒时，驱动可能在 BUSY 仍为低时继续发送命令，违反面板 BUSY 期间不得发命令的要求。

决定：为不同阶段设置独立超时，刷新阶段先使用至少 45 秒的安全上限；所有等待错误必须向 Display Worker 传播。超时时不得继续发送普通命令，应记录阶段、BUSY 电平、温度和图像统计，随后走经过验证的硬件复位/电源恢复流程。

### P0：先统一显示所有权，再叠加优化

当前 Web HTTP handler 会调用 `app_manager_display_local_photo()`，继而直接解码图片、写共享 Canvas 并刷新 EPD。与此同时，日期更新已经采用“HTTP 只发请求、UI task 执行显示”的模式。这两条路径的线程模型不一致。

风险：并发的 Web 请求、按键、轮播、EzData 更新可能同时修改 Canvas、显示模式或刷新状态。`g_refresh_in_progress` 还是普通 `bool`，不能构成跨任务同步。

决定：建立唯一的 Display Worker。所有来源只能提交不可变显示任务，只有该 worker 可以访问 Canvas、设置 EPD mode、传输 framebuffer 和等待 BUSY。

### P0：不能直接复制 GPL 实现

`MarsTechHAN/PaperColor-Frame` 对 PaperColor 色彩管线有较完整的公开验证，但项目许可证是 GPL-3.0。当前仓库是 MIT，不能直接拷贝其实现而继续以 MIT 发布。

决定：仅把它作为研究对照。算法实现基于公开颜色科学资料自行编写；若复用第三方实现，优先选择 MIT 许可的 `OpenDisplay/epaper-dithering`，并保留许可证和归属记录。

### P1：当前颜色距离和调色板不适合反射式面板

固件以理想 RGB 调色板和 RGB 平方距离做量化。网页预览使用另一套调色板，而且网页和固件的抖动强度不同。上传的仍是原始 PNG，由设备再次量化，所以预览和实体结果无法一致。

决定：采用同一份版本化校准数据和同一套核心算法。匹配空间使用固定点 OKLab 或 Lab；在量化前把源图亮度和色度压缩到面板实测范围。

官方手册数据只能作为同型号面板的 fallback。保护盖板、批次、光源和测量几何都会改变实测结果，不能把资料中的典型值当作每台设备的最终校准值。

### P1：应把“刷新快”拆成四项测量

端到端等待必须拆成：

- 图片接收/读取与解码；
- 色彩处理与量化；
- 120 KB 4bpp 数据的 SPI 传输；
- 面板 BUSY 对应的物理刷新及外围固定延时。

没有分段计时之前，不接受“fastest 更快”或“LUT 缩短刷新”的结论。

### P1：区域更新目前只是软件裁剪

当前 `_exec_transfer()` 总是遍历完整高度和宽度。日期区域刷新会付出完整面板刷新成本。

决定：第一阶段不尝试伪局刷。通过任务合并、内容哈希、状态延迟提交降低完整刷新次数。真正局刷需要控制器命令、波形和残影验证三项证据齐全。

### P1：驱动记录的 RESET 引脚与官方 PinMap 不一致

M5GFX 初始化时确实通过 GPIO12 做了一次 EPD reset，但随后写入 panel config 的 `pin_rst` 是 GPIO43；官方 PinMap 显示 GPIO43 是 EINK_DC、GPIO12 才是 EINK_RST。当前初始化碰巧绕过了 panel 的 reset 配置，但通用 reset、deep-sleep wake 和未来的超时恢复可能操作错误引脚。

决定：在 Phase 0 用原理图和样机确认后修正为 GPIO12，并验证 sleep/wake 和超时恢复；该修复应进入团队 M5GFX fork 并提交上游，不在应用层绕过。

### P2：M5GFX 子模块需要明确维护策略

ED2208 的传输和量化代码位于上游 M5GFX 子模块中。直接修改 detached submodule 会造成无法复现的构建。

决定：

1. 应用层色彩模块和测试代码保留在主仓库。
2. 必须修改 ED2208 驱动时，在团队可写的 M5GFX fork 建分支并固定 submodule commit。
3. 同时准备最小化上游 PR；主仓库不能依赖未提交的子模块工作区。

## 3. 目标架构

```text
Web / Local Album / EzData / Home UI / Buttons
                      |
                      v
              Display Job Queue
      replace-latest + debounce + priority
                      |
                      v
                Display Worker
       decode/render -> color pipeline
       -> packed 4bpp -> hash/dedupe
       -> SPI transfer -> panel refresh
                      |
                      v
          metrics + completion event
```

建议模块边界：

- `main/display/display_worker.*`：任务队列、唯一显示所有权、取消/合并和完成通知。
- `main/display/display_metrics.*`：分段耗时、温度、堆内存、刷新原因和结果。
- `main/color/panel_profile.*`：六色 Lab/OKLab、profile 版本和校验。
- `main/color/color_pipeline.*`：色域压缩、色调映射、量化和抖动。
- `main/color/packed_epd.*`：4bpp 格式、校验、hash 和持久化格式。
- `tools/color_lab/`：桌面端 golden image、指标计算和校准数据生成。

不得让 Web、相册或 EzData 分别维护独立的量化实现。

核心算法优先采用无异常、无运行时动态分配的 C/C++，同一份源代码编译到 ESP32 host test 和浏览器 WASM。MIT 许可的 Rust 实现可用作离线对照和生成测试向量，但第一版不把 Rust toolchain 引入 ESP-IDF 构建。

## 4. 分阶段实施

### Phase 0：建立基线和测试夹具

任务：

- 在现有显示路径添加微秒级分段计时，不改变输出。
- 记录请求时间、任务排队、解码、绘制、量化、SPI、POWER_ON、BUSY、POWER_OFF。
- 把 BUSY 等待改成分阶段超时并检查返回值；先使用保守的刷新超时，不在本阶段缩短任何合法时序。
- 定义刷新失败恢复状态机：停止后续命令、上报失败、受控复位、重新初始化；不得在 BUSY 低电平时直接 POWER_OFF。
- 按官方 PinMap 修正并验证 EPD reset 配置，覆盖冷启动、deep sleep 唤醒和故障恢复。
- 记录显示来源、模式、输入尺寸、最终六色直方图、SHT40 温度、最小内部堆和 PSRAM。
- 建立 12 张固定测试图：人像、肤色、天空、绿植、暖色、暗部、渐变、饱和 logo、黑白文字、细线、小字号和六色色块。
- 增加 host-side 测试入口；固件算法与 host 测试使用同一源文件。
- 在至少两台设备上，于接近 10/25/40 摄氏度的环境分别运行测试；所有温度必须在面板 0 到 50 摄氏度工作范围内。

产物：

- `baseline.json/csv` 性能数据；
- 基线输出 4bpp 文件及渲染预览；
- 测试照片授权/来源清单；
- 基线固件二进制和 commit 标识。

验收：

- 每次刷新均能分解成上述阶段；
- 模拟 BUSY 超时时能够返回失败并恢复，不会继续发送后续显示命令；
- 连续 50 次刷新无死锁、看门狗和内存下降；
- 当前固件输出通过 golden regression 固定下来。

实施记录（2026-09-08）：

- 样机运行态会将原生 USB Serial/JTAG 切换为 TinyUSB MSC，因此串口日志不能作为持续采样通道。现已将运行态 USB 改为 MSC + CDC 复合设备，并保留 `/api/display/metrics` 作为只读备用通道；Mac 无需离开当前网络。
- 已建立 16 条 RAM 环形记录及 USB 拉取脚本，应用页面资源未修改。
- 首次 `home_full` 冒烟样本：渲染 1.606371 秒、当前面板调用 17.230902 秒、总计 18.837292 秒；刷新成功，结束时内部堆 187235 字节、PSRAM 7105284 字节。
- 该样本只证明采集链路可用，尚不满足固定图集、重复次数、温度点和第二台设备要求，Phase 0 继续进行。

### Phase 1：单一 Display Worker

任务：

- 创建长度受限的显示任务队列。
- HTTP handler 立即返回 job id；提供 job 状态查询或复用现有状态接口。
- 按键和模式切换使用高优先级；轮播/EzData 使用普通优先级；日期和状态更新允许被更新的全屏任务吞并。
- `replace-latest`：刷新过程中同类请求只保留最后一帧。
- Canvas、EPD mode、`pushSprite()` 和 BUSY 等待全部移到 worker。
- 文件只在读取/解码期间持有 storage lock，不在 12 到 30 秒 BUSY 期间锁住存储。
- 使用队列/事件组或原子状态替代跨任务普通 `bool`。

验收：

- 并发上传、按键和自动轮播不会并发进入显示驱动；
- 十次突发显示请求最多执行“当前帧 + 最新帧”；
- Web 请求线程不阻塞整个物理刷新周期；
- 200 次混合来源压力测试无死锁和画面撕裂。

### Phase 2：面板 profile 和感知色彩映射

任务：

- 以 EL040EF1 手册的六色 CIELAB 值建立 `factory-default-v1` profile。
- 支持 NVS/文件加载 profile，包含版本、测量条件、六色值和 CRC。
- 实现 sRGB 反伽马、D65 XYZ、Lab 或固定点 OKLab 转换。
- 把输入亮度压缩到实测纸黑和纸白范围，把色度压缩到六色凸包附近。
- 首先实现无抖动 nearest 模式，作为 UI 和算法诊断基线。
- 提供 32K 或 64K RGB LUT 加速 nearest 路径；LUT 是颜色转换缓存，不改变面板波形。

验收：

- 固定输入在设备端和 host 端得到逐字节相同的 4bpp 输出；
- 六种原生 UI 色严格映射到正确 nibble；
- 与当前 RGB 欧氏距离相比，测试色块平均 Delta E 下降至少 15%，且关键肤色/天空/绿植类别没有明显污染色回退；
- Delta E 的算法目标使用色域映射后的目标色，实体指标使用受控光源下的仪器读数；
- nearest 全屏量化目标不超过 100 ms，64 KB LUT 可完整驻留，且不得侵占保留给 Wi-Fi/HTTP 的 internal heap。

Phase 2 实施记录（2026-09-08，进行中）：

- 已实现共享的 5-bit/channel（32 KiB）LUT 查找与 ED2208 4bpp 打包核心，以及基于 CIEDE2000 的离线生成器；CIEDE2000 由公开参考向量校验。
- 名义 M5GFX 色板的 LUT SHA-256 为 `b15a687e34aefb3eee93e93b2e1f7889ff0b46543a471249ba1652fc2a2cf9b4`；机器可读记录位于 `artifacts/color_lut/nominal-5bit.json`。
- 完整 32 x 32 x 32 网格的离线对照中，平均 Delta E 由 22.5315 降到 19.6045，下降 12.99%；7,847 个映射改善、24,921 个持平、0 个退化，P95 由 47.2214 降到 29.7250。
- 12.99% 低于实体目标 15%，且使用的是名义 RGB 色板，因此不得据此宣称实体屏已达标；必须填入受控光源下的实测六色数据后重新生成与复测。
- host C++ 对 400 x 600 RGB888 帧的纯 LUT + 4bpp 打包为约 140 微秒/帧（当前 Mac），低于 100 ms 算法预算；仍需采集 ESP32 上的端到端色彩处理耗时。
- 已加入默认关闭的 `CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT`。关闭时所有显示入口仍调用原有 `pushSprite()`；开启时通过应用层逐行适配器做 nearest A/B，不修改 M5GFX 子模块。默认版和开启版均已通过 ESP-IDF 构建。
- 开启版首次 app-only 尝试因运行态 TinyUSB CDC 无法触发 ROM 下载而在写入前失败；手动进入下载模式后已成功仅写入 app 分区并通过烧录哈希校验，分区表和照片存储未改动。
- 实验固件已在 C151 实机正常启动并枚举为 PaperColor USB 设备。首屏 smoke sample 为：总耗时 18.030 s、render 1.635 s、panel 16.395 s；Phase 0 单次基线分别为 18.837 s、1.606 s、17.231 s。总耗时单样本下降 4.3%，但尚未控制温度和重复次数，因此只证明功能通路成立，不作为刷新性能验收结论。
- 操作者已确认实验版主页方向、裁切和颜色均无明显异常，Phase 2 的 nominal-LUT 功能 smoke test 通过；实体色准仍等待仪器测量和盲测。
- 实机原始日志、CSV、摘要和构建元数据保存在 `artifacts/display_metrics/phase2-nominal-lut-smoke.*`。

### Phase 3：照片抖动和内容模式

任务：

- 实现蛇形 Floyd-Steinberg 作为简单基线。
- 实现 Stucki 或 Burkes 作为照片候选；使用行缓冲控制内存。
- 误差扩散在线性光或感知空间中完成，并限制误差范围。
- 增加亮区污染色抑制、暖色/肤色蓝绿抑制、冷色天空红黄抑制；这些只能作为接近候选的 tie-break，不能覆盖强色证据。
- 提供三个稳定模式：`ui`、`photo-balanced`、`photo-detail`。
- 通过 feature flag 保留 `legacy` 回退。

验收：

- 12 张测试图进行盲测，候选方案偏好率至少 70%；
- 小字号文字和 1 px 线条不因照片算法变脏；
- 平坦亮区的黑/红/蓝孤立点数量不高于基线；
- 设备端照片全屏处理目标不超过 1 秒，浏览器端目标不超过 500 ms；
- 处理时间不增加端到端物理刷新 P95 超过 5%。

Phase 3 实施记录（2026-09-08，进行中）：

- 已实现确定性的逐行量化核心：`ui` 使用 LUT nearest，`photo-balanced` 使用蛇形 Floyd-Steinberg，`photo-detail` 使用蛇形 Burkes，`legacy` 保留原始 `pushSprite()` 回退。
- 误差扩散使用 12-bit、gamma-2 固定点线性近似线性光，避免设备端浮点；两种照片模式使用两行误差缓冲、4,096-byte 逆传递查找表和 512-byte 正向表。设备的未旋转 Canvas 行宽为 600，工作区共 19,104 bytes；仅当内部 RAM 仍能保留 96 KiB 且最大连续块足够时走内部 RAM，否则回退 PSRAM。工作区在物理刷屏前释放。
- 全屏本地照片和 EZData 照片接入 `photo-balanced`；主页、二维码、错误页和缩略图所在的 UI 仍使用无抖动 `ui` 路径。网页文件和 API 未作功能性修改。
- host 测试覆盖原生六色保持、非法工作区拒绝、输出索引范围、reset 后逐字节确定性，以及 M5Canvas byte-swapped RGB565 快路径与 RGB888 路径逐字节一致；当前 Mac 上 400 x 600 Burkes 基准约 8.3 ms。10 项 Python 测试和 C++ host 测试均通过。
- USB 指标新增 `PaperColorPipeline` 记录，独立报告刷新触发前的逐行读取、量化和传输准备耗时及工作区大小。默认关闭 LUT 和实验开启 LUT 两种配置均已通过 ESP-IDF 完整构建；颜色热路径两个源文件单独使用 `-O2`，其余应用继续沿用项目的 `-Og` 调试配置。
- C151 同一张本地照片的逐轮实测为：初版二分反查 3,167,658 us；O(1) 逆表 1,992,479 us；正向表和内部 RAM 1,585,915 us；RGB565 直读与无边界分支传播 1,022,860 us；最终仅热路径 `-O2` 为 638,422 us。相对初版下降 79.8%，通过设备端不超过 1 秒的阶段目标。
- 最终照片样本总耗时 20.537727 s，其中解码/绘制 3.746447 s、`panel_us` 16.791251 s。以 `panel_us - prepare_us` 估算的物理段，初版为 16.144846 s、最终版为 16.152829 s，单样本变化约 +0.05%；说明本轮提速来自颜色准备路径，未调整面板波形。该值不是 P95，仍需受控重复测试。
- 最终照片刷新前后内部 RAM 均为 140,107 bytes、PSRAM 均为 7,105,084 bytes，工作区完整释放。实测原始数据见 `artifacts/display_metrics/phase3-photo-balanced-o2-smoke.*`。性能子目标通过；12 张测试图盲测、污染点统计和实体色准测量仍待完成。

### Phase 4：网页预览与 4bpp 资产

任务：

- 将 Phase 2/3 的同一核心编译为浏览器 WASM，或使用逐字节一致的共享测试向量约束 JS 实现。
- 网页预览用 profile 的实测外观色渲染最终 index，而不是理想 RGB。
- 上传格式新增版本化 `.pc4`：magic、版本、宽高、旋转、profile id、algorithm id、payload length、CRC32、120 KB packed 4bpp payload。
- 保留原图或缩略图，支持重新生成；不得只保存不可逆 4bpp 而丢失用户原图。
- 在团队 M5GFX fork 为 `Panel_ED2208` 增加最小化的 native 4bpp 写入 API；复用现有 POWER_ON/BUSY/POWER_OFF 实现，不在应用层复制电源时序。
- 设备校验 `.pc4` 后通过 native API 进入传输路径；旧 PNG/JPEG/BMP 继续兼容。
- 预览和设备输出使用相同 golden vectors 做 CI。

验收：

- 浏览器生成和固件生成的 4bpp 对测试集逐字节一致；
- 格式版本、尺寸、索引范围或 CRC 错误时安全拒绝，不触发刷新；
- 预量化照片二次显示不重复解码和量化；
- legacy 图片库无需迁移即可继续显示。

### Phase 5：刷新去重、合并与用户感知延迟

任务：

- 对最终 4bpp framebuffer 计算快速 hash，并在 hash 相同后做字节确认，避免碰撞误判。
- 相同输出直接完成任务并报告 `unchanged`，不发送刷新命令。
- 对短时间内的状态更新 debounce；整屏任务自动包含较早的局部状态任务。
- 刷新进行中更新 Web job 状态和 LED，不让用户重复提交。
- 收集“每个用户动作触发的实际物理刷新次数”。

验收：

- 相同图像连续显示 20 次只产生第一次物理刷新；
- 音量等无需画面反馈的状态不触发刷新；
- 同一 debounce 窗口内的多项主页变化只产生一次刷新；
- 页面和设备明确区分 `queued / processing / refreshing / complete / unchanged / failed`。

### Phase 6：低风险传输与固定延时实验

前置条件：Phase 0 到 Phase 5 全部稳定，且有至少两台测试设备。

任务：

- 按 4、8、12、16 MHz 阶梯测试 SPI，不直接跳到最高值。
- 保持现有单数据线连接方式；除非原理图和样机走线确认，不把 dual/quad SPI 纳入本阶段。
- 每档运行纯色、条纹、随机六色和真实照片各 100 次；检查错行、颜色 nibble 错误、BUSY 超时和重启。
- 用逻辑分析仪确认时钟、CS 和数据建立/保持时间。
- 单独测量 `_wait_busy()` 后 200 ms 与 `_turn_on_display()` 固定延时；每次只改变一个延时。
- 遵守面板 POWER_ON/OFF 时序，任一批次出现异常即回退。

验收：

- 选择在全部测试设备和温度点零错误的最高保守频率；
- 连续 500 次刷新无新增显示异常；
- 固定延时优化有可重复的净收益，且不增加 BUSY 超时、残影或颜色偏差；
- 如果总收益小于 200 ms，保留上游默认值，避免维护成本。

### Phase 7：可选的厂商波形路线

只有取得以下材料才启动：

- 与 ED2208-DOA / EL040EF1 和面板批次匹配的 waveform/initial data；
- 支持的温度范围、刷新模式和寿命限制；
- 对应控制器命令及官方参考实现；
- M5Stack/E Ink 对 VCOM 和电源配置的书面说明。

该路线在独立实验分支和专用样机执行，不进入默认固件，直到完成颜色、残影、温度和寿命验证。

## 5. 测量与验收指标

### 颜色

- 六色固体 patch 的实测 CIELAB；
- 测试色块和照片区域的平均、P95 Delta E 2000；
- 肤色、天空、植被、灰阶的分类指标；
- 高亮区污染点比例和同色聚簇度；
- 盲测偏好率；
- 网页预览与实体屏在受控光源下的差异，仅作为辅助指标。

### 性能

- 请求到 job 入队；
- 排队到处理开始；
- 解码、缩放、色彩处理、量化；
- SPI 数据传输；
- POWER_ON、DISPLAY_REFRESH/BUSY、POWER_OFF；
- 端到端 P50/P95；
- 每个用户动作的物理刷新次数；
- 最小 internal heap、最小 PSRAM 和任务 stack high-water mark。

### 稳定性

- 连续刷新 500 次；
- 上传、按键、轮播、EzData 并发压力 200 轮；
- 掉电/低电量、SD 拔插、Wi-Fi 中断和损坏 `.pc4`；
- 10/25/40 摄氏度测试；
- legacy 文件和设置向后兼容。

## 6. Feature flags 与回滚

建议开关：

- `display.worker_v2`
- `color.profile_v1`
- `color.pipeline_v2`
- `color.dither_mode`
- `asset.pc4_enabled`
- `display.dedupe_enabled`
- `display.spi_mhz`
- `display.timing_profile`

每个阶段保持 `legacy` 可选。profile 和 `.pc4` 都带版本；新固件遇到未知版本应回退到原图 legacy 路径，而不是尝试显示。

回滚触发条件：

- 任一 BUSY 超时或显示驱动死锁；
- 新增错行、随机颜色、残影或不可恢复的面板状态；
- 内存持续下降；
- 关键测试图颜色指标或盲测显著回退；
- 旧图片库不能显示。

## 7. 推荐交付顺序

1. PR 1：仅 metrics、测试语料描述和 host golden harness。
2. PR 2：Display Worker 与线程安全迁移，画面保持逐字节不变。
3. PR 3：factory profile、感知 nearest 和 LUT，默认仍可切 legacy。
4. PR 4：照片误差扩散和三种内容模式。
5. PR 5：WASM 预览、`.pc4` 格式和设备直通路径。
6. PR 6：hash 去重、任务合并和 job 状态 UI。
7. PR 7：经硬件数据支持的 SPI/固定延时调整。

每个 PR 必须独立可回滚，包含基线对比、构建结果、host 测试和样机记录。不要把 Display Worker、色彩算法、存储格式和 SPI 时序合并到同一个 PR。

## 8. 决策门与粗略工期

以下估算按一名熟悉 ESP-IDF 的工程师、可随时使用两台样机计算，不包含等待色差仪、逻辑分析仪或厂商资料的时间：

| 阶段 | 预计工程日 | 进入下一阶段的决策门 |
| --- | ---: | --- |
| Phase 0 | 2 到 3 | 基线可重复，计时与 golden 输出可信 |
| Phase 1 | 3 到 5 | 所有显示入口完成串行化，压力测试通过 |
| Phase 2 | 3 到 5 | 感知 nearest 达到颜色指标且资源预算通过 |
| Phase 3 | 4 到 7 | 盲测达到偏好率，文字/高亮污染无回退 |
| Phase 4 | 5 到 8 | M5GFX fork 可复现，WASM/设备输出逐字节一致 |
| Phase 5 | 2 到 4 | 重复与突发操作显著减少物理刷新次数 |
| Phase 6 | 2 到 4 | 硬件压力测试证明净收益和稳定性 |

预计合计 21 到 36 工程日。Phase 0/1 是后续工作的强制前置；Phase 2/3 可先在 host 端并行试验，但合入顺序不变；Phase 6 可以在收益不足时直接取消。

项目级 Go/No-Go：

- Phase 2 后如果颜色指标和盲测均无明显提升，停止 WASM/存储格式扩展，保留 legacy。
- Phase 4 前必须确认团队可维护 M5GFX fork；否则只做 RGB888 legacy 传输，不承诺 4bpp 直通。
- Phase 5 后重新评估用户感知等待；如果主要问题仍是物理波形，软件侧停止追求数量级提速。
- Phase 6 后只有具备正式厂商材料才讨论 Phase 7。

## 9. 外部依据

- M5Stack PaperColor：<https://docs.m5stack.com/en/core/PaperColor>
- 4 英寸 EL040EF1/Spectra 6 面板资料：<https://files.waveshare.com/wiki/4inch-e-Paper-HAT%2B-(E)/4-inch-e-paper-user-manual.pdf>
- E Ink ED2208-DOA 评估套件：<https://shopkits.eink.com/en/product/detail/4%27%27Spectra6ePaperDisplay>
- E Ink Ripple/第二代波形：<https://www.eink.com/news/detail/E-Ink-Ripple-Second-Generation-Waveform-Architecture-E%20Ink-Spectra-Displays>
- MIT 许可的 OpenDisplay dithering：<https://github.com/OpenDisplay/epaper-dithering>
- GPL-3.0 研究对照 PaperColor-Frame：<https://github.com/MarsTechHAN/PaperColor-Frame>
