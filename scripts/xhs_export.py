#!/usr/bin/env python3
"""最终导出：统一到小红书规格（默认 1080×1920 / 30fps / H.264 High / AAC 48k / 响度 -16 LUFS / faststart）并自检。
用法: python3 xhs_export.py in.mp4 [-o out.mp4] [--aspect 9:16|3:4] [--fit blur|crop|pad] [--fps 30] [--crf 19] [--no-loudnorm] [--allow-silent]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (PAPER, default_output, ensure_parent, ffmpeg_base, filter_complex_video, fit_chain, fmt_dur,  # noqa: E402
                     fmt_size, has_faststart, media_info, run, target_size)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--fit", default="blur", choices=["blur", "crop", "pad"], help="尺寸不符时怎么适配")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--color", default=PAPER)
    ap.add_argument("--no-loudnorm", action="store_true")
    ap.add_argument("--allow-silent", action="store_true", help="允许无声成片（默认判 FAIL：每条成片都要有配音）")
    a = ap.parse_args()

    info = media_info(a.input)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {a.input}")
    w, h = target_size(a.aspect)
    out = a.output or default_output(a.input, "-xhs")
    ensure_parent(out)

    if (info["width"], info["height"]) == (w, h):
        chain = f"scale={w}:{h}"
    else:
        print(f"尺寸 {info['width']}×{info['height']} ≠ {w}×{h}，用 {a.fit} 适配")
        chain = fit_chain(a.fit, w, h, a.color)
    cmd = ffmpeg_base() + ["-i", a.input] + filter_complex_video(chain, f"fps={a.fps},format=yuv420p,setsar=1")
    cmd += ["-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", a.preset, "-crf", str(a.crf),
            "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p"]
    if info["has_audio"]:
        cmd += ["-map", "0:a:0"]
        if not a.no_loudnorm:
            cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    else:
        cmd += ["-an"]
        print("[提醒] 源无音轨，成片将无声。先跑 voiceover.py 配音。")
    cmd += ["-movflags", "+faststart", out]
    run(cmd)

    o = media_info(out)
    checks = [
        ("分辨率", f"{o['width']}×{o['height']}", (o["width"], o["height"]) == (w, h)),
        ("帧率", f"{o['fps']:.2f}", abs(o["fps"] - a.fps) < 0.5),
        ("编码", f"{o['vcodec']} / {o['acodec'] or '无音频'}", o["vcodec"] == "h264"),
        ("配音音轨", "有" if o["has_audio"] else "无（先跑 voiceover.py）", o["has_audio"] or a.allow_silent),
        ("faststart", "是" if has_faststart(out) else "否", has_faststart(out)),
        ("时长", fmt_dur(o["duration"]), True),
        ("大小", f"{fmt_size(o['size'])}（{o['bitrate'] / 1e6:.1f} Mbps）", o["size"] < 5 * 1024 ** 3),
    ]
    print(f"\n完成: {out}")
    for name, val, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<8} {val}")
    if o["duration"] > 60:
        print("  WARN  时长超过 60 秒，带货视频建议 20–45 秒")
    elif o["duration"] < 12:
        print("  WARN  时长不足 12 秒，检查是否漏了段落")
    if not all(ok for _, _, ok in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
