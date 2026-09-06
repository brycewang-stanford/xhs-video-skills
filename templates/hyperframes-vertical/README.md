# hyperframes-vertical · 小红书带货竖屏模板

1080×1920，32 秒，五幕：钩子 → 痛点 → 演示 → 证据 → CTA。复制整个目录到工作区即可 `npm run check && npm run render`。

## 改文案 / 换商品
- `index.html` 顶部 `:root` 的 `--accent` 换成商品主色（托福 #1B6B5F ｜ 雅思 #B03A2E ｜ GRE #2F4A9B）。
- 五个 `<section id="s1..s5">` 里的文字按 `edit/脚本.md` 替换；`.foot` 是商品代号。
- 改幕长：同时改 section 的 `data-start` / `data-duration`、脚本末尾 `S` 表、root 的 `data-duration`。

## 替换为真实屏录（第三幕）
1. 把屏录放到 `assets/demo.mp4`（竖屏 1080×1920 最好，横屏会被拉伸，先用 `to_vertical.py`）。
2. 删掉 `#s3` 里的 `.term` 块，在 `#root` 直下（不要套在带 `data-start` 的 div 里）加：
   `video` 元素：`id="demo" class="clip" src="assets/demo.mp4" data-start="9.1" data-duration="12.4" muted playsinline`
   `audio` 元素：`id="demo-a" src="assets/demo.mp4" data-start="9.1" data-duration="12.4" data-volume="1"`
3. 想保留标题「一句话开工」叠在屏录上：把 `#s3` 的 `.scene-content` 只留 `.h2`，并给 `#s3` 加 `pointer-events:none`，让它排在 video 之后（DOM 靠后者在上层）。

## 配音 / BGM
- 配音：`npx --yes hyperframes@0.8.29 tts "口播全文" --output assets/vo.wav`，再在 `#root` 直下加
  `audio` 元素：`id="vo" src="assets/vo.wav" data-start="0" data-duration="32" data-volume="1"`。
- BGM：`assets/bgm.mp3` + `audio` 元素 `id="bgm" ... data-volume="0.25"`；有配音时可在时间线上 `tl.to("#bgm", { volume: 0.12 }, 0)` 压低。
- 每个 `audio` 必须有 `id`，否则渲染无声。

## 渲染
```bash
npm run check                                   # 必须 0 error
npx --yes hyperframes@0.8.29 preview --background   # 看完 preview --stop
npm run render -- --output ../edit/motion.mp4 --quality high
```
之后用 `scripts/xhs_export.py` 规格化。
