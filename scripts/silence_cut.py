#!/usr/bin/env python3
"""按静音自动剪：检测静音段，保留有声段（两侧各留 pad 秒），逐段精确切出后无损拼接。
用法: python3 silence_cut.py in.mp4 [-o out.mp4] [--noise -35] [--min-silence 0.6] [--pad 0.15] [--min-keep 0.3] [--dry-run] [--edl edl.json]"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import concat_same_encoded, default_output, ensure_parent, ffmpeg_base, fmt_dur, media_info, need, run, x264_args  # noqa: E402


def detect_silences(path, noise_db, min_sil, duration):
    need("ffmpeg")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_sil}", "-f", "null", "-"],
        text=True, capture_output=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    sil = list(zip(starts, ends))
    if len(starts) > len(ends):
        sil.append((starts[-1], duration))
    return [(max(0.0, s), min(duration, e)) for s, e in sil if e > s]


def build_keeps(silences, duration, pad, min_keep):
    keeps = []
    cursor = 0.0
    for s, e in silences:
        if e - s <= 2 * pad:
            continue
        keep_end = s + pad
        if keep_end - cursor >= min_keep:
            keeps.append((cursor, keep_end))
        cursor = max(cursor, e - pad)
    if duration - cursor >= min_keep:
        keeps.append((cursor, duration))
    return keeps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--noise", type=float, default=-35, help="低于此 dB 视为静音（默认 -35；环境噪音大用 -30）")
    ap.add_argument("--min-silence", type=float, default=0.6, help="静音至少持续多少秒才剪（默认 0.6）")
    ap.add_argument("--pad", type=float, default=0.15, help="每段有声两侧各保留多少秒静音（默认 0.15）")
    ap.add_argument("--min-keep", type=float, default=0.3, help="短于此的有声段丢弃（默认 0.3）")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--dry-run", action="store_true", help="只打印 EDL，不剪")
    ap.add_argument("--edl", help="把 EDL 写到这个 json")
    a = ap.parse_args()

    info = media_info(a.input)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {a.input}")
    if not info["has_audio"]:
        sys.exit("素材没有音轨，无法按静音剪。")
    dur = info["duration"]
    silences = detect_silences(a.input, a.noise, a.min_silence, dur)
    keeps = build_keeps(silences, dur, a.pad, a.min_keep)
    removed = dur - sum(e - s for s, e in keeps)

    print(f"原时长 {fmt_dur(dur)}；静音段 {len(silences)} 个；保留 {len(keeps)} 段；去掉 {removed:.1f}s → 新时长 {fmt_dur(dur - removed)}")
    for i, (s, e) in enumerate(keeps, 1):
        print(f"  keep {i:02d}: {s:8.3f} → {e:8.3f}  ({e - s:.2f}s)")
    edl = {"source": os.path.abspath(a.input), "duration": dur, "silences": silences, "keeps": keeps,
           "params": {"noise": a.noise, "min_silence": a.min_silence, "pad": a.pad, "min_keep": a.min_keep}}
    if a.edl:
        ensure_parent(a.edl)
        with open(a.edl, "w", encoding="utf-8") as f:
            json.dump(edl, f, ensure_ascii=False, indent=2)
        print(f"EDL 已写: {a.edl}")
    if a.dry_run:
        return
    if not silences:
        print("没有可剪的静音，未生成输出。")
        return

    out = a.output or default_output(a.input, "-cut")
    ensure_parent(out)
    tmp = tempfile.mkdtemp(prefix="xhs-cut-")
    fps = f"{info['fps']:.3f}" if info["fps"] else "30"
    parts = []
    try:
        for i, (s, e) in enumerate(keeps):
            part = os.path.join(tmp, f"part_{i:03d}.mp4")
            seg = e - s
            fade_out_start = max(0.0, seg - 0.03)
            cmd = ffmpeg_base() + ["-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", a.input]
            cmd += ["-vf", f"fps={fps},format=yuv420p", "-af", f"afade=t=in:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03"]
            cmd += x264_args(a.crf) + ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", part]
            run(cmd, quiet=True)
            parts.append(part)
        concat_same_encoded(parts, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    o = media_info(out)
    print(f"完成: {out}  时长 {fmt_dur(o['duration'])}")


if __name__ == "__main__":
    main()
