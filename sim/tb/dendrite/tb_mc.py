"""Mismatch Monte Carlo of the D1 plateau threshold (typical, 27 C, S = 100).

usage: python3 sim/tb/dendrite/tb_mc.py [nseeds=30] [workers=2]
Per seed: tb_plateau.py ramp with sw_stat_mismatch=1 (.option seed).  vsrc stays at the typical
calibration (one shared rail per die), vsrcp = vsrc.  Writes sim/results/dendrite/mc_summary.txt.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import OUT  # noqa

n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
nw = int(sys.argv[2]) if len(sys.argv) > 2 else 2


def one(s):
    f = OUT / f"plateau_typical_27_mc{s}_ramp.json"
    if not f.exists():
        subprocess.run(["python3", "sim/tb/dendrite/tb_plateau.py", "typical", "27", "ramp", str(s)],
                       cwd="/work", capture_output=True, text=True)
    print("seed", s, flush=True)


if "summary" not in sys.argv:
    with ThreadPoolExecutor(nw) as ex:
        list(ex.map(one, range(1, n + 1)))
rows = []
for s in range(1, n + 1):
    f = OUT / f"plateau_typical_27_mc{s}_ramp.json"
    if f.exists():
        p = json.loads(f.read_text())
        rows.append([p["thr_d1"]["v_el"], p["thr_d1"]["v_rest"], p["thr_d1"]["i"],
                     p["thr_d2"]["v_el"], p["thr_d2"]["v_rest"], p["thr_d2"]["i"]])
a = np.array(rows) * np.array([1e3, 1e3, 1e12] * 2)
ok = np.all(np.isfinite(a), axis=1)
a = a[ok]
L = [f"D1 plateau threshold, mismatch MC, typical 27 C, {len(a)} seeds ({(~ok).sum()} without a trigger)",
     "quantity                        mean     sigma    min      max"]
names = ["d1 thr (mV above EL)", "d1 thr (mV above own rest)", "d1 trigger current (pA)",
         "d2 thr (mV above EL)", "d2 thr (mV above own rest)", "d2 trigger current (pA)"]
for k, nm in enumerate(names):
    L.append(f"{nm:30s} {a[:, k].mean():8.1f} {a[:, k].std(ddof=1):8.2f} {a[:, k].min():8.1f} {a[:, k].max():8.1f}")
com = (a[:, 0] + a[:, 3]) / 2
dif = a[:, 0] - a[:, 3]
L.append(f"{'common (d1+d2)/2 (mV>EL)':30s} {com.mean():8.1f} {com.std(ddof=1):8.2f}")
L.append(f"{'difference d1-d2 (mV)':30s} {dif.mean():8.1f} {dif.std(ddof=1):8.2f}")
TR = 47.5   # trim_gap4w (lr 0.6u) half span at 27 C with the 2026-11-19 OTA and EL 1.3 V: -41.4 .. +53.6 mV
for k, nm in ((1, "d1"), (4, "d2")):
    g = a[:, k] - a[:, k].mean()
    sg = g.std(ddof=1)
    L.append(f"{nm}: per-subunit gap trim covers +-{TR:.0f} mV = +-{TR / sg:.2f} sigma of threshold-above-rest; "
             f"{np.mean(np.abs(g) <= TR) * 100:.0f} % of seeds inside; +-3 sigma needs +-{3 * sg:.0f} mV")
L.append("Each subunit has its own trim (d1 nibble 7, d2 nibble 8); the trimmed quantity is threshold - rest.")
txt = "\n".join(L)
print(txt)
(OUT / "mc_summary.txt").write_text(txt + "\n")
