---
name: xhs-video-skills
description: 小红书带货短视频一站式制作流程：选题钩子 → 分镜脚本 → 素材剪辑（口播 / 屏录 / 纯动效 / AI 生成）→ 女声普通话 AI 配音 + 逐句同步字幕 → 封面 → 按小红书规格导出 → 发布前合规检查。封装本机视频工具链（FFmpeg 零依赖脚本、HyperFrames 竖屏模板、video-use 自动剪辑、youtube-clipper、runcomfy 等生成模型 skill），并内置本店商品（雅思 / 托福 / GRE 写作批改考官、AI PPT Skill 选型导航）的品牌视觉与合规红线。当用户提到 小红书、带货、爆款视频、短视频、竖屏、口播、配音、旁白、TTS、屏录、剪辑、字幕、封面、导出、发笔记、xhs、daihuo，或想把某个商品做成视频时使用。
---

# 小红书带货视频制作流程

你在为一家卖 Claude Code 技能包的小红书店铺做带货短视频。店铺现有四个商品，
品牌视觉与合规红线在 `references/06-brand-and-compliance.md`，不要另起炉灶。

## 一次完整运行要交付什么

| 产物 | 位置 / 命名 |
|---|---|
| 成片 | `<项目>/<商品>-<渠道>-<YYYYMMDD>-v<N>.mp4`，1080×1920、H.264、30fps（例：`托福-claudecode-20260905-v1.mp4`） |
| 配音 + 字幕 | `<项目>/edit/vo/voiceover.wav`、`voiceover.srt`、`voiceover.json`（成片里已合轨、已烧录） |
| 封面 | `<项目>/edit/covers/cover.png`，3:4（1242×1656） |
| 文案 | `<项目>/edit/文案.md`：标题 3 个候选（≤ 20 字）、正文、8–10 个标签、评论区置顶 |
| 脚本 | `<项目>/edit/脚本.md`：用户确认过的分镜表 |
| 报告 | 对话里给：时长、尺寸、大小、配音引擎与音色、字幕检查、合规检查各一行 |

## 铁律

1. **先脚本后开工。** 没有用户确认的分镜表，不动任何素材、不渲染任何东西。
2. **前 3 秒必须有钩子，且钩子文字要在画面里**，不能只靠声音。
3. **每条成片都要有女声普通话 AI 配音，和与配音逐句同步的烧录字幕**，不分流水线，没有例外。
   两样都由 `scripts/voiceover.py` 从分镜表的「口播」列一次生成：字幕时间轴只认它出的 SRT，不手掐、不估。
   引擎自动取本机能用的最自然的一档（MiniMax speech-2.8-hd → Qwen3-TTS → edge-tts 晓晓），一个账号固定一个音色。
   只有用户明说「这条用我自己的声音」才跳过配音，字幕改走转写。
4. 字幕一句一屏、≤ 14 个汉字，放在安全区（`references/02`）。
5. 合规：`references/06` 的红线逐条过；不说「独家」「最」「官方认证」。
6. 中间产物只写 `<项目>/edit/`，不写进本 skill 目录。
7. 成片必须经 `scripts/xhs_export.py` 规格化（无声成片会被它判 FAIL）；交付前跑 `references/07-checklist.md`。
8. 任何要花钱的调用（ElevenLabs 转写、AI 生成模型）先报价再执行。付费配音一条约 ¥0.01–0.05，
   `voiceover.py --dry-run` 会打印约价，在分镜确认时一并报给用户即可，不用单独再问。

## Step 0 · 环境体检

```bash
python3 <skill>/scripts/doctor.py
```

输出会告诉你哪几条流水线可走。缺东西按提示装（`scripts/setup.sh`），不要在对话里猜。

## Step 1 · 明确商品与素材

