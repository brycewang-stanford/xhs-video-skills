#!/usr/bin/env python3
"""xhs-video-skills 脚本公用函数。零第三方依赖，只要 ffmpeg / ffprobe。"""
import json
import os
import shlex
import shutil
import subprocess
import sys

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic"}

ASPECTS = {"9:16": (1080, 1920), "3:4": (1080, 1440), "1:1": (1080, 1080)}
COVER_SIZES = {"3:4": (1242, 1656), "9:16": (1080, 1920), "1:1": (1080, 1080)}
PAPER = "#FBFAF7"

# 常见中文字体文件位置（macOS 优先，其次 Linux）。libass 通过 fontsdir 找字体最稳。
FONT_FILES = {
    "PingFang SC": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/PrivateFrameworks/FontServices.framework/Versions/A/Resources/Fonts/Apple/PingFang.ttc",
    ],
    "Hiragino Sans GB": [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Hiragino Sans GB.ttc",
    ],
    "Songti SC": ["/System/Library/Fonts/Supplemental/Songti.ttc"],
    "STHeiti": ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/STHeiti Light.ttc"],
    "Noto Sans CJK SC": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ],
    "WenQuanYi Micro Hei": ["/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"],
}


def which(name):
    return shutil.which(name)


def need(name):
    p = which(name)
    if not p:
        sys.exit(f"[缺少工具] 找不到 {name}。先运行: python3 scripts/doctor.py")
    return p


def run(cmd, quiet=False, check=True, capture=False):
    cmd = [str(c) for c in cmd]
    if not quiet:
        print("$ " + " ".join(shlex.quote(c) for c in cmd), flush=True)
    r = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and r.returncode != 0:
        if capture and r.stderr:
            sys.stderr.write(r.stderr[-3000:] + "\n")
        sys.exit(f"[失败] 命令退出码 {r.returncode}")
    return r


def ffmpeg_base():
    """所有 ffmpeg 调用共用的前缀：覆盖输出、少打日志。"""
    need("ffmpeg")
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"]


def ffprobe_json(path):
    need("ffprobe")
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def parse_fps(s):
    try:
        if "/" in str(s):
            a, b = str(s).split("/")
            b = float(b)
            return float(a) / b if b else 0.0
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def media_info(path):
    """返回 dict：kind, width, height, fps, duration, vcodec, acodec, has_audio, bitrate, size, rotation。"""
    data = ffprobe_json(path)
    if not data:
        return None
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    ext = os.path.splitext(str(path))[1].lower()
    info = {
        "path": str(path),
        "kind": "image" if ext in IMAGE_EXT else ("audio" if v is None else "video"),
        "width": int(v.get("width", 0)) if v else 0,
        "height": int(v.get("height", 0)) if v else 0,
        "fps": parse_fps(v.get("avg_frame_rate", "0")) if v else 0.0,
        "duration": float(fmt.get("duration") or (v or {}).get("duration") or 0.0),
        "vcodec": (v or {}).get("codec_name", ""),
        "acodec": (a or {}).get("codec_name", ""),
        "has_audio": a is not None,
        "bitrate": int(fmt.get("bit_rate") or 0),
        "size": int(fmt.get("size") or 0),
        "rotation": 0,
    }
    rot = 0
    if v:
        tags = v.get("tags") or {}
        try:
            rot = int(float(tags.get("rotate", 0)))
        except (TypeError, ValueError):
            rot = 0
        for sd in v.get("side_data_list") or []:
            if "rotation" in sd:
                try:
                    rot = int(float(sd["rotation"]))
                except (TypeError, ValueError):
                    pass
    if rot % 180 != 0:
        info["width"], info["height"] = info["height"], info["width"]
    info["rotation"] = rot
    return info


def orientation(w, h):
    if not w or not h:
        return "-"
    if h > w * 1.05:
        return "竖"
    if w > h * 1.05:
        return "横"
    return "方"


def fmt_dur(sec):
    sec = float(sec or 0)
    m = int(sec // 60)
    return f"{m}:{sec - m * 60:04.1f}"


def display_len(s):
    """字幕占位：汉字等全角算 1，英文数字半角算 0.5。"""
    return sum(1.0 if ord(c) > 0x2E7F else 0.5 for c in str(s))


def fmt_size(b):
    b = float(b or 0)
    for u in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB"


def hex_to_ffmpeg(color):
    c = str(color).strip().lstrip("#")
    if len(c) != 6:
        sys.exit(f"颜色格式应为 #RRGGBB，收到: {color}")
    return "0x" + c.upper()


def target_size(aspect):
    if aspect not in ASPECTS:
        sys.exit(f"--aspect 只支持 {', '.join(ASPECTS)}")
    return ASPECTS[aspect]


def fit_chain(mode, w, h, color=PAPER):
    """把任意尺寸画面适配到 w×h 的 filter 片段（不带输入 / 输出标签）。mode: crop | blur | pad"""
    if mode == "crop":
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if mode == "pad":
        return (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={hex_to_ffmpeg(color)}"
        )
    if mode == "blur":
        return (
            "split[bgsrc][fgsrc];"
            f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            "boxblur=luma_radius=40:luma_power=2:chroma_radius=20:chroma_power=2[bg];"
            f"[fgsrc]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    sys.exit(f"未知 fit 模式: {mode}（可选 crop / blur / pad）")


def filter_complex_video(chain, extra=""):
    """组装 -filter_complex 参数：[0:v]chain[,extra][vout]"""
    tail = f",{extra}" if extra else ""
    return ["-filter_complex", f"[0:v]{chain}{tail}[vout]", "-map", "[vout]"]


def x264_args(crf=18, preset="medium"):
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]


def default_output(path, suffix, ext=".mp4"):
    base, _ = os.path.splitext(str(path))
    return base + suffix + ext


def ensure_parent(path):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)


def has_faststart(path):
    """moov 在 mdat 之前即为 faststart。只读文件头部。"""
    try:
        with open(path, "rb") as f:
            head = f.read(1024 * 1024)
    except OSError:
        return False
    moov = head.find(b"moov")
    mdat = head.find(b"mdat")
    if moov < 0:
        return False
    return mdat < 0 or moov < mdat


def find_font_file(name):
    for p in FONT_FILES.get(name, []):
        if os.path.exists(p):
            return p
    return ""


def available_cjk_fonts():
    return [n for n in FONT_FILES if find_font_file(n)]


def fonts_dir_for(font_file):
    """把字体文件符号链接到一个小目录，作为 libass 的 fontsdir，避免扫描整个系统字体目录。"""
    cache = os.path.join(os.path.expanduser("~"), ".cache", "xhs-video-fonts")
    os.makedirs(cache, exist_ok=True)
    link = os.path.join(cache, os.path.basename(font_file))
    if not os.path.exists(link):
        try:
            os.symlink(font_file, link)
        except OSError:
            shutil.copy2(font_file, link)
    return cache


def escape_filter_path(p):
    """ffmpeg filter 选项里的路径转义。"""
    out = []
    for ch in str(p):
        if ch in "\\:'[],;":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def concat_same_encoded(parts, out, keep_list=False):
    """用 concat demuxer 无损拼接编码参数一致的片段。"""
    ensure_parent(out)
    list_path = os.path.splitext(out)[0] + ".concat.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '" + os.path.abspath(p).replace("'", "'\\''") + "'\n")
    run(ffmpeg_base() + ["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", "-movflags", "+faststart", out])
    if not keep_list:
        os.remove(list_path)
    return out
