# Burkes 照片扩散候选

IMG_9967 在同一屏幕、相同颜色目标和相同面板刷新中比较 Floyd–Steinberg A 与 Burkes B。B 明显缩短 22/23 灰、16 洋红和 14 橙色中的长斜线及人字形连锁；21/24 明暗保持，色相保护没有可辨退步。因此照片模式选择 Burkes。

实现只改变 `PhotoBalanced` 与首页照片局部所使用的扩散核。LUT、可达色域投影、候选颜料集合、目标覆盖比例、原生 RGB565 重建和边缘保护均保持不变。`PhotoDetail` 原本已经使用 Burkes；首页照片局部与浏览器整图调用同一个选择函数，避免两处再次分叉。

完整 400×600 色表中，31,928/240,000 个像素位置改变，反映空间纹理重排。Floyd–Steinberg 全帧黑/白/黄/红/蓝/绿为 `34130/135893/11410/20868/21878/15821`，Burkes 为 `34083/135853/11422/20893/21918/15831`；任一颜料全帧变化不超过 47。任一标准色块内单一颜料计数变化不超过 27，21–24 灰阶仍只含黑白码。Floyd–Steinberg 帧 SHA-256 为 `42407c96d85fd2e70fba200c4485ae4339397a13c02f4ad378c68e22e1231a67`，Burkes 为 `d0f71129301d96d340d84e6f084cf7f4e30d8371cab63e2c4b62108291cb16a4`。逐块数据见 `artifacts/color_calibration/burkes-photo-adoption-comparison.json`。

`run_burkes_photo_tests.py` 的 ASan/UBSan 检查覆盖完整照片算法、两种核和 RGB565 输入。真实显示适配器测试覆盖浏览器整图与首页照片局部逐像素一致、四种旋转、RGB565/RGB888、UI 隔离、裁剪刷新、空区域和分配失败回退。

完整色表 ESP-IDF 候选位于 `.cache/firmware/burkes-chart-candidate/paper_color.bin`，3,263,264 字节，SHA-256 `d61a36577e5e89e96921fa64e893bbf42970614b87424e9cba959680fd3d1315`；checksum `cd`、validation hash `283fcc79ed85265ca056869c5a8bfe3a322eadbc0b3004852ca57942642ad21e` 有效。配置只开启完整参考色表启动页。2026-09-11 已核对 Color 的 USB 序列号及芯片 MAC `44:1B:F6:C1:34:10`，只向 `/dev/cu.usbmodem83301` 的应用地址 `0x10000` 写入该文件；3,263,264 字节在 27.0 秒内完成，设备端数据哈希校验通过。stopwatch `/dev/cu.usbmodem83401` 未打开。当前等待完整色表物理保护复核。
