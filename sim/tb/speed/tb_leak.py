"""Speed track: leak_ota_deg (cells/neuron/membrane.spice, as in every slot) vs S (Ib = 324 pA * S/100).

usage: python3 sim/tb/speed/tb_leak.py [nproc]  -> sim/results/speed/leak_summary.txt
Metrics as sim/tb/tb_slot_leak.py: g/Ib (small-signal at vm = EL), lin-/lin+ (|dV| where the current
falls 10 % below g dV), Isat+ (sourced at EL - 0.5 V, % Ib), tail headroom t. Pass: g/Ib >= 5 S/A,
lin >= 75 mV, Isat+ >= 90 %. Also the follower bandwidth: small-signal pole g/C vs the expected 1/tau
(should be 1: the OTA itself must not add a second pole near 1/tau) from an AC run with 200 fF on vm.
"""
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
from ngs import deck, run, include, CORNERS, TEMPS  # noqa: E402

import os
EL = float(os.environ.get("LEAK_EL", "1.30"))
SS = tuple(int(x) for x in os.environ.get("LEAK_S", "100,300,1000,3000,10000").split(","))


def case(arg):
    c, t, S = arg
    ib = 324e-12 * S / 100
    body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {EL}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {EL}
Xl  vm el vbn vdd 0 leak_ota_deg
"""
    r = run(deck(body, f"dc Vm {EL - 0.5:.3f} {EL + 0.5:.3f} 1m", ["i(vm)", "v(xl.t)"], corner=c, temp=t),
            f"leak_{c}_{t}_S{S}_EL{EL}")
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
    # AC: el driven, vm loaded by 200 fF: -3 dB frequency vs g/(2 pi C)
    body2 = body.replace(f"Vm  vm 0 {EL}", "Cm vm 0 200f").replace(f"Vel el 0 {EL}", f"Vel el 0 dc {EL} ac 1")
    ra = run(deck(body2, "ac dec 40 1e2 1e9", ["vm(vm)"], corner=c, temp=t), f"leakac_{c}_{t}_S{S}_EL{EL}")
    f, a = ra["_x"], ra["vm(vm)"]
    f3 = float(f[np.where(a < a[0] / np.sqrt(2))[0][0]])
    fexp = g / (2 * np.pi * 200e-15)
    return dict(c=c, t=t, S=S, ib=ib, gib=g / ib, lm=-dv[lo[0]] * 1e3 if lo else float("nan"),
                lp=dv[hi[0]] * 1e3 if hi else float("nan"), sp=100 * iin[0] / ib, sn=-100 * iin[-1] / ib,
                tv=float(r["v(xl.t)"][k0]), f3_ratio=f3 / fexp, a0=float(a[0]))


if __name__ == "__main__":
    NP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    cases = [(c, t, S) for S in SS for c in CORNERS for t in TEMPS]
    with Pool(NP) as p:
        res = p.map(case, cases)
    L = [f"leak_ota_deg (in 4/1, dio 8/1, tail 2/4) at EL = {EL} V, Ib = 324 pA x S/100; "
         "pass: g/Ib >= 5, lin >= 75 mV, Isat+ >= 90 %",
         "     S  corner   T  g/Ib(S/A) lin-(mV) lin+(mV) Isat+(%Ib) Isat-(%Ib)  t(V)  f3dB/(g/2piC) A0   pass"]
    for r in res:
        ok = r["gib"] >= 5 and r["lm"] >= 75 and r["lp"] >= 75 and r["sp"] >= 90
        L.append(f" {r['S']:5d}  {r['c']:7s} {r['t']:3d}   {r['gib']:6.2f}   {r['lm']:6.0f}   {r['lp']:6.0f}"
                 f"    {r['sp']:6.0f}     {r['sn']:6.0f}    {r['tv']:.3f}   {r['f3_ratio']:5.2f}   {r['a0']:.3f}  {'yes' if ok else 'NO'}")
    for S in SS:
        rs = [r for r in res if r["S"] == S]
        bad = [f"{r['c']}/{r['t']}" for r in rs if not (r["gib"] >= 5 and r["lm"] >= 75 and r["lp"] >= 75 and r["sp"] >= 90)]
        typ = [r for r in rs if r["c"] == "typical" and r["t"] == 27][0]
        L.append(f"S = {S}: min g/Ib {min(r['gib'] for r in rs):.2f}, min lin {min(min(r['lm'], r['lp']) for r in rs):.0f} mV, "
                 f"min Isat+ {min(r['sp'] for r in rs):.0f} %, typ g/Ib {typ['gib']:.2f}, min f3/(g/2piC) "
                 f"{min(r['f3_ratio'] for r in rs):.2f}; fails: {', '.join(bad) or 'none'}")
    txt = "\n".join(L)
    print(txt)
    (RESULTS / ("leak_summary.txt" if EL == 1.30 else f"leak_summary_EL{EL}.txt")).write_text(txt + "\n")
