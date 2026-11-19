"""A1 AdEx functional checks (typical 27 C, S = 100): probe mux, hold, mreset, all-zero (power-up) state.

usage: python3 sim/tb/tier2/tb_adex_func.py [corner] [temp] [netlist]
  netlist: optional extracted netlist (e.g. layout/tier2/out/adex_a1_pex.spice) used instead of the schematic.

probe   en = 1, abus loaded by 10 Mohm; (sel_adex, sub1, sub0) stepped through all 8 codes with vm at rest and
        vw driven to 0.45 V through a switch: abus must follow vm (code 1,0,0), vw (1,0,1), else stay ~0.
hold    vm released at Vth - 18 mV (between rest and trip) with vw = 0.30 V (adaptation active): with hold = 1 vm
        must stay put for 1 ms; with hold = 0 it relaxes (leak + adaptation) or fires (exp term).
mreset  400 pA input, adaptation on; mreset pulse 3.0-3.3 ms: vm -> vreset, vw -> 0 during the pulse.
zero    all bias lines off (vbn_* = 0, vbp_* = vdd, el = vreset = vsrc = 0), all logic 0, vdd ramped 0 -> 3.3 V
        in 20 us: supply current, spk, abus, vm, vw at 1-1.5 ms; then a 20 us mreset pulse: vw after it.
Writes sim/results/tier2/adexf_<corner>_<temp>.json.
"""
import json
import sys

import numpy as np

sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
NET = sys.argv[3] if len(sys.argv) > 3 else None
S = 100.0
vsrc = cal_vsrc(corner, temp, S)
DUT = ("XA vm vw spk sel_adex sub0 sub1 sta stb hold mreset vbp_syn el vsrc vreset vbn_leak vbp_st "
       "vbn_ref vbn_prb vbp_w en abus vdd 0 adex_a1")
if NET:                          # extracted netlist: its port order differs, map by name
    import re
    _txt = open("/work/" + NET).read().replace("\n+", " ")
    _ports = re.search(r"^\.subckt adex_a1 (.*)$", _txt, re.M).group(1).split()
    DUT = "XA " + " ".join("0" if p in ("vss", "VSUBS") else p for p in _ports) + " adex_a1"


def cellsx():
    if NET:
        return f"{cells()}\n.include /work/{NET}"
    return cells("adex/adex.spice")


def strip(body, *names):
    """remove the bias() sources that a test drives itself."""
    out = []
    for ln in body.splitlines():
        if ln.split() and ln.split()[0] in names:
            continue
        out.append(ln)
    return "\n".join(out)


SWM = ".model swm sw vt=1.65 vh=0.1 ron=1k roff=1e15\n"
res = dict(corner=corner, temp=temp, vsrc=vsrc, netlist=NET or "schematic")

# ------------------------------------------------------------------------------------ probe mux
seq = []
for k in range(8):
    seq.append(k)
tt = 40e-6
pwl = {n: [] for n in ("sa", "s1", "s0")}
for k in range(8):
    sa, s1, s0 = (k >> 2) & 1, (k >> 1) & 1, k & 1
    for nm, val in (("sa", sa), ("s1", s1), ("s0", s0)):
        pwl[nm] += [f"{k*tt + 1e-7:.7g} {3.3*val}", f"{(k+1)*tt:.7g} {3.3*val}"]
body = strip(bias(S=S, vsrc=vsrc), "Ven", "Vsa", "Vsb0", "Vsb1", "Vab")
body = f"""{cellsx()}
{body}
{SWM}
Ven en 0 3.3
Vsa sel_adex 0 pwl(0 0 {' '.join(pwl['sa'])})
Vsb1 sub1 0 pwl(0 0 {' '.join(pwl['s1'])})
Vsb0 sub0 0 pwl(0 0 {' '.join(pwl['s0'])})
Rab abus 0 10meg
Cab abus 0 1p
Vww vwf 0 0.45
Vct ct 0 3.3
Sww vw vwf ct 0 swm
Vsta sta 0 0
Vstb stb 0 0
{DUT}
"""
r = run(deck(body, f"tran 100n {8*tt}", ["v(abus)", "v(vm)", "v(vw)"], corner=corner, temp=temp),
        f"tier2/adexf_probe_{corner}_{temp}")
x = r["_x"]
pr = {}
for k in range(8):
    m = (x > k * tt + 0.8 * tt) & (x < (k + 1) * tt)
    pr[f"sel{(k>>2)&1}_sub{k&3}"] = dict(abus=float(r["v(abus)"][m].mean()), vm=float(r["v(vm)"][m].mean()),
                                         vw=float(r["v(vw)"][m].mean()))
res["probe"] = pr
print("probe:", {k: round(v["abus"], 3) for k, v in pr.items()}, "vm", round(pr["sel1_sub0"]["vm"], 3), flush=True)

