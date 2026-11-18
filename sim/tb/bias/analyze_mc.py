#!/usr/bin/env python3
"""Mismatch MC summary for idac: sigma/mean per code, split into die-common (ladder/diode/master)
and instance-to-instance (idac units) parts; monotonicity yield and DNL distribution."""
import sys, glob, os
import numpy as np
from analyze_idac import parse, metrics
d = sys.argv[1]
runs = [parse(f)[0] for f in sorted(glob.glob(os.path.join(d, "idac_mc_*.log")))]
runs = [r for r in runs if r]
nk = len(runs[0][(1, 0)]); ni = nk // 2
print(f"{len(runs)} MC runs x {ni} instances per polarity (tt, 27 C, Vout=1.0 V)")
for pol, off in (("n", 0), ("p", ni)):
    for r in (1, 3, 4):
        A = np.array([[[run[(r, c)][off + i] for c in range(32)] for i in range(ni)] for run in runs])  # run,inst,code
        mean = A.mean(axis=(0, 1))
        tot = A.std(axis=(0, 1)) / mean
        inst = (A[:, 0, :] - A[:, 1, :]).std(axis=0) / np.sqrt(2) / mean
        common = A.mean(axis=1).std(axis=0) / mean
        mono = 0; dmin = []
        for run in A:
            for inst_ in run:
                lsb, dnl, inl, m = metrics(inst_); mono += m; dmin.append(dnl.min())
        dmin = np.array(dmin)
        print(f"idac_{pol} range {r}: LSB mean {mean[1]:.3e}  monotonic {mono}/{A.shape[0]*A.shape[1]}  "
              f"DNLmin median {np.median(dmin):.2f} worst {dmin.min():.2f}")
        for c in (1, 2, 4, 8, 10, 16, 19, 20, 31):
            print(f"   code {c:2d}: mean {mean[c]:.3e}  sigma/I total {100*tot[c]:5.1f}%  "
                  f"instance {100*inst[c]:5.1f}%  die-common {100*common[c]:5.1f}%")