- 商品是哪一个？对照 `references/06` 的商品表拿到：目录、主色、一句话卖点、价格。
- 已有文案先复用：`宣传海报-汇总/<商品>-海报/文案.md`（若存在；效果截图在同目录 `效果截图/`）里的卖点、标签、合规表述。
- 用户给了素材目录 → `python3 <skill>/scripts/probe.py <目录>` 盘点，看清横竖、时长、有无音频。
- 没有素材 → 走 B（纯动效，零素材出片），或先按 `references/04` 的「屏录」一节录一段。

## Step 2 · 分镜脚本（HARD GATE）

读 `references/03-hooks-and-scripts.md`，用 `templates/脚本模板.md` 写出分镜表，写入 `<项目>/edit/脚本.md`，
并把表格贴给用户。**等用户回复确认（或修改意见）后再进入 Step 3。**

脚本要满足：总时长 20–45 秒；钩子三选一（反常识 / 结果先行 / 痛点直击）；
每段有「画面 + 口播 + 屏幕大字 + 字幕」四列；口播总字数 ≈ 时长 × 4.5。

口播是写给 TTS 念的，也是字幕的唯一来源，所以：
- 为耳朵写：短句、多逗号（逗号就是换屏点，也是字幕对时的锚点）；一口气超过 14 字的无标点长句会被硬拆，难看。
- 想指定换屏处写 ` / `；显示和读音不一样的写 `{¥9.9=九块九}`、`{TPO=T P O}`（画面出前者，嘴上念后者）。
- 贴分镜表之前先跑 `python3 <skill>/scripts/voiceover.py <项目>/edit/脚本.md --dry-run`，
  把它打印的「屏：」断句填进「字幕」列一起给用户看；断得不顺就改口播，不要改 SRT。
- 账号第一次做视频：`voiceover.py --audition "一句试听文案"` 把候选女声各出一段，让用户挑一个，之后每条都用它（`--voice`）。

## Step 3 · 选流水线并执行

详细命令在 `references/04-pipelines.md`。

| 手里有什么 | 走哪条 |
|---|---|
| 口播 / 屏录素材，且有 `ELEVENLABS_API_KEY` | **A1** video-use 自动剪辑 |
| 口播 / 屏录素材，无 key | **A2** 本地：`probe → silence_cut → to_vertical → voiceover --burn → xhs_export` |
| 只有文字、截图、卖点 | **B** HyperFrames 竖屏模板（`templates/hyperframes-vertical/`） |
| 想要片头 / 价格卡 + 真实演示 | **C** 混合：B 出片头片尾，A 出主体，`concat.py` 拼接 |
| 需要真人 / 场景镜头但没得拍 | **D** AI 生成（付费，用户同意后），产物作为素材回到 A / C |

写 HyperFrames 动效时先读 `~/.claude/skills/hyperframes-core/SKILL.md`；只改模板文案时直接改 `index.html` 后 `npm run check`。

## Step 4 · 配音 + 同步字幕（每条必做）

画面定稿（无声或原声都行）之后，一条命令完成「合成女声 → 对时出 SRT → 合轨 → 烧字幕」：

```bash
python3 <skill>/scripts/voiceover.py <项目>/edit/脚本.md --video <画面.mp4> --burn -o <项目>/edit/subbed.mp4
```

- 每句从分镜表「时间」列的起点开始念；前一句念超了后一句自动顺延，并在表里标「比分镜晚 N 秒」。
  晚了就改：缩口播、`--speed 1.12`，或按它打印的起点回去调画面时长。不要带着错位交付。
- 配音比画面长会定格最后一帧补足；超过 1.5 秒说明分镜时长写短了，回去改画面。
- 屏录原声默认丢弃（键盘声、环境声）；要留一点用 `--keep-audio 0.2`。BGM 用 `--bgm x.mp3`，会随人声自动压低。
- 浅色画面（流水线 B 的米白底）用 `--style box --bottom 520`；深色 / 屏录用默认 `--style clean --bottom 640`。
- 流水线 B 要先知道每句多长才能定幕长：先不带 `--video` 跑一遍，读 `edit/vo/voiceover.json` 排幕，见 `references/04`。
- 只有用户明确要用自己的原声时才走转写字幕：video-use 的转写 → `npx --yes hyperframes@0.8.29 transcribe` → `burn_subs.py`。