# ------------------------------------------------------------------------------------ hold
hold_res = {}
for hold in (1, 0):
    body = strip(bias(S=S, vsrc=vsrc, i_adw=8e-9, hold=hold), "Vhold")
    body = f"""{cellsx()}
{body}
{SWM}
Vhold hold 0 {3.3*hold}
Vvf vmf 0 {VTH - 0.018:.3f}
Vwf vwf 0 0.30
Vct ct 0 pwl(0 3.3 50u 3.3 51u 0)
Svm vm vmf ct 0 swm
Svw vw vwf ct 0 swm
Vsta sta 0 0
Vstb stb 0 0
{DUT}
"""
    r = run(deck(body, "tran 200n 1.05m", ["v(vm)", "v(vw)", "v(spk)"], corner=corner, temp=temp),
            f"tier2/adexf_hold{hold}_{corner}_{temp}")
    x = r["_x"]
    vm = r["v(vm)"]
    v0 = float(np.interp(60e-6, x, vm))
    v1 = float(np.interp(1.05e-3, x, vm))
    hold_res[f"hold{hold}"] = dict(vm_60us=v0, vm_1ms=v1, drift_mV_per_ms=(v1 - v0) / 0.99e-3 * 1e-3 * 1e3,
                                   spikes=int(len(crossings(x, r["v(spk)"], 1.65))),
                                   vw_60us=float(np.interp(60e-6, x, r["v(vw)"])),
                                   vw_1ms=float(np.interp(1.05e-3, x, r["v(vw)"])))
res["hold"] = hold_res
print("hold:", hold_res, flush=True)

# ------------------------------------------------------------------------------------ mreset
body = strip(bias(S=S, vsrc=vsrc, i_adw=8e-9), "Vmrst")
body = f"""{cellsx()}
{body}
Vmrst mreset 0 pwl(0 0 3.0m 0 3.001m 3.3 3.3m 3.3 3.301m 0)
Iin vdd vm pwl(0 0 0.5m 0 0.501m 400p)
Vsta sta 0 0
Vstb stb 0 0
{DUT}
"""
r = run(deck(body, "tran 200n 4m", ["v(vm)", "v(vw)", "v(spk)"], corner=corner, temp=temp),
        f"tier2/adexf_mreset_{corner}_{temp}")
x = r["_x"]
m = (x > 3.2e-3) & (x < 3.3e-3)
st = crossings(x, r["v(spk)"], 1.65)
res["mreset"] = dict(vw_before=float(np.interp(2.99e-3, x, r["v(vw)"])), vm_during=float(r["v(vm)"][m].mean()),
                     vw_during=float(r["v(vw)"][m].max()), spikes_during=int(((st > 3.01e-3) & (st < 3.3e-3)).sum()),
                     first_isi_after_us=float((st[st > 3.3e-3][1] - st[st > 3.3e-3][0]) * 1e6)
                     if (st > 3.3e-3).sum() > 1 else None,
                     first_isi_step_us=float((st[1] - st[0]) * 1e6) if len(st) > 1 else None)
print("mreset:", res["mreset"], flush=True)

# ------------------------------------------------------------------------------------ all-zero state
body = f"""{cellsx()}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vel el 0 0
Vrs vreset 0 0
Vsr vsrc 0 0
Xbl vbn_leak 0 nmaster
Xbr vbn_ref 0 nmaster
Vpb vbn_prb 0 0
Xbs vbp_st vdd pmaster w=1u l=2u
Xad vbp_w vdd pmaster w=1u l=2u
Xsyn vbp_syn vdd pmaster w=2u l=4u
Ven en 0 0
Vsa sel_adex 0 0
Vsb0 sub0 0 0
Vsb1 sub1 0 0
Rab abus 0 10meg
Vhold hold 0 0
Vmrst mreset 0 pwl(0 0 1.5m 0 1.501m 3.3 1.52m 3.3 1.521m 0)
Vsta sta 0 0
Vstb stb 0 0
{DUT}
"""
r = run(deck(body, "tran 1u 2m", ["v(vm)", "v(vw)", "v(spk)", "v(abus)", "i(Vdd)", "v(vbp_st)", "v(vbn_leak)"],
             corner=corner, temp=temp), f"tier2/adexf_zero_{corner}_{temp}")
x = r["_x"]
m = (x > 1.0e-3) & (x < 1.5e-3)
res["zero"] = dict(vw_after_mreset=float(r["v(vw)"][-1]), idd_nA=float(-r["i(vdd)"][m].mean() * 1e9), spk_max_after_100us=float(r["v(spk)"][x > 1e-4].max()),
                   abus=float(r["v(abus)"][m].mean()), vm=float(r["v(vm)"][m].mean()), vw=float(r["v(vw)"][m].mean()),
                   spikes=int(len(crossings(x, r["v(spk)"], 1.65))))
print("zero:", res["zero"], flush=True)
(OUT / f"adexf_{corner}_{temp}{'_pex' if NET else ''}.json").write_text(json.dumps(res, indent=1))
