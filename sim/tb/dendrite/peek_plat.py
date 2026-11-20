"""Peek plateau pulse traces: detector edges and timer node for given tags."""
import sys
import numpy as np
for tag in sys.argv[1:]:
    for mode in ("pas", "spk"):
        f = f"/work/sim/results/dendrite/pulse_{mode}_{tag}.dat"
        d = np.genfromtxt(f, names=True)
        n = d.dtype.names
        t = d[n[0]]
        g = lambda s: d[[k for k in n if s in k][0]]
        xb, vt, d1, vs = g("xp1_xb") if any("xp1_xb" in k for k in n) else g("xp1xb"), g("vt"), d["vd1"], d["vvs"]
        hi = xb > 1.65
        e = np.flatnonzero(np.diff(hi.astype(int)))
        print(tag, mode, "xb edges (ms):", np.round(t[e] * 1e3, 3)[:12])
        for tt in (2.2e-3, 2.8e-3, 3.4e-3, 3.8e-3, 4.1e-3, 4.4e-3, 5e-3):
            k = np.searchsorted(t, tt)
            print(f"   t={tt*1e3:.1f} ms vt={vt[k]:.2f} d1={d1[k]:.3f} vs={vs[k]:.3f} xb={xb[k]:.2f}")