## Step 5 · 导出、封面、文案

```bash
python3 <skill>/scripts/xhs_export.py <成片前> -o <项目>/<商品>-<渠道>-<日期>-v1.mp4
python3 <skill>/scripts/cover_frames.py <成片> -o <项目>/edit/covers --every 2        # 出候选网格 contact.jpg
python3 <skill>/scripts/cover_frames.py <成片> -o <项目>/edit/covers --pick <秒> --aspect 3:4
```

文案按 `references/03` 的标题 / 封面文案 / 标签规则写入 `<项目>/edit/文案.md`。

## Step 6 · 交付前检查

逐条过 `references/07-checklist.md`，然后在对话里给一份简短报告：文件路径、时长、尺寸、大小、
配音引擎与音色、字幕是否逐句跟上配音且在安全区、合规三条是否通过。有任何一条没过，说明原因，不要宣称完成。

## 脚本速查（零第三方 Python 依赖，只要 ffmpeg；配音另需 edge-tts 命令或一个 TTS key）

| 脚本 | 作用 | 常用参数 |
|---|---|---|
| `doctor.py` | 环境体检、给出可走流水线 | `--json` |
| `setup.sh` | 安装缺的工具 | `--tts` `--video-use` `--clipper` `--runcomfy` `--all` |
| `probe.py` | 素材盘点表 | `<目录或文件...>` `--json` |
| `silence_cut.py` | 按静音自动剪 | `--noise -35` `--min-silence 0.6` `--pad 0.15` `--dry-run` `--edl x.json` |
| `to_vertical.py` | 横屏转 9:16 / 3:4 | `--mode blur|crop|pad` `--aspect 9:16` |
| `voiceover.py` | 口播 → 女声配音 + 同步 SRT，可合轨并烧字幕 | `--video x.mp4 --burn -o out.mp4` `--dry-run` `--audition "文案"` `--engine auto|minimax|qwen|edge` `--voice` `--speed 1.08` `--bgm` `--keep-audio 0.2` `--no-anchor` |
| `burn_subs.py` | 烧录中文字幕（SRT/ASS） | `--style clean|box|accent` `--bottom 640` `--size 64` `--accent '#1B6B5F'` `--preview 5` |
| `concat.py` | 多段统一规格后拼接 | `--fit blur` `--aspect 9:16` |
| `cover_frames.py` | 封面候选网格 / 指定帧出封面 | `--every 2` `--pick 12.5 --aspect 3:4` |
| `xhs_export.py` | 最终规格化导出 + 自检 | `--aspect 9:16` `--fit blur` `--fps 30` `--crf 19` `--no-loudnorm` `--allow-silent` |
| `selftest.py` | 自检（应看到 All 13 checks passed） | |

## 何时读哪份参考

| 需要 | 读 |
|---|---|
| 装什么、用哪个工具、配音引擎与 key | `references/01-toolchain.md` |
| 尺寸、时长、安全区、字幕规范 | `references/02-xhs-video-spec.md` |
| 钩子、结构、标题、封面文案、标签 | `references/03-hooks-and-scripts.md` |
| 每条流水线的逐步命令、屏录方法 | `references/04-pipelines.md` |
| 手写 ffmpeg 命令 | `references/05-ffmpeg-cookbook.md` |
| 商品表、配色字体、合规红线 | `references/06-brand-and-compliance.md` |
| 发布前清单 | `references/07-checklist.md` |
| 分镜表格式 | `templates/脚本模板.md` |
| HyperFrames 品牌设计规范 | `templates/DESIGN.md` |
| 一次完整对话长什么样 | `示例/对话示例.md` |
