# 首页缩略图与Logo颜色策略不一致修复（2026-09-10）

用户要求暂停色表调参，先解决首页与图片浏览器显色差异。本轮不改任何颜色补偿系数、LUT、色域策略或扩散算法。

## 根因

首页不是完全绕过颜色处理。`app_manager.cpp` 的完整首页与局部刷新原先均调用默认 `papercolor_push_canvas(..., Ui)`，其模式是最近色LUT映射，不执行PhotoBalanced的目标补偿和Floyd–Steinberg扩散。

本地与Ezdata的 `drawThumbnail()` 只负责缩放、裁剪、解码到首页RGB565 Canvas，没有独立颜色处理；首页嵌入的78×46 `papercolor_web_logo.png` 同样只解码到这个Canvas。整页最终走Ui，所以缩略图和Logo均受影响。两种图片浏览器的完整图片路径显式使用 `PhotoBalanced`。这是可确认的调用路径差异；无需重新调整色表系数才能修复。

## 修改

- 新增 `UiWithPhotos` 合成方式：底层UI仍用原最近色映射，在指定彩色区域覆盖PhotoBalanced生成的原生码。
- 首页缩略图 `(16,398,176,145)`、Logo `(306,7,78,46)` 各有独立目标缓存和误差行，使用与浏览器完全相同的照片算法。没有缩略图时只处理Logo；文字、线框、占位图保留Ui。
- 逻辑400×600首页旋转为600×400背板坐标后，缩略图为 `(57,16,145,176)`，Logo为 `(547,306,46,78)`。共用一个行传输循环、一次startWrite/endWrite，无二次量化或额外整屏刷新。
- 两区域各从局部第0行开始扩散，外部文字或另一张图不会贡献误差。原Canvas不改写，旋转、裁剪、滚动矩形以及显示刷新模式返回时恢复。
- 完整首页与日期/音频等局部提交都通过 `papercolor_home_push()`，沿用已有物理裁剪，避免局部刷新时把图片重新按Ui输出。
- 仅支持最多两个互不重叠、完整位于Canvas内的区域及0..3旋转；无效区域拒绝并退回Ui。实验颜色管线关闭时仍保持原pushSprite行为，内存不足沿用既有回退行为。

照片浏览器本身的算法、缩放裁剪逻辑和两类图片获取流程未修改；嵌入Logo素材未修改。当前完整24色通过的所有补偿开关继续保留。正常构建关闭完整色表启动，启动进入首页。

同尺寸、同RGB565像素的目标与输出一致；实际首页缩略图缩小且使用cover裁剪，不能承诺与全屏照片逐像素网点或所有小面积颜色完全一致。网页RGB与六色实体颜料的色域差异也不会仅靠统一调用路径消失。

## 验证

`python3 tools/color_lab/run_home_photo_tests.py` 在主机链接**真实** `papercolor_lut_display.cpp`、照片算法与真实LUT；只模拟M5/ESP输入输出。ASan/UBSan通过：

- 两个彩色区域与独立Canvas通过浏览器PhotoBalanced渲染的同尺寸裁剪逐像素一致。
- 彩色区域外与旧Ui输出逐像素一致；改变外部背景不影响区域内结果。
- 四种旋转对应相同物理区域；RGB565快速读取与RGB888读取结果一致。
- Canvas状态、显示模式恢复；一次传输；物理局部裁剪外像素不变。
- 空区域/Logo单区域、非法矩形/重叠/越界/过多区域、内存分配失败与释放检查通过。
- 两区域工作区共4,776字节，不需要预分配整屏照片码缓存。

另编译并执行颜色管线关闭的真实显示适配器，确认保持单次pushSprite与无pipeline统计。ESP-IDF构建通过；镜像checksum9d、validation hash有效。代码未重新调色，无需重复跑此前所有色表参数扫描。

## 固件与烧录

配置 `tools/color_lab/home-photo-pipeline-sdkconfig.defaults`；相对IMG_9952配置仅关闭 `REFERENCE_CHART_ON_BOOT`。构建目录 `/private/tmp/papercolor-home-photo-pipeline-build`，缓存 `.cache/firmware/home-photo-pipeline-candidate/`，含二进制、配置、匹配源码/测试快照、构建与验证记录。

应用3,234,032字节，SHA-256 `29e7cb9045f24eb1fe4a76974baf54c4251bd91b560c532db8be458284af2604`。Color已处于下载模式，重新核对USB序列号及同连接芯片MAC `44:1B:F6:C1:34:10` 后，仅向 `/dev/cu.usbmodem83301` 应用0x10000写入，26.8秒，哈希校验成功、退出码0。stopwatch未打开；照片/设置分区未写入，RTS重启已请求。

尚待物理首页/图片浏览器复核。请松开Boot、单按Reset，等首页刷新后查看缩略图和Logo，再按B打开同一图片比较。收到实拍后先查颜色差异是否缓解、文字/边框是否保持、局部刷新是否影响彩色区域，并读取身份核对后的Color运行指标；正常首页预计报告 `ui-with-photos`。

回退镜像仍为 `.cache/firmware/purple-smooth-chart-candidate/paper_color.bin`（IMG_9952完整表457106f2…）。本轮未提交/推送，色表调参保持暂停。

## 用户人工验收通过

用户明确反馈“我已人工校验，通过；继续校色任务吧”。据此将首页修复标为通过并保留，不要求重复实拍。没有本轮照片或新的运行指标，不将用户验收写成模型实拍检查。校色恢复，后续固件必须保留UiWithPhotos及分区渲染修复。
