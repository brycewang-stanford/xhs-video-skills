#!/usr/bin/env bash
# 安装本 skill 用到的外部工具。默认只体检；带参数才装。
#   bash setup.sh                 只跑 doctor
#   bash setup.sh --tts           装 edge-tts（免费女声配音；付费引擎只要 key，不用装）
#   bash setup.sh --video-use     装 browser-use/video-use（需 git、uv）
#   bash setup.sh --clipper       装 op7418/Youtube-clipper-skill
#   bash setup.sh --runcomfy      装 runcomfy 生成模型 skills（付费 API）
#   bash setup.sh --hyperframes   预下载 HyperFrames CLI 与 Chrome，并刷新 skills
#   bash setup.sh --all           以上全部
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DO_VU=0; DO_CLIP=0; DO_RC=0; DO_HF=0; DO_TTS=0
for arg in "$@"; do
  case "$arg" in
    --tts) DO_TTS=1 ;;
    --video-use) DO_VU=1 ;;
    --clipper) DO_CLIP=1 ;;
    --runcomfy) DO_RC=1 ;;
    --hyperframes) DO_HF=1 ;;
    --all) DO_VU=1; DO_CLIP=1; DO_RC=1; DO_HF=1; DO_TTS=1 ;;
    -h|--help) sed -n 2,10p "$0"; exit 0 ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then echo "== 安装 ffmpeg"; brew install ffmpeg; else echo "缺 ffmpeg 且没有 brew，请先装 Homebrew"; exit 1; fi
fi

if [ "$DO_TTS" = 1 ]; then
  echo "== edge-tts"
  if command -v edge-tts >/dev/null; then echo "已安装: $(command -v edge-tts)"
  elif command -v uv >/dev/null; then uv tool install edge-tts
  elif command -v brew >/dev/null; then brew install edge-tts
  else python3 -m pip install --user edge-tts; fi
  mkdir -p "$HOME/.config/xhs-video-skills"
  [ -f "$HOME/.config/xhs-video-skills/tts.env" ] || printf '# 付费配音 key（可选，填了 voiceover.py 自动优先用）\n# MINIMAX_API_KEY=\n# MINIMAX_API_HOST=https://api.minimaxi.com   # 国际站改 https://api.minimax.io\n# DASHSCOPE_API_KEY=\n' > "$HOME/.config/xhs-video-skills/tts.env"
  echo ">> 想要更自然的女声：把 key 填进 $HOME/.config/xhs-video-skills/tts.env"
fi

if [ "$DO_VU" = 1 ]; then
  echo "== video-use"
  command -v uv >/dev/null || { echo "缺 uv：curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
  mkdir -p "$HOME/Developer"
  if [ ! -d "$HOME/Developer/video-use" ]; then git clone https://github.com/browser-use/video-use "$HOME/Developer/video-use"; else (cd "$HOME/Developer/video-use" && git pull --ff-only || true); fi
  ln -sfn "$HOME/Developer/video-use" "$HOME/.claude/skills/video-use"
  (cd "$HOME/Developer/video-use" && uv sync)
  [ -f "$HOME/Developer/video-use/.env" ] || cp "$HOME/Developer/video-use/.env.example" "$HOME/Developer/video-use/.env" 2>/dev/null || true
  echo ">> 把 ELEVENLABS_API_KEY 写进 $HOME/Developer/video-use/.env"
fi

if [ "$DO_CLIP" = 1 ]; then
  echo "== youtube-clipper"
  npx -y skills add https://github.com/op7418/Youtube-clipper-skill -g -y
  command -v yt-dlp >/dev/null || brew install yt-dlp
  python3 -m pip install --quiet --user pysrt python-dotenv yt-dlp || true
fi

if [ "$DO_RC" = 1 ]; then
  echo "== runcomfy skills（付费 API，用前看其 SKILL.md 配 key）"
  for s in video-edit image-to-video ai-video-generation; do
    npx -y skills add "prime-skills/runcomfy-agent-skills@$s" -g -y
  done
fi

if [ "$DO_HF" = 1 ]; then
  echo "== HyperFrames"
  npx --yes hyperframes@0.8.29 doctor || true
  npx --yes hyperframes@latest skills update || true
fi

echo
python3 "$HERE/doctor.py"
