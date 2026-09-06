#!/usr/bin/env python3
"""自检：生成一段测试素材，把每个脚本跑一遍并校验产物。应看到 All 12 checks passed。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _common import has_faststart, media_info  # noqa: E402

PY = sys.executable
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")


def sh(args, cwd=None):
    r = subprocess.run([str(x) for x in args], text=True, capture_output=True, cwd=cwd)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def script(name, *args):
    return sh([PY, os.path.join(HERE, name), *args])


def frame_bytes(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", "scale=64:-2,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    return r.stdout


def main():
    tmp = tempfile.mkdtemp(prefix="xhs-selftest-")
    try:
        # 1 工具
        check("ffmpeg / ffprobe 可用", shutil.which("ffmpeg") and shutil.which("ffprobe"))
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            return finish()

        # 2 生成横屏测试素材：4 秒画面 + 440Hz 音，1.5–2.6s 静音
        src = os.path.join(tmp, "landscape.mp4")
        code, out = sh(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=4",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
                        "-af", "volume=enable='between(t,1.5,2.6)':volume=0",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", src])
        info = media_info(src) if code == 0 else None
        check("生成测试素材", info and info["width"] == 1920 and info["has_audio"], out[-200:] if code else "")
        if not info:
            return finish()

        # 3 probe
        code, out = script("probe.py", tmp)
        check("probe.py 识别横屏素材", code == 0 and "横" in out and "非竖屏" in out)

        # 4 to_vertical
        v = os.path.join(tmp, "v.mp4")
        code, out = script("to_vertical.py", src, "-o", v, "--mode", "blur")
        vi = media_info(v) if code == 0 else None
        check("to_vertical.py 输出 1080×1920", vi and (vi["width"], vi["height"]) == (1080, 1920), out[-200:] if code else "")

        # 5 silence_cut
        cut = os.path.join(tmp, "cut.mp4")
        edl = os.path.join(tmp, "edl.json")
        code, out = script("silence_cut.py", src, "-o", cut, "--edl", edl)
        ci = media_info(cut) if code == 0 else None
        ok = ci and info["duration"] - ci["duration"] >= 0.5 and os.path.exists(edl)
        check("silence_cut.py 剪掉静音段", ok, f"{info['duration']:.2f}s → {ci['duration']:.2f}s" if ci else out[-200:])

        # 6 burn_subs（中文）
        srt = os.path.join(tmp, "subs.srt")
        with open(srt, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,200 --> 00:00:03,800\n托福写作改版了，你的 TPO 还考吗\n\n2\n00:00:03,800 --> 00:00:04,000\n早鸟价 ¥9.9\n")
        subbed = os.path.join(tmp, "subbed.mp4")
        code, out = script("burn_subs.py", v, srt, "-o", subbed, "--style", "clean")
        si = media_info(subbed) if code == 0 else None
        before, after = (frame_bytes(v, 1.0), frame_bytes(subbed, 1.0)) if si else (b"", b"")
        ok = si and abs(si["duration"] - vi["duration"]) < 0.2 and before and after and before != after
        check("burn_subs.py 中文字幕烧录", ok, out[-300:] if not ok else "")

        # 7 cover
        covers = os.path.join(tmp, "covers")
        code, out = script("cover_frames.py", v, "-o", covers, "--pick", "1.0", "--aspect", "3:4")
        cov = media_info(os.path.join(covers, "cover.png")) if code == 0 else None
        check("cover_frames.py 输出 3:4 封面", cov and (cov["width"], cov["height"]) == (1242, 1656), out[-200:] if code else "")
        code, out = script("cover_frames.py", v, "-o", covers, "--every", "1")
        check("cover_frames.py 候选网格", code == 0 and os.path.exists(os.path.join(covers, "contact.jpg")), out[-200:] if code else "")

        # 8 export
        final = os.path.join(tmp, "final.mp4")
        code, out = script("xhs_export.py", src, "-o", final)
        fi = media_info(final) if code == 0 else None
        ok = fi and (fi["width"], fi["height"]) == (1080, 1920) and abs(fi["fps"] - 30) < 0.5 and has_faststart(final)
        check("xhs_export.py 规格化导出", ok, out[-300:] if not ok else "")

        # 9 concat
        joined = os.path.join(tmp, "joined.mp4")
        code, out = script("concat.py", src, v, "-o", joined)
        ji = media_info(joined) if code == 0 else None
        ok = ji and abs(ji["duration"] - (info["duration"] + vi["duration"])) < 0.3
        check("concat.py 拼接时长正确", ok, f"{ji['duration']:.2f}s" if ji else out[-300:])

        # 10 doctor
        code, out = script("doctor.py", "--json")
        try:
            d = json.loads(out)
            ok = "pipelines" in d and d["pipelines"].get("A2 本地静音剪辑 + 字幕 + 导出") is True
        except json.JSONDecodeError:
            ok = False
        check("doctor.py 可运行且 A2 可走", ok)

        # 11 模板
        tpl = os.path.join(ROOT, "templates", "hyperframes-vertical")
        idx = os.path.join(tpl, "index.html")
        html = open(idx, encoding="utf-8").read() if os.path.exists(idx) else ""
        ok = all(os.path.exists(os.path.join(tpl, f)) for f in ["index.html", "package.json", "hyperframes.json", "meta.json"]) \
            and 'data-width="1080"' in html and 'data-height="1920"' in html and "window.__timelines" in html
        check("HyperFrames 竖屏模板齐全", ok)

        # 12 文档
        refs = [f"0{i}-" for i in range(1, 8)]
        have = os.listdir(os.path.join(ROOT, "references")) if os.path.isdir(os.path.join(ROOT, "references")) else []
        ok = all(any(h.startswith(p) for h in have) for p in refs) \
            and os.path.exists(os.path.join(ROOT, "SKILL.md")) \
            and os.path.exists(os.path.join(ROOT, "templates", "脚本模板.md")) \
            and os.path.exists(os.path.join(ROOT, "templates", "DESIGN.md"))
        check("SKILL.md / references / templates 齐全", ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return finish()


def finish():
    n = len(RESULTS)
    failed = [r for r in RESULTS if not r[1]]
    print()
    if failed:
        print(f"{len(failed)} of {n} checks failed: " + ", ".join(r[0] for r in failed))
        sys.exit(1)
    print(f"All {n} checks passed")


if __name__ == "__main__":
    main()
