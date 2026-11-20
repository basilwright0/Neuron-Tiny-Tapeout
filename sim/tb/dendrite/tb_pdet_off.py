"""Plateau detector pdet with all biases off: candidate reset fixes, standalone (fast).

usage: python3 sim/tb/dendrite/tb_pdet_off.py [variant ...]
vdd ramps 0 -> 3.3 V in 20 us, 1 ms; vsrc = 0; vbp_st = unpowered 1/2 p-master diode or 3.3 V;
vd in {0, 0.1, 1.4} V. 5 corners x 0/27/85 C. Variants (stage-3 node pb):
  k1: keeper XK (pfet vdd -> pb, gate xb, 0.22/1)          [= det_ah's fix; current dendrite.spice]
  kq: k1 + XQ weak unstarved pull-up (pfet vdd -> pb, gate p, 0.22/4)
  kw: k1 + XW leaker (pfet vdd -> pb, gate vdd, 2/0.28)
"""
import sys
from multiprocessing import Pool
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

src = open("/work/cells/dendrite/dendrite.spice").read()
i0 = src.index(".subckt pdet ")
BASE = src[i0:src.index(".ends pdet", i0) + len(".ends pdet")]
EXTRA = {"k1": "", "kq": "XQ  pb  p   vdd vdd pfet_03v3 W=0.22u L=4u",
         "kw": "XW  pb  vdd vdd vdd pfet_03v3 W=2u L=0.28u"}


def subckt(v):
    return BASE.replace(".subckt pdet ", f".subckt pdet_{v} ").replace(".ends pdet", f"{EXTRA[v]}\n.ends pdet_{v}")


def case(a):
    v, c, t, vbs, vd = a
    body = f"""{include('neuron/membrane.spice')}
{subckt(v)}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vsr vsrc 0 0
{"Xbs vbs vdd pmaster w=1u l=2u" if vbs == "diode" else "Vbs vbs 0 3.3"}
Vd vd 0 {vd}
X1 vd xb vsrc vbs vdd 0 pdet_{v}
"""
    r = run(deck(body, "tran 1u 1m", ["v(xb)", "v(x1.pb)", "v(x1.p)", "i(vdd)"], corner=c, temp=t),
            f"dendrite/pdoff_{v}_{c}_{t}_{vbs}_{vd}")
    return dict(v=v, c=c, t=t, vbs=vbs, vd=vd, xb=float(r["v(xb)"][-1]), pb=float(r["v(x1.pb)"][-1]),
                p=float(r["v(x1.p)"][-1]), idd=float(-r["i(vdd)"][-1]))


if __name__ == "__main__":
    vs = sys.argv[1:] or ["k1", "kq", "kw"]
    cases = [(v, c, t, b, d) for v in vs for c in CORNERS for t in TEMPS for b in ("diode", "3v3") for d in (0.0, 0.1, 1.4)]
    with Pool(1) as p:
        res = p.map(case, cases)
    for v in vs:
        rs = [r for r in res if r["v"] == v]
        lo = [r for r in rs if r["vd"] < 1]
        print(f"== {v}: vd low: worst xb {max(r['xb'] for r in lo)*1e3:.1f} mV, worst Idd {max(r['idd'] for r in rs)*1e9:.2f} nA;"
              f" vd 1.4: xb {min(r['xb'] for r in rs if r['vd'] > 1):.2f}..{max(r['xb'] for r in rs if r['vd'] > 1):.2f} V")
        for r in rs:
            if (r["vd"] < 1 and r["xb"] > 0.05) or r["idd"] > 1e-9:
                print(f"   {r['c']:7s} {r['t']:3d} {r['vbs']:5s} vd={r['vd']}: xb {r['xb']:.3f} pb {r['pb']:.3f} p {r['p']:.3f} "
                      f"Idd {r['idd']*1e9:.2f} nA")
