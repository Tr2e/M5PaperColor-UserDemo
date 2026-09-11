# IMG_9958 阶段检查点

2026-09-11。首页区域颜色修复已独立提交为3c255db。本检查点保存此后的校色工作，包括实验过程与被否决方案；不代表整个颜色还原任务完成。

当前保留：原生峰值/精确顶点保护、彩色边缘残差保护、蓝色次级配比与白量调整、暖色旧补偿旁路、紫色补偿平滑、青色局部平滑配比，以及仅四个原生量化单元的RGB565重建。最新完整24色实拍为IMG_9958，检查记录见 `IMG_9958_REVIEW.md`。完整紫色旁路已否决，不启用。

默认配置保持原样。重现本阶段使用完整色表配置，并为SDKCONFIG选择一个新的文件，避免旧配置覆盖defaults：

```sh
./tools/idf.sh -B .cache/checkpoint-9958/build \
  -D SDKCONFIG="$PWD/.cache/checkpoint-9958/sdkconfig" \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/native565-chart-sdkconfig.defaults' build
python3 tools/color_lab/run_native565_tests.py
python3 tools/color_lab/run_home_photo_tests.py
```

主机工具面向macOS，部分图表工具需要Pillow、NumPy及Menlo字体。首页标准测试使用其独立基础开关；本阶段另外已用全部候选开关测试首页/浏览器同格式一致性。`run_native565_tests.py`验证当前完整候选及关闭重建的负对照，不以失败的历史负对照代表当前构建失败。

当前实拍应用SHA-256为 `0d073d1ba28e48931dcea5b73cc4efe37abd7a55373346c45b005b57728d565f`，3,258,096字节；匹配源代码、配置和烧录记录保存在本地 `.cache/firmware/native565-chart-candidate/`。Git版本元数据或工具环境变化可使重新构建的应用哈希不同。主机完整图表输出为 `61b7a31855ef42f920eb37fdadd4b0f6925995c1a2be5fc6c16fad42edc6b2f1`。

Git包含源码、测试、配置、诊断用小型原生码载荷、预览、数值报告和USB测量记录；本地固件缓存、构建目录、下载目录中的手机HEIC不包含在提交中。

历史A/B的`.sha256`、报告和固定基线检查刻意保留当时身份。当前源码比它们新，部分旧图表配置会因校验拒绝构建，部分历史比较脚本会拒绝不匹配基线。应使用对应历史源码快照复现，或为新实验重新生成并重新验收；不要删除哈希校验、把旧报告当当前输出，或为使旧命令通过而覆盖历史证据。最新完整24色启动路径不使用这些旧A/B载荷。

后续：先分开研究11黄绿、12青绿的颜料比例、白色量与扩散纹理；14/15暖色、16洋红、灰阶网纹及青色旧渐变白点带仍待办。保持09/17/18、10/19、20及原生量化保护。完整色彩阶段后再处理人像。

烧录只操作身份核对的PaperColor（USB和同连接MAC均44:1B:F6:C1:34:10），仅应用0x10000；stopwatch为44:1B:F6:C1:8A:00，不打开。不要使用构建输出中的全分区flash命令覆盖照片/设置。
