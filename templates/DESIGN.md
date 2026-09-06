# DESIGN.md · 小红书带货视频 · 品牌规范

复制到 HyperFrames 项目根目录。`hyperframes-creative` 会读它作为设计规范；改 accent 即换商品。

## Style Prompt
米白纸面上的编辑感排版：细网格底纹、粗宋体大标题、克制的位移淡入动效，一枚黄色竖排标签做撞色，
顶部一条商品主色横条。像一本认真做的备考手册，不像广告。竖屏 1080×1920，关键内容居中 60%，避开顶部 200px、底部 420px、右侧 180px。

## Colors
| 角色 | 值 |
|---|---|
| paper（底） | #FBFAF7 |
| grid（网格线 / 分隔） | #E4E1DA |
| ink（正文） | #14161A |
| muted（次级） | #8A8F96 |
| accent（商品主色） | 托福 #1B6B5F ｜ 雅思 #B03A2E ｜ GRE #2F4A9B ｜ PPT #2F4A9B |
| tag（撞色标签） | #FFD23F |

## Typography
- 标题：`"Songti SC", "Source Han Serif SC", "Noto Serif SC", serif`，900 字重，120–160px
- 正文：`"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`，48–60px
- 代号 / 页码：`"Times New Roman", serif`，字距 0.18em
- 一屏字幕 ≤ 14 字；一屏最多 1 处高亮

## Motion
- 进场：`gsap.from` 位移 40–80px + 淡入，0.5–0.7s，`power3.out`；同组元素 stagger 0.1s
- 标签：`back.out(1.7)` 弹一下即可，不重复弹
- 幕间：0.4s 交叉淡入，不用 wipe / 3D 翻转
- 数字与价格：可用 scale 1.15 → 1 的强调，只用一次

## What NOT to Do
- 不用霓虹、渐变球、深色赛博底
- 不用 Roboto / Inter 做中文标题
- 不放机构 logo（ETS / IELTS / ETS 等），不出现官方评分描述符原文
- 不在底部 420px 内放关键文字
- 不用「独家」「最」「第一」
