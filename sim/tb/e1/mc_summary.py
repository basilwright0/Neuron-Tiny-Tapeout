"""Summary of the e1_fb MC (sim/results/e1/mc_*.json from tb_e1.py mc): mean, sigma, relative spread, 5-95 % range.
usage: python3 sim/tb/e1/mc_summary.py  -> sim/results/e1/mc_summary.txt"""
import glob
import json
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2] / "results" / "e1"
rows = []
for f in sorted(glob.glob(str(R / "mc_*.json"))):
    rows += json.load(open(f))
ok = [r for r in rows if "error" not in r and np.isfinite(r.get("tau", np.nan))]
L = [f"e1_fb MC: {len(ok)} of {len(rows)} dies (statistical corner: global process + mismatch, one seed per die, "
     f"typical 27 C, S = 100)", "", f"{'param':10s} {'mean':>10s} {'sigma':>10s} {'sigma/mean':>10s} {'p5':>10s} "
     f"{'p95':>10s} {'min':>10s} {'max':>10s}"]
for k, sc, u in (("tau", 1e6, "us"), ("t_ref", 1e6, "us"), ("gap", 1e3, "mV"), ("rheo", 1e12, "pA"), ("EL", 1, "V"),
                 ("Vth", 1, "V"), ("g", 1e9, "nS"), ("rate2", 1e-3, "kHz"), ("rateA", 1e-3, "kHz"), ("rate50", 1e-3, "kHz")):
    v = np.array([r[k] for r in ok if k in r and np.isfinite(r[k])]) * sc
    if not len(v):
        continue
    L.append(f"{k + ' [' + u + ']':14s} {v.mean():9.3f} {v.std():10.3f} {100 * v.std() / abs(v.mean()):9.1f}% "
             f"{np.percentile(v, 5):10.3f} {np.percentile(v, 95):10.3f} {v.min():10.3f} {v.max():10.3f}")
bad = [r["seed"] for r in rows if r not in ok]
L.append("")
L.append(f"failed dies: {bad}" if bad else "no failed dies")
(R / "mc_summary.txt").write_text("\n".join(L) + "\n")
print("\n".join(L))
