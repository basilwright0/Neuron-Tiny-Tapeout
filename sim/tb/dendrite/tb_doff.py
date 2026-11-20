"""Whole D1 (dend_d1) with all biases off (BIAS_EN = 0): outputs must be clean and supply current ~ leakage.

usage: python3 sim/tb/dendrite/tb_doff.py      -> sim/results/dendrite/doff_summary.txt
As sim/tb/tb_slot_detoff.py: vdd ramps 0 -> 3.3 V in 20 us, 1 ms transient. All bias currents 0 (n-masters at 0 V);
vbp_st / vbp_syn either unpowered 2/4 / 1/2 p-master diodes or tied to 3.3 V; el = vsrc = vsrcp = vreset = 0;
all digital inputs 0 (trim codes 0). 5 corners x 0/27/85 C. Reports soma spk, both plateau-detector outputs xb,
and Idd at the end.
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

L = [__doc__.strip().splitlines()[0], "corner  T  vbp      spk(mV)  xb1(mV)  xb2(mV)  pb1(V)  Idd(nA)"]
worst = [0.0, 0.0]
for c in CORNERS:
    for t in TEMPS:
        for vbs in ("diode", "3v3"):
            pb = ("Xbs vbs vdd pmaster w=1u l=2u\nXbp vbp vdd pmaster w=2u l=4u" if vbs == "diode"
                  else "Vbs vbs 0 3.3\nVbp vbp 0 3.3")
            body = f"""{cells()}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vel el 0 0
Vrs vrst 0 0
Vsr vsrc 0 0
Vsp vsrcp 0 0
Xbl vbl 0 nmaster
Xba vba 0 nmaster
Xbr vbr 0 nmaster
{pb}
Vpr vpr 0 0
Ven en 0 0
Vs0 sel0 0 0
Vs1 sel1 0 0
Vs2 sel2 0 0
Vab abus 0 0
Vpl plen 0 0
Vch chain 0 0
Vbsel bsel 0 0
Vhold hold 0 0
Vmrst mreset 0 0
Vta ta 0 0
Vsta sta 0 0
Vstb stb 0 0
XD vs d1 d2 spk sel0 sel1 sel2 plen chain bsel sta stb hold mreset vsy 0 0 0 ta 0 0 0 ta el vsrc vsrcp vrst vbl vbs vbr vpr vba en abus vdd 0 dend_d1
"""
            r = run(deck(body, "tran 1u 1m", ["v(spk)", "v(xd.xp1.xb)", "v(xd.xp2.xb)", "v(xd.xp1.xdt.pb)", "i(vdd)", "v(d1)", "v(d2)", "v(xd.xp1.xdt.p)", "v(xd.xp1.xdt.n1)", "v(xd.xp1.xdt.h)", "v(vs)"],
                         corner=c, temp=t), f"dendrite/doff_{c}_{t}_{vbs}")
            spk, x1, x2, p1 = (float(r[k][-1]) for k in ("v(spk)", "v(xd.xp1.xb)", "v(xd.xp2.xb)", "v(xd.xp1.xdt.pb)"))
            idd = float(-r["i(vdd)"][-1])
            worst = [max(worst[0], spk, x1, x2), max(worst[1], idd)]
            L.append(f"{c:7s} {t:3d} {vbs:5s}  {spk*1e3:7.1f}  {x1*1e3:7.1f}  {x2*1e3:7.1f}  {p1:6.3f}  {idd*1e9:7.2f}")
            print(L[-1], flush=True)
L.append(f"worst output {worst[0]*1e3:.1f} mV, worst Idd {worst[1]*1e9:.2f} nA")
print(L[-1])
(OUT / "doff_summary.txt").write_text("\n".join(L) + "\n")
