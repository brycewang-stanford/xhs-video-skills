# 四条流水线（逐步命令）

约定：`SK` 指本 skill 目录，`P` 指本次视频的工作目录（素材所在处）。所有中间产物写到 `P/edit/`。

```bash
SK=~/.claude/skills/xhs-video-skills   # 本 skill 所在目录，按实际 clone 位置改
P=~/Desktop/toefl-video; mkdir -p "$P/edit"
python3 "$SK/scripts/doctor.py"
```

## 屏录（没素材先录）

- 目标：竖屏或接近竖屏的画面，字够大，节奏按脚本走。
- 方法 1（最简单）：QuickTime → 文件 → 新建屏幕录制 → 框选一个 **540×960 逻辑像素** 的区域
  （Retina 下即 1080×1920）；终端字号调到 18–20pt，浅色主题对比更好。
- 方法 2（命令行）：
  ```bash
  ffmpeg -f avfoundation -list_devices true -i ""      # 看屏幕设备编号
  ffmpeg -f avfoundation -framerate 30 -capture_cursor 1 -i "1:none" -t 60 "$P/screen.mov"
  ```
  之后用 `to_vertical.py --mode crop` 或在 ffmpeg 里 `crop` 出目标区域。
- 方法 3（网页演示）：Playwright MCP 加 `--save-video=1080x1920` 录浏览器。
- 录之前把演示串好：一句话开工 → 取证表 → Word 批注 → 修订稿；每个画面停 3–5 秒，鼠标别乱晃。
- 口播可以后配：先录画面，再按脚本用手机 / 麦录音，`concat.py` 前用 ffmpeg 合轨（见 05）。

## A · 口播 / 屏录剪辑

### A1 video-use（有 ELEVENLABS_API_KEY）

```bash
cd "$P" && claude
```

对 Claude 说：

> 用 video-use 把这些素材剪成 30 秒小红书带货视频，按 edit/脚本.md 的分镜；去口水词和静音；
> 字幕中文一句一屏 ≤ 14 字，放在距底 640px；输出 edit/final.mp4。

video-use 会先盘点、转写、给出策略等你确认，再出 `edit/final.mp4`。拿到后跳到「导出」。

### A2 本地（无 key）

```bash
python3 "$SK/scripts/probe.py" "$P"                                                    # 1 盘点
python3 "$SK/scripts/silence_cut.py" "$P/raw.mov" --dry-run                            # 2 先看 EDL
python3 "$SK/scripts/silence_cut.py" "$P/raw.mov" -o "$P/edit/cut.mp4" --noise -35 --min-silence 0.6 --pad 0.15
python3 "$SK/scripts/to_vertical.py" "$P/edit/cut.mp4" -o "$P/edit/v.mp4" --mode blur  # 3 转竖屏（crop / blur / pad）
# 4 字幕：按脚本手写 edit/subs.srt；或
#   npx --yes hyperframes@0.8.29 transcribe "$P/edit/v.mp4" --model small --language zh  → 整理成 srt
python3 "$SK/scripts/burn_subs.py" "$P/edit/v.mp4" "$P/edit/subs.srt" -o "$P/edit/subbed.mp4" --style clean --bottom 640
```

口播偏慢时在第 3 步之后整体加速 1.1–1.2 倍（见 05）。

## B · 纯动效（零素材出片）

```bash
cp -R "$SK/templates/hyperframes-vertical" "$P/hf" && cd "$P/hf"
cp "$SK/templates/DESIGN.md" ./DESIGN.md          # 品牌规范，改 accent
# 1 改 index.html：:root 里的 --accent 换成商品主色；五幕文案按 edit/脚本.md 替换
npm run check                                     # 2 校验（lint + 布局 + 对比度）
npx --yes hyperframes@0.8.29 preview --background # 3 浏览器预览；看完 preview --stop
npm run render -- --output ../edit/motion.mp4 --quality high    # 4 渲染
```

- 配音：用 edge-tts 每幕生成一段（命令见 01 的「转写与配音」），量出每段时长，幕长 = max(最短幕长, 配音 + 0.7s)，
  按此重排各幕 `data-start` / `data-duration` 与脚本里的 `S` 表，再在 `#root` 直下每幕加一个
  `<audio id="voN" src="assets/voN.wav" data-start="幕起点+0.3" data-duration="该段时长" data-track-index="8">`。
  `xhs_export.py` 会做响度归一，不用手动调音量。
- 放真实屏录：`<video id="demo" class="clip" src="assets/demo.mp4" data-start="9.1" data-duration="12.4" muted playsinline>`
  放进第三幕位置，音频另起 `<audio>`；不要把 `<video>` 套在带 `data-start` 的 div 里。
- 加 BGM：`<audio id="bgm" src="assets/bgm.mp3" data-start="0" data-duration="32" data-volume="0.25">`。
- 写新动效不要凭记忆，先读 `~/.claude/skills/hyperframes-core/SKILL.md`。

## C · 混合（片头 / 价格卡 + 真实演示）

```bash
# B 出 intro.mp4（前两幕）和 outro.mp4（价格卡）；A 出 body.mp4
python3 "$SK/scripts/concat.py" "$P/edit/intro.mp4" "$P/edit/body.mp4" "$P/edit/outro.mp4" -o "$P/edit/joined.mp4" --fit blur
```

拆幕：把模板 index.html 复制两份，分别只保留前两幕 / 最后一幕，改 root 的 `data-duration` 和各幕 `data-start`。

## D · AI 生成 B-roll（付费，先问再花）

- 先向用户报：用哪个模型、几条、每条大概多少钱；得到明确同意再调用。
- 已装 `video-edit` / `image-to-video` skill 时按其 SKILL.md 调；产物存 `P/gen/`，再作为素材进 A / C。
- 提示词：主体 + 动作 + 镜头 + 光线 + 竖屏 9:16 + 时长 5s。不要生成任何考试机构 logo 或真题画面。

## 导出、封面（所有流水线共用）

```bash
D=$(date +%Y%m%d)
python3 "$SK/scripts/xhs_export.py" "$P/edit/subbed.mp4" -o "$P/托福-claudecode-$D-v1.mp4"
python3 "$SK/scripts/cover_frames.py" "$P/托福-claudecode-$D-v1.mp4" -o "$P/edit/covers" --every 2       # 候选网格
python3 "$SK/scripts/cover_frames.py" "$P/托福-claudecode-$D-v1.mp4" -o "$P/edit/covers" --pick 1.2 --aspect 3:4
```

## 引用他人视频（youtube-clipper）

```bash
python3 ~/.claude/skills/youtube-clipper/scripts/download_video.py <url>
```

只做引用 / 对比用途，画面里注明来源；带货主体仍用自己的画面。
