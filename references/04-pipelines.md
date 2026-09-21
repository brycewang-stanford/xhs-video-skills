# 四条流水线（逐步命令）

不管走哪条，收尾都是同一步：**`voiceover.py` 配女声 + 出同步字幕 + 合轨 + 烧录**（见「配音 + 同步字幕」一节），然后导出。

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
- 不用自己录口播：只管录画面，声音由 `voiceover.py` 按分镜表统一配。录的时候每个画面的停留时长照分镜表「时间」列来。

## A · 口播 / 屏录剪辑

### A1 video-use（有 ELEVENLABS_API_KEY）

```bash
cd "$P" && claude
```

对 Claude 说：

> 用 video-use 把这些素材剪成 30 秒小红书带货视频，按 edit/脚本.md 的分镜；去口水词和静音；
> **不要烧字幕**（后面统一配音再上字幕）；输出 edit/final.mp4。

video-use 会先盘点、转写、给出策略等你确认，再出 `edit/final.mp4`。拿到后当作画面，进「配音 + 同步字幕」。

### A2 本地（无 key）

```bash
python3 "$SK/scripts/probe.py" "$P"                                                    # 1 盘点
python3 "$SK/scripts/silence_cut.py" "$P/raw.mov" --dry-run                            # 2 先看 EDL
python3 "$SK/scripts/silence_cut.py" "$P/raw.mov" -o "$P/edit/cut.mp4" --noise -35 --min-silence 0.6 --pad 0.15
python3 "$SK/scripts/to_vertical.py" "$P/edit/cut.mp4" -o "$P/edit/v.mp4" --mode blur  # 3 转竖屏（crop / blur / pad）
python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md" --video "$P/edit/v.mp4" --burn -o "$P/edit/subbed.mp4"   # 4 配音 + 同步字幕
```

画面段落和分镜表「时间」列对不上时，先按分镜裁画面（`ffmpeg -ss/-to`，见 05），再配音；不要反过来迁就错位。

## B · 纯动效（零素材出片）

```bash
cp -R "$SK/templates/hyperframes-vertical" "$P/hf" && cd "$P/hf"
cp "$SK/templates/DESIGN.md" ./DESIGN.md          # 品牌规范，改 accent
# 1 改 index.html：:root 里的 --accent 换成商品主色；五幕文案按 edit/脚本.md 替换
npm run check                                     # 2 校验（lint + 布局 + 对比度）
npx --yes hyperframes@0.8.29 preview --background # 3 浏览器预览；看完 preview --stop
npm run render -- --output ../edit/motion.mp4 --quality high    # 4 渲染
```

- **先配音后定幕长**（动效要跟着声音走，不是反过来）：
  ```bash
  python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md"              # 0 先只出声音，看每句实际多长
  # 读 edit/vo/voiceover.json 的 lines[].start / duration：幕长 = max(最短幕长, 该幕配音 + 0.7s)，
  # 据此改各幕 data-start / data-duration、脚本末尾 S 表、root 的 data-duration，并把分镜表「时间」列改成新起点
  # …… 上面 1–4 步渲染出无声的 edit/motion.mp4 ……
  python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md" --video "$P/edit/motion.mp4" --burn --style box --bottom 520 -o "$P/edit/subbed.mp4"
  ```
  第二次跑不会重新合成（有缓存），只按新锚点重排、合轨、烧字幕。模板已在距底 460–640px 留出字幕带，
  米白底用 `--style box`（黑字）；不要再往 HyperFrames 里塞 `<audio>` 配音，声音统一后合。
- 放真实屏录：`<video id="demo" class="clip" src="assets/demo.mp4" data-start="9.1" data-duration="12.4" muted playsinline>`
  放进第三幕位置，音频另起 `<audio>`；不要把 `<video>` 套在带 `data-start` 的 div 里。
