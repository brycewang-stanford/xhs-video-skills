# -*- coding: utf-8 -*-
"""讲解型竖屏视频的构建引擎（HyperFrames，1080×1920）。

一条视频 = 三个手写文件：tools/script.py（口播，一条一屏字幕）、tools/scenes.py（各幕画面）、
以及本文件。tools/voice.py 录完音后，scenes.py 末尾调用 build()，生成
compositions/<幕>.html、compositions/backdrop.html（深紫背景 + 全程固定标题 + 进度条）、
compositions/captions.html、index.html 和 assets/bgm.m4a。改一句口播后重跑 voice.py 再跑 scenes.py，全部重新对时。

画面：深色舞台、3Blue1Brown 式的描线曲线和公式；顶部是抖音式固定标题（黄底黑字两行 + 黑底白字两行）。
版式数字见 references/08-explainer-style.md。"""
import html as _h, json, math, os, random, re, subprocess

W, H = 1080, 1920
SX, SY, SW, SH = 48, 584, 984, 810            # stage box
CAP_TOP, CAP_H = 1408, 170
BLUE, YEL, GRN, RED, WHT, GRY = "#58C4DD", "#FFE94A", "#83C167", "#FC6255", "#F3EEF7", "#A79BB3"
GSAP = '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>'

FONTS = """
@font-face{font-family:"MathI";src:url("assets/fonts/STIXTwoText-Italic.ttf") format("truetype")}
@font-face{font-family:"MathR";src:url("assets/fonts/STIXTwoText.ttf") format("truetype")}
@font-face{font-family:"Hei";src:local("PingFangSC-Medium"),local("PingFang SC Medium"),local("PingFang SC");font-weight:100 500}
@font-face{font-family:"Hei";src:local("PingFangSC-Semibold"),local("PingFang SC Semibold"),local("PingFang SC");font-weight:600 900}
"""
CJK = '"Hei",sans-serif'

CSS = FONTS + """
[data-composition-id="__ID__"]{position:absolute;inset:0;font-family:%(cjk)s;font-weight:600;color:%(wht)s;font-size:40px;line-height:1.35}
.body{position:absolute;left:%(sx)dpx;top:%(sy)dpx;width:%(sw)dpx;height:%(sh)dpx}
.abs{position:absolute}
.cv{position:absolute;left:0;top:0;width:%(sw)dpx;height:%(sh)dpx;overflow:visible}
.cv text{font-family:%(cjk)s;font-weight:600;fill:%(wht)s}
.cv .dr{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1}
.cv .ax{stroke:#6E6280;stroke-width:3;fill:none;stroke-linecap:round}
.m{font-family:"MathI";font-style:normal;font-weight:400;letter-spacing:.01em}
.m b{font-family:"MathR";font-style:normal;font-weight:400}
.m sub{font-size:.58em;vertical-align:-.28em;line-height:0}
.m sup{font-size:.58em;vertical-align:.5em;line-height:0}
.eq{position:absolute;white-space:nowrap;font-size:64px;line-height:1.2}
.hl{display:inline-block;border-radius:10px;padding:0 6px;margin:0 -2px;background-color:rgba(255,233,74,0)}
.chip{display:inline-block;white-space:nowrap;border:3px solid %(blue)s;color:%(blue)s;border-radius:14px;padding:4px 22px 6px;font-size:38px;font-weight:700;background:rgba(88,196,221,.10)}
.chip.y{border-color:%(yel)s;color:%(yel)s;background:rgba(255,233,74,.10)}
.chip.g{border-color:%(grn)s;color:%(grn)s;background:rgba(131,193,103,.10)}
.note{position:absolute;white-space:nowrap;font-size:34px;color:%(gry)s;font-weight:500}
.big{position:absolute;white-space:nowrap;font-size:80px;font-weight:800;line-height:1.15}
.mk{background:linear-gradient(transparent 58%%,rgba(255,233,74,.42) 58%%) no-repeat left / 0%% 100%%}
.y{color:%(yel)s}.b{color:%(blue)s}.g{color:%(grn)s}.r{color:%(red)s}.gr{color:%(gry)s}
.card{position:absolute;box-sizing:border-box;border:3px solid #6E6280;border-radius:22px;background:rgba(18,6,26,.72)}
.ctr{left:0;width:%(sw)dpx;text-align:center}
.stamp{position:absolute;white-space:nowrap;font-size:64px;font-weight:800;color:%(red)s;border:6px solid %(red)s;border-radius:16px;padding:0 22px 4px;background:rgba(18,6,26,.8)}
.shot{position:absolute;background-size:cover;background-position:center;border-radius:18px;box-shadow:0 16px 50px rgba(0,0,0,.6)}
""" % dict(cjk=CJK, wht=WHT, sx=SX, sy=SY, sw=SW, sh=SH, blue=BLUE, yel=YEL, grn=GRN, red=RED, gry=GRY)

