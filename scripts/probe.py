#!/usr/bin/env python3
"""素材盘点：列出目录里视频 / 音频 / 图片的规格，标出不符合小红书竖屏要求的项。
用法: python3 probe.py <目录或文件...> [--json]"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT, fmt_dur, fmt_size, media_info, orientation  # noqa: E402

SKIP_DIRS = {"node_modules", "__pycache__", ".git"}


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                for n in sorted(names):
                    if n.startswith("."):
                        continue
                    if os.path.splitext(n)[1].lower() in VIDEO_EXT | AUDIO_EXT | IMAGE_EXT:
                        files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"[跳过] 不存在: {p}")
    return files


def notes_for(i):
    n = []
    if i["kind"] == "video":
        if orientation(i["width"], i["height"]) != "竖":
            n.append("非竖屏，需 to_vertical.py")
        elif i["width"] < 1080 or i["height"] < 1920:
            n.append("低于 1080×1920，导出会放大")
        if not i["has_audio"]:
            n.append("无音频")
        if i["fps"] and abs(i["fps"] - 30) > 1 and abs(i["fps"] - 60) > 1:
            n.append(f"{i['fps']:.2f}fps 非 30/60")
        if i["duration"] > 60:
            n.append("长素材，需剪")
        if i["rotation"] % 180:
            n.append(f"带旋转元数据 {i['rotation']}°")
    elif i["kind"] == "image":
        if orientation(i["width"], i["height"]) != "竖":
            n.append("非竖图")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    files = collect(a.paths)
    rows = []
    for f in files:
        i = media_info(f)
        if not i:
            rows.append({"path": f, "kind": "?", "error": "ffprobe 读不了"})
            continue
        i["notes"] = notes_for(i)
        rows.append(i)

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("没找到素材文件。")
        return
    print("| 文件 | 类型 | 宽×高 | 方向 | 时长 | fps | 码率 | 音频 | 备注 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        name = os.path.relpath(r["path"])
        if r.get("error"):
            print(f"| {name} | ? | | | | | | | {r['error']} |")
            continue
        wh = f"{r['width']}×{r['height']}" if r["width"] else "-"
        dur = fmt_dur(r["duration"]) if r["kind"] != "image" else "-"
        fps = f"{r['fps']:.0f}" if r["kind"] == "video" and r["fps"] else "-"
        br = f"{r['bitrate'] / 1e6:.1f}M" if r["bitrate"] else "-"
        au = (r["acodec"] or "有") if r["has_audio"] else "无"
        print(f"| {name} | {r['kind']} | {wh} | {orientation(r['width'], r['height'])} | {dur} | {fps} | {br} | {au} | {'；'.join(r['notes'])} |")

    vids = [r for r in rows if r.get("kind") == "video"]
    total = sum(r["duration"] for r in vids)
    print(f"\n视频 {len(vids)} 个，合计 {fmt_dur(total)}；图片 {sum(1 for r in rows if r.get('kind') == 'image')} 张；"
          f"音频 {sum(1 for r in rows if r.get('kind') == 'audio')} 个；总大小 {fmt_size(sum(r.get('size', 0) for r in rows))}")
    if any("非竖屏" in "".join(r.get("notes", [])) for r in vids):
        print("建议：横屏素材先 to_vertical.py --mode blur（保留全画面）或 --mode crop（居中裁）。")
    if any(not r["has_audio"] for r in vids):
        print("建议：无音频素材走 B 或 C 流水线补配音 / BGM。")


if __name__ == "__main__":
    main()
