#!/usr/bin/env python3
"""横屏 / 任意尺寸转小红书竖屏。
用法: python3 to_vertical.py in.mp4 [-o out.mp4] [--mode blur|crop|pad] [--aspect 9:16|3:4|1:1] [--color '#FBFAF7'] [--crf 18]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import PAPER, default_output, ensure_parent, ffmpeg_base, filter_complex_video, fit_chain, media_info, run, target_size, x264_args  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--mode", default="blur", choices=["blur", "crop", "pad"], help="blur=模糊背景填充（默认）；crop=居中裁切；pad=纯色填充")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--color", default=PAPER, help="pad 模式的填充色")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    info = media_info(a.input)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {a.input}")
    w, h = target_size(a.aspect)
    out = a.output or default_output(a.input, f"-{a.aspect.replace(':', 'x')}")
    ensure_parent(out)
    print(f"源 {info['width']}×{info['height']} → 目标 {w}×{h}，模式 {a.mode}")
    cmd = ffmpeg_base() + ["-i", a.input] + filter_complex_video(fit_chain(a.mode, w, h, a.color), "setsar=1")
    cmd += ["-map", "0:a?", "-c:a", "copy"] + x264_args(a.crf) + ["-movflags", "+faststart", out]
    run(cmd)
    o = media_info(out)
    print(f"完成: {out}  {o['width']}×{o['height']}")


if __name__ == "__main__":
    main()
