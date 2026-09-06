---
name: xhs-video-skills
description: 小红书带货短视频一站式制作流程：选题钩子 → 分镜脚本 → 素材剪辑（口播 / 屏录 / 纯动效 / AI 生成）→ 字幕 → 封面 → 按小红书规格导出 → 发布前合规检查。封装本机视频工具链（FFmpeg 零依赖脚本、HyperFrames 竖屏模板、video-use 自动剪辑、youtube-clipper、runcomfy 等生成模型 skill），并内置本店商品（雅思 / 托福 / GRE 写作批改考官、AI PPT Skill 选型导航）的品牌视觉与合规红线。当用户提到 小红书、带货、爆款视频、短视频、竖屏、口播、屏录、剪辑、字幕、封面、导出、发笔记、xhs、daihuo，或想把某个商品做成视频时使用。
---

# 小红书带货视频制作流程

你在为一家卖 Claude Code 技能包的小红书店铺做带货短视频。店铺现有四个商品，
品牌视觉与合规红线在 `references/06-brand-and-compliance.md`，不要另起炉灶。

## 一次完整运行要交付什么

| 产物 | 位置 / 命名 |
|---|---|
| 成片 | `<项目>/<商品>-<渠道>-<YYYYMMDD>-v<N>.mp4`，1080×1920、H.264、30fps（例：`托福-claudecode-20260905-v1.mp4`） |
| 封面 | `<项目>/edit/covers/cover.png`，3:4（1242×1656） |
| 文案 | `<项目>/edit/文案.md`：标题 3 个候选（≤ 20 字）、正文、8–10 个标签、评论区置顶 |
| 脚本 | `<项目>/edit/脚本.md`：用户确认过的分镜表 |
| 报告 | 对话里给：时长、尺寸、大小、字幕检查、合规检查各一行 |

## 铁律

1. **先脚本后开工。** 没有用户确认的分镜表，不动任何素材、不渲染任何东西。
2. **前 3 秒必须有钩子，且钩子文字要在画面里**，不能只靠声音。
3. 字幕一句一屏、≤ 14 个汉字，放在安全区（`references/02`）。
4. 合规：`references/06` 的红线逐条过；不说「独家」「最」「官方认证」。
5. 中间产物只写 `<项目>/edit/`，不写进本 skill 目录。
6. 成片必须经 `scripts/xhs_export.py` 规格化；交付前跑 `references/07-checklist.md`。
7. 任何要花钱的调用（ElevenLabs 转写、AI 生成模型）先报价再执行。

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

## Step 3 · 选流水线并执行

详细命令在 `references/04-pipelines.md`。

| 手里有什么 | 走哪条 |
|---|---|
| 口播 / 屏录素材，且有 `ELEVENLABS_API_KEY` | **A1** video-use 自动剪辑 |
| 口播 / 屏录素材，无 key | **A2** 本地：`probe → silence_cut → to_vertical → burn_subs → xhs_export` |
| 只有文字、截图、卖点 | **B** HyperFrames 竖屏模板（`templates/hyperframes-vertical/`） |
| 想要片头 / 价格卡 + 真实演示 | **C** 混合：B 出片头片尾，A 出主体，`concat.py` 拼接 |
| 需要真人 / 场景镜头但没得拍 | **D** AI 生成（付费，用户同意后），产物作为素材回到 A / C |

写 HyperFrames 动效时先读 `~/.claude/skills/hyperframes-core/SKILL.md`；只改模板文案时直接改 `index.html` 后 `npm run check`。

## Step 4 · 字幕

来源优先级：video-use 的转写 → `npx --yes hyperframes@0.8.29 transcribe` → 按脚本手写 SRT。
拿到 SRT 后：`python3 <skill>/scripts/burn_subs.py <视频> <srt> -o <输出> --style clean --bottom 640`。
HyperFrames 模板的文字本身就是字幕，走 B 时不用再烧。

## Step 5 · 导出、封面、文案

```bash
python3 <skill>/scripts/xhs_export.py <成片前> -o <项目>/<商品>-<渠道>-<日期>-v1.mp4
python3 <skill>/scripts/cover_frames.py <成片> -o <项目>/edit/covers --every 2        # 出候选网格 contact.jpg
python3 <skill>/scripts/cover_frames.py <成片> -o <项目>/edit/covers --pick <秒> --aspect 3:4
```

文案按 `references/03` 的标题 / 封面文案 / 标签规则写入 `<项目>/edit/文案.md`。

## Step 6 · 交付前检查

逐条过 `references/07-checklist.md`，然后在对话里给一份简短报告：文件路径、时长、尺寸、大小、
字幕是否在安全区、合规三条是否通过。有任何一条没过，说明原因，不要宣称完成。

## 脚本速查（全部零第三方依赖，只要 ffmpeg）

| 脚本 | 作用 | 常用参数 |
|---|---|---|
| `doctor.py` | 环境体检、给出可走流水线 | `--json` |
| `setup.sh` | 安装缺的工具 | `--video-use` `--clipper` `--runcomfy` `--all` |
| `probe.py` | 素材盘点表 | `<目录或文件...>` `--json` |
| `silence_cut.py` | 按静音自动剪 | `--noise -35` `--min-silence 0.6` `--pad 0.15` `--dry-run` `--edl x.json` |
| `to_vertical.py` | 横屏转 9:16 / 3:4 | `--mode blur|crop|pad` `--aspect 9:16` |
| `burn_subs.py` | 烧录中文字幕（SRT/ASS） | `--style clean|box|accent` `--bottom 640` `--size 64` `--accent '#1B6B5F'` `--preview 5` |
| `concat.py` | 多段统一规格后拼接 | `--fit blur` `--aspect 9:16` |
| `cover_frames.py` | 封面候选网格 / 指定帧出封面 | `--every 2` `--pick 12.5 --aspect 3:4` |
| `xhs_export.py` | 最终规格化导出 + 自检 | `--aspect 9:16` `--fit blur` `--fps 30` `--crf 19` `--no-loudnorm` |
| `selftest.py` | 自检（应看到 All 13 checks passed） | |

## 何时读哪份参考

| 需要 | 读 |
|---|---|
| 装什么、用哪个工具 | `references/01-toolchain.md` |
| 尺寸、时长、安全区、字幕规范 | `references/02-xhs-video-spec.md` |
| 钩子、结构、标题、封面文案、标签 | `references/03-hooks-and-scripts.md` |
| 每条流水线的逐步命令、屏录方法 | `references/04-pipelines.md` |
| 手写 ffmpeg 命令 | `references/05-ffmpeg-cookbook.md` |
| 商品表、配色字体、合规红线 | `references/06-brand-and-compliance.md` |
| 发布前清单 | `references/07-checklist.md` |
| 分镜表格式 | `templates/脚本模板.md` |
| HyperFrames 品牌设计规范 | `templates/DESIGN.md` |
| 一次完整对话长什么样 | `示例/对话示例.md` |
