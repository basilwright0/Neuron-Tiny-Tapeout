"""Speed track: synapse syn_in charge per pulse when I_w scales up and pulse widths scale down with S.

usage: python3 sim/tb/speed/tb_syn.py [nproc]  -> sim/results/speed/syn_summary.txt
Bench = sim/tb/synapse/tb_syn.py (read-only) standalone syn_in, vm held at 1.34 V (mid sub-threshold),
vbp_syn from an ideal I_set into a 2/4 pmaster. At each S: I_set = 1 nA * S/100 and pulse widths
tw = {0.1, 1, 10, 50} us * 100/S (the same bio-time pulses: the ideal charge I_set*tw is S-independent),
2 ns edges. Fit Q = a*tw + b: gain a/I_set, fixed charge b, residual; Q(shortest)/ideal.
Also the weight DC gain I_w/I_set and compliance (vm 1.0 vs 1.34 V) at I_set up to 1 uA (max weights at S = 10000).
"""
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
from ngs import deck, run, include, CORNERS  # noqa: E402

VM = 1.34


def bench(vm=VM, sta="0", iset="1e-9"):
    return f"""{include('neuron/membrane.spice', 'neuron/lif.spice', 'neuron/synapse.spice')}
Vdd vdd 0 3.3
Isy vsyn 0 {iset}
Xsy vsyn vdd pmaster w=2u l=4u
Vvm vm 0 {vm}
Vvl vl 0 {vm}
Vvr vr 0 0
Vsa sta 0 {sta}
Vsb stb 0 0
Vho hold 0 0
Vmr mrst 0 0
XS vm vl vr sta stb hold mrst vsyn vdd 0 syn_in
"""


def charge(tag, corner, temp, tw, iset, edge=2e-9):
    t0 = 0.2e-6 + 2 * tw
    tstop = t0 + tw + max(5 * tw, 1e-6)
    pulse = f"PULSE(0 3.3 {t0} {edge} {edge} {tw} 1)"
    r = run(deck(bench(sta=pulse, iset=iset), f"tran {min(tw, 1e-6) / 200} {tstop}", ["i(Vvm)"],
                 corner=corner, temp=temp), f"syn_{tag}")
    t, i = r["_x"], r["i(vvm)"]
    base = np.median(i[t < t0 * 0.9])
    m = t > t0 * 0.9
    return float(np.trapezoid(i[m] - base, t[m]))


def case(arg):
    corner, temp, S = arg
    iset = 1e-9 * S / 100
    tws = np.array([0.1e-6, 1e-6, 10e-6, 50e-6]) * 100 / S
    q = np.array([charge(f"q_{corner}_{temp}_S{S}_{k}", corner, temp, tw, iset) for k, tw in enumerate(tws)])
    a, b0 = np.polyfit(tws, q, 1)
    # DC weight gain at large I_set (max weights): vm at 1.34 and 1.0 V
    dc = {}
    for vm in (VM, 1.0):
        body = bench(vm=vm, sta="3.3", iset="0").replace("Isy vsyn 0 0", "Bsy vsyn 0 I = 1e-12*pow(10, v(x))\nVx x 0 0")
        r = run(deck(body, "dc Vx 2 6 0.25", ["i(Vvm)"], corner=corner, temp=temp), f"syndc_{corner}_{temp}_{vm}")
        dc[vm] = r["i(vvm)"]
    isw = 1e-12 * 10 ** np.arange(2, 6.01, 0.25)
    gain = dc[VM] / isw
    return dict(corner=corner, temp=temp, S=S, iset=iset, gain=a / iset, qfix=b0, qfix_rel=b0 / (iset * tws[0]),
                resid=float(np.max(np.abs(q - (a * tws + b0)))) / (iset * tws[0]),
                q_short_rel=float(q[0] / (iset * tws[0])),
                dc_gain={f"{x:.0e}": float(g) for x, g in zip(isw, gain)},
                compl={f"{x:.0e}": float(dc[1.0][k] / dc[VM][k]) for k, x in enumerate(isw)})


if __name__ == "__main__":
    NP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    cases = [(c, t, S) for S in (100, 1000, 10000) for c, t in
             (("typical", 27), ("ss", 0), ("ff", 85), ("sf", 0), ("fs", 85))]
    with Pool(NP) as p:
        res = p.map(case, cases)
    L = ["syn_in, vm = 1.34 V: I_set = 1 nA x S/100, tw = {0.1,1,10,50} us x 100/S (bio-equal charge)",
         "     S corner   T  I_set(nA) tw_min(ns) gain(Q/I tw)  Q_fixed(fC) Q_fixed/Q(tw_min)  resid/Q(tw_min)  Q(tw_min)/ideal"]
    for r in res:
        L.append(f" {r['S']:5d} {r['corner']:7s} {r['temp']:3d} {r['iset']*1e9:8.1f} {0.1e-6*100/r['S']*1e9:9.1f}   {r['gain']:7.3f}"
                 f"      {r['qfix']*1e15:+8.3f}      {r['qfix_rel']:+8.3f}        {r['resid']:7.3f}         {r['q_short_rel']:7.3f}")
    L.append("DC weight gain I_w/I_set at vm = 1.34 V (100 nA, 316 nA, 1 uA) and compliance I(1.0 V)/I(1.34 V):")
    for r in res:
        if r["S"] == 100:
            g, cp = r["dc_gain"], r["compl"]
            L.append(f"   {r['corner']:7s} {r['temp']:3d}  gain " + " ".join(f"{g[k]:.3f}" for k in ("1e-07", "3e-07", "1e-06"))
                     + "   compl " + " ".join(f"{cp[k]:.3f}" for k in ("1e-07", "3e-07", "1e-06")))
    txt = "\n".join(L)
    print(txt)
    (RESULTS / "syn_summary.txt").write_text(txt + "\n")
