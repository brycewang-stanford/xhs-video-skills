#!/usr/bin/env python3
"""环境体检：本机有哪些视频工具可用，哪几条流水线能走。用法: python3 doctor.py [--json]"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import available_cjk_fonts  # noqa: E402

HOME = os.path.expanduser("~")
SKILLS = os.path.join(HOME, ".claude", "skills")


def ver(cmd, args=("--version",)):
    try:
        r = subprocess.run([cmd, *args], text=True, capture_output=True, timeout=20)
        lines = (r.stdout or r.stderr).strip().splitlines()
        return lines[0][:90] if lines else ""
    except Exception:
        return ""


def check_bin(name, hint, required=False, version_args=("--version",)):
    p = shutil.which(name)
    return {"name": name, "ok": bool(p), "detail": ver(name, version_args) if p else "", "hint": hint, "required": required}


def node_major():
    if not shutil.which("node"):
        return 0
    m = re.search(r"v(\d+)", ver("node"))
    return int(m.group(1)) if m else 0


def check_skill(name, hint, required=False):
    p = os.path.join(SKILLS, name)
    ok = os.path.exists(os.path.join(p, "SKILL.md"))
    return {"name": f"skill:{name}", "ok": ok, "detail": p if ok else "", "hint": hint, "required": required}


def ffmpeg_filters():
    if not shutil.which("ffmpeg"):
        return ""
    try:
        return subprocess.run(["ffmpeg", "-hide_banner", "-filters"], text=True, capture_output=True, timeout=20).stdout
    except Exception:
        return ""


def elevenlabs_key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "环境变量"
    for env in [os.path.join(HOME, "Developer", "video-use", ".env"), os.path.join(SKILLS, "video-use", ".env")]:
        try:
            with open(env, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("ELEVENLABS_API_KEY=") and len(line.split("=", 1)[1].strip()) > 5:
                        return env
        except OSError:
            pass
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    checks = []
    checks.append(check_bin("ffmpeg", "brew install ffmpeg", required=True, version_args=("-version",)))
    checks.append(check_bin("ffprobe", "随 ffmpeg 安装", required=True, version_args=("-version",)))
    filters = ffmpeg_filters()
    for f in ["ass", "silencedetect", "loudnorm", "boxblur", "tile", "drawtext"]:
        checks.append({
            "name": f"ffmpeg filter:{f}", "ok": bool(re.search(rf"\s{f}\s", filters)), "detail": "",
            "hint": "重装 ffmpeg（brew 版自带 libass / freetype）", "required": f in ("ass", "silencedetect"),
        })
    nm = node_major()
    checks.append({"name": "node ≥ 22", "ok": nm >= 22, "detail": ver("node"), "hint": "brew install node（HyperFrames 渲染需要）", "required": False})
    checks.append(check_bin("npx", "随 node 安装"))
    checks.append(check_bin("python3", "系统自带", version_args=("--version",)))
    checks.append(check_bin("uv", "curl -LsSf https://astral.sh/uv/install.sh | sh（video-use 需要）"))
    checks.append(check_bin("yt-dlp", "brew install yt-dlp（下载在线素材才需要）"))
    fonts = available_cjk_fonts()
    checks.append({"name": "中文字体", "ok": bool(fonts), "detail": ", ".join(fonts), "hint": "缺中文字体字幕会变方块", "required": True})

    checks.append(check_skill("hyperframes", "npx --yes hyperframes@latest skills update"))
    checks.append(check_skill("hyperframes-core", "npx --yes hyperframes@latest skills update"))
    checks.append(check_skill("hyperframes-cli", "npx --yes hyperframes@latest skills update"))
    checks.append(check_skill("media-use", "npx --yes hyperframes@latest skills update（配音 / BGM / 转写）"))
    checks.append(check_skill("video-use", "bash scripts/setup.sh --video-use"))
    key = elevenlabs_key()
    checks.append({"name": "ELEVENLABS_API_KEY", "ok": bool(key), "detail": key, "hint": "video-use 转写需要；写进 ~/Developer/video-use/.env", "required": False})
    checks.append(check_skill("youtube-clipper", "bash scripts/setup.sh --clipper"))
    checks.append(check_skill("remotion-best-practices", "可选：npx skills add remotion-dev/skills -g -y"))
    for s in ["video-edit", "image-to-video", "ai-video-generation"]:
        checks.append(check_skill(s, f"可选（付费 API）：npx skills add prime-skills/runcomfy-agent-skills@{s} -g -y"))

    ok = {c["name"]: c["ok"] for c in checks}
    pipelines = {
        "A1 video-use 自动剪辑": ok["ffmpeg"] and ok["skill:video-use"] and ok["ELEVENLABS_API_KEY"],
        "A2 本地静音剪辑 + 字幕 + 导出": ok["ffmpeg"] and ok["ffmpeg filter:ass"] and ok["中文字体"],
        "B HyperFrames 竖屏动效": ok["ffmpeg"] and ok["node ≥ 22"] and ok["skill:hyperframes-core"],
        "C 混合拼接": ok["ffmpeg"],
        "D AI 生成 B-roll": any(ok.get(f"skill:{s}") for s in ["video-edit", "image-to-video", "ai-video-generation"]),
    }

    if a.json:
        print(json.dumps({"checks": checks, "pipelines": pipelines}, ensure_ascii=False, indent=2))
        return

    print("== 工具体检 ==")
    for c in checks:
        mark = "✔" if c["ok"] else ("✘" if c.get("required") else "－")
        detail = c["detail"] if c["ok"] else c["hint"]
        print(f"{mark} {c['name']:<32} {detail}")
    print("\n== 可走的流水线 ==")
    for name, yes in pipelines.items():
        print(f"{'✔' if yes else '－'} {name}")
    missing_required = [c["name"] for c in checks if c.get("required") and not c["ok"]]
    if missing_required:
        print("\n必需项缺失: " + ", ".join(missing_required))
        sys.exit(1)
    print("\n必需项齐全。选流水线看 references/04-pipelines.md。")


if __name__ == "__main__":
    main()
