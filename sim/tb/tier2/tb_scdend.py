"""S1 switched-capacitor dendrite (cells/scdend/scdend.spice), typical corner.

usage: python3 sim/tb/tier2/tb_scdend.py [corner] [temp] [part]      part = r | xfer | spike | all
  r     : equivalent resistance of the axial (C_A) and leak (C_L) SC resistors vs f_sc, alone
          (sc_nov + switches + ideal C; one node at 1.20 V, the other at 1.20 V + dV, dV = 50 / 200 mV).
          R = dV / <I>, <I> averaged over 10 sc_clk periods after 5 settling periods.
  xfer  : the full scdend_s1 (detector parked, vsrc = 1.3 V): +20 pA step into d and into vs at
          f_sc = 100 / 400 kHz; settled dV vs model/reference.py Compartments with g = f * C_eff.
  spike : vsrc calibrated (trip 1.28 V), f_sc = 400 kHz: DC step into d only -> soma firing rate,
          vs the same current into vs.
Results: sim/results/tier2/scdend_<part>_<corner>_<temp>.json
"""
import json
import re
import sys

import numpy as np

sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
from ngs import header
from reference import Compartments
import subprocess

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
part = sys.argv[3] if len(sys.argv) > 3 else "all"
S = 100.0
CA, CL = 10e-15, 5e-15
F_LIST = [50e6 / 2 ** k for k in (4, 5, 7, 9, 11, 13)]    # SC_DIV 4..13 at clk = 50 MHz
CELLS = cells("scdend/scdend.spice")


def meas_deck(body, tstop, meas):
    m = "\n".join(meas)
    return f"""* tier2 meas
{header(corner=corner, temp=temp)}
{body}
.control
tran {tstop / 4000:.4g} {tstop}
{m}
quit
.endc
.end
"""


