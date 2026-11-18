#!/usr/bin/env python3
"""Settling testbench: idac_n at the 150 pA design point (range 3, code 19).

usage: gen_settle.py OUT.cir --corner tt --temp 27 --c0 18 --c1 19 [--cline 1p] [--held]

At t=0.2 ms the fine code steps c0 -> c1.  The idac output feeds a 16-unit pfet
receiving diode (trim_ref_p) whose gate line carries --cline plus 20 trim4_p loads
(code 8 = 1.00x, outputs held at 1 V).  i(vt1) is the current one neuron sees.
With --held the idac output is instead held at 1.0 V by a voltage source (intrinsic
switching glitch of the DAC only).
"""
import argparse
from gen_idac import header, chain, P

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
ap.add_argument("--c0", type=int, default=18); ap.add_argument("--c1", type=int, default=19)
ap.add_argument("--r", type=int, default=3); ap.add_argument("--cline", default="1p")
ap.add_argument("--held", action="store_true"); ap.add_argument("--tstop", default="4m")
a = ap.parse_args()
a.seed = 0; a.iref = 8e-6; a.m = 1; a.noshift = False
L = header(a, "B1 idac settling") + chain(a)
for r in range(6):
    L.append(f"Vr{r} r{r} 0 {3.3 if r == a.r else 0}")
L.append("Vroff roff 0 0")
t0 = 0.2e-3
for b in range(5):
    v0 = 3.3 if (a.c0 >> b) & 1 else 0; v1 = 3.3 if (a.c1 >> b) & 1 else 0
    L.append(f"Vb{b} b{b} 0 PWL(0 {v0} {t0} {v0} {t0+5e-9} {v1})")
sel = " ".join(f"r{r}" for r in range(6)) + " roff " + " ".join(f"b{b}" for b in range(5))
L.append(f"XN1 on1 vdd {sel} " + " ".join(f"vgn{r}" for r in range(6)) + " vsn vglp vdd 0 idac_n")
if a.held:
    L.append("Von1 on1 0 1.0")
else:
    L.append("Von1 on1 vgline 0")
    L.append("Xrx vgline vsp vdd trim_ref_p")
    L.append(f"Cline vgline vdd {a.cline}")
    for k in range(20):
        L.append(f"Xt{k} t{k} vgline vsp 0 0 0 vdd vdd 0 trim4_p")
        L.append(f"Vt{k} t{k} 0 1.0")
L += [".control", "set noaskquit", f"tran 1u {a.tstop} 0 2u uic" if False else f"tran 1u {a.tstop}",
      "let iout=-i(von1)" if a.held else "let iout=i(vt1)",
      "set wr_singlescale", "set wr_vecnames",
      f"wrdata {a.out[:-4]}.dat iout", "quit", ".endc", ".end"]
open(a.out, "w", newline="\n").write("\n".join(L) + "\n")
