# 验收版堆叠油画：固件接入与含照片烧录准备

日期：2026-09-14。分支：`codex/local-oil-paint`。

状态：用户已验收主机视觉效果；已接入固件、打包九张测试照片，并准备离线烧录包。设备当前不在身边，**没有执行烧录，没有完成实体屏、设备耗时或长时间运行验收**。不合入 `feat/papercolor-os`。

## 1. 实现与文档关系

保留[最初方案](papercolor_local_oil_paint_pipeline.md)、[功能与按键契约](papercolor_local_oil_paint_implementation.md)、[九图旧版验证](papercolor_stacked_brush_validation.md)、[验收版算法优化](papercolor_stacked_brush_optimization.md)。本文件补充已验收算法的固件实现与后续烧录方法，不删除历史方案。

当前链路：浏览器显示照片 → A 键单击 → 本机 `papercolor_stacked_render_swap565()` → 原 Canvas `pushSprite()` → M5GFX 官方 Spectra 6 转换/抖动 → 墨水屏。再单击恢复原图。没有引入神经网络、外部计算或预先油画化照片。

### 开关与文件

| 项目 | 行为 |
| --- | --- |
| `CONFIG_PAPERCOLOR_OIL_PAINT` | 默认仍关闭；独立 `on` 构建启用，不改变 OS 默认行为 |
| `CONFIG_PAPERCOLOR_OIL_PAINT_STACKED` | 依赖前项，启用油画时默认选验收版；关闭可回退旧核心 |
| `main/display/papercolor_stacked_painter.h/.cpp` | 固定工作区、五层笔触、细节预算、实时误差、四轴路径拟合 |
| `main/apps/photo_effects/photo_effect_controller.cpp` | PSRAM 快照/工作区申请，当前照片 generation 校验，原图恢复，失败回滚 |
| `tools/oil_paint_lab/render_stacked_ppm.cpp` | 保留为验收视觉参考，不直接编译进设备 |
| `main/apps/local_photo_slideshow/images/` | 四张原有 PNG + 九张测试 JPEG + `SOURCES.TXT` |
| 项目根 `CMakeLists.txt` | 已有 `fatfs_create_spiflash_image(... FLASH_IN_PROJECT)` 将图库打包进 `storage.bin` |

## 2. 移植中保持与改变的部分

保持验收版的像素运算顺序、默认种子、粗细参考、五档半径、误差门限、细节预算与笔触形状。没有再次调节视觉参数。

改变的是运行时资源组织：

- 将 `vector` 改成调用方一次申请的固定布局 PSRAM 工作区；核心内部不调用 malloc/new 分配堆内存（placement new 仅建立工作区对象生命周期）。
- 随机状态改成每次渲染的实例成员，避免跨调用共享可变状态。
- 将 `stable_sort` 改成“优先级 + 洗牌后序号”的严格全序 `std::sort`，保持同优先级的原顺序，又不依赖额外堆内存。
- 接入原图矩形、stride、对齐与重叠检查；错误参数不改目标帧。所有绘制先完成到工作区，再复制到目标帧，保留留边和行尾 padding。
- 在细参考生成、降采样、铺底、候选初始化/生成/洗牌、优先级计算/排序、落笔和输出复制中设置协作回调。控制器沿用 20ms 门限与 `vTaskDelay(1)`，不是每像素无条件休眠。
- 编译使用 `-O2 -ffp-contract=off`，生成 `.su` 栈使用报告供后续检查。仍使用浮点数学库，未承诺设备实时处理。

工作区包含：粗参考 + 细参考 + 紧凑输出 + 铺底颜色网格 + 固定上界笔触候选数组。候选容量为 `floor(w/2)×floor(h/2)`，实际落笔仍受已验收的细笔预算限制。

| 内容矩形 | 核心工作区 |
| --- | --- |
| 594×400（L1） | 3,147,480 字节 |
| 310×400（P1/L2） | 1,644,840 字节 |
| 267×400（P2/S2 等） | 1,414,484 字节 |
| 600×383（P3） | 3,039,248 字节 |

除此之外仍有 Canvas、原图快照及系统资源；例如 600×400 的原图快照是 480,000 字节。申请不到连续 PSRAM 时保持原图，不覆盖、不刷新错误结果。以上不是整机峰值实测。

交叉编译的核心对象无 malloc/堆分配符号引用。`.su` 报告显示渲染入口自身 720 字节、排序递归帧 176 字节；排序还会递归，不能将 720 字节当作最大总栈。现有 `app_mgr` 任务栈为 10,240 字节，仍应实机观测高水位与看门狗情况。

## 3. 验证证据

