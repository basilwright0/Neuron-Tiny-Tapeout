"""Speed track: D1 dendrite (cells/dendrite) plateau threshold / duration / burst and attenuation at speed S.

usage: python3 sim/tb/speed/tb_d1.py <S> [corner:temp,...] [nproc]
Bench = sim/tb/dendrite/dcommon.py bias(S) (read-only; every bias current x S/100, vsrc calibrated at the
S-scaled I_st) and the tb_plateau.py 'ramp' and 'pulse' stimuli time-scaled by 100/S, currents by S/100:
  ramp   d1: 0 -> 700 pA * S/100 over 7 ms * 100/S, soma spiking: plateau threshold (mV above EL, current)
  pulse  d1: 800 pA * S/100 for 100 us * 100/S: plateau duration (detector high), d1 > EL + 250 mV time,
         soma spikes / burst rate; durations reported in S = 100 units (x S/100)
  atten  d1: 300 pA * S/100 step for 6 tau, plateau off, soma passive (vsrc 1.4 V): soma/d1 at the end
-> sim/results/speed/d1_S<S>.json
Env overrides (defaults = the behaviour above): D1_OUT=<dir under /work> (results dir), D1_SPICE=<path> (dendrite
netlist instead of cells/dendrite/dendrite.spice), D1_TAG=<str> (file/json suffix), D1_TRIM=<0..15> (TRIM nibbles
7/8 code on both subunits; default 8), D1_TESTS=ramp,pulse,atten (subset).
"""
import json
import os
import sys
from pathlib import Path
from multiprocessing import Pool

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
import ngs  # noqa: E402
if os.environ.get("D1_OUT"):
    RESULTS = ngs.RESULTS = Path(os.environ["D1_OUT"])
    (RESULTS / "dendrite").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa: E402,F403
import dcommon  # noqa: E402

TAG = os.environ.get("D1_TAG", "")
TRIM = int(os.environ.get("D1_TRIM", "8"))
TESTS = os.environ.get("D1_TESTS", "ramp,pulse,atten").split(",")
_cells = cells
if os.environ.get("D1_SPICE"):
    def cells():  # noqa: F811
        return _cells().replace(str(ngs.CELLS / "dendrite/dendrite.spice"), os.environ["D1_SPICE"])
if os.environ.get("D1_REPL"):   # level 4: "cells/rel/path=/abs/copy;..." swaps included cell files (before/after copies)
    _cells2 = cells

    def cells():  # noqa: F811
        out = _cells2()
        for kv in os.environ["D1_REPL"].split(";"):
            a_, b_ = kv.split("=")
            out = out.replace(str(ngs.CELLS / a_), b_)
        return out
if os.environ.get("D1_DEL"):    # level 4: EL / Vth / Vreset shifted together (level-1 operating point EL 1.5 V)
    _d = float(os.environ["D1_DEL"])
    dcommon.EL, dcommon.VTH, dcommon.VRESET = dcommon.EL + _d, dcommon.VTH + _d, dcommon.VRESET + _d
    EL, VTH, VRESET = dcommon.EL, dcommon.VTH, dcommon.VRESET
if TRIM != 8:   # per-bit trim lines (dcommon's DUT ties ta3/tb3 to one 'ta' source = code 8)
    DUT = DUT.replace("vsyn 0 0 0 ta 0 0 0 ta", "vsyn tq0 tq1 tq2 tq3 tq0 tq1 tq2 tq3")
    _bias = bias

    def bias(**kw):  # noqa: F811
        return _bias(**kw) + "".join(f"Vtq{b} tq{b} 0 {3.3 if TRIM >> b & 1 else 0}\n" for b in range(4))

if os.environ.get("D1_PEX"):    # 10000x gate: extracted dend_d1 (layout/dendrite/out/dend_d1_pex.spice, as tb_synapse.py pex)
    import re as _re
    _src = open("/work/cells/dendrite/dendrite.spice").read().replace("\n+", " ")
    _sch = [t_ for t_ in _re.search(r"^\.subckt dend_d1 (.*)$", _src, _re.M).group(1).split() if "=" not in t_]
    _m = dict(zip(_sch, DUT.split()[1:-1]), VSUBS="0")
    _pex = open(os.environ["D1_PEX"]).read().replace("\n+", " ")
    DUT = "XD " + " ".join(_m[p_] for p_ in _re.search(r"^\.subckt dend_d1 (.*)$", _pex, _re.M).group(1).split()) + " dend_d1"

    def cells():  # noqa: F811
        return (include("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice", "dendrite/dtrim.spice")
                + f"\n.include {os.environ['D1_PEX']}")
if os.environ.get("D1_IBSCALE"):    # 10000x gate, Option 0: leak-code calibration = leak master (ib_leak) x D1_IBSCALE
    _bias3 = bias

    def bias(**kw):  # noqa: F811
        return _bias3(ib_leak=g_leak(kw.get("S", 100.0)) / dcommon.G_PER_IB * float(os.environ["D1_IBSCALE"]), **kw)
XB = os.environ.get("D1_XB", "xd.xp1.xb")      # plateau detector output (PEX: the extracted net name of XP1.XDT xb)
S = float(sys.argv[1])
CASES = [(c.split(":")[0], int(c.split(":")[1])) for c in
         (sys.argv[2] if len(sys.argv) > 2 else "typical:27,ss:0,ff:85,sf:0").split(",")]
NP = int(sys.argv[3]) if len(sys.argv) > 3 else 2
k = 100.0 / S          # time scale
SV = ["v(vs)", "v(d1)", "v(d2)", "v(spk)", f"v({XB})"]