KIT = """
(function(){
const R=document.querySelector('[data-composition-id="__ID__"]');
const q=k=>R.querySelectorAll('[data-k~="'+k+'"]');
const tl=gsap.timeline({paused:true});
const C=__CUES__, D=__DUR__;
const at=(i,f)=>C[i][0]+(C[i][1]-C[i][0])*(f||0);
const fade=(k,t,d)=>tl.fromTo(q(k),{opacity:0},{opacity:1,duration:d||.35,ease:"none"},t);
const out=(k,t,d)=>tl.to(q(k),{opacity:0,duration:d||.3,ease:"none"},t);
const rise=(k,t,o)=>tl.fromTo(q(k),{y:44,opacity:0},Object.assign({y:0,opacity:1,duration:.5,ease:"power3.out"},o||{}),t);
const pop=(k,t,o)=>tl.fromTo(q(k),{scale:.4,opacity:0},Object.assign({scale:1,opacity:1,duration:.45,ease:"back.out(1.9)"},o||{}),t);
const draw=(k,t,d,o)=>tl.fromTo(q(k),{strokeDashoffset:1},Object.assign({strokeDashoffset:0,duration:d||.8,ease:"power1.inOut"},o||{}),t);
const growY=(k,t,d,o)=>tl.fromTo(q(k),{scaleY:0},Object.assign({scaleY:1,duration:d||.6,ease:"power3.out"},o||{}),t);
const growX=(k,t,d,o)=>tl.fromTo(q(k),{scaleX:0},Object.assign({scaleX:1,duration:d||.6,ease:"power3.out"},o||{}),t);
const mark=(k,t,d)=>tl.fromTo(q(k),{backgroundSize:"0% 100%"},{backgroundSize:"100% 100%",duration:d||.5,ease:"power2.out"},t);
const glow=(k,t)=>tl.fromTo(q(k),{backgroundColor:"rgba(255,233,74,0)",color:"#F3EEF7"},{backgroundColor:"rgba(255,233,74,.22)",color:"#FFE94A",duration:.35,stagger:.12},t);
const pulse=(k,t)=>tl.fromTo(q(k),{scale:1},{scale:1.14,duration:.18,ease:"power2.out",yoyo:true,repeat:1,immediateRender:false},t);
const B=q("body");
const so=(c,o)=>{const e=R.querySelectorAll(c);if(e.length)gsap.set(e,{transformOrigin:o})};so(".cv .sc","50% 50%");so(".cv .gy","50% 100%");so(".cv .gx","0% 50%");
tl.fromTo(B,{opacity:0,y:36},{opacity:1,y:0,duration:.4,ease:"power2.out"},0);
__JS__
__EXIT__
window.__timelines["__ID__"]=tl;
})();
"""
EXIT = 'tl.to(B,{opacity:0,y:-30,duration:.26,ease:"power2.in"},D-.27);'

def svg(inner): return '<svg class="cv" viewBox="0 0 %d %d">%s</svg>' % (SW, SH, inner)
def path(k, d, color, w=7, extra=""):
    return '<path class="dr" data-k="%s" pathLength="1" d="%s" stroke="%s" stroke-width="%s" %s/>' % (k, d, color, w, extra)
