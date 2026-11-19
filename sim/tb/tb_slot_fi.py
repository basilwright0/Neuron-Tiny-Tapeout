"""Post-layout f-I check of the neuron-array slot cells: schematic vs magic-extracted netlist.

usage: python3 sim/tb/tb_slot_fi.py [corner] [temp] [S] [cell]
       cell = slot_ah | slot_ah_h | slot_ah_p | slot_ah_f | slot_cmp_h | slot_ah_50 | slot_ah_800 | slot_dummy
  Variants: input currents are multiples of the cell's own rheobase (F: half the leak g) and the run length
  scales with its own tau (F: 2x; AH50 / AH800: C/200 fF). CMP: threshold on aux = VTH (1.38 V; vsrc unused).
  slot_dummy has no spk pin: spikes are counted as vm falling through 1.24 V (the reset).
  sch : cells/neuron/slot.spice (ideal Cfb = 8 fF)
  pex : layout/slot/out/<cell>_pex.spice (magic extract, all coupling caps, Cfb = extracted MOM)
Same biases / per-die vsrc calibration as tb_lif_fi.py (ah variant). Probe disabled (en = sel = 0),
follower sink biased (1 uA master), abus held at 0.6 V. Synapse off (stim/hold/mreset = 0, vbp_syn
from a 1 fA master), input = ideal current into vm. Trim cells: code 8. aux tied to el (P slot: to the vbn_leak bias, i.e. tau code 8).
Writes sim/results/slotfi_<cell>_<corner>_<T>_S<S>.json.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/sim/tb/trim")
from ngs import deck, run, crossings, rate, RESULTS   # noqa: E402
import slotbench as sb                                # noqa: E402

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
S = float(sys.argv[3]) if len(sys.argv) > 3 else 100.0
CELL = sys.argv[4] if len(sys.argv) > 4 else "slot_ah"
PEX = Path(f"/work/layout/slot/out/{CELL}_pex.spice")

b = sb.Bias(S)
GF, CF = sb.GFAC.get(CELL, 1.0), sb.CFAC.get(CELL, 1.0)
RHEO, TAU = b.rheo * GF, b.tau * CF / GF
Iins = RHEO * np.array([1.5, 2, 3, 5, 8])
tstop = 40 * TAU
HAS_SPK = "spk" in sb.PORTS[CELL]
VSRC = sb.cal_vsrc(corner, temp, S, tag=f"slotfi_{corner}_{temp}_S{S:g}")
print(f"calibrated vsrc = {VSRC:.4f} V (schematic detector)")


def dut(kind):
    if kind == "sch":
        return True, None
    txt = re.sub(r"\n\+", " ", PEX.read_text())
    m = re.search(rf"^\.subckt\s+{CELL}\s+(.*)$", txt, re.M | re.I)
    ports = m.group(1).split()
    return False, f".include {PEX}\nXn " + " ".join(sb.nets(CELL)[p] for p in ports) + f" {CELL}"


out = {}
KINDS = ("sch",) if os.environ.get("SCH_ONLY") else ("sch", "pex")
for kind in KINDS:
    libs, inst = dut(kind)
    res = []
    for Iin in Iins:
        body = sb.slot_body(CELL, b, VSRC, iin=Iin, i_syn=1e-15, code=8, inst=inst, include_libs=libs)
        r = run(deck(body + f".ic v(vm)={sb.EL}\n", f"tran {TAU / 200} {tstop} uic",
                     ["v(vm)", "v(spk)"] if HAS_SPK else ["v(vm)"], corner=corner, temp=temp),
                f"slotfi_{CELL}_{kind}_{corner}_{temp}_S{S:g}_I{Iin * 1e12:.0f}p")
        t, vm = r["_x"], r["v(vm)"]
        st = crossings(t, r["v(spk)"], 1.65) if HAS_SPK else crossings(t, vm, 1.24, rising=False)
        res.append(dict(Iin=float(Iin), rate=float(rate(st, t_settle=5 * TAU)), nspk=int(len(st)),
                        vm_min=float(vm[t > 5 * TAU].min()), vm_max=float(vm[t > 5 * TAU].max())))
    out[kind] = res

print(f"{CELL} {corner} {temp}C S={S:g}: tau={TAU * 1e6:.1f}us rheobase={RHEO * 1e12:.0f}pA vsrc={VSRC:.3f}")
print(" Iin/rheo  rate_sch(Hz)  rate_pex(Hz)  pex/sch   vm[min,max] sch        vm[min,max] pex      sch/ideal-LIF")
TREF = sb.TREF_BIO / S
for a, c in zip(out["sch"], out.get("pex", out["sch"])):
    ratio = c["rate"] / a["rate"] if a["rate"] > 0 else float("nan")
    ideal = 1.0 / (TREF + TAU * np.log(a["Iin"] / (a["Iin"] - RHEO)))      # LIF from vreset = EL, no Cfb
    a["ideal"] = float(ideal)
    print(f" {a['Iin'] / RHEO:7.2f} {a['rate']:12.1f} {c['rate']:13.1f} {ratio:8.3f}   "
          f"[{a['vm_min']:.3f},{a['vm_max']:.3f}]   [{c['vm_min']:.3f},{c['vm_max']:.3f}]   {a['rate'] / a['ideal']:.3f}")
(RESULTS / f"slotfi_{CELL}_{corner}_{temp}_S{S:g}.json").write_text(json.dumps(
    dict(cell=CELL, corner=corner, temp=temp, S=S, vsrc=VSRC, tau=TAU, rheo=RHEO, **out), indent=1))
