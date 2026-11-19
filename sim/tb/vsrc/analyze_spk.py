"""Re-analyse saved spike runs (sim/results/vsrc_spk_*.dat) with a settle window that ends before the
spikers' next approach to threshold (refractory ~2 us at S = 1000).

  python3 sim/tb/vsrc/analyze_spk.py <glob-tag> [vin_ref_from_name]     e.g.  vsrc_buf_*_n4
Columns: peak / min at the far tap vs the pre-spike value, time back within 2 mV of the value
1.5 us after the spike, and the same within 5 mV.
"""
import sys, glob, os
import numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import crossings
for f in sorted(glob.glob(f"/work/sim/results/vsrc_spk_{sys.argv[1]}.dat")):
    hdr = open(f).readline().split()
    d = np.loadtxt(f, skiprows=1)
    col = {h: d[:, k] for k, h in enumerate(hdr)}
    t = d[:, 0]
    st = crossings(t, col["v(sp0)"], 1.65)
    st = st[st > 0.3e-6]
    name = os.path.basename(f)[10:-4]
    if not len(st):
        print(f"{name:40s} no spike"); continue
    ts = st[0]
    far = col["v(l3)"]
    v0 = np.interp(ts - 0.5e-6, t, far)
    vend = np.interp(ts + 1.5e-6, t, far)
    m = (t > ts - 0.3e-6) & (t < ts + 1.5e-6)
    aft = m & (t > ts)
    res = []
    for tol in (2e-3, 5e-3):
        bad = np.where(aft & (np.abs(far - vend) > tol))[0]
        res.append((t[bad[-1]] - ts) * 1e9 if len(bad) else 0.0)
    print(f"{name:40s} peak {1e3*(far[m].max()-v0):6.1f}  min {1e3*(far[m].min()-v0):6.1f} mV  "
          f"settled-pre {1e3*(vend-v0):+5.2f} mV  back<2mV {res[0]:5.0f} ns  back<5mV {res[1]:5.0f} ns")