def run_meas(text, name):
    cir = OUT / f"{name}.cir"
    cir.write_text(text)
    p = subprocess.run(["ngspice", "-b", str(cir)], cwd=OUT, capture_output=True, text=True, timeout=3600)
    (OUT / f"{name}.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
    vals = {}
    for k, v in re.findall(r"^(\w+)\s*=\s*([-+0-9.eE]+)", p.stdout, re.M):
        vals[k.lower()] = float(v)
    return vals


def sc_r(which, f, dv):
    """Average current through one SC resistor between n1 (1.2 V + dv) and n2 (1.2 V)."""
    T = 1 / f
    t1, t2 = 5 * T, 15 * T
    if which == "ax":
        sw = f"XA1 n1 p1 c 0 nfet_03v3 W=0.22u L=0.28u\nXA2 n2 p2 c 0 nfet_03v3 W=0.22u L=0.28u\nCC c 0 {CA}"
    else:
        sw = f"XL1 n1 p1 c 0 nfet_03v3 W=0.22u L=0.28u\nXL2 n2 p2 c 0 nfet_03v3 W=0.22u L=0.28u\nCC c 0 {CL}"
    body = f"""{CELLS}
Vdd vdd 0 3.3
Vck ck 0 pulse(0 3.3 {T/4} 1n 1n {T/2 - 1e-9} {T})
XN ck p1 p2 vdd 0 sc_nov
V1 n1 0 {1.2 + dv}
V2 n2 0 1.2
{sw}
"""
    v = run_meas(meas_deck(body, t2, [f"meas tran q1 integ i(V1) from={t1} to={t2}",
                                      f"meas tran q2 integ i(V2) from={t1} to={t2}"]),
                 f"scr_{which}_{f:.0f}_{dv*1e3:.0f}_{corner}_{temp}")
    i1 = -v["q1"] / (t2 - t1)          # current out of V1 into n1 (ngspice i(V) = into + terminal)
    return dv / i1, i1, -v["q2"] / (t2 - t1)


def part_r():
    out = {}
    for which, Cn in (("ax", CA), ("leak", CL)):
        rows = []
        for f in F_LIST:
            for dv in (0.05, 0.2, -0.05):
                R, i1, i2 = sc_r(which, f, dv)
                rows.append(dict(f=f, dv=dv, R=R, R_ideal=1 / (f * Cn), ratio=R * f * Cn, i1=i1, i2=i2))
                print(f"{which:4s} f={f/1e3:9.2f} kHz dV={dv*1e3:+4.0f} mV  R={R/1e6:10.2f} MOhm  "
                      f"1/(fC)={1/(f*Cn)/1e6:10.2f}  R*fC={R*f*Cn:.4f}  C_eff={1/(R*f)*1e15:.2f} fF", flush=True)
        out[which] = rows
    return out


DUT = ("XS vs d spk sel0 sel2 sc_clk sta stb hold mreset vbp_syn el vsrc vreset vbn_leak vbp_st "
       "vbn_ref vbn_prb en abus vdd 0 scdend_s1")


def s1_tran(f, extra, tstop, save, tag, vsrc):
    T = 1 / f
    body = f"""{CELLS}
{bias(S=S, vsrc=vsrc)}
Vsta sta 0 0
Vstb stb 0 0
Vck sc_clk 0 pulse(0 3.3 {T/4} 1n 1n {T/2 - 1e-9} {T})
{extra}
{DUT}
"""
    return run(deck(body, f"tran {min(T / 8, 2e-6):.4g} {tstop}", save, corner=corner, temp=temp), f"tier2/{tag}")


def avg(x, v, t1, t2):
    m = (x >= t1) & (x <= t2)
    return float(np.trapezoid(v[m], x[m]) / (x[m][-1] - x[m][0]))


def part_xfer(ceff):
    out = {}
    IST, TS, TM = 20e-12, 1.5e-3, 3.0e-3
    for f in (100e3, 400e3):
        R = np.zeros((2, 2))
        rest = None
        for j, nj in enumerate(("vs", "d")):
            r = s1_tran(f, f"Iin vdd {nj} pwl(0 0 {TS} 0 {TS + 1e-6} {IST})", TM, ["v(vs)", "v(d)"],
                        f"scx_{f/1e3:.0f}k_{j}_{corner}_{temp}", vsrc=1.3)
            x = r["_x"]
            for i, ni in enumerate(("vs", "d")):
                before = avg(x, r[f"v({ni})"], TS - 0.3e-3, TS - 1e-6)
                after = avg(x, r[f"v({ni})"], TM - 0.3e-3, TM)
                R[i, j] = (after - before) / IST
            rest = [avg(x, r[f"v({n})"], TS - 0.3e-3, TS - 1e-6) for n in ("vs", "d")]
            ripple = float(np.ptp(r["v(d)"][x > TM - 0.1e-3]))
        gax, gld = f * ceff["ax"], f * ceff["leak"]
        G = np.array([[0, gax], [gax, 0]])
        m = Compartments(C=np.array([C, C]), gL=np.array([g_leak(S), gld]), G=G, EL=EL)
        Rm = m.steady_state_transfer()
        att, attm = R[0, 1] / R[1, 1], Rm[0, 1] / Rm[1, 1]
        print(f"f={f/1e3:.0f} kHz: g_ax={gax*1e9:.2f} nS gL_d={gld*1e9:.2f} nS  rest vs,d = {rest[0]:.4f}, {rest[1]:.4f}  "
              f"ripple(d) {ripple*1e3:.2f} mVpp", flush=True)
        print("  R spice (MOhm):", np.round(R / 1e6, 1).tolist(), " model:", np.round(Rm / 1e6, 1).tolist())
        print(f"  ratio spice/model: {np.round(R / Rm, 3).tolist()}  attenuation d->soma {att:.3f} (model {attm:.3f})")
        out[f"{f:.0f}"] = dict(R=R.tolist(), Rm=Rm.tolist(), rest=rest, att=att, att_model=attm, ripple=ripple,
                               gax=gax, gld=gld)
    return out


def part_spike():
    vsrc = cal_vsrc(corner, temp, S)
    out = {}
    f = 400e3
    for node in ("d", "vs"):
        for ist in (400e-12, 700e-12, 1000e-12):
            r = s1_tran(f, f"Iin vdd {node} pwl(0 0 0.3m 0 {0.3e-3 + 1e-6} {ist})", 3.3e-3,
                        ["v(vs)", "v(d)", "v(spk)"], f"scs_{node}_{ist*1e12:.0f}_{corner}_{temp}", vsrc=vsrc)
            st = crossings(r["_x"], r["v(spk)"], 1.65)
            st = st[st > 0.3e-3]
            rt = rate(st, 0.8e-3)
            out[f"{node}_{ist*1e12:.0f}"] = dict(n=len(st), rate=rt)
            print(f"input into {node:2s} {ist*1e12:5.0f} pA: {len(st):3d} soma spikes, rate {rt:7.0f} Hz", flush=True)
    return out


res = {}
ceff = dict(ax=CA, leak=CL)
if part in ("r", "all"):
    res["r"] = part_r()
    for k in ("ax", "leak"):
        rows = [r for r in res["r"][k] if r["dv"] == 0.05]
        ceff[k] = float(np.median([1 / (r["R"] * r["f"]) for r in rows]))
    print("C_eff:", {k: f"{v*1e15:.2f} fF" for k, v in ceff.items()})
if part in ("xfer", "all"):
    res["xfer"] = part_xfer(ceff)
if part in ("spike", "all"):
    res["spike"] = part_spike()
res["ceff"] = ceff
(OUT / f"scdend_{part}_{corner}_{temp}.json").write_text(json.dumps(res, indent=1))
