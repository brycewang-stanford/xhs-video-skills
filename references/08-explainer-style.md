# 讲解型视频（流水线 E）· 抖音风固定标题 + 3Blue1Brown 画面

用一篇文章、一篇论文、一条新闻做 1–3 分钟讲解视频时，默认这样做。
样片：《2026 诺贝尔经济学奖：给宏观政策装上微观基础》（2:54，2026-10-13），本模板就是从它抽出来的。
模板在 `templates/explainer-douyin/`，本页是做法和版式数字。

## 画面长什么样

| 元素 | 规格（1080×1920 画布） |
|---|---|
| 背景 | 深紫径向渐变（中心 `#4B1560` → 边缘 `#0C0410`）+ 极淡网格 + 暗角，全片不变 |
| 固定标题 | 左上 x44 y196 起，**全程不动、第 0 帧就在**（也是封面的标题）。两行黄底黑字（`#FFE94A`，76px，粗）+ 两行黑底白字（52px） |
| 进度条 | 标题下方 y556，一幕一段，黄色随时间填满 |
| 舞台 | x48 y584，984×810。所有图表、公式、截图都画在这里 |
| 字幕 | y1408 起，白字 54px 粗体 + 黑描边 + 半透明黑底，居中，最多两行 |
| 底部 | y1580 以下留空，给抖音 / 小红书的账号栏和按钮 |

配色（3Blue1Brown 一路）：蓝 `#58C4DD`、黄 `#FFE94A`、绿 `#83C167`、红 `#FC6255`、白 `#F3EEF7`、灰 `#A79BB3`。
中文用系统苹方（`local()` 声明），公式用随模板带的 STIX Two（斜体变量、正体算子）。

## 固定标题怎么写

- **写结论，不写问句。** 第一行是主题（「2026诺贝尔经济学奖」），第二行直接给答案（「给宏观政策装上微观基础」）。
  「两位得主到底研究了什么？」这种问句被用户当场否掉过。
- 两行白字各写一个要点，一人 / 一事一行（「霍尔：消费是一条「随机游走」」）。
- 每行 ≤ 12 个汉字，否则 76px 放不下。

## 一条视频三份手写文件

```
<项目>/tools/script.py   口播稿：FRAMES = [(幕 id, [(字幕, 读音或 None), ...]), ...]，一项一屏字幕
<项目>/tools/scenes.py   各幕画面：SCENES = {幕 id: dict(html=..., js=...)}，末尾调 build()
<项目>/tools/kit.py      引擎，一般不动
```

```bash
cp -R <skill>/templates/explainer-douyin <项目>
cd <项目>
PY=~/.cache/hyperframes/tts-venv/bin/python        # 要有 numpy、soundfile；本地备用音色还要 sherpa-onnx
$PY tools/voice.py                                  # 录音 → assets/voice/narration.wav + timings.json
$PY tools/scenes.py                                 # 生成 compositions/、index.html、assets/bgm.m4a
npx hyperframes check                               # 必须 Check passed
npx hyperframes snapshot --no-end --at 5,20,40      # 抽帧看版面（每幕至少看一帧）
npx hyperframes preview                             # 给用户预览；用户说 render 再渲染
npx hyperframes render -o renders/<名字>.mp4 --fps 30
```

改一句口播：改 `script.py` → 重跑 `voice.py`（只重录改过的句子）→ 重跑 `scenes.py`，动画自动重新对时。

## 口播稿

- 3 分钟 ≈ 55 屏字幕、10 幕；每屏 ≤ 26 个汉字（超过 22 字自动缩一号字）。**这条流水线不受「一屏 ≤ 14 字」限制**，因为字幕区是两行宽版。
- 结构：钩子（一个问题或反常识）→ 事件与人物 → 旧做法为什么不行 → 核心结论（每人 2–3 幕）→ 两条线怎么合上 → 去处（「完整版见图文」）。
- 数字、年份、英文在「读音」里写念法：`("1978 年，他发了…", "一九七八年，他发了…")`；人名里的间隔号在读音里去掉。
- 事实只用来源文章里有的；来源里的归属、日期、保留语气照留。自己补的东西（例如教科书标准公式）要在交付时说明。

## 画面写法（scenes.py）

- 每幕的 `js` 用 `at(i, f)` 对时：第 i 句口播念到 f（0–1）处。常用助手：
  `draw` 描线、`rise` 上浮出现、`pop` 弹出、`fade` / `out` 淡入淡出、`mark` 黄色划线、`glow` 高亮公式里的一项、`growX` / `growY` 柱子长出来、`pulse`。
