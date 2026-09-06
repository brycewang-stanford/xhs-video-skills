# xhs-video-skills

小红书带货短视频一站式制作 Claude Code skill：
环境体检 → 分镜脚本 → 剪辑 / 动效 → 字幕 → 封面 → 按小红书规格导出 → 发布前合规检查。

- 脚本零第三方 Python 依赖，只要 `ffmpeg` / `ffprobe`
- 自带 1080×1920 HyperFrames 五幕竖屏模板，复制即渲染
- 内置钩子库、分镜模板、小红书规格、ffmpeg 速查、品牌视觉与合规红线、发布前清单

## 安装

```bash
git clone https://github.com/brycewang-stanford/xhs-video-skills.git ~/.claude/skills/xhs-video-skills
python3 ~/.claude/skills/xhs-video-skills/scripts/selftest.py   # 应看到 All 13 checks passed
python3 ~/.claude/skills/xhs-video-skills/scripts/doctor.py     # 看哪几条流水线可走
```

缺什么按 `doctor.py` 的提示装，或跑 `bash scripts/setup.sh`。

## 用法

在 Claude Code 里说，例如：

> 用 xhs-video-skills 给托福写作批改考官做一条 30 秒带货视频，屏录在 ~/Desktop/toefl-demo/，钩子用「改版」。

它会先出分镜表等你确认，再动手。完整对话见 [示例/对话示例.md](示例/对话示例.md)，
细节见 [使用说明.md](使用说明.md) 与 [SKILL.md](SKILL.md)。

## 目录

```
xhs-video-skills/
├── SKILL.md                 主流程（Claude 读这个）
├── 使用说明.md               自用说明
├── references/              规格、钩子库、流水线命令、ffmpeg 速查、品牌与合规、发布清单
├── scripts/                 probe / to_vertical / silence_cut / burn_subs / cover_frames / concat / xhs_export / doctor / selftest
├── templates/
│   ├── 脚本模板.md           分镜表
│   ├── DESIGN.md            品牌设计规范（给 HyperFrames 用）
│   └── hyperframes-vertical/ 1080×1920 五幕带货模板
└── 示例/                    对话示例、模板五幕截图、草稿画质渲染样片
```

## 四条流水线

| 手里有什么 | 走哪条 |
|---|---|
| 口播 / 屏录素材 + `ELEVENLABS_API_KEY` | A1 video-use 自动剪辑 |
| 口播 / 屏录素材，不想花钱 | A2 本地静音剪辑 + 字幕 + 导出 |
| 没有素材 | B HyperFrames 竖屏动效 |
| 动效 + 屏录混合 | C 拼接 |
| 需要 AI 生成 B-roll | D runcomfy 等生成模型（付费） |

命令逐步见 [references/04-pipelines.md](references/04-pipelines.md)。
