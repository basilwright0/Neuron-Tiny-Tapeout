#!/usr/bin/env python3
"""C-V of 3.3 V MOS gate caps (S=D=B tied) to pick decap orientations for the shifted rails.
usage: python3 cv_moscap.py  (inside the EDA container, from sim/tb/bias)"""
import subprocess, os
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
out = []
for model in ("nfet_03v3", "pfet_03v3"):
    deck = f"""* cv {model}
.include {P}/design.ngspice
.lib {P}/sm141064.ngspice typical
Vg g 0 0 AC 1
Vb b 0 0
X1 b g b b {model} W=10u L=10u
.control
set noaskquit
foreach v -3.0 -2.0 -1.0 -0.6 -0.3 0 0.3 0.6 1.0 2.0 3.0
  alter vg dc = $v
  ac lin 1 1e6 1e6
  let c = -imag(i(vg))/(2*3.14159265*1e6)
  echo "CV {model} $v" $&c
end
quit
.endc
.end
"""
    r = subprocess.run(["ngspice", "-b"], input=deck, capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("CV"):
            t = ln.split()
            out.append(f"{t[1]} Vgb={float(t[2]):+.1f} V  C={float(t[3])*1e15/100:.2f} fF/um^2")
open("out/recheck/cv_moscap.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
