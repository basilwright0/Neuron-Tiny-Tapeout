"""Level 4 (docs/m2-level4-proposal.md): leak OTA root cause and candidate fixes, DC/AC characterization.

usage: python3 sim/tb/speed/tb_leak4.py <variant[,variant..]> [nproc]   (env LEAK_EL, LEAK_S, LEAK_CT)
Variants are inline subckts `lk` (ports vm el vbn vdd vss) with a 0 V sense source on the tail, so the bench reports
the real tail current at vm = EL (I_tail / Ib: < 1 means the tail nFET is pushed out of saturation), the tail node t,
the input source node s1, and the stack voltage el - t. Other metrics as tb_leak.py: g/Ib at vm = EL, lin-/lin+
(10 % compression), Isat+ (sourcing at EL - 0.5 V, % Ib), f3dB/(g/2piC) with 200 fF.
-> sim/results/level4/leak4_<variant>_EL<EL>.txt
"""
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, "/work/sim/lib")
import ngs  # noqa: E402
from ngs import deck, run, include  # noqa: E402

ngs.RESULTS = Path("/work/sim/results/level4/raw")
ngs.RESULTS.mkdir(parents=True, exist_ok=True)
OUT = Path("/work/sim/results/level4")

EL = float(os.environ.get("LEAK_EL", "1.30"))
SS = tuple(int(x) for x in os.environ.get("LEAK_S", "10,100,1000,10000").split(","))
CT = [tuple((x.split(":")[0], int(x.split(":")[1]))) for x in
      os.environ.get("LEAK_CT", "typical:27,ss:0,ff:85,sf:0,ss:27,typical:0").split(",")]


def deg(wi, li, wd, ld, wt="2u", lt="4u", wl="2u", ll="4u"):
    return f""".subckt lk vm el vbn vdd vss
XMT  tt  vbn vss vss nfet_03v3 W={wt} L={lt}
Vst  t   tt 0
XM1  a   el  s1  vss nfet_03v3 W={wi} L={li}
XD1  s1  s1  t   vss nfet_03v3 W={wd} L={ld}
XM2  vm  vm  s2  vss nfet_03v3 W={wi} L={li}
XD2  s2  s2  t   vss nfet_03v3 W={wd} L={ld}
XP1  a   a   vdd vdd pfet_03v3 W={wl} L={ll}
XP2  vm  a   vdd vdd pfet_03v3 W={wl} L={ll}
.ends lk
"""


VARIANTS = {
    "base": deg("4u", "1u", "8u", "1u"),                 # today (leak_ota_deg / _degx / _dega)
    "L05": deg("4u", "0.5u", "8u", "0.5u"),              # same W, L halved: inside today's footprints
    "in16d32": deg("16u", "1u", "32u", "1u"),            # speed-limits roadmap level 4
    "in8L05d16L05": deg("8u", "0.5u", "16u", "0.5u"),    # same gate area as today, W/L x4
    "nodeg": deg("4u", "1u", "8u", "1u").replace("XD1  s1  s1  t", "Rd1 s1 t 1\n*").replace("XD2  s2  s2  t", "Rd2 s2 t 1\n*"),
}


def pin(wi="4u", li="1u", wd="8u", ld="1u", wp="2u", lp="4u", wn="2u", ln="4u", bs=False):
    """p-input flip of leak_ota_deg: the n tail XMT (2/4 on vbn) feeds a p diode XPD; XPT mirrors Ib into the
    p-input pair + p degeneration diodes; the mirror load is n (2/4). bs: input/diode bodies at their sources."""
    b1, b2, bd1, bd2 = ("s1", "s2", "t", "t") if bs else ("vdd",) * 4
    return f""".subckt lk vm el vbn vdd vss
XMT  pb  vbn vss vss nfet_03v3 W=2u L=4u
XPD  pb  pb  vdd vdd pfet_03v3 W={wp} L={lp}
XPT  tt  pb  vdd vdd pfet_03v3 W={wp} L={lp}
Vst  tt  t 0
XM1  a   el  s1  {b1} pfet_03v3 W={wi} L={li}
XD1  s1  s1  t   {bd1} pfet_03v3 W={wd} L={ld}
XM2  vm  vm  s2  {b2} pfet_03v3 W={wi} L={li}
XD2  s2  s2  t   {bd2} pfet_03v3 W={wd} L={ld}
XN1  a   a   vss vss nfet_03v3 W={wn} L={ln}
XN2  vm  a   vss vss nfet_03v3 W={wn} L={ln}
.ends lk
"""


VARIANTS["pin"] = pin()
VARIANTS["pin_bs"] = pin(bs=True)


def variant_text(v):
    if v in VARIANTS:
        return VARIANTS[v]
    # free form: d_<wi>_<li>_<wd>_<ld>[_<wt>_<lt>]  e.g. d_4_0.5_8_0.5
    p = v.split("_")[1:]
    u = [x + "u" for x in p]
    return deg(*u)


MC = int(os.environ.get("LEAK_MC", "0"))      # > 0: mismatch Monte Carlo of the rest offset, typical 27, S = 100