- 图表全部用 SVG 手画：`path(k, poly(点列), 颜色)` 配 `draw()` 就是「描出来的曲线」。有真实数据就读真实数据（复现结果的 CSV），并在画面角落注明出处。
- 公式用 `M("c<sub>t</sub> = …")`，要强调的项包 `HL(...)`，再 `glow()`。
- **每幕第一秒就要有东西**：开场别空着等口播，先放截图卡片或一句大字。
- SVG 元素的缩放原点一律用 `class="sc" / "gx" / "gy"`（引擎用 GSAP 设原点）。不要在 CSS 里写 `transform-origin`，缩放后位置会跑偏。
- 两个 `@font-face` 不要共用一个 family 名再靠 `font-style` 区分：预览正常，渲染会整体退回无衬线。

## 真实截图

人物和论文第一次出场时，用真实页面截图做成斜放的卡片（`shot(k, 图名, 左, 上, 宽, 高, 倾斜角, "来源说明")`），2–4 秒后淡出，让位给图表和公式。去哪找：

| 要什么 | 怎么拿 |
|---|---|
| 论文首页 | 作者主页 / NBER / Brookings 的 PDF：`curl -L -A "<浏览器 UA>" -o x.pdf <url>`，`pdftoppm -r 150 -f 1 -l 1 -png x.pdf out`（NBER 章节 PDF 第 1 页是封套，取第 2 页） |
| 学校 / 机构介绍页、出版社书页 | 无头 Chrome：`chrome-headless-shell --headless --window-size=1280,1100 --force-device-scale-factor=2 --virtual-time-budget=9000 --screenshot=out.png <url>`（HyperFrames 自带一份在 `~/.cache/hyperframes/chrome/`） |
| 截图里只要一块 | `ffmpeg -i in.png -vf crop=w:h:x:y out.jpg`，裁到手机上读得清的那一块（标题 + 作者，或头像 + 一段简介） |

- 截完**逐张看一眼**：有的站第二次请求会返回人机验证页；nobelprize.org、期刊官网（JSTOR / UChicago）、部分出版社会直接 403，拿不到就换来源或如实告诉用户，不要拿验证页充数。
- 下载的文件放进单独的空目录；原图存 `assets/src/`，裁好的放 `assets/img/`。
- 每张图配一行来源说明；新闻图注明「图源：××报道截图」。

## 配音

- 一个女声普通话，全片同一把声音。默认 edge-tts 晓伊；连不上（403）时 `voice.py` 自动退到本地 MeloTTS 中文女声。**不要用 Kokoro 的中文音色**（用户评价「so ugly」）。
- **响度必须一句一个样大。** 逐句合成的音量天然忽大忽小（实测相差近 10 dB），`voice.py` 已经处理：每句先拉到同一 RMS，再整轨压缩 + 限幅顶到接近满刻度。处理后句间差应 ≤ 2 dB，峰值约 -1 dB。
- 背景音乐：`build(..., bgm="x.mp3")`，默认压到 -33 LUFS（人声约 -16），开头 1.2 秒淡入、结尾 3 秒淡出。

## 封面

1. 从成片里挑「标题 + 人物 / 主图」那一幕的一帧做底图（`cover_frames.py --pick <秒>`，或用户自己截的图）。
2. 用 `scripts/cover_compose.py` 把一张更抓眼的图（官方画像、产品图）嵌进底图中央的图片位，圆角贴合，**另存 `-v2`，不覆盖原图**：

```bash
python3 <skill>/scripts/cover_compose.py 底图.png 画像.jpg -o 封面-v2.png                       # 底图是一帧原始画面
python3 <skill>/scripts/cover_compose.py 底图.png 画像.jpg -o 封面-v2.png --box 740,752,1384,790  # 底图带留白 / 被裁过：给像素框
```

- 新图要把原来的「图源」那行一起盖住（默认图片位已含这一行），否则来源标注就张冠李戴了；新图的出处另行注明。
- 原图宽度不到图片位的 2/3 会发虚，脚本会提示，尽量换大图。

## 交付前自查（在 07 清单之外）

- [ ] 固定标题是结论句，四行都没被截断，第 0 帧就在
- [ ] `npx hyperframes check` 通过；每幕抽过帧，没有元素重叠、没有空舞台超过 1 秒
- [ ] **渲染后的 MP4** 里抽帧看过公式字体（预览对不等于渲染对）
- [ ] 人声句间响度差 ≤ 2 dB；有音乐时人声始终清楚
- [ ] 每张截图都看过内容、都有来源说明；拿不到的来源已告诉用户
- [ ] 先给预览，用户说渲染再渲染
