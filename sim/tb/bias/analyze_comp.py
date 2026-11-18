#!/usr/bin/env python3
"""Compliance: current at Vout 0.5/1.0/2.5 V relative to 1.0 V; and the Vout window where |dI/I|<2 %."""
import sys, glob, os
import numpy as np
print("case            pol  I(1.0V)    I(0.5)/I(1)  I(2.5)/I(1)  window(+-2%)")
for fn in sorted(glob.glob(os.path.join(sys.argv[1], "comp_*.log"))):
    V = []; N = []; Pp = []
    for l in open(fn):
        t = l.split()
        if t and t[0] == "V":
            V.append(float(t[2])); N.append(abs(float(t[3]))); Pp.append(abs(float(t[4])))
    V = np.array(V)
    for pol, I in (("n", np.array(N)), ("p", np.array(Pp))):
        if len(I) == 0: continue
        i1 = np.interp(1.0, V, I); ok = np.abs(I / i1 - 1) < 0.02
        lo = V[ok].min() if ok.any() else np.nan; hi = V[ok].max() if ok.any() else np.nan
        print(f"{os.path.basename(fn)[5:-4]:15s} {pol}  {i1:9.3e}  {np.interp(0.5, V, I)/i1:8.3f}    "
              f"{np.interp(2.5, V, I)/i1:8.3f}    {lo:.2f}-{hi:.2f} V")
