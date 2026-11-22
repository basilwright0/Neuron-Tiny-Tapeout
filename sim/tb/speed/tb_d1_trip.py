"""Level 3 D1: static plateau-detector (pdet) trip vs the soma detector (det_ah) trip at speed S.

usage: python3 sim/tb/speed/tb_d1_trip.py <S,S,...> [corner:temp,...] [netlist]
vsrc calibrated per corner/S (dcommon.cal_vsrc: det_ah trip = VTH 1.38 V), I_st = 100 nA * max(1, S/100).
Slow triangle on vd (1.25 -> 1.55 -> 1.25 V, 2 ms * 100/S each way; a DC sweep lands on the latched branch inside
the hysteresis band) on pdet (default cells/dendrite/dendrite.spice) and det_ah: trip / release - soma trip (mV).
Output dir: $D1_OUT (default /work/sim/results/speed).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402,F401
import ngs  # noqa: E402
if os.environ.get("D1_OUT"):
    ngs.RESULTS = Path(os.environ["D1_OUT"])
    (ngs.RESULTS / "dendrite").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa: E402,F403

SS = [float(x) for x in sys.argv[1].split(",")]
CASES = [(c.split(":")[0], int(c.split(":")[1])) for c in
         (sys.argv[2] if len(sys.argv) > 2 else "typical:27,ss:0,ff:27").split(",")]
NET = sys.argv[3] if len(sys.argv) > 3 else str(ngs.CELLS / "dendrite/dendrite.spice")
TAG = os.environ.get("D1_TAG", "")

for S in SS:
    for corner, temp in CASES:
        vc = cal_vsrc(corner, temp, S)
        body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
.include {NET}
Vdd vdd 0 3.3
Vsr vsrc 0 {vc}
Ibs vbs 0 {100e-9 * max(1, S / 100)}
Xbs vbs vdd pmaster w=1u l=2u
Vm vd 0 pwl(0 1.25 {2e-3 * 100 / S} 1.55 {4e-3 * 100 / S} 1.25)
Xp vd xb vsrc vbs vdd 0 pdet
Xd vd spk vsrc vbs vdd 0 det_ah
"""
        k = 100 / S
        r = run(deck(body, f"tran {0.2e-6 * k} {4e-3 * k}", ["v(xb)", "v(spk)", "v(vd)"], corner=corner, temp=temp),
                f"pdtrip_{corner}_{temp}_S{S:g}{TAG}")
        t, vd = r["_x"], r["v(vd)"]
        nan = float("nan")
        f = lambda x: float(np.interp(x[0], t, vd)) if len(x) else nan  # noqa: E731
        tr, rl = f(crossings(t, r["v(xb)"], 1.65)), f(crossings(t, r["v(xb)"], 1.65, rising=False))
        ts = f(crossings(t, r["v(spk)"], 1.65))
        print(f"pdet{TAG} S={S:g} {corner:7s} {temp:3d}: vsrc {vc:.4f}  soma trip {ts:.4f} V  pdet trip {tr:.4f} V "
              f"= soma {(tr - ts) * 1e3:+.1f} mV (EL +{(tr - EL) * 1e3:.1f})  release {(rl - ts) * 1e3:+.1f} mV "
              f"(hyst {(tr - rl) * 1e3:.1f})", flush=True)
