"""vsrc buffer offset Monte Carlo (device mismatch, incl. the R1 receiver), 27 C.

  python3 sim/tb/vsrc/mc_offset.py [N] [corner]      (default 40 seeds, typical)

Each seed: DC sweep of the closed-loop buffer vin 0.35..0.75 V (no load and 32 uA sink load);
offset = vsrc - vin at 0.35/0.55/0.75 V. Also re-run at 0 and 85 C with the same seed to show the
offset drift (what a once-per-die calibration does not remove).
"""
import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
CORNER = sys.argv[2] if len(sys.argv) > 2 else "typical"
body = f"""{include('vsrc/vsrc_buf.spice')}
Vdd vdd 0 3.3
Ib vbp 0 4u
XPR vbp vbp vdd vdd pfet_03v3 W=0.4u L=1u
Vin vin 0 0.55
Xb vin vsrc vbp vdd 0 vsrc_buf
Cl vsrc 0 100f
"""
VS = (0.35, 0.55, 0.75)
rows = []
for s in range(1, N + 1):
    row = []
    for T in (27, 0, 85):
        d = deck(body, "dc Vin 0.30 0.80 0.01", ["v(vsrc)"], mismatch=True, seed=s, corner=CORNER, temp=T)
        r = run(d, f"vsrc_mc_s{s}_{T}")
        row += [1e3 * (np.interp(v, r["_x"], r["v(vsrc)"]) - v) for v in VS]
    rows.append(row)
    print(f"seed {s:3d}  27C " + " ".join(f"{o:+6.2f}" for o in row[:3]) + "   0C " +
          " ".join(f"{o:+6.2f}" for o in row[3:6]) + "   85C " + " ".join(f"{o:+6.2f}" for o in row[6:]) + "  mV",
          flush=True)
a = np.array(rows)
print(f"\nN = {N} seeds, {CORNER} (offset = vsrc - vth_ref, mV)")
for k, v in enumerate(VS):
    print(f"vin {v:.2f} V, 27 C: mean {a[:, k].mean():+6.2f}  sigma {a[:, k].std(ddof=1):5.2f}  "
          f"min {a[:, k].min():+6.2f}  max {a[:, k].max():+6.2f}")
for k, v in enumerate(VS):
    dr = np.maximum(np.abs(a[:, 3 + k] - a[:, k]), np.abs(a[:, 6 + k] - a[:, k]))
    print(f"vin {v:.2f} V: per-seed drift vs 27 C over 0..85 C: sigma {np.std(a[:, 6 + k] - a[:, 3 + k], ddof=1):5.2f}  max |drift| {dr.max():5.2f}")
