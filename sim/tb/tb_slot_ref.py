"""REF slot (slot_ref): its tap on el must read exactly like an array slot's vm tap at the same voltage.

usage: python3 sim/tb/tb_slot_ref.py [corner] [temp] [pex]
DC sweep of the probed voltage 1.0 .. 2.0 V. REF: el = V, rsel = sub = en = 1 (PROBE_SUB = 3 -> row 0,
column 0, sub = 1). Reference: slot_ah with vm forced to V, rsel = en = sub_b = 1, sub = 0 (membrane tap).
abus: weak pull-down (pad_psf's XPD) only; the pad follower is a gate load. vbn_prb from a 1 uA 2/2 master.
'pex' uses layout/slot/out/<cell>_pex.spice for both cells. Prints abus(REF) - abus(S vm tap) in mV.
"""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/sim/tb/trim")
from ngs import deck, run, include   # noqa: E402
import slotbench as sb               # noqa: E402

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
PEX = "pex" in sys.argv[3:]


def inst(cell, name, nets):
    if PEX:
        p = Path(f"/work/layout/slot/out/{cell}_pex.spice")
        txt = re.sub(r"\n\+", " ", p.read_text())
        ports = re.search(rf"^\.subckt\s+{cell}\s+(.*)$", txt, re.M | re.I).group(1).split()
        return f".include {p}\n{name} " + " ".join(nets.get(q, "0") for q in ports) + f" {cell}"
    return f"{name} " + " ".join(nets.get(q, "0") for q in sb.PORTS[cell]) + f" {cell}"


common = dict(vdd="vdd", vss="0", VSUBS="0", vbn_prb="vbp", en="hi", rsel="hi")
ref = dict(common, el="vin", sub="hi", abus="abr")
s = dict(common, vm="vin", sub_b="hi", sub="0", abus="abs", el="elx", vbn_leak="0", vbp_st="vdd", vbp_syn="vdd",
         vsrc="0", vreset="0", vbn_ref="0", aux="0", sta="0", stb="0", hold="hi", mreset="0", spk="spk")
body = f"""{include(*sb.LIBS)}
Vdd vdd 0 3.3
Vhi hi 0 3.3
Vex elx 0 1.2
Ibp vdd vbp 1u
Xbp vbp 0 nmaster w=2u l=2u
Vin vin 0 1.2
XPDr abr vdd 0 0 nfet_03v3 W=0.22u L=20u
XPDs abs vdd 0 0 nfet_03v3 W=0.22u L=20u
{inst("slot_ref", "Xr", ref)}
{inst("slot_ah", "Xs", s)}
"""
r = run(deck(body, "dc Vin 1.0 2.0 0.1", ["v(abr)", "v(abs)"], corner=corner, temp=temp),
        f"slotref_{corner}_{temp}{'_pex' if PEX else ''}")
print(f"REF vs S vm tap, {corner} {temp} C, {'PEX' if PEX else 'schematic'}")
print("  V_in    abus REF   abus S-tap   diff (mV)")
for v, a, b in zip(r["_x"], r["v(abr)"], r["v(abs)"]):
    print(f"  {v:4.2f}   {a:8.4f}   {b:8.4f}    {1e3 * (a - b):+7.2f}")
d = (r["v(abr)"] - r["v(abs)"]) * 1e3
print(f"max |diff| = {np.max(np.abs(d)):.2f} mV; gain REF {np.polyfit(r['_x'], r['v(abr)'], 1)[0]:.4f}, "
      f"S tap {np.polyfit(r['_x'], r['v(abs)'], 1)[0]:.4f}")
