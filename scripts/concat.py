#!/usr/bin/env python3
"""多段视频统一到同一规格（尺寸 / 帧率 / 音轨）后拼接。无音轨的段自动补静音。
用法: python3 concat.py a.mp4 b.mp4 [c.mp4 ...] -o out.mp4 [--aspect 9:16] [--fit blur|crop|pad] [--fps 30] [--crf 18]"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (PAPER, concat_same_encoded, ensure_parent, ffmpeg_base, filter_complex_video, fit_chain,  # noqa: E402
                     fmt_dur, media_info, run, target_size, x264_args)


def normalize(src, dst, w, h, fit, fps, crf, color):
    info = media_info(src)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {src}")
    chain = fit_chain(fit, w, h, color) if (info["width"], info["height"]) != (w, h) else f"scale={w}:{h}"
    cmd = ffmpeg_base() + ["-i", src]
    if not info["has_audio"]:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += filter_complex_video(chain, f"fps={fps},format=yuv420p,setsar=1")
    cmd += ["-map", "0:a" if info["has_audio"] else "1:a"]
    if not info["has_audio"]:
        cmd += ["-shortest"]
    cmd += x264_args(crf) + ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-video_track_timescale", "90000", dst]
    run(cmd, quiet=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--fit", default="blur", choices=["blur", "crop", "pad"])
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--color", default=PAPER)
    a = ap.parse_args()
    if len(a.inputs) < 2:
        sys.exit("至少两个输入。")
    w, h = target_size(a.aspect)
    ensure_parent(a.output)
    tmp = tempfile.mkdtemp(prefix="xhs-concat-")
    parts = []
    try:
        for i, src in enumerate(a.inputs):
            dst = os.path.join(tmp, f"part_{i:03d}.mp4")
            print(f"[{i + 1}/{len(a.inputs)}] 规格化 {os.path.basename(src)}")
            normalize(src, dst, w, h, a.fit, a.fps, a.crf, a.color)
            parts.append(dst)
        concat_same_encoded(parts, a.output)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    o = media_info(a.output)
    print(f"完成: {a.output}  {o['width']}×{o['height']}  时长 {fmt_dur(o['duration'])}")


if __name__ == "__main__":
    main()
