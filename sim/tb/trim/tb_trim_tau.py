"""Leak-tau trim cell trim_tau4 (cells/trim/trim_tau.spice) driving the P column's aux line.

usage: python3 sim/tb/trim/tb_trim_tau.py [quick]
  gain  I_tail(P)/I_ref vs code (DC), corners x 0/27/85 C at S = 100, plus S = 10 / 1000;
        I_tail = current of a slot tail copy (W/L 2/4, drain at 0.6 V) on aux; I_ref = leak IDAC current
        into B1's trim_ref_n (16 units on vsn = 0.30 V), i.e. the current of the vbn_leak master.
  load  4 P-slot gate loads on aux (tail 2/4 + 9 ladder devices 0.5/1.5..0.5/4 each) + 100 fF of line.
  settle  code 0 <-> 15 steps at S = 10 (I_ref = 32 pA), 27 and 85 C: time for I_tail to reach 1 %.
  leak  85 C: current into aux from everything hanging on it: the 4 slot loads, the line and the
        mirror output's drain junction (XPM held off), aux held at its operating voltage, vs the master current at code 0, S = 10.
Writes sim/results/trim/trim_tau_summary.txt.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slotbench as sb                        # noqa: E402
from ngs import deck, run, include, RESULTS   # noqa: E402

OUT = RESULTS / "trim"
DEC = "\n".join(f"Bb{k} b{k} 0 V = 3.3*(floor(v(code)/{2**k}+0.01) - 2*floor(v(code)/{2**(k+1)}+0.01))"
                for k in range(4))
LOAD = "\n".join(f"""XT{i} dt{i} aux 0 0 nfet_03v3 W=2u L=4u
XLa{i} dl{i} aux 0 0 nfet_03v3 W=0.5u L=4u m=2
XLb{i} dl{i} aux 0 0 nfet_03v3 W=0.5u L=3u m=4
XLc{i} dl{i} aux 0 0 nfet_03v3 W=0.5u L=1.5u m=3
Vdt{i} dt{i} 0 0.6
Vdl{i} dl{i} 0 0.9""" for i in range(4)) + "\nCline aux 0 100f"


def body(iref, code_src="Vcode code 0 0", diode=True, bits=None):
    return f"""{include('bias/bias_trim.spice', 'trim/trim_tau.spice')}
Vdd vdd 0 3.3
Vsn vsn 0 0.30
Iref vdd vg {iref}
XR vg vsn 0 trim_ref_n
{code_src if bits is None else ""}
{DEC if bits is None else bits}
{"XC aux vg vsn b0 b1 b2 b3 vdd 0 trim_tau4" if diode else ""}
{LOAD}
"""


def case(arg):
    corner, temp, S = arg
    b = sb.Bias(S)
    r = run(deck(body(b.ib), "dc Vcode 0 15 1", ["i(Vdt0)", "v(aux)"], corner=corner, temp=temp),
            f"trim/tau_{corner}_{temp}_S{S:g}")
    g = -r["i(vdt0)"] / b.ib
    return dict(corner=corner, temp=temp, S=S, gain=g.tolist(), aux=r["v(aux)"].tolist())


def settle(temp):
    b = sb.Bias(10.0)
    T = 40e-3
    bits = chr(10).join(f"Vb{k} b{k} 0 PWL(0 0 {T} 0 {T + 1e-6} 3.3 {2 * T} 3.3 {2 * T + 1e-6} 0)" for k in range(4))
    r = run(deck(body(b.ib, bits=bits), f"tran 20u {3 * T}", ["i(Vdt0)"], temp=temp), f"trim/tau_settle_{temp}")
    t, i = r["_x"], -r["i(vdt0)"]
    out = {}
    for nm, t0, t1 in (("up", T, 2 * T), ("down", 2 * T, 3 * T)):
        m = (t > t0) & (t < t1)
        fin = i[m][-1]
        bad = np.where(np.abs(i[m] / fin - 1) > 0.01)[0]
        out[nm] = float(t[m][bad[-1]] - t0) if len(bad) else 0.0
    return temp, out


def leak():
    b = sb.Bias(10.0)
    r = run(deck(body(b.ib), "dc Vcode 0 0 1", ["v(aux)"], temp=85), "trim/tau_auxv")
    va = float(r["v(aux)"][0])
    # everything on aux except the diode XND: replace the cell by its pfet mirror only, trim off (vg -> vsn)
    bod = f"""{include('bias/bias_trim.spice')}
Vdd vdd 0 3.3
XPM aux vdd vdd vdd pfet_03v3 W=0.84u L=2u
{LOAD}
Vaux aux 0 {va}
"""
    r = run(deck(bod, "dc Vaux 0 3.3 0.1", ["i(Vaux)"], temp=85), "trim/tau_leak")
    k = int(round(va / 0.1))
    return va, float(r["i(vaux)"][k]), 0.5 * b.ib


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quick = "quick" in sys.argv
    cases = [("typical", 27, 100.0)] if quick else \
        [(c, t, 100.0) for c in ("typical", "ff", "ss", "fs", "sf") for t in (0, 27, 85)] + \
        [("typical", 27, 10.0), ("typical", 27, 1000.0), ("ss", 85, 10.0)]
    with Pool(int(__import__("os").environ.get("TAU_POOL", "2"))) as p:
        res = p.map(case, cases)
        st = dict(p.map(settle, (27, 85)))
    va, il, im = leak()
    (OUT / "trim_tau_cases.json").write_text(json.dumps(dict(cases=res, settle=st), indent=1))
    L = ["tau trim trim_tau4: P tail current / I_ref vs code (ideal 0.5 + c/16); 4 slot gate loads on aux",
         " corner   T     S   code0   code8   code15   max |err vs ideal|   monotonic"]
    for r in res:
        g = np.array(r["gain"])
        ideal = (8 + np.arange(16)) / 16
        L.append(f" {r['corner']:7s} {r['temp']:3d} {r['S']:5g}  {g[0]:.3f}   {g[8]:.3f}   {g[15]:.3f}      "
                 f"{np.max(np.abs(g / ideal - 1)) * 100:5.1f} %          {bool(np.all(np.diff(g) > 0))}")
    for t, s in st.items():
        L.append(f"settling at S=10 (I_ref 32 pA), {t} C, code 0->15: {s['up'] * 1e3:.2f} ms, 15->0: {s['down'] * 1e3:.2f} ms (to 1 %)")
    L.append(f"85 C leakage into aux (4 slot loads + line + mirror drain junction, aux at {va:.3f} V): {il * 1e15:.1f} fA vs master current "
             f"at code 0, S=10: {im * 1e12:.1f} pA (ratio {abs(il) / im:.1e})")
    txt = "\n".join(L)
    print(txt)
    (OUT / "trim_tau_summary.txt").write_text(txt + "\n")