- 加 BGM：在 `voiceover.py` 那一步加 `--bgm assets/bgm.mp3`（自动循环、随人声压低、首尾淡入淡出），不要在 HyperFrames 里加。
- 写新动效不要凭记忆，先读 `~/.claude/skills/hyperframes-core/SKILL.md`。

## C · 混合（片头 / 价格卡 + 真实演示）

```bash
# B 出 intro.mp4（前两幕）和 outro.mp4（价格卡）；A 出 body.mp4
python3 "$SK/scripts/concat.py" "$P/edit/intro.mp4" "$P/edit/body.mp4" "$P/edit/outro.mp4" -o "$P/edit/joined.mp4" --fit blur
```

拼完的 `joined.mp4` 再整条过 `voiceover.py`（一条配音贯穿片头、主体、片尾，语气才连贯；不要分段配）：

```bash
python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md" --video "$P/edit/joined.mp4" --burn -o "$P/edit/subbed.mp4"
```

拆幕：把模板 index.html 复制两份，分别只保留前两幕 / 最后一幕，改 root 的 `data-duration` 和各幕 `data-start`。

## D · AI 生成 B-roll（付费，先问再花）

- 先向用户报：用哪个模型、几条、每条大概多少钱；得到明确同意再调用。
- 已装 `video-edit` / `image-to-video` skill 时按其 SKILL.md 调；产物存 `P/gen/`，再作为素材进 A / C。
- 提示词：主体 + 动作 + 镜头 + 光线 + 竖屏 9:16 + 时长 5s。不要生成任何考试机构 logo 或真题画面。

## 配音 + 同步字幕（所有流水线共用，每条必做）

```bash
python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md" --dry-run        # 看断句、字数、用哪个引擎、约价；分镜确认前就该跑
python3 "$SK/scripts/voiceover.py" --audition "早鸟九块九，评论区扣一" --outdir "$P/edit/audition"   # 账号首次：挑女声
python3 "$SK/scripts/voiceover.py" "$P/edit/脚本.md" --video "$P/edit/v.mp4" --burn -o "$P/edit/subbed.mp4"
```

它做了什么：
1. 取分镜表「口播」列（或 `口播.txt` 一行一句），整句送 TTS（整句合成语气才自然，不按屏切碎了合）。
2. 每句掐掉首尾静音，从「时间」列的起点开始放；前一句超时则后一句顺延并报警。
3. 字幕按标点和 ` / ` 断成 ≤ 14 字一屏；屏与屏的交界**吸附到音频里真实的停顿**（静音检测），不是按字数估的。
   没有标点的长句只能按音节比例插值，准头差一些，所以口播要多用逗号。
4. 合轨（原声默认丢弃，`--keep-audio 0.2` 保留；`--bgm` 自动压低），配音超出画面则定格末帧。
5. `--burn` 直接调 `burn_subs.py` 烧录。产物在 `edit/vo/`：`voiceover.wav`、`voiceover.srt`、`voiceover.json`、逐句 `vo_NNN.wav`。

常见调整：

| 现象 | 怎么办 |
|---|---|
| 某句「比分镜晚 N 秒」 | 缩短前一句口播；或 `--speed 1.12`–`1.18`；或按打印的起点改画面时长 |
| 价格 / 英文念得怪 | 口播里写 `{¥9.9=九块九}`、`{TPO=T P O}`、`{rubric=评分标准}` |
| 某屏断得不顺 | 在口播里用 ` / ` 指定断点，或补逗号；改完重跑（只重合成改过的句子） |
| 想换音色 / 模型 | `--voice <音色>`、`--model <模型>`、`--engine minimax\|qwen\|edge` |
| 某屏一闪而过（< 0.55s） | 脚本会提醒；把它和相邻短句合成一句，或删掉 ` / ` |
| 字幕要微调样式 / 位置 | `--style clean\|box\|accent`、`--bottom`；或拿 `voiceover.srt` 单独跑 `burn_subs.py` |

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
