"""Leak OTA of the slots (leak_ota_deg as now in cells/neuron/membrane.spice, defaults = the cell) at EL = 1.30 V.

usage: python3 sim/tb/tb_slot_leak.py        -> sim/results/leak/slot_leak_summary.txt
Same metrics as sim/tb/dendrite/tb_leak_lin.py (D1 track): g = small-signal at vm = el; linear range = |dV| at which
the current falls 10 % below g dV (lin- below el, OTA sourcing; lin+ above); Isat+ = current sourced at el - 0.5 V,
Isat- = sunk at el + 0.5 V (% of Ib); t = tail node voltage (headroom). All 5 corners x 0/27/85 C at
S = 100 (Ib = 324 pA) and S = 1000 (3.24 nA). Pass: g/Ib >= 5 S/A, lin- and lin+ >= 75 mV, Isat+ >= 90 %.
"""
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, RESULTS, CORNERS, TEMPS   # noqa: E402

EL = float(__import__("os").environ.get("LEAK_EL", "1.30"))
OUT = RESULTS / "leak"


def case(arg):
    c, t, ib = arg
    body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {EL}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {EL}
Xl  vm el vbn vdd 0 leak_ota_deg
"""
    r = run(deck(body, f"dc Vm {EL - 0.5:.3f} {EL + 0.5:.3f} 1m", ["i(vm)", "v(xl.t)"], corner=c, temp=t),
            f"leak/slotleak_{c}_{t}_{ib * 1e12:.0f}")
    vm = r["_x"]
    iin = -r["i(vm)"]
    if iin[np.argmin(np.abs(vm - (EL - 0.1)))] < 0:
        iin = -iin
    k0 = np.argmin(np.abs(vm - EL))
    g = -np.gradient(iin, vm)[k0]
    dv = vm - EL
    ilin = -g * dv
    lo = [k for k in range(k0 - 5, -1, -1) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
    hi = [k for k in range(k0 + 5, len(vm)) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
    return dict(c=c, t=t, ib=ib, gib=g / ib, lm=-dv[lo[0]] * 1e3 if lo else float("nan"),
                lp=dv[hi[0]] * 1e3 if hi else float("nan"), sp=100 * iin[0] / ib, sn=-100 * iin[-1] / ib,
                tv=float(r["v(xl.t)"][k0]))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [(c, t, ib) for ib in (324e-12, 3.24e-9) for c in CORNERS for t in TEMPS]
    with Pool(6) as p:
        res = p.map(case, cases)
    L = [f"leak_ota_deg (in 4/1, dio 8/1, tail 2/4) at EL = {EL} V; pass: g/Ib >= 5, lin >= 75 mV, Isat+ >= 90 %",
         " S      corner   T   g/Ib(S/A) lin-(mV) lin+(mV) Isat+(%Ib) Isat-(%Ib)  t(V)  pass"]
    for r in res:
        ok = r["gib"] >= 5 and r["lm"] >= 75 and r["lp"] >= 75 and r["sp"] >= 90
        L.append(f" {r['ib'] / 3.24e-12:5.0f}  {r['c']:7s} {r['t']:3d}   {r['gib']:6.2f}   {r['lm']:6.0f}   {r['lp']:6.0f}"
                 f"    {r['sp']:6.0f}     {r['sn']:6.0f}    {r['tv']:.3f}  {'yes' if ok else 'NO'}")
    for S in (100, 1000):
        rs = [r for r in res if abs(r["ib"] / 3.24e-12 - S) < 1]
        L.append(f"S = {S}: min g/Ib {min(r['gib'] for r in rs):.2f}, min lin {min(min(r['lm'], r['lp']) for r in rs):.0f} mV, "
                 f"min Isat+ {min(r['sp'] for r in rs):.0f} %, g/Ib typical 27 C {[r['gib'] for r in rs if r['c'] == 'typical' and r['t'] == 27][0]:.2f}")
    txt = "\n".join(L)
    print(txt)
    (OUT / "slot_leak_summary.txt").write_text(txt + "\n")
