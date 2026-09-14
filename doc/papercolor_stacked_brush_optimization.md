# 堆叠笔触优化：结构保留与补画预算

日期：2026-09-14。范围：`tools/oil_paint_lab/render_stacked_ppm.cpp` 主机原型；没有替换固件中的油画算法，没有修改 OS 分支，没有运行六色量化或设备测试。

后续状态：用户已验收本版视觉效果；固件适配与含九张照片的烧录准备已另行实现，见 [固件接入记录](papercolor_stacked_brush_firmware.md)。本文保留视觉优化阶段的设计、消融结果与当时限制。

## 本轮结果

同样九张照片、相同归一化输入、统一算法规则，无逐图配置或人脸手工裁剪。优化后，P2 黑白人像的眼鼻口结构、S2 玻璃瓶的瓶口与圆环得到明显改善，L1 湖山和 S1 水果仍保留大笔覆盖色块。

这不是“所有图均已解决”：P3 逆光人像的低对比五官仍不够稳定；L2 天空和 S3 墙面的条带只得到部分改善；S2 玻璃细边更清楚，但透明感没有完整保留。细节密集区域仍可能出现过碎的小笔触。

- [重点对比：原图 / 旧版 / 优化版](../artifacts/oil_paint_optimized/focus-comparison.png)
- [完整九图册，支持展开原图对比](../artifacts/oil_paint_optimized/index.html)
- [风景旧新对比](../artifacts/oil_paint_optimized/landscape.png)
- [人像旧新对比](../artifacts/oil_paint_optimized/portrait.png)
- [静物旧新对比](../artifacts/oil_paint_optimized/still_life.png)
- [逐项关闭功能的局部对比](../artifacts/oil_paint_optimized/ablation-crops.png)

照片来源、使用许可和旧版逐图观察见[九图验证报告](papercolor_stacked_brush_validation.md)。本组已经参与调参，是开发回归集，不再是独立留出测试集。

## 算法改动

### 1. 粗细参考分离

保留旧版降采样参考，用于粗笔与铺底。新增全尺寸 RGB565 细节参考，3×3 边缘约束平均：中心权重 4，邻点与中心色差超过 32 时不参与，以抑制细小噪声而不直接抹掉高对比薄边。

第四层的目标为 40% 粗参考 + 60% 细参考；第五层读取细参考。细笔取色、方向估计、误差评估都使用对应层的参考，而不是仅把笔触尺寸缩小。

### 2. 内容尺寸自适应

按 `max(0.35, min(width, height) / 400)` 缩放笔触名义半径和铺底网格。半径四舍五入且不小于 1；候选网格步长不小于 2。宽高仍受原型的 1～600 输入限制。

典型结果：

| 照片内容区域 | 实际五层半径 |
| --- | --- |
| 594×400 | 26 / 15 / 9 / 4 / 2 |
| 310×400 | 20 / 12 / 7 / 3 / 2 |
| 267×400 | 17 / 10 / 6 / 3 / 1 |

自适应使用照片内容矩形，而非含白色留边的整个屏幕。它不是尺度不变性保证；细节参考半径、阈值等仍包含固定像素常量。

### 3. 细节优先级与补画预算

第一轮直接加入细笔，九图中的细节被过量重建，画面过于接近照片滤镜。最终采用：

- 第四、第五层候选按“当前色差 × 截断后的局部结构强度”稳定排序，同优先级保留种子决定的顺序。
- 实际落笔前再次计算实时画布误差，避免把排序前的误差当成仍未修复。
- 第四层每图最多 `max(1, width×height/85)` 笔，第五层最多 `max(1, width×height/110)` 笔，均为整数除法。
- 局部结构对比小于 18 / 30 时分别跳过这两层，减少平坦区域的全面细描。
- 预算限制的是实际补画笔数，不限制全部候选的生成、评估或排序成本。

该优先级不理解人物语义。眼睛得到改善是其边缘进入了细节补画，不代表已有“人脸保护”；柔光小脸仍可能输给衣物、头发等强结构。

### 4. 笔触拟合检查中间路径

旧版只检查前后左右四个端点。现在沿这四个轴线逐步检查色差，粗笔步长 2 像素、细笔步长 1 像素，遇到明显跨色边界提前缩短。仍然绘制完整笔触，不做逐像素硬切碎片。

这不是完整二维足迹检测：非轴线上的薄边、弯曲足迹和极细结构仍可能漏检，不能保证所有边界都不越界。

