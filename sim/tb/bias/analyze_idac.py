#!/usr/bin/env python3
"""Summarise idac code sweeps: LSB/FS per range, step ratio, DNL/INL, monotonicity, code-0 floor."""
import sys, glob, os
import numpy as np

def parse(fn):
    D = {}; rails = None
    for l in open(fn):
        t = l.split()
        if not t: continue
        if t[0] == "RAILS": rails = [float(x) for x in t[1:]]
        if t[0] == "D":
            r, c = int(t[1]), int(t[2]); v = [abs(float(x)) for x in t[3:]]
            D[(r, c)] = v
    return D, rails

def metrics(I):
    """I: array(32) currents for codes 0..31 -> lsb, dnl, inl (end-point), monotonic"""
    I = np.asarray(I)
    lsb = (I[31] - I[0]) / 31
    st = np.diff(I) / lsb
    dnl = st - 1
    inl = (I - I[0]) / lsb - np.arange(32)
    return lsb, dnl, inl, bool(np.all(np.diff(I) > 0))

if __name__ == "__main__":
    d = sys.argv[1]
    files = sorted(glob.glob(os.path.join(d, "idac_*.log")))
    print("file  pol  r  I(code1)  FS(code31)  ratio(r-1/r)  DNLmin DNLmax |INL|max  mono  I(code0)")
    for fn in files:
        D, rails = parse(fn)
        name = os.path.basename(fn)[5:-4]
        if not D: print(name, "NO DATA"); continue
        nk = len(D[(0, 0)])
        for j, pol in ((0, "n"), (nk // 2, "p")):
            prev = None
            for r in range(6):
                if (r, 31) not in D: continue
                I = [D[(r, c)][j] for c in range(32)]
                lsb, dnl, inl, mono = metrics(I)
                ratio = prev / lsb if prev else float("nan"); prev = lsb
                print(f"{name:12s} {pol} {r} {I[1]:9.3e} {I[31]:9.3e} {ratio:6.2f} "
                      f"{dnl.min():6.2f} {dnl.max():6.2f} {abs(inl).max():5.2f} {'Y' if mono else 'N'} {I[0]:9.2e}")
        if rails: print(f"{name:12s} rails vsn={rails[0]:.3f} vsp={rails[1]:.3f} in_n={rails[4]:.3f} in_p={rails[5]:.3f} nd={rails[6]:.3f}")