def case(arg):
    v, c, t, S = arg[:4]
    hdr = dict(mismatch=True, seed=arg[4]) if len(arg) > 4 else {}
    ib = 324e-12 * S / 100
    sub = variant_text(v)
    body = f"""{include('neuron/membrane.spice')}
{sub}
Vdd vdd 0 3.3
Vel el 0 {EL}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {EL}
Xl  vm el vbn vdd 0 lk
"""
    tag = f"{v}_{c}_{t}_S{S}_EL{EL}" + (f"_mc{arg[4]}" if hdr else "")
    r = run(deck(body, f"dc Vm {EL - 0.5:.3f} {EL + 0.5:.3f} 1m",
                 ["i(vm)", "v(xl.t)", "v(xl.s1)", "i(v.xl.vst)"], corner=c, temp=t, **hdr), f"lk_{tag}")
    vm = r["_x"]
    iin = -r["i(vm)"]
    if iin[np.argmin(np.abs(vm - (EL - 0.1)))] < 0:
        iin = -iin
    k0 = np.argmin(np.abs(vm - EL))
    z = np.where(np.diff(np.sign(iin)) != 0)[0]
    voff = float(np.interp(0.0, -iin[z[0]:z[0] + 2], vm[z[0]:z[0] + 2]) - EL) * 1e3 if len(z) else float("nan")     # vm at zero OTA current (rest) - EL, mV
    g = -np.gradient(iin, vm)[k0]
    dv = vm - EL
    ilin = -g * dv
    lo = [k for k in range(k0 - 5, -1, -1) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
    hi = [k for k in range(k0 + 5, len(vm)) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
    if hdr:
        return dict(v=v, seed=arg[4], voff=voff)
    body2 = body.replace(f"Vm  vm 0 {EL}", "Cm vm 0 200f").replace(f"Vel el 0 {EL}", f"Vel el 0 dc {EL} ac 1")
    ra = run(deck(body2, "ac dec 40 1e1 1e9", ["vm(vm)"], corner=c, temp=t), f"lkac_{tag}")
    f, a = ra["_x"], ra["vm(vm)"]
    f3 = float(f[np.where(a < a[0] / np.sqrt(2))[0][0]])
    itail = abs(float(r["i(v.xl.vst)"][k0]))
    return dict(voff=voff, v=v, c=c, t=t, S=S, ib=ib, gib=g / ib, lm=-dv[lo[0]] * 1e3 if lo else float("nan"),
                lp=dv[hi[0]] * 1e3 if hi else float("nan"), sp=100 * iin[0] / ib, sn=-100 * iin[-1] / ib,
                tv=float(r["v(xl.t)"][k0]), s1=float(r["v(xl.s1)"][k0]), itail=itail / ib,
                f3_ratio=f3 / (g / (2 * np.pi * 200e-15)), g=g)


if __name__ == "__main__":
    vs = sys.argv[1].split(",")
    NP = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if MC:
        with Pool(NP) as p:
            res = p.map(case, [(v, "typical", 27, 100, k + 1) for v in vs for k in range(MC)])
        L = [f"leak OTA rest offset (vm at I = 0) - EL, mismatch MC, typical 27, S = 100, EL = {EL}, {MC} seeds (tb_leak4.py)"]
        for v in vs:
            o = np.array([r["voff"] for r in res if r["v"] == v])
            L.append(f" {v:16s} mean {o.mean():+6.2f} mV  sigma {o.std(ddof=1):5.2f} mV  min {o.min():+6.2f}  max {o.max():+6.2f}")
        print("\n".join(L))
        (OUT / f"leak4_mc_EL{EL:.2f}.txt").write_text("\n".join(L) + "\n")
        sys.exit(0)
    cases = [(v, c, t, S) for v in vs for S in SS for (c, t) in CT]
    with Pool(NP) as p:
        res = p.map(case, cases)
    for v in vs:
        rs = [r for r in res if r["v"] == v]
        L = [f"leak OTA variant {v} at EL = {EL} V, Ib = 324 pA x S/100 (tb_leak4.py); pass: g/Ib >= 5, lin >= 75 mV, Isat+ >= 90 %",
             "     S  corner   T  g/Ib(S/A) lin-(mV) lin+(mV) Isat+(%Ib) Isat-(%Ib) Itail/Ib  t(V)   s1(V)  el-t(V) f3/(g/2piC) g/g(S100) off(mV)  pass"]
        for r in rs:
            ok = r["gib"] >= 5 and r["lm"] >= 75 and r["lp"] >= 75 and r["sp"] >= 90
            b = [x for x in rs if x["c"] == r["c"] and x["t"] == r["t"] and x["S"] == 100]
            gn = (r["g"] / r["S"]) / (b[0]["g"] / 100) if b else float("nan")
            L.append(f" {r['S']:5d}  {r['c']:7s} {r['t']:3d}   {r['gib']:6.2f}   {r['lm']:6.0f}   {r['lp']:6.0f}"
                     f"    {r['sp']:6.0f}     {r['sn']:6.0f}    {r['itail']:6.3f}  {r['tv']:.3f}  {r['s1']:.3f}  {EL - r['tv']:.3f}"
                     f"   {r['f3_ratio']:5.2f}     {gn:5.3f}  {r['voff']:+6.2f}   {'yes' if ok else 'NO'}")
        txt = "\n".join(L)
        print(txt)
        (OUT / f"leak4_{v}_EL{EL:.2f}.txt").write_text(txt + "\n")
