#!/usr/bin/env python3
"""烧录中文字幕（SRT 或 ASS）。SRT 会先转成与画面同尺寸的 ASS，字号即像素，位置可控；字体走 fontsdir，不会变方块。
用法: python3 burn_subs.py video.mp4 subs.srt [-o out.mp4] [--style clean|box|accent] [--font 'PingFang SC'] [--font-file x.ttc]
      [--size 64] [--bottom 640] [--accent '#1B6B5F'] [--bold] [--preview 5]"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (FONT_FILES, default_output, display_len, ensure_parent, escape_filter_path, ffmpeg_base,  # noqa: E402
                     find_font_file, fonts_dir_for, media_info, run, x264_args)

PAPER = "#FBFAF7"
INK = "#14161A"


def ass_color(hex_rgb, alpha=0):
    c = hex_rgb.strip().lstrip("#")
    if len(c) != 6:
        sys.exit(f"颜色格式应为 #RRGGBB: {hex_rgb}")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def srt_time_to_ass(t):
    m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)", t.strip())
    if not m:
        sys.exit(f"SRT 时间格式错误: {t}")
    h, mi, s, ms = m.groups()
    cs = int(ms.ljust(3, "0")[:3]) // 10
    return f"{int(h)}:{int(mi):02d}:{int(s):02d}.{cs:02d}"


def parse_srt(text):
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if "-->" not in lines[0] and len(lines) >= 2 and "-->" in lines[1]:
            lines = lines[1:]
        if "-->" not in lines[0]:
            continue
        start, end = [x.strip() for x in lines[0].split("-->")[:2]]
        end = end.split(" ")[0]
        body = lines[1:]
        cues.append((srt_time_to_ass(start), srt_time_to_ass(end), body))
    return cues


def clean_text(lines):
    out = []
    for l in lines:
        l = re.sub(r"<[^>]+>", "", l)
        l = l.replace("{", "｛").replace("}", "｝").replace("\\", "＼")
        out.append(l.strip())
    return "\\N".join(x for x in out if x)


def build_ass(cues, w, h, style, font, size, bottom, accent, bold):
    scale = w / 1080.0
    size = int(round(size * scale))
    margin_v = int(round(bottom * (h / 1920.0)))
    margin_lr = int(round(90 * scale))
    if style == "clean":
        primary, outline, back, border_style, outline_w, shadow = ass_color("#FFFFFF"), ass_color(INK), ass_color(INK, 0x80), 1, 3, 0
    elif style == "box":
        primary, outline, back, border_style, outline_w, shadow = ass_color(INK), ass_color(PAPER), ass_color(PAPER), 3, 14, 0
    elif style == "accent":
        primary, outline, back, border_style, outline_w, shadow = ass_color("#FFFFFF"), ass_color(accent), ass_color(accent, 0x60), 1, 4, 0
    else:
        sys.exit(f"未知 style: {style}")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,{outline},{back},{-1 if bold else 0},0,0,0,100,100,1,0,{border_style},{outline_w},{shadow},2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{clean_text(t)}\n" for s, e, t in cues)
    return header + body


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("subs", help=".srt 或 .ass")
    ap.add_argument("-o", "--output")
    ap.add_argument("--style", default="clean", choices=["clean", "box", "accent"], help="clean=白字深描边；box=米白底黑字盒；accent=白字主色描边")
    ap.add_argument("--font", default="", help="字体名（默认自动挑一款系统中文字体）")
    ap.add_argument("--font-file", default="", help="字体文件路径（优先级高于 --font）")
    ap.add_argument("--size", type=int, default=64, help="字号 px，按 1080 宽计（默认 64）")
    ap.add_argument("--bottom", type=int, default=640, help="字幕底边距画面底部 px，按 1920 高计（默认 640，避开小红书底部 UI）")
    ap.add_argument("--accent", default="#1B6B5F", help="accent 样式的主色")
    ap.add_argument("--bold", action="store_true")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preview", type=float, default=0, help="只渲染前 N 秒用于快速检查")
    a = ap.parse_args()

    info = media_info(a.video)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {a.video}")
    w, h = info["width"], info["height"]

    font_file = a.font_file
    font_name = a.font
    if font_file:
        if not os.path.exists(font_file):
            sys.exit(f"字体文件不存在: {font_file}")
        font_name = font_name or os.path.splitext(os.path.basename(font_file))[0]
    else:
        order = [font_name] if font_name else []
        order += ["PingFang SC", "Hiragino Sans GB", "STHeiti", "Songti SC", "Noto Sans CJK SC", "WenQuanYi Micro Hei"]
        for n in order:
            if n in FONT_FILES and find_font_file(n):
                font_name = n
                font_file = find_font_file(n)
                break
        if not font_file:
            print("[警告] 没找到已知中文字体文件，交给 libass 自己找；若变方块请用 --font-file 指定。")
            font_name = font_name or "PingFang SC"

    out = a.output or default_output(a.video, "-sub")
    ensure_parent(out)
    ext = os.path.splitext(a.subs)[1].lower()
    if ext == ".ass":
        ass_path = a.subs
    else:
        with open(a.subs, encoding="utf-8") as f:
            cues = parse_srt(f.read())
        if not cues:
            sys.exit("SRT 里没有解析到任何字幕。")
        long = [t for _, _, t in cues if display_len("".join(t)) > 14]
        if long:
            print(f"[提醒] 有 {len(long)} 条字幕超过 14 字（英文数字算半个），小红书一句一屏建议拆开。")
        ass_path = os.path.splitext(out)[0] + ".ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(build_ass(cues, w, h, a.style, font_name, a.size, a.bottom, a.accent, a.bold))
        print(f"ASS 已生成: {ass_path}（可手改后用 .ass 重烧）")

    vf = f"ass={escape_filter_path(ass_path)}"
    if font_file:
        vf += f":fontsdir={escape_filter_path(fonts_dir_for(font_file))}"
    cmd = ffmpeg_base() + ["-i", a.video]
    if a.preview:
        cmd += ["-t", str(a.preview)]
    cmd += ["-vf", vf, "-c:a", "copy"] + x264_args(a.crf) + ["-movflags", "+faststart", out]
    run(cmd)
    print(f"完成: {out}  字体 {font_name}  样式 {a.style}")


if __name__ == "__main__":
    main()
