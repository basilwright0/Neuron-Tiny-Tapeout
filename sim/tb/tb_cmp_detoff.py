"""slot_cmp_h with all biases off (BIAS_EN = 0): spk must be a clean 0 and the supply current ~ leakage.
Level-3 CMP check (docs/m2-level3-proposal.md 2.1): the new det_cmp leg (XNC on vbn_prb -> XPC diode -> vbp_cmp)
must be off or harmless when B1 is off. As sim/tb/tb_slot_detoff.py, but on the whole CMP slot:
vdd ramps 0 -> 3.3 V in 20 us, 1 ms transient; every bias line is in its B1-off state:
  vbn_prb / vbn_leak / vbn_ref: an unpowered nfet master diode (2/2, 1/2 ... as the bench masters) or tied to 0 V,
  vbp_st / vbp_syn: an unpowered pfet master diode or tied to 3.3 V,
  el / vreset / vth_cmp (aux) / vsrc: 0 V (B1 copies off), all logic inputs 0, abus 0.
vm forced to 0 V or 1.4 V (a membrane left high). All 5 corners x 0/27/85 C.
usage: python3 sim/tb/tb_cmp_detoff.py <slot.spice path> [tag]   -> sim/results/level3_cmp/detoff_<tag>.txt
"""
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, "/work/sim/lib")
import ngs  # noqa: E402
from ngs import deck, run, include, CORNERS, TEMPS   # noqa: E402

SLOT = sys.argv[1] if len(sys.argv) > 1 else "/work/cells/neuron/slot.spice"
TAG = sys.argv[2] if len(sys.argv) > 2 else "cur"
ngs.RESULTS = Path("/work/sim/results/level3_cmp")
(ngs.RESULTS / "detoff").mkdir(parents=True, exist_ok=True)
LIBS = ("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice", "neuron/synapse.spice",
        "trim/trim_gap.spice")
PORTS = ("vm spk rsel sub sub_b el vsrc vreset vbn_leak vbp_st vbn_ref vbn_prb en abus vdd vss aux vbp_syn sta stb "
         "hold mreset t0 t1 t2 t3").split()
NETS = dict(vm="vm", spk="spk", vbn_leak="vbl", vbp_st="vbs", vbn_ref="vbr", vbn_prb="vbp", vdd="vdd",
            vbp_syn="vsyn")


def case(arg):
    c, t, mode, vm = arg
    inst = "Xn " + " ".join(NETS.get(p, "0") for p in PORTS) + " slot_cmp_h"
    if mode == "diode":
        bias = """Xbl vbl 0 nmaster
Xbr vbr 0 nmaster
Xbp vbp 0 nmaster w=2u l=2u
Xbs vbs vdd pmaster w=1u l=2u
Xsy vsyn vdd pmaster w=2u l=4u"""
    else:
        bias = "Vbl vbl 0 0\nVbr vbr 0 0\nVbp vbp 0 0\nVbs vbs 0 pwl(0 0 20u 3.3)\nVsy vsyn 0 pwl(0 0 20u 3.3)"
    body = f"""{include(*LIBS)}
.include {SLOT}
Vdd vdd 0 pwl(0 0 20u 3.3)
{bias}
Vm vm 0 {vm}
{inst}
"""
    sv = ["v(spk)", "v(vbp)", "i(Vdd)"]
    has_leg = "vbp_cmp" in Path(SLOT).read_text()
    if has_leg:
        sv += ["v(xn.vbp_cmp)"]
    r = run(deck(body, "tran 1u 1m", sv, corner=c, temp=t), f"detoff/{TAG}_{c}_{t}_{mode}_vm{vm}")
    d = dict(c=c, t=t, mode=mode, vm=vm, spk=float(r["v(spk)"][-1]), vbp=float(r["v(vbp)"][-1]),
             idd=float(-r["i(vdd)"][-1]))
    if has_leg:
        d["vbpc"] = float(r["v(xn.vbp_cmp)"][-1])
    return d


if __name__ == "__main__":
    cases = [(c, t, m, vm) for c in CORNERS for t in TEMPS for m in ("diode", "tied") for vm in (0.0, 1.4)]
    with Pool(2) as p:
        res = p.map(case, cases)
    L = [f"slot_cmp_h bias-off ({TAG}, {SLOT}): worst spk {max(r['spk'] for r in res) * 1e3:.2f} mV, "
         f"worst Idd {max(r['idd'] for r in res) * 1e9:.3f} nA, max vbn_prb {max(r['vbp'] for r in res) * 1e3:.1f} mV"]
    if "vbpc" in res[0]:
        L.append(f"  leg: min vbp_cmp {min(r['vbpc'] for r in res):.3f} V (vdd 3.3; Idd includes the leg)")
    for r in res:
        L.append(f"  {r['c']:7s} {r['t']:3d} {r['mode']:5s} vm={r['vm']}: spk {r['spk'] * 1e3:7.2f} mV  Idd "
                 f"{r['idd'] * 1e9:8.3f} nA  vbn_prb {r['vbp'] * 1e3:6.1f} mV"
                 + (f"  vbp_cmp {r['vbpc']:.3f} V" if "vbpc" in r else ""))
    txt = "\n".join(L)
    print(txt)
    (ngs.RESULTS / f"detoff_{TAG}.txt").write_text(txt + "\n")