def poly(pts): return "M" + " L".join("%.1f,%.1f" % p for p in pts)
def txt(k, x, y, s, size=32, fill=WHT, anchor="start", extra=""):
    return '<text data-k="%s" x="%s" y="%s" font-size="%s" fill="%s" text-anchor="%s" %s>%s</text>' % (k, x, y, size, fill, anchor, extra, s)
def M(s): return '<span class="m">%s</span>' % s
def HL(s, k="E"): return '<span class="hl" data-k="%s">%s</span>' % (k, s)
E = "<b>E</b><sub>t</sub>"

def shot(k, img, l, t, w, h, rot=0, cap=""):
    """A real screenshot (paper first page, faculty page...) as a tilted card with a small source label."""
    lab = '<div class="note" style="left:4px;top:%dpx;font-size:26px;color:%s">%s</div>' % (h + 8, WHT, cap) if cap else ""
    return ('<div class="abs" data-k="%s" style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;transform:rotate(%sdeg)">'
            '<div class="shot" style="inset:0;background-color:#fff;background-image:url(\'assets/img/%s.jpg\')"></div>%s</div>') % (k, l, t, w, h, rot, img, lab)


def build(ROOT, SCENES, title, subs, bgm=None, bgm_lufs=-33):
    """ROOT: 项目目录。SCENES: {幕 id: dict(html=, js=, exit=可选)}，id 与顺序要和 tools/script.py 一致。
    title: 两行黄底标题 (行1, 行2)，写结论，不写问句。subs: 两行黑底白字副标题。
    bgm: 背景音乐文件路径（可无）；bgm_lufs: 音乐响度，人声约 -16 LUFS，默认压在人声下约 17 dB。"""
    TITLE_1, TITLE_2 = title; SUB_1, SUB_2 = subs
    T = json.load(open(os.path.join(ROOT, "assets/voice/timings.json"), encoding="utf-8"))
    assert [f["id"] for f in T["frames"]] == list(SCENES), "scene ids/order must match tools/script.py"
    os.makedirs(os.path.join(ROOT, "compositions"), exist_ok=True)
    TOTAL = T["total"]
    for fr in T["frames"]:
        sid, sc, D = fr["id"], SCENES[fr["id"]], fr["duration"]
        cues = json.dumps([[c["start"], c["end"]] for c in fr["cues"]])
        js = (KIT.replace("__JS__", sc["js"]).replace("__EXIT__", sc.get("exit", EXIT)).replace("__CUES__", cues)
              .replace("__DUR__", str(D)).replace("__ID__", sid))
        page = ('<!doctype html>\n<html lang="zh-Hans">\n<head><meta charset="UTF-8"></head>\n<body>\n<template id="%s-template">\n<style>%s</style>\n'
                '<div data-composition-id="%s" data-width="%d" data-height="%d" data-duration="%s">\n<div class="body" data-k="body">%s</div>\n</div>\n'
                '<script>%s</script>\n</template>\n</body>\n</html>\n') % (sid, CSS.replace("__ID__", sid), sid, W, H, D, sc["html"], js)
        open(os.path.join(ROOT, "compositions", sid + ".html"), "w", encoding="utf-8").write(page)

    def sub(cid, style, body, js):
        return ('<!doctype html>\n<html lang="zh-Hans">\n<head><meta charset="UTF-8"></head>\n<body>\n<template id="%s-template">\n<style>%s%s</style>\n'
                '<div data-composition-id="%s" data-width="%d" data-height="%d" data-duration="%s">\n%s\n</div>\n'
                '<script>(function(){const R=document.querySelector(\'[data-composition-id="%s"]\');const tl=gsap.timeline({paused:true});\n%s\nwindow.__timelines["%s"]=tl;})();</script>\n</template>\n</body>\n</html>\n'
                ) % (cid, FONTS, style, cid, W, H, TOTAL, body, cid, js, cid)

    slots, caps, caps_js, seg, seg_js = [], [], [], [], []
    for i, fr in enumerate(T["frames"]):
        slots.append('<div id="el-%s" class="clip slot" data-composition-id="%s" data-composition-src="compositions/%s.html" data-start="%s" data-duration="%s" data-track-index="1" data-width="%d" data-height="%d"></div>'
                     % (fr["id"], fr["id"], fr["id"], fr["start"], fr["duration"], W, H))
        seg.append('<i style="flex:%s"><b></b></i>' % fr["duration"])
        seg_js.append('tl.to(s[%d],{scaleX:1,duration:%s,ease:"none"},%s);' % (i, round(fr["duration"] - 0.02, 3), fr["start"]))
        cs = fr["cues"]
        for j, c in enumerate(cs):
            s = fr["start"] + c["start"] - 0.08
            e = fr["start"] + (cs[j + 1]["start"] - 0.08 if j + 1 < len(cs) else fr["duration"] - (0.0 if i == len(T["frames"]) - 1 else 0.2))
            n = len(caps)
            parts = "".join('<span class="cl">%s</span>' % _h.escape(x) for x in re.findall(r"[^，、：；]+[，、：；]?", c["zh"]))
            caps.append('<div class="cap" data-n="%d"><div class="zh%s">%s</div></div>' % (n, " long" if len(c["zh"]) > 22 else "", parts))
            caps_js.append('tl.set(c[%d],{opacity:1},%.3f);tl.set(c[%d],{opacity:0},%.3f);' % (n, s, n, e))

    BACK_CSS = """
    [data-composition-id="backdrop"]{position:absolute;inset:0;font-family:%(cjk)s;color:#fff}
    .bg{position:absolute;inset:0;background:radial-gradient(120%% 62%% at 50%% 30%%,#4B1560 0%%,#32103F 38%%,#1A0822 72%%,#0C0410 100%%)}
    .glow{position:absolute;left:-200px;top:300px;width:1480px;height:1100px;background:radial-gradient(closest-side,rgba(150,60,190,.30),rgba(150,60,190,0));}
    .grid{position:absolute;left:0;top:%(gy)dpx;width:1080px;height:%(gh)dpx;background-image:linear-gradient(rgba(255,255,255,.045) 2px,transparent 2px),linear-gradient(90deg,rgba(255,255,255,.045) 2px,transparent 2px);background-size:82px 82px;background-position:7px 0;-webkit-mask-image:radial-gradient(70%% 60%% at 50%% 50%%,#000 40%%,transparent 100%%);mask-image:radial-gradient(70%% 60%% at 50%% 50%%,#000 40%%,transparent 100%%)}
    .vig{position:absolute;inset:0;background:radial-gradient(90%% 70%% at 50%% 45%%,transparent 55%%,rgba(0,0,0,.55) 100%%)}
    .ttl{position:absolute;left:44px;top:196px;width:1000px}
    .ttl .t{display:block;width:fit-content;background:#FFE94A;color:#111;font-weight:800;font-size:76px;line-height:1;padding:8px 14px 12px;margin-bottom:8px;letter-spacing:.01em;white-space:nowrap}
    .ttl .s{display:block;width:fit-content;background:#000;color:#fff;font-weight:700;font-size:52px;line-height:1;padding:8px 12px 11px;margin-bottom:0;white-space:nowrap}
    .ttl .gap{height:8px}
    .prog{position:absolute;left:48px;top:556px;width:984px;height:8px;display:flex;gap:8px}
    .prog i{display:block;height:8px;background:rgba(255,255,255,.16);border-radius:4px;overflow:hidden}
    .prog b{display:block;width:100%%;height:8px;background:#FFE94A;transform-origin:left center}
    """ % dict(cjk=CJK, gy=SY - 20, gh=SH + 40)
    BACK = sub("backdrop", BACK_CSS,
               '<div class="bg"></div><div class="glow" data-k="glow"></div><div class="grid"></div><div class="vig"></div>'
               '<div class="ttl"><span class="t">%s</span><span class="t">%s</span><div class="gap"></div><span class="s">%s</span><span class="s">%s</span></div>'
               '<div class="prog">%s</div>' % (TITLE_1, TITLE_2, SUB_1, SUB_2, "".join(seg)),
               'const s=R.querySelectorAll(".prog b");gsap.set(s,{scaleX:0});\n' + "\n".join(seg_js)
               + '\ntl.fromTo(R.querySelector(".glow"),{x:-120,y:-60,opacity:.75},{x:120,y:80,opacity:1,duration:%s,ease:"sine.inOut"},0);' % TOTAL)
    CAP_CSS = """
    [data-composition-id="captions"]{position:absolute;inset:0}
    .cap{position:absolute;left:40px;top:%(top)dpx;width:1000px;height:%(h)dpx;display:flex;align-items:flex-start;justify-content:center;text-align:center;opacity:0}
    .cap .zh{font-family:%(cjk)s;font-weight:800;font-size:54px;line-height:1.28;color:#fff;max-width:980px;text-wrap:balance;background:rgba(0,0,0,.58);border-radius:14px;padding:8px 22px 12px;-webkit-text-stroke:5px #000;paint-order:stroke fill}
    .cap .zh.long{font-size:48px}
    .cap .cl{display:inline-block}
    """ % dict(top=CAP_TOP, h=CAP_H, cjk=CJK)
    CAPS = sub("captions", CAP_CSS, "\n".join(caps), 'const c=R.querySelectorAll(".cap");\n' + "\n".join(caps_js))
    open(os.path.join(ROOT, "compositions/backdrop.html"), "w", encoding="utf-8").write(BACK)
    open(os.path.join(ROOT, "compositions/captions.html"), "w", encoding="utf-8").write(CAPS)

    # 背景音乐：裁到成片长度，压到人声之下，首尾淡入淡出
    bgm_tag = ""
    if bgm:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", bgm, "-t", str(TOTAL), "-af",
                        "loudnorm=I=%s:TP=-8:LRA=7,afade=t=in:d=1.2,afade=t=out:st=%.2f:d=3" % (bgm_lufs, TOTAL - 3.0),
                        "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "160k", os.path.join(ROOT, "assets/bgm.m4a")], check=True)
        bgm_tag = '<audio id="bgm" src="assets/bgm.m4a" data-start="0" data-duration="%s" data-track-index="11" data-volume="1"></audio>' % TOTAL

    INDEX = """<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=%d, height=%d">
<title>%s</title>
%s
<style>
body{margin:0;background:#0C0410}
#root{position:relative;width:100%%;height:100%%;overflow:hidden}
.slot{position:absolute;inset:0}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="%d" data-height="%d" data-duration="%s">
  <div id="el-backdrop" class="clip slot" data-composition-id="backdrop" data-composition-src="compositions/backdrop.html" data-start="0" data-duration="%s" data-track-index="0" data-width="%d" data-height="%d"></div>
  %s
  <div id="el-captions" class="clip slot" data-composition-id="captions" data-composition-src="compositions/captions.html" data-track-kind="captions" data-start="0" data-duration="%s" data-track-index="3" data-width="%d" data-height="%d"></div>
  <audio id="vo" src="assets/voice/narration.wav" data-start="0" data-duration="%s" data-track-index="10" data-volume="1"></audio>
  %s
</div>
<script>
window.__timelines["main"] = gsap.timeline({ paused: true });
</script>
</body>
</html>
""" % (W, H, TITLE_1 + " · " + TITLE_2, GSAP, W, H, TOTAL, TOTAL, W, H, "\n  ".join(slots), TOTAL, W, H, TOTAL, bgm_tag)
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(INDEX)
    print("built %d scenes, total %.2fs (%d:%04.1f)" % (len(T["frames"]), TOTAL, TOTAL // 60, TOTAL % 60))
