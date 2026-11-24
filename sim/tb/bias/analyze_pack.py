#!/usr/bin/env python3
"""Summarise out/pack/pack_<c>_<t>.log: per DAC and variant: endpoints, LSB, INL/DNL (LSB), monotonicity,
and max |new - old| over all codes."""
import numpy as np
from pathlib import Path
D = Path(__file__).resolve().parent / "out/pack"
DACS = [("el", 32), ("vr", 32), ("vc", 32), ("vt", 64)]
out = ["corner temp dac | v0_old v0_new vfs_old vfs_new (V) | DNL_new min/max INL_new |max| (LSB) | mono_new | max|new-old| mV | DNL_old min/max"]
worst = 0
for c in ("tt", "ss", "ff"):
    for t in (0, 27, 85):
        rows = [ln.split() for ln in (D / f"pack_{c}_{t}.log").read_text().splitlines() if ln.startswith("P ")]
        a = np.array([[float(x) for x in r[2:]] for r in rows])
        for i, (k, n) in enumerate(DACS):
            s, o, nw = a[:n, 3 * i], a[:n, 3 * i + 1], a[:n, 3 * i + 2]
            def lin(v):
                lsb = (v[-1] - v[0]) / (n - 1)
                d = np.diff(v) / lsb - 1
                inl = (v - (v[0] + lsb * np.arange(n))) / lsb
                return lsb, d, inl
            lsb, d, inl = lin(nw); _, do, _ = lin(o)
            dmax = np.max(np.abs(nw - o)) * 1e3
            worst = max(worst, dmax)
            out.append(f"{c} {t:2d} {k} | {o[0]:.4f} {nw[0]:.4f} {o[-1]:.4f} {nw[-1]:.4f} | LSB {lsb*1e3:.2f} mV "
                       f"DNL {d.min():+.2f}/{d.max():+.2f} INL {np.abs(inl).max():.2f} | "
                       f"{'mono' if np.all(np.diff(nw) > 0) else 'NONMONO'} | {dmax:.3f} | {do.min():+.2f}/{do.max():+.2f}")
out.append(f"WORST max|new-old| over all corners, DACs, codes: {worst:.4f} mV")
(D / "pack_summary.txt").write_text("\n".join(out) + "\n")
print("\n".join(out))
