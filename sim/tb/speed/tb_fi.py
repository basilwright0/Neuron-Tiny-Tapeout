"""Speed track: slot f-I, rheobase, refractory, spike width at speed S (schematic slot cells).

usage: python3 sim/tb/speed/tb_fi.py <cell> <corner> <temp> <S> [nproc]
  cell = slot_ah | slot_ah_h | slot_ah_f | slot_cmp_h | slot_ah_50 | slot_ah_800
Bench = tb_slot_fi.py / slotbench (biases x S/100, vsrc calibrated per corner/temp/S, trim code 8, probe off,
synapse off, ideal input current into vm). Metrics:
  rheo_meas  DC: current needed to hold vm 1 mV below the detector trip (forced-vm sweep on the whole slot)
  rate/ideal f at Iin = k * rheo_nom vs the ideal LIF 1/(t_ref + tau ln(I/(I-rheo))) (Vreset = EL, t_ref = 2 ms/S)
  t_ref_meas spk rising -> vm 10 mV above its post-spike minimum (8 x rheo run)
  w_spk      spk > 1.65 V duration; w/ISI at 8 x rheo
-> sim/results/speed/fi_<cell>_<corner>_<T>_S<S>.json
"""
import json
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS, sb  # noqa: E402
from ngs import deck, run, crossings, rate  # noqa: E402
import ngs  # noqa: E402

# level-3 overrides (defaults = original bench): FI_RESULTS = output dir, FI_SLOTLIB = absolute path of an
# alternative slot.spice (before/after and sweep copies of slot_cmp_h), FI_TAG = output-name suffix
import os as _os
if _os.environ.get("FI_RESULTS"):
    from pathlib import Path as _P
    RESULTS = ngs.RESULTS = _P(_os.environ["FI_RESULTS"])
    RESULTS.mkdir(parents=True, exist_ok=True)
if _os.environ.get("FI_SLOTLIB"):
    sb.LIBS = tuple(_os.environ["FI_SLOTLIB"] if x == "neuron/slot.spice" else x for x in sb.LIBS)

CELL, corner, temp, S = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
NP = int(sys.argv[5]) if len(sys.argv) > 5 else 2
import os
DEL = float(os.environ.get("FI_DEL", "0"))     # shift EL / Vth / Vreset together (operating-point test)
if DEL:
    sb.EL, sb.VTH, sb.VRESET = sb.EL + DEL, sb.VTH + DEL, sb.VRESET + DEL
b = sb.Bias(S)
IBSCALE = float(os.environ.get("FI_IBSCALE", "1"))   # 10000x gate, Option 0: leak-code calibration = leak master x IBSCALE
b.ib *= IBSCALE
PEXF = os.environ.get("FI_PEX")                 # 10000x gate: absolute path of a <name>_pex.spice (DUT = that subckt)
if PEXF:
    import re as _re
    _pn = os.path.basename(PEXF)[:-len("_pex.spice")]
    _txt = _re.sub(r"\n\+", " ", open(PEXF).read())
    _ports = _re.search(rf"^\.subckt\s+{_pn}\s+(.*)$", _txt, _re.M | _re.I).group(1).split()
    _pinst = f".include {PEXF}\nXn " + " ".join(sb.nets(CELL)[p_] for p_ in _ports) + f" {_pn}"
    _sb_body0 = sb.slot_body
    sb.slot_body = lambda *a, **kw: _sb_body0(*a, **{**kw, "inst": _pinst, "include_libs": False})
VTHC = os.environ.get("FI_VTHC")                # CMP only: vth_cmp level (re-calibration test)
if VTHC:
    _sb_body = sb.slot_body
    sb.slot_body = lambda *a, **kw: _sb_body(*a, **kw).replace(f"Vthc vthc 0 {sb.VTH}", f"Vthc vthc 0 {VTHC}")
IPRB = os.environ.get("FI_IPRB")                # vbn_prb master current (default 1 uA; level 3: B1 value per corner)
if IPRB:
    _sb_body2 = sb.slot_body
    sb.slot_body = lambda *a, **kw: _sb_body2(*a, **kw).replace("Ibp vdd vbp 1u", f"Ibp vdd vbp {IPRB}")
GF, CF = sb.GFAC.get(CELL, 1.0), sb.CFAC.get(CELL, 1.0)
RHEO, TAU = b.rheo * GF, b.tau * CF / GF
TREF = sb.TREF_BIO / S
KS = [1.1, 1.5, 2, 3, 5, 8]
TAG = f"{CELL}_{corner}_{temp}_S{S:g}" + (f"_EL{sb.EL:.2f}" if DEL else "") + (f"_vthc{VTHC}" if VTHC else "") + (f"_iprb{IPRB}" if IPRB else "") + os.environ.get("FI_TAG", "")
HAS_SPK = "spk" in sb.PORTS[CELL]


def ideal(I):
    return 1.0 / (TREF + TAU * np.log(I / (I - RHEO))) if I > RHEO else 0.0


