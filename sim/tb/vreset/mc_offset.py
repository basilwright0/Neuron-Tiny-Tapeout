"""Vreset buffer offset Monte Carlo (device mismatch only, typical corner, 27 C).

  python3 sim/tb/vreset/mc_offset.py [N]        (default N = 40 seeds)

Each seed: DC sweep of the closed-loop follower vin 0.9..1.5 V, offset = vout - vin at 0.9/1.2/1.5 V.
Bias: receiver W0.4/L1 fed 4 uA (ib_r1), as in tb_vreset.py; receiver mismatch included (it only
moves the tail current).  Output: sim/tb/vreset/out/vreset_mc.txt (written by the caller's redirect).
"""
import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
body = f"""{include('vreset/vreset_buf.spice')}
Vdd vdd 0 3.3
Ib vbp 0 4u
XPD vbp vbp vdd vdd pfet_03v3 W=0.4u L=1u
Vin vin 0 1.2
Xb vin vout vbp vdd 0 vreset_buf
Cl vout 0 250f
"""
VS = (0.9, 1.2, 1.5)
rows = []
for s in range(1, N + 1):
    d = deck(body, "dc Vin 0.9 1.5 0.05", ["v(vout)"], mismatch=True, seed=s)
    r = run(d, f"vr_mc_s{s}")
    rows.append([1e3 * (np.interp(v, r["_x"], r["v(vout)"]) - v) for v in VS])
    print(f"seed {s:3d}  " + "  ".join(f"{o:+7.2f}" for o in rows[-1]) + "  mV", flush=True)
a = np.array(rows)
print(f"\nN = {N} seeds, typical, 27 C (offset = vout - vin, mV)")
for k, v in enumerate(VS):
    print(f"vin {v:.1f} V: mean {a[:, k].mean():+6.2f}  sigma {a[:, k].std(ddof=1):5.2f}  "
          f"min {a[:, k].min():+6.2f}  max {a[:, k].max():+6.2f}")
