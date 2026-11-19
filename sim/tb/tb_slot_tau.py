"""F slot (slot_ah_f, leak tail W/L 1/4) vs S slot (slot_ah, 2/4) on the same vbn_leak line: tau_F / tau_S.

usage: python3 sim/tb/tb_slot_tau.py [N_mc]          (default N_mc = 200)
Per case one deck holds an S and an F slot (schematic, cells/neuron/slot.spice) with vm forced by a DC
sweep (EL +- 0.3 V, vsrc = 1.6 V so the AH detector never trips, hold = 0 so the leak OTA output reaches vm through XHL; synapse, probe, detector and
reset carry no DC current into vm). From the current into each slot's vm:
  g      = dI/dV at vm = EL (central difference +- 10 mV)   -> tau = C/g (same 200 fF membrane: ratio = g_S/g_F)
  I_sat  = |I(EL - 0.3 V)| (the OTA's output saturates at its tail current)
  dV0    = rest offset: vm where I = 0, minus EL
  VL     = I_sat / g (linear range of the follower-integrator leak)
Corners: typical/ff/ss/fs/sf x 0/27/85 C at S = 100, + typical 27 C at S = 10 / 1000 and ss 85 C at S = 10
(the F tail then carries 16 pA: checked against the leakage at that corner, I(vm) with the tail gate at 0).
Mismatch MC (typical 27 C, S = 100): every seed gives an independent S and F instance; bias lines from
mismatch-free masters (a master's mismatch is common to all neurons on a die). tau_F/tau_S spread per pair.
Writes sim/results/tau_f/tau_f_summary.txt (+ tau_f.json).
"""
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/sim/tb/trim")
from ngs import deck, run, include, RESULTS   # noqa: E402
import slotbench as sb                        # noqa: E402

OUT = RESULTS / "tau_f"
DV = 0.3


def inst(cell, tag, vbl="vbl"):
    n = sb.nets(cell)
    n = dict(n, vm=f"vm{tag}", spk=f"spk{tag}", vbn_leak=vbl)
    return f"X{tag} " + " ".join(n[p] for p in sb.PORTS[cell]) + f" {cell}"


def body(b, vbias=None, vbl="vbl"):
    masters = (sb.MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=1e-15) if vbias is None else
               "\n".join(f"V{n} {n} 0 {v}" for n, v in vbias.items()))
    return f"""{include(*sb.LIBS)}
Vdd vdd 0 3.3
Vel el 0 {sb.EL}
Vrs vrst 0 {sb.VRESET}
Vsr vsrc 0 1.6
Vab abus 0 0.6
{masters}
Vsa sta 0 0
Vsb stb 0 0
Vho hold 0 0
Vmr mrst 0 0
Vg0 vg0 0 0
Vs vms 0 {sb.EL}
Ef vmf0 0 vms 0 1
Vf vmf0 vmf 0
{inst("slot_ah", "s", vbl)}
{inst("slot_ah_f", "f", vbl)}
"""


def analyse(r, b):
    v = r["_x"]
    out = {}
    for k, src in (("S", "i(vs)"), ("F", "i(vf)")):
        i = r[src]                       # current OUT of the source into the slot's vm is -i(V)
        i = -i if k == "S" else i        # Vf is in series (vmf0 -> vmf): i(vf) flows into the slot
        k0 = int(np.argmin(np.abs(v - sb.EL)))
        h = int(round(0.01 / (v[1] - v[0])))
        g = (i[k0 + h] - i[k0 - h]) / (v[k0 + h] - v[k0 - h])      # current into the slot rises with vm
        isat = abs(i[0])
        z = np.where(np.diff(np.sign(i)) != 0)[0]
        dv0 = float(v[z[0]] - i[z[0]] * (v[z[0] + 1] - v[z[0]]) / (i[z[0] + 1] - i[z[0]]) - sb.EL) if len(z) else float("nan")
        out[k] = dict(g=float(g), tau=float(sb.C / g), isat=float(isat), isat_rel=float(isat / b.ib), dv0=dv0,
                      VL=float(isat / g))
    out["ratio"] = out["S"]["g"] / out["F"]["g"]
    return out


