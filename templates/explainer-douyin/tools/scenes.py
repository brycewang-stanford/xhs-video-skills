# -*- coding: utf-8 -*-
"""各幕画面（示例三幕，照着改）。每幕 = dict(html=舞台内的 HTML/SVG, js=按口播下标对时的动画)。
舞台是 984×810 的盒子；at(i, f) = 第 i 句口播念到 f（0–1）处的时刻。可用的动画助手见 kit.py 的 KIT。
用法: python tools/voice.py && python tools/scenes.py && npx hyperframes check"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 01 钩子：描一条阶梯线 + 大问号
S01 = dict(html=svg(
    '<path class="ax" d="M80,24 V344 H924"/>'
    + path("st", "M84,286 H430 V118 H900", BLUE, 9) + txt("stl", 100, 262, "利率", 34, BLUE))
    + '<div class="big y abs" data-k="qm" style="left:640px;top:140px;font-size:190px">?</div>'
    + '<div class="big ctr" data-k="line" style="top:560px"><span class="mk" data-k="linemk">先看<span class="y">一张图</span></span></div>',
 js="""
draw("st",at(0,.05),1.1);fade("stl",at(0,.05));pop("qm",at(0,.7));
rise("line",at(1,.1));mark("linemk",at(1,.5),.6);
""")

# 02 出处：真实截图做成斜放的卡片先亮相，再让位给公式
S02 = dict(html=
    '<div class="abs" data-k="intro" style="inset:0">'
    + shot("a", "sample-page", 0, 16, 620, 329, -2, "来源页面 · 截图") + "</div>"
    + '<div class="eq" data-k="eq" style="left:0;width:984px;text-align:center;top:300px;font-size:84px">'
    + M(HL(E + "[ c<sub>t+1</sub> ]", "lhs") + " = " + HL("c<sub>t</sub>", "rhs")) + "</div>"
    + '<div class="note" data-k="l1" style="left:196px;top:414px">对明天的预测</div><div class="note" data-k="l2" style="left:640px;top:414px">今天</div>',
 js="""
pop("a",at(0,.02),{rotation:-2});out("intro",at(1,0)-.25,.25);
rise("eq",at(1,.1));glow("lhs",at(1,.3));fade("l1",at(1,.3));glow("rhs",at(1,.6));fade("l2",at(1,.6));
""")

# 03 收尾：描一条曲线 + 一句结论 + 去处
curve = [(100 + i * 8, 420 - 260 * (1 - math.exp(-i / 22.0))) for i in range(101)]
S03 = dict(html=svg('<path class="ax" d="M90,120 V440 H930"/>' + path("cv", poly(curve), YEL, 8))
    + '<div class="big ctr" data-k="res" style="top:520px;font-size:66px"><span class="mk" data-k="resmk">一句话<span class="y">结论</span></span></div>'
    + '<div class="abs ctr" data-k="more" style="top:680px;font-size:38px;font-weight:800">完整文章 <span class="y">→ 见图文</span></div>',
 js="""
draw("cv",at(0,.1),1.5);rise("res",at(0,.6));mark("resmk",at(0,.9),.6);rise("more",at(1,.1));
""", exit="")

SCENES = {"01-hook": S01, "02-source": S02, "03-outro": S03}

if __name__ == "__main__":
    build(ROOT, SCENES,
          title=("一行大标题写主题", "第二行直接写结论"),          # 结论，不是问句
          subs=("要点一：一句话说清", "要点二：一句话说清"),
          bgm=None)                                             # 例：bgm="/path/to/music.mp3"