1. `verify_device_renderer.py`：直接编译与固件相同的核心，对九张已验收 RGB565 输入各渲染两次；18 次 ASan/UBSan 运行通过，输出像素逐字节等于验收版。证据在 [设备核心主机验证](../artifacts/oil_paint_device/results.json)。
2. 新核心测试：工作区前后哨兵、过小/未对齐/重叠缓冲、非法矩形、stride、单行/单列/1×1、横竖图、回调以及源图不变；同一矩形嵌入不同偏移/行距后与紧凑图输出一致。
3. 控制器测试：旧核心/新核心 × 100/1000Hz 四组，覆盖过期点击、恢复、忙碌、两处内存申请失败和非零限频调度；既有旧核心测试也保留。
4. `on` 和 `off` 两套 ESP-IDF 5.5.4 / ESP32-S3 构建。准备包使用 `on`；构建脚本会核对两个有效开关，防止旧 sdkconfig 悄悄禁用验收版。
5. `prepare_flash_bundle.py` 使用 ESP-IDF 官方 FAT 解析工具解开实际生成的 `storage.bin`，逐文件比较 SHA256，确认九张测试照片、四张原图和来源说明均真实在镜像内，而非只检查源目录。

主机逐像素一致不保证不同 CPU/libm/解码缩放实现、不同旋转下屏幕画面逐像素相同；真正屏显与耗时仍须到机验收。九张原始 JPEG 未预先转成油画；设备使用自身图片解码器，和主机 Pillow 归一化可能有细微差别。

## 4. 九张照片与储存分区

九张文件直接提交在 `main/apps/local_photo_slideshow/images`，与之前验证使用的 CDN 源文件 SHA256 一致。原有 `imaged001.png` 至 `imaged004.png` 不变。

| 风景 | 人像 | 静物 |
| --- | --- | --- |
| L1 `417074.jpg` 湖山 | P1 `6643922.jpg` 棚拍 | S1 `15683363.jpg` 水果 |
| L2 `19316865.jpg` 沙漠 | P2 `14173111.jpg` 黑白 | S2 `35769733.jpg` 玻璃 |
| L3 `29508251.jpg` 雾林 | P3 `7244127.jpg` 逆光 | S3 `10170980.jpg` 花卉茶具 |

照片作者、原始链接及许可在同目录 `SOURCES.TXT`，随 FAT 镜像一起烧录。第三方照片不属于项目 MIT 源码许可证；遵循 [Pexels 许可](https://www.pexels.com/license/)。没有重新下载或调色替换验收素材。

沿用 16MB Flash 分区：factory 从 `0x10000` 起，容量 `0x9F0000`；storage 从 `0xA00000` 起，容量 `0x600000`（6MiB）。无需改分区表。包含照片的完整烧录必须写入 `storage.bin`，单独 app-flash 不会更新图库。

## 5. 设备到手前：只准备，不烧录

从项目根执行：

```sh
bash tools/oil_paint_lab/run_host_tests.sh
python3 tools/oil_paint_lab/verify_device_renderer.py
bash tools/oil_paint_lab/build_firmware.sh on build/oil-stacked-ready
bash tools/oil_paint_lab/build_firmware.sh off build/oil-off
```

准备可离线携带的 ZIP（路径按实际 ESP-IDF 环境替换）：

```sh
python3 tools/oil_paint_lab/prepare_flash_bundle.py build/oil-stacked-ready \
  --idf-path /Users/xudanyang/Documents/stopwatch/esp-idf \
  --idf-python /Users/xudanyang/.espressif/python_env/idf5.5_py3.9_env/bin/python
```

输出：`build/oil-stacked-ready/papercolor-stacked-ready.zip`，包含 bootloader、分区表、程序、照片 FAT 镜像、原始烧录参数、来源说明及 SHA256 清单。该脚本只生成包，不调用 esptool 烧录，也不打开串口。二进制在忽略的 build 目录，源码/素材/验证证据/文档进入 Git，可按脚本重建。

## 6. 设备到手后：备份、确认端口，再烧录

**整包烧录会覆盖内置图库。必须先备份设备原有内置照片；不能以“更新程序”为由误写 storage。不会主动擦整片 Flash，烧录清单不包含 NVS；SD 卡不在写入范围。**

确认连接的是目标 PaperColor，替换实际 `PORT` 后才执行：

```sh
tools/idf.sh -B build/oil-stacked-ready -p PORT flash
```

或解压 ZIP，在其目录使用 ESP-IDF 5.5 Python 环境中附带的 esptool：

```sh
python -m esptool --chip esp32s3 -p PORT -b 460800 --before default_reset --after hard_reset write_flash @flash_args
```

若只想更新程序并保留现有图库，应使用同构建的 `app-flash`，但这样不会新增九张测试照片。当前设备不在身边，上述两条真正烧录命令均未执行。

## 7. 到机验收清单

- 选择内置存储；若插入 SD 导致相册优先读 SD，先切回内置或取出 SD。
- 能浏览原有四张和新增九张，横竖方向正常；A 单击油画化、再次单击恢复；B/C 换图、A 双击回首页不处理旧帧。
- P2 五官、S2 瓶口与圆环仍可辨；L1/S1 保留大笔色块，六色抖动没有把细笔打碎成噪点。
- 连续九张处理无重启/看门狗错误；记录 `Stacked render ... compute_us ... workspace` 与显示指标、任务栈高水位。
- 操作忙碌时无交叉画布写入；反复恢复/切图没有 PSRAM 泄漏；内存不足可安全保留原图。
- 实机通过后再决定是否合并到 OS 主分支，本次不自动合并。
