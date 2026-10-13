# explainer-douyin · 讲解型竖屏模板（抖音风固定标题 + 3Blue1Brown 画面）

1080×1920。深紫背景，顶部四行固定标题全程不动，中间舞台画图表 / 公式 / 截图，下方两行宽版字幕。
做法、版式数字和注意事项见 `references/08-explainer-style.md`。

## 用法

```bash
cp -R <skill>/templates/explainer-douyin <项目> && cd <项目>
PY=~/.cache/hyperframes/tts-venv/bin/python
$PY tools/voice.py          # 改完 tools/script.py 后录音
$PY tools/scenes.py         # 改完 tools/scenes.py 后生成
npx hyperframes check && npx hyperframes preview
npx hyperframes render -o renders/<名字>.mp4 --fps 30
```

## 改哪里

| 文件 | 改什么 |
|---|---|
| `tools/script.py` | 口播稿，一项一屏字幕；`RATE` 调语速 |
| `tools/scenes.py` | 各幕画面与动画；末尾 `build()` 里的标题、副标题、`bgm=` |
| `tools/kit.py` | 引擎（版式、配色、动画助手），一般不动 |
| `assets/img/` | 裁好的截图（`shot()` 用）；原图放 `assets/src/` |

## 依赖

- `tools/voice.py` 要 `numpy`、`soundfile`；默认引擎 edge-tts（命令行）。
- 备用本地女声（edge-tts 连不上时自动启用）：`pip install sherpa-onnx`，模型解压到
  `~/.cache/hyperframes/tts/melo/vits-melo-tts-zh_en/`
  （https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2）。
- 字体：公式用 `assets/fonts/` 里的 STIX Two（SIL OFL）；中文用系统苹方。
