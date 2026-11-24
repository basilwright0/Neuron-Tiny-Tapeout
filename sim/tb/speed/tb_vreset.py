"""Speed track: Vreset buffer (cells/vreset) recovery after 20 simultaneous resets vs t_ref = 2 ms / S.

usage: python3 sim/tb/speed/tb_vreset.py [S list] [nproc]   -> sim/results/speed/vreset_summary.txt
Bench as sim/tb/vreset/tb_vreset.py (read-only): buffer + R1 receiver (ib_r1 = 4 uA, NOT scaled with S),
line 300 Ohm + 250 fF, 20 neurons (19 x 200 fF + 1 x 800 fF) = mcap + refrac with I_ref scaled to S,
all at vreset + 0.2 V, one 20 ns spike at 0.5 us (the slot spike is ~15 ns). vin = 1.30 V (nominal).
Reported: t back within 5 mV; line error and the membranes' error (vm - vin, worst of the 20) at
0.5 t_ref and at 0.9 t_ref (just before the reset switch lets go: this is the reset value the neuron keeps).
"""
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
from ngs import deck, run, include, CORNERS, TEMPS  # noqa: E402

import os
VIN, NN = float(os.environ.get("VR_VIN", "1.30")), 20
IB = float(os.environ.get("VR_IB", "4e-6"))     # ib_r1 (ib_x2 = 1 doubles it to ~8 uA)
WSW = os.environ.get("VR_WSW", "")              # per-neuron reset switch W (refrac default 0.5u; slots 1u)
IRX = float(os.environ.get("VR_IREF_X", "1"))
TAG = (f"_wsw{WSW}" if WSW else "") + (f"_irx{IRX:g}" if IRX != 1 else "") + (f"_vin{VIN:g}" if "VR_VIN" in os.environ else "")


def case(arg):
    c, T, S = arg
    tref = 2e-3 / S
    i_ref = 50e-15 * 1.35 / tref * IRX              # IRX: vbn_ref recalibration factor (EL 1.5: t_ref ~0.5-0.66x)
    tstop = 0.5e-6 + max(1.2 * tref, 0.5e-6)
    L = [include('neuron/membrane.spice', 'neuron/lif.spice', 'vreset/vreset_buf.spice'), f"""Vdd vdd 0 3.3
Ib vbp 0 {IB}
XPD vbp vbp vdd vdd pfet_03v3 W=0.4u L=1u
Ir vdd vbnr {i_ref}
Xnr vbnr 0 nmaster w=2u l=4u
Vin vin 0 {VIN}
Xb vin vout vbp vdd 0 vreset_buf
Rl vout vline 300
Cl vline 0 250f
Vspk spk 0 PWL(0 0 0.5u 0 0.502u 3.3 0.52u 3.3 0.522u 0)"""]
    for k in range(NN):
        L.append(f"Xm{k} vm{k} 0 mcap wl={'14.1u' if k == 0 else '7.07u'}\nXr{k} spk vm{k} vr{k} vline vbnr vdd 0 refrac" + (f" wsw={WSW}" if WSW else ""))
    L.append(".ic " + " ".join(f"v(vm{k})={VIN + 0.2}" for k in range(NN)))
    sv = ["v(vline)", "v(vm0)", "v(vm1)", "v(vr1)"]
    r = run(deck("\n".join(L) + "\n", f"tran 0.5n {tstop}", sv, corner=c, temp=T), f"vreset_{c}_{T}_S{S}_ib{IB:g}{TAG}")
    t, v = r["_x"], r["v(vline)"]
    v0 = np.interp(0.49e-6, t, v)
    after = t > 0.5e-6
    bad = np.where(after & (np.abs(v - v0) > 5e-3))[0]
    t5 = (t[bad[-1]] - 0.5e-6) * 1e9 if len(bad) else 0.0
    # switch release: vr falls below ~vreset + Vt; take the vr crossing of 2.0 V as the release time
    vr = r["v(vr1)"]
    hi = np.where(after & (vr > 2.0))[0]
    rel = np.where(after & (t > t[hi[0]]) & (vr < 2.0))[0] if len(hi) else []
    trel = (t[rel[0]] - 0.5e-6) if len(rel) else float("nan")

    def err(tt):
        ts = 0.5e-6 + tt
        return (float(np.interp(ts, t, v) - v0) * 1e3,
                max(abs(float(np.interp(ts, t, r[f"v(vm{k})"]) - v0)) for k in (0, 1)) * 1e3)
    return dict(c=c, T=T, S=S, tref=tref, t5=t5, pk=float((v[after].max() - v0) * 1e3), off=float((v0 - VIN) * 1e3),
                e50=err(0.5 * tref), e90=err(0.9 * tref), trel=trel)


if __name__ == "__main__":
    SS = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1000.0, 3000.0, 10000.0]
    NP = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    cases = [(c, T, S) for S in SS for c in CORNERS for T in TEMPS]
    with Pool(NP) as p:
        res = p.map(case, cases)
    Ls = [f"ib_r1 = {IB*1e6:g} uA, wsw {WSW or '0.5u (default)'}, I_ref x{IRX:g}. Vreset buffer: 20 membranes reset from vin + 0.2 V (vin {VIN:.2f} V), errors in mV vs the settled line (line / worst membrane)",
          "     S corner  T  t_ref(ns) t5mV(ns) peak(mV) offset | @0.5 t_ref line/vm | @0.9 t_ref line/vm | t_release(ns)"]
    for r in res:
        Ls.append(f" {r['S']:5.0f} {r['c']:7s} {r['T']:3d} {r['tref']*1e9:7.0f} {r['t5']:7.0f}  {r['pk']:7.1f}  {r['off']:+6.2f} | "
                  f"{r['e50'][0]:+6.2f} / {r['e50'][1]:6.2f} | {r['e90'][0]:+6.2f} / {r['e90'][1]:6.2f} | {r['trel']*1e9:7.0f}")
    for S in SS:
        rs = [r for r in res if r["S"] == S]
        Ls.append(f"S = {S:g}: t_ref {2e-3/S*1e9:.0f} ns, worst t5mV {max(r['t5'] for r in rs):.0f} ns, worst membrane error "
                  f"at 0.9 t_ref {max(r['e90'][1] for r in rs):.2f} mV, at 0.5 t_ref {max(r['e50'][1] for r in rs):.2f} mV")
    txt = "\n".join(Ls)
    print(txt)
    (RESULTS / ("vreset_summary.txt" if IB == 4e-6 and not TAG else f"vreset_summary_ib{IB:g}{TAG}.txt")).write_text(txt + "\n")
