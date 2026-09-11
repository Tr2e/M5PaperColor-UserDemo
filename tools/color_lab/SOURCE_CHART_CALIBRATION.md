# 色彩表主线（2026-09-09）

用户要求暂不依赖红帽照片调色：先以既有色彩表尽量还原整体颜色，
通过色表验收后再做人物局部优化。红帽仅保留为后续回归，不作为本阶段
补偿系数、区域识别或调色板的拟合依据。

## 固定输入与两个参照

主验收输入保持 `artifacts/color_calibration/papercolor-calibration-v1.png`：
400×600，24 个精确 sRGB 色块，加 0–255、步长 17 的中性阶梯。
RGB 和采样区域以同名 JSON 为准，每轮保持布局、输入像素和采样区不变。

新的 `CONFIG_PAPERCOLOR_REFERENCE_CHART_ON_BOOT` 测试入口默认关闭。
开启后用独立 600×400 RGB565 Canvas、旋转 1、原生 PNG 解码、比例 1:1，
经 `PhotoBalanced` 渲染此图。无裁剪、缩放或宿主机预抖动；普通启动显示，
A 返回主页，不写照片库/NVS。原生色表和红帽测试配置均关闭。
页面、网络、存储、显示波形及运行颜色算法保持原样。

辅助参照使用已有 **原生颜料与已知覆盖率混色图**。它绕过照片算法，
用于观察屏幕本身的六种颜料及混色能力；不能把主色表通过照片算法处理后的
色块反过来当作独立原生颜料测量，也不能把驱动 RGB 触发值替换为相机采样值。

## 调整次序与验收

1. 灰阶、黑白：检查是否中性、单调、亮暗可分，先排除彩色污染和层次反转。
2. 红/黄/绿/蓝及橙色：结合原生颜料参照判断亮度与饱和度取舍，保住
   纯红无异常白点，同时不删除浅色所需的白色覆盖。
3. 紫/洋红/青/青绿/黄绿：结合已知比例的相邻颜料混色，判断色相偏移、
   偏蓝或过灰。先选择目标混色比例，再讨论抖动纹理。
4. 每个候选必须同时检查完整色表和连续渐变（红→粉、红→黑、中性及
   色相边界），避免为了单块好看损坏邻色或引入跳变。
5. 色表整体稳定后，再回到红帽人像及其它照片做局部层次和纹理回归。

“尽量还原”以屏幕可达颜色为边界；手机只支持相同条件下的相对比较。
固定光源、距离、角度、曝光和白平衡，保留完整白边；照片本身无法提供
绝对色度 profile 或可靠 Delta-E。先留下一张本次基准色表实拍，后续每次
只改变一个因素（目标映射、颜料模型或抖动），记录变化及受保护色块。

## 第一份色表固件：沿用基准算法

```sh
./tools/idf.sh -B /private/tmp/papercolor-reference-chart-build \
  -D SDKCONFIG=/private/tmp/papercolor-reference-chart-sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/reference-chart-sdkconfig.defaults' build
```

配置为 LUT 和单颜料白色约束开启；没有新补偿。离线使用实际 RGB565
背板方向及 FS 渲染完整主色表，输出 SHA-256 与 21b0370 已记录结果一致：
`898fa4b5f40af6f867faaf8ad88ecaaf2c16e500c0ebab440f5c35c7045c20c9`。
分块基准保存为 `artifacts/color_calibration/source-chart-baseline-21b0370.json`。
这些是原生色码比例，不是物理校色数据。

默认关闭入口编译、既有 host 回归及 H5 源图回归通过。
独立 ESP 构建通过，镜像 3,252,064 字节，内部校验通过；SHA-256：
`5bb589d5325e1a111832e90b769bbc31d4e68f3803e02d3ae7353528823e5205`。
与已验收 sdkconfig 的唯一启用项差异为
`CONFIG_PAPERCOLOR_REFERENCE_CHART_ON_BOOT=y`。链接映射含源色表 PNG，
不含 Kodak PNG。固件及 sdkconfig 已保存到
`.cache/firmware/source-chart-baseline-21b0370/`，正常回退镜像哈希再次核验不变。
用户进入下载模式后，已将此镜像应用分区烧录到 PaperColor：USB 序列号和
同一打开连接上的芯片 MAC 均核对为 `44:1B:F6:C1:34:10`，目标端口
`/dev/cu.usbmodem83301`。写入 `0x10000`，3,252,064 字节，26.9 s，
`Hash of data verified`，退出码 0。stopwatch 未访问，照片与配置分区未写入。
已请求 RTS 重启，源色表实际显示及本轮基准实拍仍待确认。

烧录前必须核对目标 USB 序列号及芯片 MAC `44:1B:F6:C1:34:10`，
仅写新构建的应用镜像到 `0x10000`，保留存储分区。
另一台 stopwatch 的 MAC 为 `44:1B:F6:C1:8A:00`，不得访问。
不要运行自动选择串口或含存储分区的全量 flash 命令。

正常回退仍使用 `.cache/firmware/accepted-21b0370/paper_color.bin`，
不要重建覆盖已验收镜像。新测试固件的构建与烧录结果见根目录 TODO。