def pwl(node, segs):
    return f"I{node} vdd {node} pwl(" + " ".join(f"{t:.6g} {i:.6g}" for t, i in segs) + ")"


def tran(corner, temp, src, tstop, name, vsrc, vsrc_cal, pl_en=1):
    body = f"""{cells()}
{bias(S=S, gax=4e-9 * S / 100, vsrc=vsrc, pl_en=pl_en, vsrcp=vsrc_cal)}
{src}
{DUT}
"""
    return run(deck(body, f"tran {1e-6 * k} {tstop}", SV, corner=corner, temp=temp), f"d1_{name}_{corner}_{temp}_S{S:g}{TAG}{'' if TRIM == 8 else f'_t{TRIM}'}")


def case(arg):
    corner, temp = arg
    vc = cal_vsrc(corner, temp, S)
    res = dict(corner=corner, temp=temp, S=S, vsrc=vc, trim=TRIM, tag=TAG)
    if "ramp" in TESTS:
        ramp(res, corner, temp, vc)
    if "pulse" in TESTS:
        pulse(res, corner, temp, vc)
    if "atten" in TESTS:
        atten(res, corner, temp, vc)
    return res


def ramp(res, corner, temp, vc):
    T, T0 = 7e-3 * k, 2e-3 * k
    r = tran(corner, temp, pwl("d1", [(0, 0), (T0, 0), (T0 + T, 700e-12 / k), (T0 + T + 1e-6 * k, 0)]),
             T0 + T + 0.5e-3 * k, "ramp", vc, vc)
    t, xb = r["_x"], r[f"v({XB})".lower()]
    m = t > T0
    tc = crossings(t[m], xb[m], 1.65)
    rest = float(np.interp(T0 - 1e-6 * k, t, r["v(d1)"]))
    if len(tc):
        res["thr_mV_el"] = (float(np.interp(tc[0], t, r["v(d1)"])) - EL) * 1e3
        res["thr_mV_rest"] = (float(np.interp(tc[0], t, r["v(d1)"])) - rest) * 1e3
        res["thr_pA_norm"] = 700 * (tc[0] - T0) / T
    res["rest_mV_el"] = (rest - EL) * 1e3


def pulse(res, corner, temp, vc):
    t0 = 2e-3 * k
    src = pwl("d1", [(0, 0), (t0, 0), (t0 + 1e-6 * k, 800e-12 / k), (t0 + 100e-6 * k, 800e-12 / k), (t0 + 101e-6 * k, 0)])
    r = tran(corner, temp, src, 6e-3 * k, "pulse", vc, vc)
    t, xb, d1 = r["_x"], r[f"v({XB})".lower()], r["v(d1)"]
    m0 = t > 0.95 * t0
    up = crossings(t[m0], xb[m0], 1.65)
    dn = crossings(t[m0], xb[m0], 1.65, rising=False)
    if len(up):
        dn = dn[dn > up[0]]
    hi = t[(d1 > EL + 0.25) & m0]
    spk = crossings(t[m0], r["v(spk)"][m0], 1.65)
    res.update(t_plat_us_norm=float(dn[0] - up[0]) / k * 1e6 if len(up) and len(dn) else float("nan"),
               t_above250_us_norm=float(hi[-1] - hi[0]) / k * 1e6 if len(hi) else 0.0,
               d1_max_mV=float(d1[m0].max() - EL) * 1e3, vs_max_mV=float(r["v(vs)"][m0].max() - EL) * 1e3,
               nspk=int(len(spk)), burst_hz_norm=float(1 / np.mean(np.diff(spk))) * k if len(spk) > 2 else 0.0)


def atten(res, corner, temp, vc):
    tau = C / g_leak(S)
    src = pwl("d1", [(0, 0), (5 * tau, 0), (5 * tau + 1e-9, 300e-12 / k)])
    r = tran(corner, temp, src, 11 * tau, "atten", 1.4, vc, pl_en=0)
    t = r["_x"]
    b = {n: float(np.interp(4.9 * tau, t, r[f"v({n})"])) for n in ("vs", "d1")}
    e = {n: float(np.interp(11 * tau, t, r[f"v({n})"])) - b[n] for n in ("vs", "d1")}
    res.update(atten=e["vs"] / e["d1"], d1_step_mV=e["d1"] * 1e3)


if __name__ == "__main__":
    with Pool(NP) as p:
        res = p.map(case, CASES)
    nan = float("nan")
    for r in res:
        g = r.get
        print(f"D1{TAG} S={S:g} trim {TRIM} {r['corner']:7s} {r['temp']:3d}: thr {g('thr_mV_el', nan):.1f} mV>EL "
              f"(rest {g('rest_mV_el', nan):+.1f}, {g('thr_pA_norm', nan):.0f} pA@S100) plateau {g('t_plat_us_norm', nan):.0f} us "
              f"d1>+250mV {g('t_above250_us_norm', nan):.0f} us d1max +{g('d1_max_mV', nan):.0f} soma max +{g('vs_max_mV', nan):.0f} mV "
              f"spikes {g('nspk', -1)} burst {g('burst_hz_norm', nan):.0f} Hz | atten soma/d1 {g('atten', nan):.3f} "
              f"(d1 +{g('d1_step_mV', nan):.1f} mV)", flush=True)
    (RESULTS / f"d1_S{S:g}{TAG}{'' if TRIM == 8 else f'_t{TRIM}'}.json").write_text(json.dumps(res, indent=1))
