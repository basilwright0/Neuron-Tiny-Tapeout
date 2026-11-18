#!/usr/bin/env python3
"""trim4_p testbench: a 16-unit trim_ref_p diode carries I_ref (drawn by an ideal sink);
NT trim4_p cells (outputs at 1.0 V) are swept over codes 0..15.
usage: gen_trim.py OUT.cir --corner tt --temp 27 --iref 1n [--seed N] [--nt 4]
echo: "D code I1..INT"
"""
import argparse
from gen_idac import CORNER, P

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
ap.add_argument("--iref", default="1n"); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--nt", type=int, default=4)
a = ap.parse_args()
mos, res, mim = CORNER[a.corner]
L = [f"* B1 trim corner={a.corner} temp={a.temp} iref={a.iref} seed={a.seed}", f".include {P}/design.ngspice"]
if a.seed:
    L += [".param sw_stat_mismatch=1", f".option seed={a.seed}"]
L += [f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
      ".include /work/cells/bias/bias_all.spice", f".temp {a.temp}",
      ".option gmin=1e-18 abstol=1e-17 reltol=1e-5", "Vdd vdd 0 3.3", "Vsp vsp 0 3.0",
      f"Iin vg 0 {a.iref}", "Xref vg vsp vdd trim_ref_p"]
for b in range(4):
    L.append(f"Vc{b} c{b} 0 0")
for k in range(1, a.nt + 1):
    L.append(f"Xt{k} o{k} vg vsp c0 c1 c2 c3 vdd 0 trim4_p"); L.append(f"Vo{k} o{k} 0 1.0")
L += [".control", "set noaskquit"]
for c in range(16):
    for b in range(4):
        L.append(f"alter vc{b} {3.3 if (c >> b) & 1 else 0}")
    L += ["op", f'echo "D {c}" ' + " ".join(f"$&i(vo{k})" for k in range(1, a.nt + 1)), "destroy all"]
L += ["quit", ".endc", ".end"]
open(a.out, "w", newline="\n").write("\n".join(L) + "\n")
