"""A1 sizing check: decay current Itau of candidate nfet stacks (gate vbn_leak, drain 0.45 V), typical 27 C.
usage: python3 sim/tb/tier2/tb_itau.py"""
import sys
sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
import re, subprocess
from ngs import header
C = {"s6_05x10": [(0.5, 10)] * 6, "s8_022x5": [(0.22, 5)] * 8, "s4_022x10": [(0.22, 10)] * 4,
     "s3_022x15": [(0.22, 15)] * 3, "s4_05x10": [(0.5, 10)] * 4, "s4_022x5": [(0.22, 5)] * 4, "s5_05x9": [(0.5, 9)] * 5, "s3_05x10": [(0.5, 10)] * 3,
     "s2_1x10": [(1, 10)] * 2, "one_022x5": [(0.22, 5)], "one_2x4": [(2, 4)], "s4_1x10": [(1, 10)] * 4}
L = [header(), include("neuron/membrane.spice"), "Ibl 0 vb 324p", "Xbl vb 0 nmaster"]
for k, st in C.items():
    L.append(f"V{k} d{k} 0 0.45")
    n = f"d{k}"
    for i, (w, l) in enumerate(st):
        nxt = "0" if i == len(st) - 1 else f"{k}_{i}"
        L.append(f"X{k}_{i} {n} vb {nxt} 0 nfet_03v3 W={w}u L={l}u")
        n = nxt
txt = "\n".join(L) + "\n.control\nop\n" + "\n".join(f"print -i(V{k})" for k in C) + "\nprint v(vb)\nquit\n.endc\n.end\n"
p = OUT / "itau.cir"; p.write_text(txt)
r = subprocess.run(["ngspice", "-b", str(p)], cwd=OUT, capture_output=True, text=True)
for ln in r.stdout.splitlines():
    if "=" in ln and ("i(" in ln or "v(vb)" in ln):
        print(ln)
