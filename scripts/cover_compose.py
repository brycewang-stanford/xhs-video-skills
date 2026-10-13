#!/usr/bin/env python3
"""封面合成：把一张图（人物画像、论文首页、产品图）嵌进封面底图中央的图片位，圆角贴合。
底图通常是 cover_frames.py 从讲解型视频里挑出的一帧（带固定标题的那一幕）。原图不改，另存新文件。
用法: python3 cover_compose.py 底图.png 要嵌的图.jpg -o 封面-v2.png
      python3 cover_compose.py 底图.png 图.jpg -o out.png --box 740,752,1384,790   # 底图有留白或被裁过时，直接给图片位的像素框
不给 --box 时，按「底图就是一帧 9:16 讲解画面」算舞台顶部的图片位（1080 宽下为 x48 y584 984×562）。"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ffmpeg_base, media_info, run  # noqa: E402

SLOT = (48, 584, 984, 562)   # 讲解模板舞台顶部图片位（含图源一行），1080 宽基准


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("image")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--box", default="", help="图片位 x,y,w,h（底图像素）")
    ap.add_argument("--radius", type=int, default=-1, help="圆角像素，默认按底图宽度折算 18/1080")
    ap.add_argument("--fit", default="cover", choices=["cover", "contain"], help="cover 铺满裁边；contain 完整放入、白底补边")
    a = ap.parse_args()

    info = media_info(a.base)
    if not info:
        sys.exit(f"读不了底图: {a.base}")
    if os.path.abspath(a.output) == os.path.abspath(a.base):
        sys.exit("输出不能覆盖底图，换个文件名（例如加 -v2）")
    bw = info["width"]
    if a.box:
        x, y, w, h = [int(v) for v in a.box.split(",")]
    else:
        k = bw / 1080.0
        x, y, w, h = [round(v * k) for v in SLOT]
    r = a.radius if a.radius >= 0 else round(18 * (w / 984.0))
    if a.fit == "cover":
        fit = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    else:
        fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:white"
    # 圆角：四个角上超出半径的像素透明
    alpha = (f"if(gt(abs(X-{w}/2),{w}/2-{r})*gt(abs(Y-{h}/2),{h}/2-{r}),"
             f"if(lte(hypot(abs(X-{w}/2)-({w}/2-{r}),abs(Y-{h}/2)-({h}/2-{r})),{r}),255,0),255)")
    fc = (f"[1:v]{fit},format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[im];"
          f"[0:v][im]overlay={x}:{y}:format=auto[out]")
    run(ffmpeg_base() + ["-i", a.base, "-i", a.image, "-filter_complex", fc, "-map", "[out]", "-frames:v", "1", "-update", "1", a.output])
    src = media_info(a.image)
    note = ""
    if src and src["width"] * 1.5 < w:
        note = f"  注意：原图只有 {src['width']}px 宽，放大到 {w}px 会发虚，最好换大图"
    print(f"OK {a.output}  图片位 {x},{y} {w}x{h} 圆角 {r}{note}")


if __name__ == "__main__":
    main()
