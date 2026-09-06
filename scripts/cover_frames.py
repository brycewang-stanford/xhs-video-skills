#!/usr/bin/env python3
"""封面：先出候选帧网格 contact.jpg 挑画面，再用 --pick 秒数 输出裁好的封面。
用法: python3 cover_frames.py video.mp4 -o covers/ [--every 2] [--max 16]
      python3 cover_frames.py video.mp4 -o covers/ --pick 12.5 [--aspect 3:4|9:16|1:1] [--y-shift 0] [--name cover.png]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import COVER_SIZES, ffmpeg_base, media_info, run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("-o", "--outdir", default="")
    ap.add_argument("--every", type=float, default=2.0, help="候选帧间隔秒")
    ap.add_argument("--max", type=int, default=16, help="候选帧最多几张")
    ap.add_argument("--pick", type=float, default=None, help="指定秒数出封面")
    ap.add_argument("--aspect", default="3:4", choices=list(COVER_SIZES))
    ap.add_argument("--y-shift", type=int, default=0, help="裁切窗口上下偏移 px（正数向下）")
    ap.add_argument("--name", default="cover.png")
    a = ap.parse_args()

    info = media_info(a.video)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {a.video}")
    outdir = a.outdir or os.path.join(os.path.dirname(os.path.abspath(a.video)), "covers")
    os.makedirs(outdir, exist_ok=True)

    if a.pick is not None:
        w, h = COVER_SIZES[a.aspect]
        t = min(max(0.0, a.pick), max(0.0, info["duration"] - 0.05))
        out = os.path.join(outdir, a.name)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h}:(iw-{w})/2:(ih-{h})/2+({a.y_shift})")
        run(ffmpeg_base() + ["-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1", "-vf", vf, out])
        print(f"封面: {out}  {w}×{h}（来自 {t:.2f}s）")
        return

    # fps=1/every 实际能产出的帧数：t = 0, every, 2*every ... < duration
    available = max(1, int((info["duration"] - 0.01) // a.every) + 1)
    n = max(1, min(a.max, available))
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    contact = os.path.join(outdir, "contact.jpg")
    run(ffmpeg_base() + ["-i", a.video, "-vf",
                         f"fps=1/{a.every},scale=270:-2,tile={cols}x{rows}:nb_frames={n}:padding=6:margin=6:color=0xFBFAF7",
                         "-frames:v", "1", "-q:v", "3", contact])
    for i in range(n):
        t = i * a.every
        run(ffmpeg_base() + ["-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1", "-q:v", "2",
                             os.path.join(outdir, f"frame_{t:06.1f}s.jpg")], quiet=True)
    print(f"候选网格: {contact}（从左到右、从上到下每格 {a.every}s）；单帧在 {outdir}/frame_*.jpg")
    print(f"选好后: python3 {os.path.basename(__file__)} {a.video} -o {outdir} --pick <秒> --aspect 3:4")


if __name__ == "__main__":
    main()