def tran(k):
    Iin = k * RHEO
    tstop = (25 if k > 1.2 else 30) * TAU
    body = sb.slot_body(CELL, b, VSRC, iin=Iin, i_syn=1e-15, code=8)
    r = run(deck(body + f".ic v(vm)={sb.EL}\n", f"tran {TAU / 300} {tstop} uic",
                 ["v(vm)", "v(spk)", "i(vdd)"], corner=corner, temp=temp), f"fi_{TAG}_k{k:g}")
    t, vm, spk = r["_x"], r["v(vm)"], r["v(spk)"]
    up = crossings(t, spk, 1.65)
    dn = crossings(t, spk, 1.65, rising=False)
    f = rate(up, t_settle=4 * TAU)
    ws = [d - u for u in up for d in dn[dn > u][:1]]
    # refractory: spk rise -> vm crosses Vreset + 20 mV rising, minus the 20 mV ramp time (C*20mV/Iin)
    trs = []
    ceff = TAU * b.g * GF
    for i, u in enumerate(up[1:-1], 1):
        m = (t > u) & (t < up[i + 1])
        if m.sum() < 5:
            continue
        x = crossings(t[m], vm[m], sb.VRESET + 0.02)
        if len(x):
            trs.append(x[0] - u - ceff * 0.02 / Iin)
    m = t > 4 * TAU
    idd = -np.trapezoid(r["i(vdd)"][m], t[m]) / (t[m][-1] - t[m][0]) if m.sum() > 2 else float("nan")
    return dict(k=k, Iin=Iin, rate=float(f), ideal=float(ideal(Iin)), nspk=int(len(up)),
                w_spk=float(np.median(ws)) if ws else float("nan"),
                t_ref=float(np.median(trs)) if trs else float("nan"),
                vm_min=float(vm[m].min()), vm_max=float(vm[m].max()), idd=float(idd),
                stuck=bool(spk[-50:].mean() > 1.65))


def rheo_dc():
    body = sb.slot_body(CELL, b, VSRC, i_syn=1e-15, code=8, vm_src=sb.EL)
    r = run(deck(body, f"dc Vvm {sb.EL - 0.05:.3f} {sb.VTH + 0.15:.3f} 0.5m", ["i(vvm)", "v(spk)"],
                 corner=corner, temp=temp), f"fidc_{TAG}")
    v, i, s = r["_x"], r["i(vvm)"], r["v(spk)"]
    trip = crossings(v, s, 1.65)
    global G_EL
    G_EL = float(abs(np.interp(sb.EL + 0.01, v, i) - np.interp(sb.EL - 0.01, v, i)) / 0.02)   # leak g at vm = EL
    vt = float(trip[0]) if len(trip) else float("nan")
    k = np.where(v < vt - 1e-3)[0][-1] if len(trip) else len(v) - 1
    return vt, float(abs(i[k]))


if CELL == "slot_cmp_h":
    VSRC = 0.6
else:
    VSRC = sb.cal_vsrc(corner, temp, S, tag=f"spd_{corner}_{temp}_S{S:g}_d{DEL:g}" + os.environ.get("FI_TAG", "") + (f"_{CELL}" if os.environ.get("FI_TAG") else ""))
vtrip, rheo_m = rheo_dc()
if os.environ.get("FI_GONLY"):                  # calibration probe: DC only (leak g at EL), no transients
    (RESULTS / f"g_{TAG}.json").write_text(json.dumps(dict(cell=CELL, corner=corner, temp=temp, S=S, ibscale=IBSCALE,
                                                           g_el=G_EL, g_nom=b.g * sb.GFAC.get(CELL, 1.0), vtrip=vtrip, rheo_meas=rheo_m)))
    print(f"{TAG}: ibscale={IBSCALE:g} g_el={G_EL:.4g} S g_nom={b.g * sb.GFAC.get(CELL, 1.0):.4g} S")
    sys.exit(0)
with Pool(NP) as p:
    res = p.map(tran, KS)
hi = res[-1]
isi8 = 1 / hi["rate"] if hi["rate"] > 0 else float("nan")
out = dict(cell=CELL, corner=corner, temp=temp, S=S, vsrc=VSRC, tau=TAU, rheo=RHEO, tref_nom=TREF,
           vtrip=vtrip, rheo_meas=rheo_m, g_el=G_EL, ibscale=IBSCALE, pex=PEXF, res=res, w_over_isi8=hi["w_spk"] / isi8)
(RESULTS / f"fi_{TAG}.json").write_text(json.dumps(out, indent=1))
print(f"{TAG}: tau={TAU*1e6:.2f}us vsrc={VSRC:.3f} trip={vtrip:.3f} rheo nom/meas={RHEO*1e12:.0f}/{rheo_m*1e12:.0f}pA "
      f"t_ref nom/meas={TREF*1e9:.0f}/{hi['t_ref']*1e9:.0f}ns w_spk={hi['w_spk']*1e9:.1f}ns w/ISI8={out['w_over_isi8']:.3f}")
print("  k  rate(Hz)  ideal(Hz)  ratio  nspk vm[min,max]  Idd(uA) stuck")
for r_ in res:
    print(f" {r_['k']:4.1f} {r_['rate']:9.4g} {r_['ideal']:9.4g} {r_['rate']/r_['ideal']:6.3f} {r_['nspk']:4d} "
          f"[{r_['vm_min']:.3f},{r_['vm_max']:.3f}] {r_['idd']*1e6:7.3f} {r_['stuck']}")
