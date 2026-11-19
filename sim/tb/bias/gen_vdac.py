#!/usr/bin/env python3
"""V-DAC testbenches (vref_string64 + vdac6).

usage: gen_vdac.py OUT.cir --corner tt --temp 27 --mode dc|tran|reset [--ndac 3] [--vdd 3.3]
 dc    : all 64 codes, echo "D code v(out1)"  (3 vdac6 share one string, the others at code 0/63)
 tran  : code 0 -> 63 -> 32 -> 31 steps into 1 pF + 20 nfet gate loads (W=2u L=1u)
 reset : code 10 (~0.57 V) line, 20 neurons of 200 fF at 1.5 V are switched onto it for 2 us
"""
import argparse
from gen_idac import CORNER, P

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
ap.add_argument("--mode", default="dc"); ap.add_argument("--vdd", type=float, default=3.3)
a = ap.parse_args()
mos, res, mim = CORNER[a.corner]
taps = " ".join(f"t{k}" for k in range(64))
L = [f"* B1 vdac {a.mode} corner={a.corner} temp={a.temp}", f".include {P}/design.ngspice",
     f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
     ".include /work/cells/bias/bias_all.spice", f".temp {a.temp}",
     ".option gmin=1e-15 reltol=1e-5", f"Vdd vdd 0 {a.vdd}",
     "Ven en_b 0 0", f"Xs {taps} en_b vdd 0 vref_string64"]
def bits(name, code):
    return [f"V{name}{b} {name}{b} 0 {a.vdd if (code >> b) & 1 else 0}" for b in range(6)]
def dac(i, cn, out):
    return f"Xd{i} {out} {taps} " + " ".join(f"{cn}{b}" for b in range(6)) + " vdd 0 vdac6"
L += bits("k", 0) + bits("x", 63)
L.append(dac(2, "x", "o2")); L.append("Co2 o2 0 1p")
if a.mode == "dc":
    L += bits("c", 0); L.append(dac(1, "c", "o1")); L.append("Co1 o1 0 1p")
    L += [".control", "set noaskquit"]
    for code in range(64):
        for b in range(6):
            L.append(f"alter vc{b} {a.vdd if (code >> b) & 1 else 0}")
        L += ["op", f'echo "D {code}" $&v(o1) $&v(t{code})', "destroy all"]
    L += ["quit", ".endc", ".end"]
else:
    if a.mode == "tran":
        seq = [(0, 0), (5e-6, 63), (15e-6, 32), (25e-6, 31)]; tstop = "35u"
    else:
        seq = [(0, 10)]; tstop = "30u"
    for b in range(6):
        v0 = a.vdd if (seq[0][1] >> b) & 1 else 0
        pw = [f"0 {v0}"]; prev = v0
        for t, c in seq[1:]:
            v = a.vdd if (c >> b) & 1 else 0
            pw.append(f"{t:g} {prev} {t + 2e-9:g} {v}"); prev = v
        L.append(f"Vc{b} c{b} 0 PWL({' '.join(pw)})")
    L.append(dac(1, "c", "o1")); L.append("Cl o1 0 1p")
    for k in range(20):
        L.append(f"XG{k} 0 o1 0 0 nfet_03v3 W=2u L=1u")
    if a.mode == "reset":
        L.append(f"Vrst rst 0 PWL(0 0 10u 0 10.01u {a.vdd} 12u {a.vdd} 12.01u 0)")
        for k in range(20):
            L.append(f"Cm{k} m{k} 0 200f IC=1.5")
            L.append(f"XS{k} m{k} rst o1 0 nfet_03v3 W=1u L=0.28u")
    L += [".control", "set noaskquit", f"tran 5n {tstop}" + (" uic" if a.mode == "reset" else ""),
          "set wr_singlescale", "set wr_vecnames",
          f"wrdata {a.out[:-4]}.dat v(o1)" + (" v(m0)" if a.mode == "reset" else ""),
          "quit", ".endc", ".end"]
open(a.out, "w", newline="\n").write("\n".join(L) + "\n")
