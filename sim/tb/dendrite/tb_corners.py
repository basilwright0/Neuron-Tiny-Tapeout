"""D1 key numbers over corners (typical/ff/ss/fs/sf x 0/27/85 C), S = 100.

usage: python3 sim/tb/dendrite/tb_corners.py [workers]   (default 2; the repo limit is 3 jobs total)
Runs tb_transfer.py (star) and tb_plateau.py ramp,pulse per case, then writes
sim/results/dendrite/corners_summary.txt.  vsrc is calibrated per corner (per-die calibration of
the shared AH rail, as for the array); vsrcp = vsrc (no trim).
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import OUT, CORNERS, TEMPS  # noqa

nw = int(sys.argv[1]) if len(sys.argv) > 1 else 2
cases = [(c, t) for c in CORNERS for t in TEMPS]


def one(ct):
    c, t = ct
    for cmd in (["python3", "sim/tb/dendrite/tb_transfer.py", c, str(t), "star"],
                ["python3", "sim/tb/dendrite/tb_plateau.py", c, str(t), "ramp,pulse"]):
        p = subprocess.run(cmd, cwd="/work", capture_output=True, text=True)
        if p.returncode:
            print("FAIL", cmd, p.stderr[-2000:], flush=True)
    print("done", c, t, flush=True)


if "summary" not in sys.argv:
    with ThreadPoolExecutor(nw) as ex:
        list(ex.map(one, cases))

L = ["D1 corners, S = 100 (vsrc calibrated per corner; transfer = star, g_ax = 4 nS)",
     "corner  T   R11/m  R01/m  att(d1->s) | thr d1: mV>EL  mV>rest  I(pA) | thr d2 mV>EL | T_plat(us) det/>250mV"
     " | d1 plat +mV  soma +mV (passive soma) | burst spikes | vep  vsrc"]
for c, t in cases:
    try:
        x = json.loads((OUT / f"xfer_{c}_{t}_star_4.json").read_text())
        p = json.loads((OUT / f"plateau_{c}_{t}_ramp-pulse.json").read_text())
    except FileNotFoundError:
        L.append(f"{c:7s} {t:3d}  missing")
        continue
    R, Rm = x["R"], x["Rm"]
    a = R[0][1] / R[1][1]
    td1, td2 = p["thr_d1"], p["thr_d2"]
    ps, pp = p["pulse_spk"], p["pulse_pas"]
    L.append(f"{c:7s} {t:3d}  {R[1][1]/Rm[1][1]:5.3f}  {R[0][1]/Rm[0][1]:5.3f}  {a:6.3f}     | "
             f"{td1['v_el']*1e3:7.1f}  {td1['v_rest']*1e3:7.1f}  {td1['i']*1e12:5.0f} | {td2['v_el']*1e3:7.1f}     | "
             f"{pp['t_detect']*1e6:6.0f} / {pp['t_above250']*1e6:6.0f}       | {pp['d1_max']*1e3:6.0f}  {pp['vs_max']*1e3:6.0f}"
             f"                  | {ps['nspk']:3d}          | {pp['vep']:.3f} {p['vsrc_cal']:.3f}")
txt = "\n".join(L)
print(txt)
(OUT / "corners_summary.txt").write_text(txt + "\n")
