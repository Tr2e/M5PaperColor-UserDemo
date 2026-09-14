# 堆叠笔触：九张照片固定参数验证

日期：2026-09-14。被测版本：`acaed4e` 中的主机 C++ 原型，未改动算法参数或固件。

后续已有[结构保留优化版本](papercolor_stacked_brush_optimization.md)。本报告保留旧版结果；要用当前代码复现此旧行为，请在批量命令后加 `--disable detail --disable scale --disable quiet`，并输出到新目录，避免覆盖历史验证记录。

## 结论

运行层面：九张照片均完成两次 ASan/UBSan 渲染，无诊断错误，每张的两次 PPM 输出逐字节一致。这个结果仅覆盖当前主机、编译器和九个输入，不等于所有输入、设备内存或性能均可靠。

视觉层面：**还不能作为通用、稳定好看的默认油画模式**。湖山、水果能形成清楚的覆盖色块与体积，但人像五官、透明器物和低对比细节损失明显。尤其 P2 是应当保留的失败样本，不能用“风格化”解释掉五官结构的消失。

用户参考图的核心是“用有组织的笔触塑造形体”。本版已经有覆盖关系，但仍有大量均匀短条纹，背景有时比主体更抢眼；并非有笔触纹理就达成目标。

## 验证方法与边界

- 先按三类各三种内容选片，再统一运行；没有根据输出好坏换图，也没有逐图调参。
- 来自公开照片页面，下载 CDN 提供的 1200 像素宽版本；不使用 AI 生图替代算法输出。来源不代表对拍摄真实性做过独立鉴定。
- 应用 EXIF 方向，完整构图等比适配 `600×400` 横屏，不裁脸、不拉伸。
- 先做 RGB565 往返，左右图在同一色深下比较，避免把色深变化误判为油画化。
- 仅将照片内容矩形传给原型，处理后添加白色留边；这是测试工具的内容区域处理，不代表主机原型已经具备固件的 stride/rect 接口。
- 统一半径 `26 / 15 / 9 / 5`、误差阈值 `7 / 12 / 17 / 23`、随机种子 `0x5041494e`。同一个编译产物处理全部图片。
- 竖图内容宽约 `267～310` 像素，横图接近 600 像素。构图、尺寸与题材因素混合，因此不能仅凭本组结果断言某一题材天生不适合算法；固定绝对笔触尺寸的风险已经暴露，但要用同图多尺寸实验进一步分离影响。
- 本轮不包含 Spectra 6 量化/抖动、不包含屏幕照片、不评价设备耗时和 PSRAM 峰值。
- 下表是人工视觉判断，不是盲评、统计通过率或可迁移的美学指标。SSIM/PSNR 也不能单独判断油画是否好看。

## 九张样本逐项检查

| 编号 / 内容 | 内容尺寸 | 笔触数 | 观察结果 | 判断 |
| --- | --- | --- | --- | --- |
| L1 湖山倒影 | 594×400 | 2238 | 冷暖关系、山体与倒影清楚，覆盖色块有体积；树林被并块，水面渐变转成较碎条纹 | 方向成立，仍需收敛水面纹理 |
| L2 沙漠夕照 | 310×400 | 625 | 暖色气氛和沙丘大轮廓保留；细脊线消失，天空笔触带状、右上高光有规律条纹 | 可作粗笔风格，不能当细节保真 |
| L3 雾林 | 267×400 | 553 | 近树、远山分层尚在；针叶和细枝合并，雾的连续性变成块面 | 条件可用，空气感减弱 |
| P1 彩色棚拍 | 310×400 | 1147 | 姿态、肤色和脸部大轮廓保留；眼睛、嘴角、手指被明显简化 | 五官保真不足 |
| P2 黑白人像 | 267×400 | 219 | 仅保留受光脸部大形与少量衣褶；眼、鼻、嘴和表情严重丢失 | 明确失败，阻止通用模式默认开启 |
| P3 户外逆光 | 600×383 | 1357 | 光照气氛和头发轮廓尚好；眼口细节变弱，波点衣物丢失，面部色块过粗 | 气氛成立，人像精度不足 |
| S1 水果玻璃碗 | 267×400 | 770 | 水果亮暗面、暖色和覆盖关系接近目标；果实分界与碗口变形，背景短条较抢眼 | 本组较接近目标，器皿轮廓需保护 |
| S2 暗背景玻璃红果 | 267×400 | 738 | 瓶子轮廓仍可辨；瓶身圆环、玻璃薄边与透明感显著损失，小红果合并 | 材质与小结构不可靠 |
| S3 花卉茶具 | 267×400 | 818 | 花瓶、杯子和黄白配色仍可辨；花朵细分形状、花枝、桌布花纹消失，墙面出现显眼方向条带 | 气氛可用，主体细节与背景控制不足 |

所有对比图保留全部样本，而非成功样本精选：

- [完整逐张图册](../artifacts/oil_paint_validation/index.html)
- [风景三图](../artifacts/oil_paint_validation/landscape.png)
- [人像三图](../artifacts/oil_paint_validation/portrait.png)
- [静物三图](../artifacts/oil_paint_validation/still_life.png)
- [运行日志、源码与素材 SHA256](../artifacts/oil_paint_validation/results.json)

## 从结果回到代码：下一轮优先级

以下是基于现象和代码的候选原因，不是已经通过消融实验验证的因果结论。本轮仅验证，不改动被测算法。

