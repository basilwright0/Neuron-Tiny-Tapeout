"""EL trim cell trim_el4 (cells/trim/trim_el.spice): aux - el vs code, corners / temperatures / speeds,
plus mismatch (40 instances, typical 27 C, S = 100).

usage: python3 sim/tb/trim/tb_trim_el.py [quick]
Load: the P slot's leak OTA input gate (W/L 2/2) + 50 fF of line. Writes sim/results/trim/trim_el_summary.txt.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slotbench as sb                       # noqa: E402
from ngs import deck, run, include, RESULTS  # noqa: E402

OUT = RESULTS / "trim"
DEC = "\n".join(f"Bb{k} b{k} 0 V = 3.3*(floor(v(code)/{2**k}+0.01) - 2*floor(v(code)/{2**(k+1)}+0.01))"
                for k in range(4))


def body(b, el=sb.EL, vb=None):
    bias = f"Ibl vdd vbl {b.ib}\nXbl vbl 0 nmaster" if vb is None else f"Vbl vbl 0 {vb}"
    return f"""{include('neuron/membrane.spice', 'trim/trim_el.spice')}
Vdd vdd 0 3.3
Vel el 0 {el}
{bias}
Vcode code 0 0
{DEC}
XE aux el vbl b0 b1 b2 b3 vdd 0 trim_el4
XG 0 aux 0 0 nfet_03v3 W=2u L=2u
Cl aux 0 50f
"""


def case(arg):
    corner, temp, S = arg
    b = sb.Bias(S)
    r = run(deck(body(b), "dc Vcode 0 15 1", ["v(aux)"], corner=corner, temp=temp),
            f"trim/el_{corner}_{temp}_S{S:g}")
    d = (r["v(aux)"] - sb.EL) * 1e3
    st = np.diff(d)
    # el compliance: offset at code 8 for el = 1.0 / 1.4 V
    comp = []
    for el in (1.0, 1.4):
        rr = run(deck(body(b, el), "dc Vcode 8 8 1", ["v(aux)"], corner=corner, temp=temp),
                 f"trim/el_{corner}_{temp}_S{S:g}_el{el}")
        comp.append(float((rr["v(aux)"][0] - el) * 1e3))
    return dict(corner=corner, temp=temp, S=S, d=d.tolist(), lo=float(d[0]), hi=float(d[-1]),
                mid=float((d[7] + d[8]) / 2), step=float(st.mean()), smin=float(st.min()), smax=float(st.max()),
                comp=comp)


def mc(seed):
    b = sb.Bias(100.0)
    vb = float(np.loadtxt(OUT / "el_vbl.txt"))
    r = run(deck(body(b, vb=vb), "dc Vcode 0 15 1", ["v(aux)"], mismatch=True, seed=seed), f"trim/elmc_s{seed}")
    return ((r["v(aux)"] - sb.EL) * 1e3).tolist()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quick = "quick" in sys.argv
    cases = [("typical", 27, 100.0)] if quick else \
        [(c, t, 100.0) for c in ("typical", "ff", "ss", "fs", "sf") for t in (0, 27, 85)] + \
        [("typical", 27, 10.0), ("typical", 27, 1000.0)]
    vbl = sb.bias_voltages(sb.Bias(100.0), tag="el")["vbl"]
    (OUT / "el_vbl.txt").write_text(f"{vbl}\n")
    with Pool(3) as p:
        res = p.map(case, cases)
        m = np.array(p.map(mc, range(1, 6 if quick else 41)))
    (OUT / "trim_el_cases.json").write_text(json.dumps(dict(cases=res, mc=m.tolist()), indent=1))
    L = ["EL trim trim_el4: aux - el (mV) vs code (follower on vbn_leak; load 2/2 gate + 50 fF)",
         " corner   T     S   code0   code15   mid   step mean [min,max]   offset@code8 for el=1.0/1.4 V"]
    for r in res:
        L.append(f" {r['corner']:7s} {r['temp']:3d} {r['S']:5g} {r['lo']:7.2f} {r['hi']:7.2f} {r['mid']:6.2f}  "
                 f"{r['step']:5.2f} [{r['smin']:5.2f},{r['smax']:5.2f}]     {r['comp'][0]:6.2f} / {r['comp'][1]:6.2f}")
    st = np.diff(m, axis=1)
    L.append(f"mismatch ({len(m)} instances, typical 27 C, S=100): offset at code 8 sigma {m[:, 8].std():.2f} mV; "
             f"step sigma {st.std():.2f} mV; worst step {st.min():.2f}..{st.max():.2f} mV; "
             f"non-monotonic instances {int((st < 0).any(axis=1).sum())}")
    txt = "\n".join(L)
    print(txt)
    (OUT / "trim_el_summary.txt").write_text(txt + "\n")
