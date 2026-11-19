"""Diagnose the PEX spike-edge runt: re-run the 400 pA step on copies of the PEX netlist with selected coupling
capacitors removed. usage: python3 tb_adex_pexcut.py"""
import sys
import re
import numpy as np
sys.argv = ["tb_adex_char.py", "pexcut"]
sys.path.insert(0, "/work/sim/tb/tier2")
import tb_adex_char as T  # noqa: E402
SRC = "/work/layout/tier2/out/adex_a1_pex.spice"
NAMES = {"n1": "a_6628_5974#", "p": "a_7060_5974#", "pb": "a_7148_1874#", "vr": "a_480_5974#", "vrb": "a_912_5974#",
         "spkb": "a_8356_5974#"}
txt = open(SRC).read()
vsrc = T.cal_vsrc("typical", 27, T.S)
CASES = {"full": [], "det-vr/vrb": [("pb", "vr"), ("pb", "vrb"), ("p", "vrb"), ("n1", "vrb"), ("p", "vr"), ("n1", "vr")],
         "det-vrb": [("pb", "vrb"), ("p", "vrb"), ("n1", "vrb")], "det-vr": [("pb", "vr"), ("p", "vr"), ("n1", "vr")],
         "vm-vr": [("vm", "vr")], "det-all-coupling": "DET"}
for name, cut in CASES.items():
    lines = []
    det = {NAMES[k] for k in ("n1", "p", "pb")}
    pairs = {frozenset((NAMES.get(a, a), NAMES.get(b, b))) for a, b in cut} if cut != "DET" else set()
    for ln in txt.splitlines():
        tok = ln.split()
        if len(tok) == 4 and re.match(r"^C\d+$", tok[0]):
            if frozenset(tok[1:3]) in pairs:
                continue
            if cut == "DET" and (tok[1] in det or tok[2] in det) and "vss" not in tok[1:3] and "vdd" not in tok[1:3]:
                continue
        lines.append(ln)
    path = f"/work/sim/results/tier2/pexcut_{name.replace('/', '_')}.spice"
    open(path, "w").write("\n".join(lines) + "\n")
    T.PEX = path
    o = T.step("typical", 27, vsrc, 400e-12, 0.0, tag=f"_{name.replace('/', '_')}", t1=1.5e-3, tend=1.6e-3)
    st = o["_st"]
    real = st[np.r_[True, np.diff(st) > 2e-6]]
    print(f"{name:18s} crossings {len(st)} spikes {len(real)} ISI {np.mean(np.diff(real))*1e6:.1f} us", flush=True)
