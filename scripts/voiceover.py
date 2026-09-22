#!/usr/bin/env python3
"""口播 → 女声普通话配音 + 逐句同步字幕（SRT）；可一步合到视频并烧字幕。每条视频必跑。
用法: python3 voiceover.py edit/脚本.md|口播.txt [--video in.mp4 -o out.mp4 --burn] [--outdir edit/vo]
      [--engine auto|minimax|qwen|edge|say] [--voice 音色] [--speed 1.05] [--gap 0.25] [--lead 0.3] [--max-chars 14]
      [--bgm bgm.mp3 --bgm-volume 0.18] [--keep-audio 0.0] [--no-anchor] [--dry-run] [--audition "试听文本"]

输入：.md 取分镜表「口播」列，「时间」列的起点当锚点；.txt 一行一句，行首 `@3.5` 是锚点（秒），`#` 开头是注释。
口播里的两个记号：` / ` 强制换屏；`{¥9.9=九块九}` 画面显示 ¥9.9、嘴上念九块九。
引擎：auto 默认 edge-tts 晓伊（zh-CN-XiaoyiNeural，语速 +5%，即 AERS 20 秒宣传片 v4 的配音），没有 edge-tts 才依次
退到 MINIMAX_API_KEY → DASHSCOPE_API_KEY → say；付费引擎用 --engine minimax|qwen 显式指定，key 也可写在
~/.config/xhs-video-skills/tts.env（KEY=VALUE）。产物：outdir 下 voiceover.wav / voiceover.srt / voiceover.json / vo_NNN.wav。"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import display_len as dlen, ensure_parent, ffmpeg_base, fmt_dur, media_info, need, run, x264_args  # noqa: E402

KEY_FILE = os.path.join(os.path.expanduser("~"), ".config", "xhs-video-skills", "tts.env")

# 每个引擎：默认模型、默认女声、试听候选（全部普通话女声）、约价（元 / 万字符，以平台账单为准）。
ENGINES = {
    "minimax": {
        "label": "MiniMax Speech", "model": "speech-2.8-hd", "voice": "Chinese (Mandarin)_Warm_Bestie", "price": 3.5,
        "voices": ["Chinese (Mandarin)_Warm_Bestie", "Chinese (Mandarin)_Sweet_Lady", "Chinese (Mandarin)_Warm_Girl",
                   "Chinese (Mandarin)_Crisp_Girl", "Chinese (Mandarin)_Gentle_Senior", "female-shaonv", "female-tianmei"],
    },
    "qwen": {
        "label": "Qwen3-TTS", "model": "qwen3-tts-flash", "voice": "Cherry", "price": 0.8,
        "voices": ["Cherry", "Serena", "Maia", "Nini", "Katerina"],
    },
    "edge": {
        "label": "edge-tts（免费）", "model": "edge", "voice": "zh-CN-XiaoyiNeural", "price": 0,
        "voices": ["zh-CN-XiaoyiNeural", "zh-CN-XiaoxiaoNeural"],
    },
    "say": {"label": "macOS say（离线兜底，机器味重）", "model": "say", "voice": "Tingting", "price": 0, "voices": ["Tingting"]},
    "mock": {"label": "自检用哑引擎", "model": "mock", "voice": "tone", "price": 0, "voices": ["tone"]},
}
# 默认音色 = AERS 20 秒宣传片 v4 的配音：edge-tts 晓伊 + 语速 1.05。付费引擎只在 --engine 显式指定或没装 edge-tts 时用。
AUTO_ORDER = ["edge", "minimax", "qwen", "say"]

HARD = set("，。！？；：,!?;:…\n")
SOFT = set("、 ")
TAIL_STRIP = "，。；：、,.;: …"
PARTICLES = set("的了吗呢吧啊着过")
LATIN = re.compile(r"[A-Za-z0-9¥￥$][A-Za-z0-9.+\-%'’]*")
BREAK = ("/", "")


# ---------- 输入 ----------

def load_keys():
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k and not k.startswith("#") and v.strip() and k not in os.environ:
                    os.environ[k.strip()] = v.strip().strip("'\"")
    except OSError:
        pass


def parse_txt(text):
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"@\s*(\d+(?:\.\d+)?)\s*s?\s+(.*)", s)
        lines.append({"anchor": float(m.group(1)), "text": m.group(2).strip()} if m else {"anchor": None, "text": s})
    return lines


def parse_script_md(text):
    """取分镜表：表头含「口播」的那张表；「时间」列第一个数字是锚点。"""
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in text.splitlines() if l.strip().startswith("|")]
    lines, col, tcol = [], None, None
    for cells in rows:
        if col is None:
            hit = [i for i, c in enumerate(cells) if c.startswith("口播")]
            if hit:
                col = hit[0]
                tcol = next((i for i, c in enumerate(cells) if c.startswith("时间")), None)
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c) or col >= len(cells):
            continue
        t = re.sub(r"[…\.]{2,}\s*$", "", cells[col]).strip()
        if not t:
            continue
        m = re.search(r"\d+(?:\.\d+)?", cells[tcol]) if tcol is not None and tcol < len(cells) else None
        lines.append({"anchor": float(m.group(0)) if m else None, "text": t})
    return lines


# ---------- 文本 → 原子 → 字幕屏 ----------

def atomize(text):
    """拆成 (显示, 读音) 原子。英文单词 / 数字整体是一个原子；{显示=读音} 是一个原子；/ 是强制换屏。"""
    atoms, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            j = text.find("}", i)
            if j > 0 and "=" in text[i:j]:
                d, s = text[i + 1:j].split("=", 1)
                atoms.append((d.strip(), s.strip()))
                i = j + 1
                continue
        if ch == "/":
            while atoms and atoms[-1][0] == " ":
                atoms.pop()
            atoms.append(BREAK)
            i += 1
            while i < len(text) and text[i] == " ":
                i += 1
            continue
        m = LATIN.match(text, i)
        if m:
            atoms.append((m.group(0), m.group(0)))
            i = m.end()
            continue
        atoms.append((ch, ch))
        i += 1
    return atoms


def spoken_text(atoms):
    out = []
    for k, a in enumerate(atoms):
        if a is BREAK:
            prev = out[-1][-1] if out and out[-1] else ""
            nxt = atoms[k + 1][1][:1] if k + 1 < len(atoms) else ""
            if prev and prev not in HARD and nxt not in HARD:
                out.append("，")
        else:
            out.append(a[1])
    return "".join(out).strip()


def weight(spoken):
    """读出来大约几个音节，用来按比例分配时间。"""
    w = 0.0
    for tok in re.findall(r"[A-Za-z]+|\d|[^\sA-Za-z\d]", spoken):
        if tok.isascii() and tok.isalpha():
            w += len(tok) if tok.isupper() and len(tok) <= 5 else max(1.0, len(tok) / 3.0)
        elif tok.isdigit() or tok in ".¥￥$%":
            w += 1.0
        elif ord(tok) > 0x2E7F and tok not in HARD and tok not in SOFT:
            w += 1.0
    return w


def split_long(atoms, max_chars):
    """一个无标点的长分句硬拆成几屏：优先在顿号 / 空格 / 助词后断，绝不拆英文单词。"""
    total = dlen("".join(a[0] for a in atoms))
    n = int(math.ceil(total / max_chars))
    if n <= 1:
        return [atoms]
    parts, start = [], 0
    for k in range(1, n):
        target, best, best_cost = total * k / n, None, 1e9
        for idx in range(start, len(atoms) - 1):
            acc_here = dlen("".join(a[0] for a in atoms[:idx + 1]))
            d = atoms[idx][0]
            cost = abs(acc_here - target) - (2.0 if d in SOFT else 1.0 if d in PARTICLES else 0.0)
            if idx + 1 - start >= 2 and len(atoms) - idx - 1 >= 2 and cost < best_cost:
                best, best_cost = idx + 1, cost
        if best is None:
            break
        parts.append(atoms[start:best])
        start = best
    parts.append(atoms[start:])
    return [p for p in parts if p]


def build_cues(atoms, max_chars):
    """返回 [{text, weight, snap}]；snap=True 表示这一屏之后有标点停顿，可以对到音频里的静音。"""
    clauses, cur = [], []
    for a in atoms:
        if a is BREAK:
            if cur:
                clauses.append([cur, True])
            elif clauses:
                clauses[-1][1] = True
            cur = []
            continue
        cur.append(a)
        if a[0] in HARD:
            clauses.append([cur, False])
            cur = []
    if cur:
        clauses.append([cur, False])

    def shown(at):
        s = "".join(a[0] for a in at).strip().rstrip(TAIL_STRIP)
        return re.sub(r"\s*[，；：。,;:]\s*", " ", s).strip()

    merged = []
    for at, forced in clauses:
        if not shown(at):
            if merged:
                merged[-1][0].extend(at)
            continue
        if merged and not merged[-1][1] and dlen(shown(merged[-1][0] + at)) <= max_chars:
            merged[-1][0].extend(at)
            merged[-1][1] = forced
        else:
            merged.append([list(at), forced])

    cues, hard_split = [], False
    for at, _ in merged:
        parts = split_long(at, max_chars) if dlen(shown(at)) > max_chars else [at]
        hard_split = hard_split or len(parts) > 1
        for k, p in enumerate(parts):
            if shown(p):
                cues.append({"text": shown(p), "weight": max(0.5, weight("".join(a[1] for a in p))), "snap": k == len(parts) - 1})
    return cues, hard_split


# ---------- 引擎 ----------

def http_json(url, payload, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")


def edge_runner():
    for c in [shutil.which("edge-tts"), os.path.join(os.path.expanduser("~"), ".venvs", "tts", "bin", "edge-tts")]:
        if c and os.path.exists(c):
            return [c]
    return ["uvx", "edge-tts"] if shutil.which("uvx") else None


def available(engine):
    if engine == "minimax":
        return bool(os.environ.get("MINIMAX_API_KEY"))
    if engine == "qwen":
        return bool(os.environ.get("DASHSCOPE_API_KEY"))
    if engine == "edge":
        return edge_runner() is not None
    if engine == "say":
        return bool(shutil.which("say"))
    return engine == "mock"


def synth(engine, model, voice, speed, text, dst_base):
    """合成一句，返回原始音频路径。speed 由引擎原生支持的在这里用掉，返回 (path, 还需 atempo 的倍数)。"""
    if engine == "edge":
        out = dst_base + ".mp3"
        cmd = edge_runner() + ["--voice", voice, f"--rate={round((speed - 1) * 100):+d}%", "--text", text, "--write-media", out]
        r = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) < 500:
            raise RuntimeError((r.stderr or "edge-tts 无输出").strip()[-300:])
        return out, 1.0
    if engine == "minimax":
        hosts = [os.environ.get("MINIMAX_API_HOST") or "https://api.minimaxi.com", "https://api.minimax.io"]
        payload = {"model": model, "text": text, "stream": False, "language_boost": "Chinese", "output_format": "hex",
                   "voice_setting": {"voice_id": voice, "speed": round(speed, 2), "vol": 1.0, "pitch": 0},
                   "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3", "channel": 1}}
        gid = os.environ.get("MINIMAX_GROUP_ID")
        err = ""
        for host in dict.fromkeys(hosts):
            url = host.rstrip("/") + "/v1/t2a_v2" + (f"?GroupId={gid}" if gid else "")
            try:
                d = http_json(url, payload, {"Authorization": "Bearer " + os.environ["MINIMAX_API_KEY"]})
            except RuntimeError as e:
                err = str(e)
                continue
            base = d.get("base_resp") or {}
            audio = (d.get("data") or {}).get("audio")
            if base.get("status_code", 0) == 0 and audio:
                out = dst_base + ".mp3"
                with open(out, "wb") as f:
                    f.write(bytes.fromhex(audio))
                return out, 1.0
            err = f"{base.get('status_code')} {base.get('status_msg')}"
        raise RuntimeError("MiniMax: " + err + "（国内站 key 用 api.minimaxi.com，国际站用 api.minimax.io，可设 MINIMAX_API_HOST）")
    if engine == "qwen":
        host = os.environ.get("DASHSCOPE_API_HOST") or "https://dashscope.aliyuncs.com"
        d = http_json(host.rstrip("/") + "/api/v1/services/aigc/multimodal-generation/generation",
                      {"model": model, "input": {"text": text, "voice": voice, "language_type": "Chinese"}},
                      {"Authorization": "Bearer " + os.environ["DASHSCOPE_API_KEY"]})
        url = ((d.get("output") or {}).get("audio") or {}).get("url")
        if not url:
            raise RuntimeError("Qwen-TTS: " + json.dumps(d, ensure_ascii=False)[:300])
        out = dst_base + ".wav"
        with urllib.request.urlopen(url, timeout=120) as r, open(out, "wb") as f:
            shutil.copyfileobj(r, f)
        return out, speed
    if engine == "say":
        out = dst_base + ".aiff"
        r = subprocess.run(["say", "-v", voice, "-o", out, text], text=True, capture_output=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[-300:])
        return out, speed
    if engine == "mock":
        # 每个分句一段正弦，标点处留 0.25s 静音：不联网也能验证「字幕对到停顿」。
        out = dst_base + ".wav"
        segs = [s for s in re.split(r"[，。！？；：,!?;:…]+", text) if s.strip()]
        parts, n = [], 0
        for s in segs:
            parts.append(f"sine=frequency=330:sample_rate=48000:duration={max(0.3, weight(s) / 4.5 / speed):.3f}[t{n}]")
            parts.append(f"anullsrc=r=48000:cl=mono,atrim=0:0.25[g{n}]")
            n += 1
        chain = "".join(f"[t{k}][g{k}]" for k in range(n))
        fc = ";".join(parts) + f";{chain}concat=n={2 * n}:v=0:a=1[a]"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", fc, "-map", "[a]", out], check=True)
        return out, 1.0
    sys.exit(f"未知引擎: {engine}")


def pick_engine(requested):
    if requested != "auto":
        if not available(requested):
            hint = {"minimax": "缺 MINIMAX_API_KEY", "qwen": "缺 DASHSCOPE_API_KEY",
                    "edge": "缺 edge-tts：brew install edge-tts 或 uv tool install edge-tts", "say": "只在 macOS 可用"}
            sys.exit(f"[引擎不可用] {requested}：{hint.get(requested, '')}")
        return requested
    for e in AUTO_ORDER:
        if available(e):
            return e
    sys.exit("没有可用的配音引擎。默认音色要 edge-tts：brew install edge-tts 或 bash scripts/setup.sh --tts。")


# ---------- 音频处理与对时 ----------

def silences(path, noise=-38, min_d=0.10):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", f"silencedetect=noise={noise}dB:d={min_d}", "-f", "null", "-"],
                       text=True, capture_output=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    dur = media_info(path)["duration"]
    return [(max(0.0, s), ends[i] if i < len(ends) else dur) for i, s in enumerate(starts)], dur


def normalize_clip(raw, dst, tempo):
    """原始合成音频 → 48k 立体声 wav，掐掉首尾静音；返回 (时长, 内部静音列表)。"""
    sil, dur = silences(raw)
    t0 = sil[0][1] if sil and sil[0][0] <= 0.02 else 0.0
    t1 = sil[-1][0] if sil and sil[-1][1] >= dur - 0.02 and sil[-1][0] > t0 else dur
    a, b = max(0.0, t0 - 0.03), min(dur, t1 + 0.10)
    af = f"atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS"
    if abs(tempo - 1.0) > 0.005:
        af += f",atempo={min(2.0, max(0.5, tempo)):.3f}"
    run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", af, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", dst], quiet=True)
    inner = [((s - a) / tempo, (e - a) / tempo) for s, e in sil if s > t0 + 0.01 and e < t1 - 0.01]
    return media_info(dst)["duration"], inner


def time_cues(cues, dur, inner):
    """按音节比例估每屏的边界，再把「标点后的边界」吸到最近的真实静音上；硬拆的边界在两侧锚点之间按比例插值。"""
    n = len(cues)
    total = sum(c["weight"] for c in cues)
    acc, prop = 0.0, []
    for c in cues[:-1]:
        acc += c["weight"]
        prop.append(dur * acc / total)
    fixed = {0: 0.0, n: dur}
    snap_idx = [k for k in range(n - 1) if cues[k]["snap"]]
    gaps = []  # 被一口气声切成两截的停顿先并起来
    for s, e in inner:
        if gaps and s - gaps[-1][1] < 0.12:
            gaps[-1][1] = e
        else:
            gaps.append([s, e])
    mids = [(s + e) / 2 for s, e in gaps]
    # 每个标点边界取离「按音节比例估的位置」最近的真实停顿（顿号、词间也会停，所以不按顺序数，按距离配）
    used = -1
    for k in snap_idx:
        cand = [(abs(m - prop[k]), j) for j, m in enumerate(mids) if j > used and abs(m - prop[k]) <= max(0.6, 0.18 * dur)]
        if cand:
            used = min(cand)[1]
            fixed[k + 1] = mids[used]
    keys = sorted(fixed)
    bounds = [0.0] * (n + 1)
    for lo, hi in zip(keys, keys[1:]):
        w = [cues[k]["weight"] for k in range(lo, hi)]
        run_w = 0.0
        for k in range(lo, hi):
            bounds[k] = fixed[lo] + (fixed[hi] - fixed[lo]) * run_w / sum(w)
            run_w += w[k - lo]
    bounds[n] = dur
    return [(bounds[k], bounds[k + 1]) for k in range(n)], len(fixed) - 2


def srt_ts(t):
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def mix_track(lines, total, dst):
    cmd = ["ffmpeg", "-y", "-v", "error"]
    fc = []
    for k, l in enumerate(lines):
        cmd += ["-i", l["wav"]]
        ms = int(round(l["start"] * 1000))
        fc.append(f"[{k}:a]adelay={ms}:all=1[d{k}]")
    fc.append("".join(f"[d{k}]" for k in range(len(lines))) + f"amix=inputs={len(lines)}:normalize=0:duration=longest,apad,atrim=0:{total:.3f}[a]")
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[a]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", dst], quiet=True)


def mux(video, vo_wav, vo_end, out, bgm, bgm_volume, keep_audio, on_overrun, tail):
    info = media_info(video)
    if not info or info["kind"] != "video":
        sys.exit(f"不是视频: {video}")
    need_len = vo_end + tail
    extend = max(0.0, need_len - info["duration"])
    if extend > 0.05:
        if on_overrun == "error":
            sys.exit(f"[超时] 配音到 {vo_end:.1f}s，视频只有 {info['duration']:.1f}s。缩短口播、提高 --speed，或用 --on-overrun extend。")
        print(f"[提醒] 配音比视频长 {extend:.1f}s，定格最后一帧补足。超过 1.5s 建议回去改画面时长。")
    total = max(info["duration"], need_len)
    cmd = ffmpeg_base() + ["-i", video, "-i", vo_wav]
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", bgm]
    fc, mixin = ["[1:a]apad,asplit=2[vo][sc]" if bgm else "[1:a]apad[vo]"], ["[vo]"]
    if keep_audio > 0 and info["has_audio"]:
        fc.append(f"[0:a]volume={keep_audio},apad[orig]")
        mixin.append("[orig]")
    if bgm:
        fc.append(f"[2:a]volume={bgm_volume}[b0];[b0][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[b1];"
                  f"[b1]afade=t=in:d=0.4,afade=t=out:st={max(0.0, total - 0.8):.3f}:d=0.8[bgm]")
        mixin.append("[bgm]")
    fc.append("".join(mixin) + f"amix=inputs={len(mixin)}:normalize=0:duration=longest,atrim=0:{total:.3f}[aout]")
    if extend > 0.05:
        fc.append(f"[0:v]tpad=stop_mode=clone:stop_duration={extend:.3f}[vout]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]"] + x264_args(18)
    else:
        cmd += ["-filter_complex", ";".join(fc), "-map", "0:v:0", "-c:v", "copy"]
    cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", f"{total:.3f}", "-movflags", "+faststart", out]
    run(cmd)


# ---------- 主流程 ----------

def audition(engine, text, outdir, speed):
    cfg = ENGINES[engine]
    os.makedirs(outdir, exist_ok=True)
    print(f"试听 {cfg['label']} 的 {len(cfg['voices'])} 个女声 → {outdir}")
    for v in cfg["voices"]:
        base = os.path.join(outdir, re.sub(r"[^\w\-]+", "_", f"{engine}-{v}"))
        try:
            raw, _ = synth(engine, cfg["model"], v, speed, text, base)
            print(f"  ✔ {v:<36} {raw}")
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            print(f"  ✘ {v:<36} {e}")
    print("听完把选中的音色用 --voice 传回来；同一个账号固定一个音色，别每条换。")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="脚本.md（取「口播」列）或 口播.txt（一行一句）")
    ap.add_argument("--video", help="要配音的视频；不给就只出 wav + srt")
    ap.add_argument("-o", "--output", help="配好音（--burn 时连字幕一起）的视频")
    ap.add_argument("--outdir", help="配音产物目录，默认 <source 所在目录>/vo")
    ap.add_argument("--engine", default="auto", choices=["auto"] + list(ENGINES))
    ap.add_argument("--model", default="", help="覆盖引擎默认模型，如 speech-2.8-turbo / qwen3-tts-instruct-flash")
    ap.add_argument("--voice", default="", help="覆盖默认女声；候选见 --audition")
    ap.add_argument("--speed", type=float, default=1.05, help="语速倍数，带货口播 1.05–1.15（默认 1.05，edge-tts 即 +5%%）")
    ap.add_argument("--gap", type=float, default=0.25, help="句与句之间至少留多少秒")
    ap.add_argument("--lead", type=float, default=0.3, help="第一句没有锚点时从第几秒开始")
    ap.add_argument("--tail", type=float, default=0.4, help="最后一句说完后至少留多少秒画面")
    ap.add_argument("--max-chars", type=int, default=14, help="每屏字幕最多几个汉字（英文数字算半个）")
    ap.add_argument("--no-anchor", action="store_true", help="忽略时间锚点，句子首尾相接")
    ap.add_argument("--bgm", help="背景音乐文件；自动循环、随人声压低、首尾淡入淡出")
    ap.add_argument("--bgm-volume", type=float, default=0.18)
    ap.add_argument("--keep-audio", type=float, default=0.0, help="保留原视频声音的音量（0 = 丢弃，屏录键盘声建议 0）")
    ap.add_argument("--on-overrun", default="extend", choices=["extend", "error"], help="配音比视频长时：定格补足 / 报错")
    ap.add_argument("--burn", action="store_true", help="合轨后直接调 burn_subs.py 烧字幕")
    ap.add_argument("--style", default="clean", choices=["clean", "box", "accent"])
    ap.add_argument("--bottom", type=int, default=640)
    ap.add_argument("--accent", default="#1B6B5F")
    ap.add_argument("--dry-run", action="store_true", help="只看断句、字数、引擎和约价，不合成")
    ap.add_argument("--audition", metavar="TEXT", help="用同一句话把当前引擎的候选女声各合成一遍，供挑选")
    a = ap.parse_args()

    need("ffmpeg")
    load_keys()
    engine = pick_engine(a.engine)
    cfg = ENGINES[engine]
    model, voice = a.model or cfg["model"], a.voice or cfg["voice"]

    if a.audition:
        return audition(engine, a.audition, a.outdir or os.path.join(os.getcwd(), "audition"), a.speed)
    if not a.source:
        ap.error("缺 source（脚本.md 或 口播.txt）")
    with open(a.source, encoding="utf-8") as f:
        text = f.read().lstrip("﻿")
    lines = parse_script_md(text) if a.source.lower().endswith(".md") else parse_txt(text)
    if not lines:
        sys.exit("没有解析到口播。.md 需要一张表头含「口播」的表；.txt 一行一句。")

    chars, hard = 0, []
    for i, l in enumerate(lines, 1):
        atoms = atomize(l["text"])
        l["spoken"] = spoken_text(atoms)
        l["cues"], was_hard = build_cues(atoms, a.max_chars)
        if not l["cues"]:
            sys.exit(f"第 {i} 句没有可显示的字：{l['text']}")
        if was_hard:
            hard.append(i)
        if a.no_anchor:
            l["anchor"] = None
        chars += len(l["spoken"])
    print(f"引擎 {cfg['label']} · 模型 {model} · 音色 {voice} · 语速 ×{a.speed} · {len(lines)} 句 {chars} 字"
          + (f" · 约 ¥{max(0.01, chars / 10000 * cfg['price']):.2f}" if cfg["price"] else " · 免费"))
    if engine == "say" and a.engine == "auto":
        print("[提示] 当前是离线兜底音色。装 edge-tts 即用默认的晓伊：bash scripts/setup.sh --tts")
    for i in hard:
        print(f"[提醒] 第 {i} 句有无标点长句被硬拆：{' / '.join(c['text'] for c in lines[i - 1]['cues'])}；不顺就在口播里用 / 指定断点。")
    if a.dry_run:
        for i, l in enumerate(lines, 1):
            at = "接上句" if l["anchor"] is None else f"@{l['anchor']:g}s"
            print(f"{i:>2} {at:<7} 念：{l['spoken']}\n{'':>11}屏：{' ｜ '.join(c['text'] for c in l['cues'])}")
        return

    outdir = a.outdir or os.path.join(os.path.dirname(os.path.abspath(a.source)), "vo")
    cache = os.path.join(outdir, "cache")
    os.makedirs(cache, exist_ok=True)

    cursor, srt, snapped, nb = None, [], 0, 0
    for i, l in enumerate(lines, 1):
        h = hashlib.sha1(f"{engine}|{model}|{voice}|{a.speed}|{l['spoken']}".encode("utf-8")).hexdigest()[:16]
        hit = [p for p in (os.path.join(cache, h + e) for e in (".mp3", ".wav", ".aiff")) if os.path.exists(p)]
        tempo = a.speed if engine in ("qwen", "say") else 1.0
        if hit:
            raw = hit[0]
        else:
            for attempt in (1, 2, 3):
                try:
                    raw, tempo = synth(engine, model, voice, a.speed, l["spoken"], os.path.join(cache, h))
                    break
                except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                    if attempt == 3:
                        sys.exit(f"[配音失败] 第 {i} 句：{e}\n整条视频必须同一个音色；修好网络 / key 后重跑（已合成的句子有缓存，不重复计费）。")
        l["wav"] = os.path.join(outdir, f"vo_{i:03d}.wav")
        l["duration"], inner = normalize_clip(raw, l["wav"], tempo)
        earliest = a.lead if cursor is None else cursor + a.gap
        l["start"] = max(earliest, l["anchor"]) if l["anchor"] is not None else earliest
        l["pushed"] = round(l["start"] - l["anchor"], 3) if l["anchor"] is not None else 0.0
        l["end"] = cursor = l["start"] + l["duration"]
        spans, ns = time_cues(l["cues"], l["duration"], inner)
        snapped += ns
        nb += len(l["cues"]) - 1
        for c, (s, e) in zip(l["cues"], spans):
            c["start"], c["end"] = round(l["start"] + s, 3), round(l["start"] + e, 3)
            srt.append(c)
        srt[-1]["end"] = round(l["end"] + 0.12, 3)
    for c, nxt in zip(srt, srt[1:]):
        c["end"] = min(c["end"], nxt["start"])

    total = lines[-1]["end"] + a.tail
    vo_wav, srt_path = os.path.join(outdir, "voiceover.wav"), os.path.join(outdir, "voiceover.srt")
    mix_track(lines, total, vo_wav)
    with open(srt_path, "w", encoding="utf-8") as f:
        for k, c in enumerate(srt, 1):
            f.write(f"{k}\n{srt_ts(c['start'])} --> {srt_ts(c['end'])}\n{c['text']}\n\n")
    manifest = {"engine": engine, "model": model, "voice": voice, "speed": a.speed, "total": round(total, 3),
                "wav": vo_wav, "srt": srt_path,
                "lines": [{"index": i, "anchor": l["anchor"], "start": round(l["start"], 3), "end": round(l["end"], 3),
                           "duration": round(l["duration"], 3), "pushed": l["pushed"], "text": l["text"], "spoken": l["spoken"],
                           "wav": l["wav"], "cues": [{k: c[k] for k in ("start", "end", "text")} for c in l["cues"]]}
                          for i, l in enumerate(lines, 1)]}
    with open(os.path.join(outdir, "voiceover.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{'#':>2}  {'起点':>6}  {'时长':>5}  口播")
    for i, l in enumerate(lines, 1):
        late = f"  ← 比分镜晚 {l['pushed']:.1f}s" if l["pushed"] > 0.3 else ""
        print(f"{i:>2}  {l['start']:>6.2f}  {l['duration']:>5.2f}  {l['spoken']}{late}")
    syl = sum(c["weight"] for l in lines for c in l["cues"])
    print(f"\n配音总长 {fmt_dur(total)} · 实测语速 {syl / sum(l['duration'] for l in lines):.1f} 字/秒 · 字幕 {len(srt)} 屏"
          f"（屏间边界 {nb} 处，其中 {snapped} 处对到真实停顿）")
    short = [c for c in srt if c["end"] - c["start"] < 0.55]
    if short:
        print(f"[提醒] {len(short)} 屏字幕不足 0.55s（{'、'.join(c['text'] for c in short[:3])}），一闪而过，考虑合并或改口播。")
    if any(l["pushed"] > 0.3 for l in lines):
        print("[提醒] 有句子被前一句挤晚了：缩短前一句口播、把 --speed 提到 1.12–1.18，或按上表起点改画面时长（流水线 B 就改幕长）。")
    print(f"产物: {vo_wav}\n      {srt_path}\n      {os.path.join(outdir, 'voiceover.json')}")

    if not a.video:
        return
    out = a.output or os.path.splitext(a.video)[0] + ("-dub-sub.mp4" if a.burn else "-dub.mp4")
    ensure_parent(out)
    dubbed = os.path.join(outdir, "dubbed.mp4") if a.burn else out
    mux(a.video, vo_wav, lines[-1]["end"], dubbed, a.bgm, a.bgm_volume, a.keep_audio, a.on_overrun, a.tail)
    if a.burn:
        run([sys.executable, os.path.join(HERE, "burn_subs.py"), dubbed, srt_path, "-o", out,
             "--style", a.style, "--bottom", a.bottom, "--accent", a.accent])
    print(f"完成: {out}")


if __name__ == "__main__":
    main()