### P0：先保护结构，再继续美化笔触

1. **保留细节参考层。** 当前构造函数先做 5×5 平均并以 3 像素间隔降采样；后续 `sample()`、误差、方向、取色均依赖此参考。已被抹掉的眼睛和玻璃细边，最后多画几笔也无法从此参考恢复。建议粗笔沿用低分辨率参考，细笔的误差与颜色来自原始 RGB565 / 更细参考；评估新增访问和内存成本。
2. **按照片内容尺度确定笔触，再按局部结构收缩。** 当前四档半径为固定像素，最小档名义半径为 5。建议先测试同一照片多尺寸，再引入基于内容矩形短边的统一比例规则；细结构区域增加约 1～3 像素级的候选笔触，不做每张照片手工调参。
3. **改进细节误差权重和停笔条件。** 全图 RGB 最大通道误差、固定阈值与粗参考并不表达“眼睛很重要”。先用原图边缘/局部对比构建轻量结构权重，尝试有限的细节补画预算；不能声称纯梯度已经等价于人脸保护。若仍无法保住人像，应保留人像提示/较轻效果，而不是默认同一强度。

### P1：减少纹理抢戏与穿越轮廓

4. **笔触形状拟合检查完整路径。** 当前只在前后左右四个方向的端点检查色差，端点相似并不表示笔触内部没有跨过瓶沿/果实边界。建议沿中心线和横截面检查边缘阻挡，提前缩短/收窄完整笔触；不要退回逐像素硬裁剪造成的碎屑。
5. **平坦区域降低密度与方向重复。** L2 天空、S1 背景和 S3 墙面的规则短条，应通过平坦度控制笔触预算、相邻笔触方向相关性及尺度变化改善。保留少量大笔底色，不全局增加噪声、浮雕阴影或锐化。
6. **主体与背景分配不同的细节预算。** 优先采用可在设备上负担的边缘/局部对比策略；人物语义识别或材质分割不是本版已有能力，需要另外评估计算成本，不能假设免费获得。

### 下一轮验收

- 固定这九张作为回归集，全部展示旧/新结果，禁止只用 L1 或 S1 验收。
- 先单独验证“细参考层”“尺寸归一化”“结构权重”，每次只改变一个因素；再组合。
- P2 的眼鼻口结构、S2 的瓶口/瓶肩薄边是优先失败用例；改善它们时不能使 L1/S1 全面退回照片滤镜或模糊涂抹。
- 增加同图多尺寸控制组，区分横屏缩放造成的损失与算法附加损失。
- 这九张后续会成为开发集；优化完成后另找未见照片做留出验证，不能再把这九张当作独立泛化证据。
- RGB565 验收后再跑实际六色量化/抖动链路；本轮的彩色预览不能作为墨水屏最终效果承诺。

## 复现

依赖：Python 3 + Pillow，支持 ASan/UBSan 的 `clang++`。脚本仅读取本地素材，不自动联网。

```sh
mkdir -p artifacts/oil_paint_validation/sources
for id in 417074 19316865 29508251 6643922 14173111 7244127 15683363 35769733 10170980; do
  curl -fLsS --retry 2 --max-time 45 "https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=1200" -o "artifacts/oil_paint_validation/sources/${id}.jpg" || exit 1
done
python3 tools/oil_paint_lab/validate_stacked_batch.py artifacts/oil_paint_validation
```

重新下载的 CDN 素材可能变化；严格复现应保留当前本地源文件，并核对 `results.json` 中的 source_sha256。源码哈希、编译器版本、笔触数量及输出哈希也在其中。确定性仅指当前编译产物在本机重复运行一致，不保证跨编译器浮点结果逐字节相同。

## 素材来源与许可

照片仅作为本地算法评估素材，使用遵循 [Pexels 许可](https://www.pexels.com/license/)。不将其视为项目自有或无条件公共领域资产；照片中的人物不代表认可本项目。作者采用核对时页面署名。

| 编号 | 作者 | 原始页面 |
| --- | --- | --- |
| L1 | James Wheeler | [Lake and Mountain](https://www.pexels.com/photo/lake-and-mountain-417074/) |
| L2 | Henrik Le-Botos | [Desert at Sunset](https://www.pexels.com/photo/view-of-dunes-in-the-desert-at-sunset-19316865/) |
| L3 | Laura Chouette | [Misty Forest](https://www.pexels.com/photo/misty-forest-landscape-with-evergreen-trees-29508251/) |
| P1 | Harry H Brewster | [Studio Portrait](https://www.pexels.com/photo/a-studio-portrait-of-a-smiling-woman-6643922/) |
| P2 | MAG Photography | [Black and White Portrait](https://www.pexels.com/photo/portrait-of-elderly-man-in-black-and-white-14173111/) |
| P3 | Gilles Scherrer | [Backlit Portrait](https://www.pexels.com/photo/backlit-portrait-of-beautiful-young-woman-7244127/) |
| S1 | Anna Astakhova | [Fruits in Glass Bowl](https://www.pexels.com/photo/fruits-in-glass-bowl-15683363/) |
| S2 | Valentin Ivantsov | [Glass Vase with Red Berries](https://www.pexels.com/photo/elegant-glass-vase-with-red-berries-still-life-35769733/) |
| S3 | Мария | [Porcelain Cup and Flowers](https://www.pexels.com/photo/porcelain-cup-and-a-bouquet-of-flowers-10170980/) |
