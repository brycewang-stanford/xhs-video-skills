# 工具链清单 · 何时用哪个

体检命令：`python3 scripts/doctor.py`（逐项检查下表，并给出可走的流水线）。

## 一览

| 工具 | 干什么 | 费用 | 装在哪 / 怎么装 | 本 skill 里谁用它 |
|---|---|---|---|---|
| **FFmpeg 7.x**（必需） | 剪辑、转竖屏、字幕、导出的底层 | 免费 | `brew install ffmpeg`（brew 版自带 libass 字幕渲染） | `scripts/*.py` 全部 |
| **HyperFrames**（HeyGen） | 用 HTML + GSAP 写动效，本地 Chrome 渲染成 MP4 | 免费 | skills 已在 `~/.claude/skills/hyperframes*` 与 `media-use`；CLI 用 `npx --yes hyperframes@0.8.29` 按需下载，首次会下 Chrome | 流水线 B / C（`templates/hyperframes-vertical/`） |
| **video-use**（browser-use 团队，MIT） | 口播 / 屏录自动转写、去口水词和静音、调色、烧字幕，输出 `edit/final.mp4` | 软件免费；转写走 ElevenLabs Scribe 按量计费 | `bash scripts/setup.sh --video-use`，再把 `ELEVENLABS_API_KEY` 写进 `~/Developer/video-use/.env` | 流水线 A1 |
| **本地静音剪辑**（本 skill 自带） | 没有 key 时的替代，`silence_cut.py` 按静音自动切 | 免费 | 已内置 | 流水线 A2 |
| **youtube-clipper**（op7418） | 下载 YouTube 视频、AI 分章节、切片、双语字幕 | 免费（下载走 yt-dlp） | `bash scripts/setup.sh --clipper` | 引用他人视频片段做对比素材 |
| **Remotion skills** | 用 React 写视频，已装 `remotion-best-practices` | 免费 | 已装 | 只在需要 React 生态（复杂图表、3D）时用，日常优先 HyperFrames |
| **runcomfy-agent-skills** | 文生视频 / 图生视频 / 视频重绘，路由到 Kling、Wan 等模型 | 付费 API | `npx skills add prime-skills/runcomfy-agent-skills@video-edit -g -y`，另有 `image-to-video`、`ai-video-generation`、`ai-avatar-video` | 流水线 D |
| **Higgsfield MCP / Runway MCP** | 30+ 生成模型，Soul ID 保持人物一致 | 付费 | 见文末链接 | 流水线 D |
| **OpenMontage**（AGPL） | 全流程制片框架（调研 → 脚本 → 素材 → 合成），较重 | 免费路径 + 可选付费 | `git clone https://github.com/calesthio/OpenMontage && cd OpenMontage && make setup` | 只在要做 60 秒以上讲解片时考虑 |
| **claude-code-video-toolkit**（digitalsamba） | Remotion 流水线 + 配音 + 发 YouTube | 免费，自备 GPU | `git clone https://github.com/digitalsamba/claude-code-video-toolkit` | 备选，不在默认流程里 |

## 决策树

```
有口播 / 屏录素材？
 ├─ 是 → 有 ELEVENLABS_API_KEY？ ├─ 是 → A1 video-use
 │                                └─ 否 → A2 本地（probe → silence_cut → to_vertical → burn_subs → xhs_export）
 └─ 否 → 只有文字 / 截图 / 卖点 → B HyperFrames 竖屏模板（零素材出片）
片头 / 价格卡 + 真实演示都要 → C 混合：B 出片头片尾，A 出主体，concat.py 拼接
要真人 / 场景镜头但没得拍     → D AI 生成（付费，先报价），产物回到 A / C 当素材
```

## HyperFrames skill 家族（2026-09-05 由 `hyperframes init` 升级为模块化版本）

`hyperframes`（入口 / 路由）、`hyperframes-core`（合成规范，写 HTML 前必读）、`hyperframes-animation`、
`hyperframes-keyframes`、`hyperframes-creative`、`hyperframes-audio`、`hyperframes-cli`、`hyperframes-registry`、
`media-use`（TTS 配音 / BGM / 转写 / 抠像 / 调色）。

- 写模板以外的新动效：按 `/hyperframes` 的路由走，它会把你送到 `/general-video` 或 `/motion-graphics`。
- 只改模板文案：直接改 `index.html`，然后 `npm run check`。
- 更新 skills：`npx --yes hyperframes@latest skills update`。

## 转写与配音

| 需要 | 用 |
|---|---|
| 口播转字幕（有 key） | video-use 自带（ElevenLabs Scribe，词级时间戳） |
| 口播转字幕（无 key） | `npx --yes hyperframes@0.8.29 transcribe <视频>`（本地 Whisper，中文用 `--model small --language zh`，不要用 `.en` 模型） |
| 文字转配音（首选） | **edge-tts**（微软 Edge 在线语音，免费，中文自然）：`uv venv ~/.venvs/tts --python 3.11 && uv pip install --python ~/.venvs/tts/bin/python edge-tts`，然后 `~/.venvs/tts/bin/python -m edge_tts --voice zh-CN-XiaoxiaoNeural --rate=+5% --text "口播" --write-media vo1.mp3`，再 `ffmpeg -i vo1.mp3 -ar 48000 -ac 2 vo1.wav` 放进 `assets/`。每幕一段，按段时长重排幕的 `data-start` / `data-duration`。其他音色：zh-CN-YunxiNeural（男）、zh-CN-XiaoyiNeural。需要联网。 |
| 文字转配音（备选） | macOS 自带 `say -v Tingting "口播" -o vo.aiff`（离线，机器味重）。HyperFrames 自带的 `tts` 中文 2026-09-05 实测本机不可用：依赖 `espeakng-loader` 的数据路径写死成打包机路径，设 `ESPEAK_DATA_PATH` 也无效，别在这上面花时间。 |

## 链接

- video-use: https://github.com/browser-use/video-use
- HyperFrames: https://hyperframes.heygen.com
- youtube-clipper: https://github.com/op7418/Youtube-clipper-skill
- runcomfy skills: https://skills.sh/prime-skills/runcomfy-agent-skills/video-edit
- Higgsfield MCP: https://claudefa.st/blog/tools/mcp-extensions/higgsfield-mcp
- Runway MCP: https://runway.com/mcp
- OpenMontage: https://github.com/calesthio/OpenMontage
- 汇总仓库: https://github.com/wilwaldon/Claude-Code-Video-Toolkit
