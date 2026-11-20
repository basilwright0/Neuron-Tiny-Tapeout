"""pdet reset pull-up XQ (pfet vdd -> pb, gate p): sizing. Per-crossing vsrc charge in normal operation
(as tb_pdet_q.py, vd ramp EL -> EL+0.4 V in 20 us and back) and the bias-off state at the corners where the
keeper alone fails (as tb_pdet_off.py).
usage: python3 sim/tb/dendrite/tb_pdet_kq.py
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

src = open("/work/cells/dendrite/dendrite.spice").read()
i0 = src.index(".subckt pdet ")
BASE = src[i0:src.index(".ends pdet", i0) + len(".ends pdet")]
BASE = "\n".join(l for l in BASE.splitlines() if not l.startswith("XQ "))
VAR = {"k1": "", "kq4": "XQ  pb  p   vdd vdd pfet_03v3 W=0.22u L=4u", "kq10": "XQ  pb  p   vdd vdd pfet_03v3 W=0.22u L=10u"}


def sub(v):
    return BASE.replace(".subckt pdet ", f".subckt pdet_{v} ").replace(".ends pdet", f"{VAR[v]}\n.ends pdet_{v}")


subs = "\n".join(sub(v) for v in VAR)
for c, t in (("typical", 27), ("ff", 0), ("ss", 0), ("ff", 85)):
    vs = cal_vsrc(c, t)
    for v in VAR:
        body = f"""{include('neuron/membrane.spice')}
{subs}
Vdd vdd 0 3.3
Vsr vsrc 0 {vs}
Ibs vbs 0 100n
Xbs vbs vdd pmaster w=1u l=2u
Vd vd 0 pwl(0 {EL} 5u {EL} 25u {EL+0.4} 45u {EL})
X1 vd xb vsrc vbs vdd 0 pdet_{v}
"""
        r = run(deck(body, "tran 2n 50u", ["i(vsr)", "i(vdd)", "v(xb)"], corner=c, temp=t), f"dendrite/pdkq_{v}_{c}_{t}")
        tt, i = r["_x"], np.abs(r["i(vsr)"])
        up = crossings(tt, r["v(xb)"], 1.65)
        print(f"[{c}_{t}] {v:5s}: vsrc charge {np.trapezoid(i, tt)*1e12:6.2f} pC, peak {i.max()*1e6:6.2f} uA, "
              f"vdd charge {np.trapezoid(np.abs(r['i(vdd)']), tt)*1e12:6.2f} pC, trip at vd = "
              f"{(np.interp(up[0], tt, np.interp(tt, [0, 5e-6, 25e-6], [EL, EL, EL + 0.4])) - EL)*1e3 if len(up) else float('nan'):.1f} mV>EL",
              flush=True)
for c, t in (("ss", 0), ("ss", 27), ("sf", 0)):
    for v in ("kq4", "kq10"):
        for vd in (0.0, 0.1):
            body = f"""{include('neuron/membrane.spice')}
{subs}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vsr vsrc 0 0
Vbs vbs 0 3.3
Vd vd 0 {vd}
X1 vd xb vsrc vbs vdd 0 pdet_{v}
"""
            r = run(deck(body, "tran 1u 1m", ["v(xb)", "i(vdd)"], corner=c, temp=t), f"dendrite/pdkqoff_{v}_{c}_{t}")
            print(f"[off {c}_{t}] {v:5s} vd={vd}: xb {r['v(xb)'][-1]*1e3:.1f} mV, Idd {-r['i(vdd)'][-1]*1e9:.2f} nA", flush=True)