def case(arg):
    corner, temp, S = arg
    b = sb.Bias(S)
    tag = f"tau_f/c_{corner}_{temp}_S{S:g}"
    r = run(deck(body(b), f"dc Vs {sb.EL - DV} {sb.EL + DV} 2.5m", ["i(Vs)", "i(Vf)"], corner=corner, temp=temp), tag)
    res = dict(corner=corner, temp=temp, speed=S, **analyse(r, b))
    if S == 10.0:     # leakage floor: same bench with the tail gate (vbn_leak) at 0 V
        r0 = run(deck(body(b, vbl="vg0"), f"dc Vs {sb.EL - DV} {sb.EL + DV} 2.5m", ["i(Vs)", "i(Vf)"],
                      corner=corner, temp=temp), tag + "_leak")
        v = r0["_x"]
        k0 = int(np.argmin(np.abs(v - sb.EL)))
        h = int(round(0.01 / (v[1] - v[0])))
        res["leak_floor_F"] = dict(i_at_EL=float(r0["i(vf)"][k0]),
                                   g=float((r0["i(vf)"][k0 + h] - r0["i(vf)"][k0 - h]) / 0.02))
    return res


def mc(arg):
    seed, vb = arg
    b = sb.Bias(100.0)
    r = run(deck(body(b, vbias=vb), f"dc Vs {sb.EL - DV} {sb.EL + DV} 2.5m", ["i(Vs)", "i(Vf)"],
                 mismatch=True, seed=seed), f"tau_f/mc_s{seed}")
    return dict(seed=seed, **analyse(r, b))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    cases = [(c, t, 100.0) for c in ("typical", "ff", "ss", "fs", "sf") for t in (0, 27, 85)] + \
        [("typical", 27, 10.0), ("typical", 27, 1000.0), ("ss", 85, 10.0)]
    vb = sb.bias_voltages(sb.Bias(100.0), tag="tau_f_mc")
    with Pool(int(os.environ.get("POOL", "6"))) as p:
        res = p.map(case, cases)
        mcr = p.map(mc, [(s, vb) for s in range(1, N + 1)])
    (OUT / "tau_f.json").write_text(json.dumps(dict(cases=res, mc=mcr), indent=1))
    L = ["F slot vs S slot (schematic): leak tail W/L 1/4 vs 2/4 on the same vbn_leak; tau = 200 fF / g at vm = EL",
         " corner   T     S   tau_S(us) tau_F(us)  tau_F/tau_S   Isat_S/Ib Isat_F/Ib  VL_S(mV) VL_F(mV)  rest dV S/F (mV)"]
    for r in res:
        s, f = r["S"], r["F"]
        L.append(f" {r['corner']:7s} {r['temp']:3d} {r['speed']:5g}  {s['tau'] * 1e6:8.1f} {f['tau'] * 1e6:9.1f}   {r['ratio']:8.3f}"
                 f"      {s['isat_rel']:6.3f}   {f['isat_rel']:6.3f}   {s['VL'] * 1e3:7.1f}  {f['VL'] * 1e3:7.1f}"
                 f"    {s['dv0'] * 1e3:+6.2f} / {f['dv0'] * 1e3:+6.2f}")
    for r in res:
        if "leak_floor_F" in r:
            lf = r["leak_floor_F"]
            L.append(f"leakage floor (F bench, tail gate at 0 V), {r['corner']} {r['temp']} C: g = {lf['g'] * 1e12:.3f} pS "
                     f"vs g_F = {r['F']['g'] * 1e12:.1f} pS at S = {r['speed']:g} ({lf['g'] / r['F']['g'] * 100:.2f} %)")
    rat = np.array([m["ratio"] for m in mcr])
    gs = np.array([m["S"]["g"] for m in mcr])
    gf = np.array([m["F"]["g"] for m in mcr])
    dvs = np.array([m["S"]["dv0"] for m in mcr])
    dvf = np.array([m["F"]["dv0"] for m in mcr])
    cv = lambda x: np.std(x) / np.mean(x) * 100
    L += [f"mismatch MC (typical 27 C, S = 100, N = {N}, independent S and F instance per seed):",
          f"  tau_F/tau_S   mean {rat.mean():.3f}  sigma {np.std(rat):.3f} ({cv(rat):.1f} %)  "
          f"5-95 % [{np.percentile(rat, 5):.3f}, {np.percentile(rat, 95):.3f}]  min/max {rat.min():.3f}/{rat.max():.3f}",
          f"  g_S cv {cv(gs):.1f} %, g_F cv {cv(gf):.1f} %  (tau cv the same)",
          f"  rest offset sigma: S {np.std(dvs) * 1e3:.2f} mV, F {np.std(dvf) * 1e3:.2f} mV"]
    txt = "\n".join(L)
    print(txt)
    (OUT / "tau_f_summary.txt").write_text(txt + "\n")
