"""I-V (leak + exp, vm forced) of the A1 schematic vs its PEX netlist, typical 27 C. usage: python3 tb_adex_pexiv.py"""
import sys
import numpy as np
sys.argv = ["tb_adex_char.py", "pexiv"]
sys.path.insert(0, "/work/sim/tb/tier2")
import tb_adex_char as T  # noqa: E402
vsrc = T.cal_vsrc("typical", 27, T.S)
for net in (None, "/work/layout/tier2/out/adex_a1_pex.spice"):
    T.PEX = net
    p = T.iv("typical", 27, vsrc, tag="_pex" if net else "_sch")
    v, i = p["_v"], p["_idut"]
    print("pex" if net else "sch", {k: round(float(x), 4) for k, x in p.items() if not k.startswith("_") and not isinstance(x, bool)})
    print("   I_neuron(pA) at", [(vv, round(float(np.interp(vv, v, i)) * 1e12, 1)) for vv in (1.15, 1.2, 1.22, 1.24, 1.26)])
