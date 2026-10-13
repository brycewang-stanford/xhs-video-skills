# -*- coding: utf-8 -*-
"""用法: python tools/voice.py [edge|melo]
逐句合成女声普通话旁白，写出 assets/voice/narration.wav 和 timings.json（每幕、每句的起止时间）。
引擎：默认 edge-tts 晓伊（zh-CN-XiaoyiNeural，本 skill 的固定音色）；连不上（403）时自动退到本地
MeloTTS 中文女声（sherpa-onnx，模型放在 ~/.cache/hyperframes/tts/melo/vits-melo-tts-zh_en/）。
每句单独缓存在 assets/voice/lines/，只重录改过的句子。
响度：每句先拉到同一 RMS，再整轨压缩 + 限幅顶到接近满刻度，所以不会一句大一句小。"""
import hashlib, json, os, subprocess, sys
import numpy as np, soundfile as sf
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
import script
FRAMES = script.FRAMES

ENGINE = sys.argv[1] if len(sys.argv) > 1 else "edge"
RATE = getattr(script, "RATE", "+0%")
EDGE_VOICE = "zh-CN-XiaoyiNeural"
SPEED = "%.2f" % (1 + int(RATE.strip("%")) / 100.0)
LEAD, GAP, COMMA_GAP, TAIL, LAST_TAIL = 0.45, 0.34, 0.14, 0.6, 2.4
SR = 24000
cache = os.path.join(root, "assets/voice/lines"); os.makedirs(cache, exist_ok=True)
MELO_DIR = os.path.expanduser("~/.cache/hyperframes/tts/melo/vits-melo-tts-zh_en/")
_melo = None

def melo(text, wav):
    global _melo
    if _melo is None:
        import sherpa_onnx
        d = MELO_DIR
        _melo = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=d + "model.onnx", lexicon=d + "lexicon.txt", tokens=d + "tokens.txt", dict_dir=d + "dict"), num_threads=4),
            rule_fsts=",".join(d + x for x in ["date.fst", "number.fst", "phone.fst", "new_heteronym.fst"])))
    for a, b in (("：", "，"), ("；", "，"), ("「", ""), ("」", ""), ("·", "")): text = text.replace(a, b)
    a = _melo.generate(text, sid=0, speed=float(SPEED))
    tmp = wav[:-4] + ".m.wav"; sf.write(tmp, np.asarray(a.samples, dtype=np.float32), a.sample_rate)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-ar", str(SR), "-ac", "1", wav], check=True)
    os.remove(tmp)

def edge(text, wav):
    mp3 = wav[:-4] + ".mp3"
    r = subprocess.run(["edge-tts", "--voice", EDGE_VOICE, "--rate=" + RATE, "--text", text, "--write-media", mp3], capture_output=True)
    if r.returncode != 0 or not os.path.exists(mp3) or os.path.getsize(mp3) < 1000:
        if os.path.exists(mp3): os.remove(mp3)
        return False
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", wav], check=True)
    os.remove(mp3); return True

def synth(text):
    global ENGINE
    for eng in ([ENGINE] if ENGINE != "edge" else ["edge", "melo"]):
        voice = {"edge": EDGE_VOICE, "melo": "melo-zh-f"}[eng]
        wav = os.path.join(cache, hashlib.md5((voice + RATE + text).encode()).hexdigest()[:16] + ".wav")
        if not os.path.exists(wav):
            if eng == "edge":
                if not edge(text, wav):
                    print("edge-tts 拒绝连接，改用本地 MeloTTS", flush=True); ENGINE = "melo"; continue
            else:
                melo(text, wav)
        break
    a, r = sf.read(wav, dtype="float32"); assert r == SR
    idx = np.where(np.abs(a) > 0.006)[0]
    a = a[max(0, idx[0] - int(.03 * SR)): min(len(a), idx[-1] + int(.05 * SR))]
    return level(a)

TARGET_RMS = 0.13
def level(a):
    """Bring every sentence to the same loudness: gain it so its voiced part (50 ms windows above the
    noise floor) has the same RMS, so no sentence comes out quieter or louder than its neighbours."""
    n = int(.05 * SR); w = a[:len(a) // n * n].reshape(-1, n)
    r = np.sqrt((w ** 2).mean(axis=1)); voiced = r[r > max(0.01, r.max() * 0.15)]
    return a * (TARGET_RMS / float(np.sqrt((voiced ** 2).mean()))) if len(voiced) else a

chunks, frames, t = [], [], 0.0
def silence(d):
    global t
    n = int(round(d * SR)); chunks.append(np.zeros(n, dtype=np.float32)); t += n / SR
for fi, (fid, sents) in enumerate(FRAMES):
    f0 = t; cues = []
    silence(LEAD)
    for si, (zh, spoken) in enumerate(sents):
        a = synth(spoken or zh)
        s = t; chunks.append(a); t += len(a) / SR
        cues.append({"i": si, "zh": zh, "start": round(s - f0, 3), "end": round(t - f0, 3)})
        if si < len(sents) - 1:
            silence(COMMA_GAP if zh.endswith("，") else GAP)
    silence(LAST_TAIL if fi == len(FRAMES) - 1 else TAIL)
    frames.append({"id": fid, "start": round(f0, 3), "duration": round(t - f0, 3), "cues": cues})
    print(fid, round(t - f0, 2), flush=True)
audio = np.concatenate(chunks)
# even out what is left inside each sentence, then hold the peaks just under full scale
raw = os.path.join(root, "assets/voice/_raw.wav"); out = os.path.join(root, "assets/voice/narration.wav")
sf.write(raw, np.clip(audio, -1, 1), SR)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
                "acompressor=threshold=-24dB:ratio=4:attack=4:release=140:knee=6:makeup=6dB,volume=5.5dB,alimiter=limit=0.89:attack=3:release=60:level=false",
                "-ar", str(SR), "-ac", "1", out], check=True)
os.remove(raw)
n0, n1 = len(audio), len(sf.read(out)[0]); assert abs(n0 - n1) < SR * 0.02, (n0, n1)
json.dump({"engine": ENGINE, "rate": RATE, "total": round(t, 3), "frames": frames},
          open(os.path.join(root, "assets/voice/timings.json"), "w"), ensure_ascii=False, indent=1)
print("engine %s | total %.2fs = %d:%04.1f, %d subtitles, rate %s" % (ENGINE, t, t // 60, t % 60, sum(len(s) for _, s in FRAMES), RATE))
