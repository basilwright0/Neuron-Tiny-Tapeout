#!/usr/bin/env python3
"""Post-layout spot check summary (typical, 27 C): PEX vs schematic idac / vdac."""
import os
import numpy as np
from analyze_idac import metrics

out = []
f = "out/postlayout/idac.log"
if os.path.exists(f):
    D = {}
    for ln in open(f):
        t = ln.split()
        if t and t[0] == "D":
            D[(int(t[1]), int(t[2]))] = [abs(float(x)) for x in t[3:]]
    out.append("== idac code sweep, tt 27 C, outputs at 1 V: schematic vs layout (PEX, C-coupling to all nets)")
    for r in (0, 3):
        for j, name in ((0, "idac_n sch"), (2, "idac_n pex"), (1, "idac_p sch"), (3, "idac_p pex")):
            I = [D[(r, c)][j] for c in range(32)]
            lsb, dnl, inl, mono = metrics(I)
            out.append(f"range {r} {name}: LSB {lsb:.4g} A  FS {I[31]:.4g} A  DNL {dnl.min():+.3f}/{dnl.max():+.3f}"
                       f"  |INL| {np.abs(inl).max():.3f}  mono {'Y' if mono else 'N'}  code0 {I[0]:.3g}")
        for jp, js, name in ((2, 0, "n"), (3, 1, "p")):
            rat = [D[(r, c)][jp] / D[(r, c)][js] for c in range(1, 32)]
            out.append(f"range {r} idac_{name}: pex/sch per code {min(rat):.4f} .. {max(rat):.4f}")
f = "out/postlayout/vdac.log"
if os.path.exists(f):
    D = []
    for ln in open(f):
        t = ln.split()
        if t and t[0] == "D":
            D.append((int(t[1]), float(t[2]), float(t[3])))
    if D:
        v = np.array([d[1] for d in D]); x = np.array([d[2] for d in D])
        out.append("\n== vdac6 DC, tt 27 C: schematic vs layout (PEX), same string")
        out.append(f"V0 {v[0]:.4f}/{x[0]:.4f}  V63 {v[-1]:.4f}/{x[-1]:.4f}  max |pex-sch| {1e6*np.abs(x-v).max():.1f} uV"
                   f"  pex monotonic {'Y' if np.all(np.diff(x) > 0) else 'N'}")
f = "out/postlayout/vdactran.dat"
if os.path.exists(f):
    a = np.loadtxt(f, skiprows=1)
    t, vs, vx = a[:, 0], a[:, 1], a[:, 2]
    out.append("\n== vdac6 transient into 1 pF + 20 gates (code 0->63 at 5 us, ->32 at 15 us, ->31 at 25 us)")
    for t0, t1 in ((5e-6, 15e-6), (15e-6, 25e-6), (25e-6, 35e-6)):
        m = (t > t0) & (t < t1)
        res = []
        for y in (vs, vx):
            yy = y[m]; tt = t[m]; fin = yy[-1]
            bad = np.where(np.abs(yy - fin) > 13.9e-3)[0]
            res.append(((tt[bad[-1]] - t0) * 1e9 if len(bad) else 0, fin))
        out.append(f"step@{t0*1e6:.0f}us  t(0.5 LSB) sch {res[0][0]:6.0f} ns  pex {res[1][0]:6.0f} ns  final {res[0][1]:.4f}/{res[1][1]:.4f} V")
open("out/postlayout/summary.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