### 5. 平坦背景的轻量控制

局部对比低于 22 时降低笔触不透明度到 0.65，并去掉附加明暗颗粒。弱方向区域增加确定性的有限方向变化，减少独立短条全部朝向同一方向的观感。

单独关闭此项的对照变化小于细节参考带来的变化；尚不能宣称背景条纹问题已根治。主体的非平坦区域仍使用原来的高不透明度覆盖。

## 消融与正确性验证

使用同一份最终 C++ 源码编译五组，每组九张、每张两次，合计 90 次 ASan/UBSan 渲染：

| 组别 | 说明 | 九图总笔触数 |
| --- | --- | --- |
| 完整优化 | 三项功能开启 | 29074 |
| 关闭细节 | 保留缩放和背景控制，关闭细节参考、路径拟合与细笔预算组 | 12341 |
| 关闭缩放 | 使用固定半径与铺底网格 | 23794 |
| 关闭背景控制 | 保留细节与缩放 | 29080 |
| 全部关闭 | 重放旧行为 | 8465 |

五组都完成确定性重复渲染，无 ASan/UBSan 诊断错误。全部关闭组的九张输出 PNG SHA256 与此前保存的旧版九张完全一致，可排除无意修改基线行为导致的假对比。

这些开关是功能组，不是每一行改动的独立因果实验。局部对照显示关闭细节组后 P2 五官重新大幅丢失；仅关闭缩放仍能保留五官，但粗细关系有所变化。不能把这解释为所有照片都需要相同细节强度。

新增 `test_stacked_lab.py` 的 38 个测试场景通过：

- 27 个纯色/尺寸组合，覆盖 1×1、单行单列、267×400、600×400、400×600、600×600。
- 检查平坦输入保持平坦、颜色误差在 RGB565 量化范围内、重复输出一致、半径与落笔预算有效。
- 3 个高频结构压力输入。
- 8 个空输入、错误格式、零/负/超限尺寸、错误最大值及截断数据的拒绝测试。

既有 `run_host_tests.sh` 也通过：固件油画核心的边界与确定性、控制器过期点击/恢复/分配失败，以及 100/1000 Hz 协作调度。此检查不等于新原型已经接入这些固件接口。

## 成本与尚未完成的工作

本轮是视觉质量优化，不是已验证的设备加速优化。九图总笔触数从 8465 增至 29074，约 3.43 倍；笔触更小，不能据此推算耗时增加倍数。

新增细节参考占 `2×width×height` 字节，600×400 时为 480000 字节（约 469 KiB）。还存在候选向量、优先级字段与 `stable_sort` 临时内存；高密度候选可比旧版更多。未测设备峰值内存与耗时，不能直接按本版数据结构移植到固件。

后续设备实现需评估固定容量候选队列、分块优先级或有界选择、协作让出执行权、工作缓冲生命周期；然后验证 Spectra 6 量化抖动是否破坏刚保住的细边。当前不合入 OS 的默认显示链路。

## 复现

依赖 Python 3、Pillow、支持 ASan/UBSan 的 clang++；九张源文件保留在 `artifacts/oil_paint_validation/sources`。输出写入新目录，不覆盖旧基线。

```sh
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_optimized --sources artifacts/oil_paint_validation/sources --baseline artifacts/oil_paint_validation
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_ablation_no_detail --sources artifacts/oil_paint_validation/sources --baseline artifacts/oil_paint_validation --disable detail
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_ablation_no_scale --sources artifacts/oil_paint_validation/sources --baseline artifacts/oil_paint_validation --disable scale
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_ablation_no_quiet --sources artifacts/oil_paint_validation/sources --baseline artifacts/oil_paint_validation --disable quiet
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_baseline_replay --sources artifacts/oil_paint_validation/sources --baseline artifacts/oil_paint_validation --disable detail --disable scale --disable quiet
python3 tools/oil_paint_lab/summarize_stacked_validation.py artifacts
python3 tools/oil_paint_lab/test_stacked_lab.py
bash tools/oil_paint_lab/run_host_tests.sh
```

每组 `results.json` 记录编译命令、源码 SHA256、素材 SHA256、基线记录 SHA256、实际半径、各层笔触数和预算。原图/新图对比与旧图/新图对比分开保存。所有可视化都是实际算法输出的排版；局部图仅做最近邻放大，没有修图或 AI 补画。
