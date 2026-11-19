"""Small-signal capacitance seen at vm (vm forced at 1.22 V, AC 1 V at 1/10/100 kHz) and at vw, schematic vs PEX,
typical 27 C. usage: python3 tb_adex_cvm.py"""
import sys
import numpy as np
sys.argv = ["tb_adex_char.py", "cvm"]
sys.path.insert(0, "/work/sim/tb/tier2")
import tb_adex_char as T  # noqa: E402
from ngs import deck, run  # noqa: E402
vsrc = T.cal_vsrc("typical", 27, T.S)
for net in (None, "/work/layout/tier2/out/adex_a1_pex.spice"):
    T.PEX = net
    for node, v0 in (("vm", 1.22), ("vw", 0.3)):
        body = f"""{T.lib()}
{T.bias(S=T.S, vsrc=vsrc)}
Vsta sta 0 0
Vstb stb 0 0
Vf {node} 0 dc {v0} ac 1
{T.dut_line()}
"""
        r = run(deck(body, "ac dec 1 1e3 1e5", ["i(Vf)"]), f"tier2/adexc_cvm_{node}_{'pex' if net else 'sch'}")
        # wrdata of a complex vector: columns freq, re, im
        print("pex" if net else "sch", node, r.keys() if False else "", end=" ")
        names = list(r.keys())
        arr = np.array([r[k] for k in names if k != "_x"])
        f = r["_x"]
        print([f"{ff:.0e}Hz C={abs(arr[-1][i]) / (2 * np.pi * ff) * 1e15:.1f}fF" for i, ff in enumerate(f)], names)
