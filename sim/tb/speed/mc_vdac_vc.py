#!/usr/bin/env python3
"""MIL-319 item 2a: die-to-die mismatch of the vth_cmp DAC output (schematic bias_rails + bias_vi + vdacr_vc).

Per seed (sw_stat_mismatch = 1, .option seed = N; seed 0 = no mismatch) and corner: DC op at vth_cmp codes 24..29.
The other three DACs (el, vr, vt) load bias_vi at their S = 10000 codes, as on the chip.
  usage: python3 sim/tb/speed/mc_vdac_vc.py [N seeds, default 100] [corners, default tt,ss,ff]
  -> $FI_RESULTS (default sim/results/m3mc)/vdac_vc_mc_<corners>.json: {corner: {seed: {code: V}}}, and a sigma summary
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
LIBS = {"tt": ("typical", "res_typical", "typical", 27), "ss": ("ss", "res_ss", "ss", 0), "ff": ("ff", "res_ff", "ff", 85)}
DACS = {"el": 5, "vr": 5, "vc": 5, "vt": 6}
FIX = {"el": 25, "vr": 30, "vt": 48}     # r0 / r1 / v0 at the S >= 300 operating point (topbench.op_point)
CODES = [24, 25, 26, 27, 28, 29]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
CORNERS = (sys.argv[2] if len(sys.argv) > 2 else "tt,ss,ff").split(",")
OUT = Path(os.environ.get("FI_RESULTS", "/work/sim/results/m3mc"))
TMP = OUT / "vdac_mc"
TMP.mkdir(parents=True, exist_ok=True)


def deck(corner, seed):
    mos, res, dio, temp = LIBS[corner]
    L = [f"* vth_cmp DAC MC {corner} seed {seed}", f".include {P}/design.ngspice"]
    if seed:
        L.append(".param sw_stat_mismatch=1")
    L += [f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
          f".lib {P}/sm141064.ngspice diode_{dio}", ".include /work/cells/bias/bias_all.spice", f".temp {temp}"]
    if seed:
        L.append(f".option seed={seed}")
    L += [".option gmin=1e-15 reltol=1e-5", "Vdd vdd 0 3.3", "Ven en 0 3.3", "Venb en_b 0 0", "Vibx ib_x2 0 0",
          "Xr vsn vsp vgln vglp en_b vdd 0 bias_rails",
          "Xvi vgln vglp en ib_x2 el vr vc vt prb ibr iint vdd 0 bias_vi", "Vib ibr 0 2.5", "Rii iint 0 100k"]
    for k, nb in DACS.items():
        if k == "vc":
            bits = [f"c{b}" for b in range(nb)]
            L += [f"Vc{b} c{b} 0 0" for b in range(nb)]
        else:
            bits = [f"{k}b{b}" for b in range(nb)]
            L += [f"V{k}b{b} {k}b{b} 0 {3.3 if (FIX[k] >> b) & 1 else 0}" for b in range(nb)]
        L.append(f"X{k} {k} " + " ".join(bits) + f" vdd 0 vdacr_{k}")
    L += [".control", "set noaskquit"]
    for c in CODES:
        L += [f"alter vc{b} dc={3.3 if (c >> b) & 1 else 0}" for b in range(5)]
        L += ["op", f'echo "P {c}" $&v(vc)', "destroy all"]
    L += ["quit", ".endc", ".end"]
    return "\n".join(L) + "\n"


res = {}
for corner in CORNERS:
    res[corner] = {}
    for seed in range(N + 1):
        f = TMP / f"vc_{corner}_{seed}.cir"
        f.write_text(deck(corner, seed))
        r = subprocess.run(["ngspice", "-b", str(f)], capture_output=True, text=True, timeout=600)
        v = {}
        for ln in r.stdout.splitlines():
            t = ln.split()
            if len(t) == 3 and t[0] == "P":
                v[int(t[1])] = float(t[2])
        if len(v) != len(CODES):
            print(f"{corner} seed {seed}: parse failed\n" + r.stdout[-800:] + r.stderr[-800:], flush=True)
            continue
        res[corner][seed] = v
    nom = res[corner].get(0)
    print(f"{corner}: nominal " + " ".join(f"{c}:{nom[c]:.5f}" for c in CODES) if nom else f"{corner}: no nominal")
    if nom:
        d = np.array([[res[corner][s][c] - nom[c] for c in CODES] for s in res[corner] if s])
        st = np.array([[res[corner][s][c + 1] - res[corner][s][c] for c in CODES[:-1]] for s in res[corner] if s])
        print(f"  {len(d)} seeds: offset vs nominal (mV) sigma " + " ".join(f"{1e3 * x:.2f}" for x in d.std(0, ddof=1))
              + f"; max |offset| {1e3 * abs(d).max():.2f}; step (mV) mean {1e3 * st.mean():.2f} sigma "
              f"{1e3 * st.std(ddof=1):.3f} min {1e3 * st.min():.2f}", flush=True)
(OUT / f"vdac_vc_mc_{'_'.join(CORNERS)}.json").write_text(json.dumps(res, indent=0))
