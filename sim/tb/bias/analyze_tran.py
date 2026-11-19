#!/usr/bin/env python3
"""Startup / settling numbers from out/revc/tran_*.dat (gen_revc.py tran)."""
import glob, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "revc")
NAMES = ["el", "vreset_src", "vth_cmp", "vth_ref", "vbn_prb", "ib_r1", "vgvi", "vglp", "vbp_st", "vbn_leak"]
for f in sorted(glob.glob(os.path.join(D, "tran_*.dat"))):
    rows = [list(map(float, l.split())) for l in open(f) if l.strip() and not l.startswith(("t", "T"))]
    t = [r[0] for r in rows]
    col = lambda k: [r[2 * k + 1] for r in rows]
    print(os.path.basename(f))
    for k, nm in enumerate(NAMES[:4]):
        v = col(k)
        def settle(t0, t1, tol):
            fin = [x for tt, x in zip(t, v) if t1 - 2e-6 <= tt <= t1]
            fin = sum(fin) / len(fin)
            last = t0
            for tt, x in zip(t, v):
                if t0 <= tt <= t1 and abs(x - fin) > tol:
                    last = tt
            return fin, (last - t0)
        lsb = 6.35e-3 if nm == "vth_ref" else 13e-3
        f0, s0 = settle(10e-6, 59.5e-6, lsb / 2)
        t1 = 79.5e-6 if nm == "vth_ref" else 79.5e-6
        tstep = 80e-6 if nm == "vth_ref" else 60e-6
        f1, s1 = settle(tstep, 99.5e-6 if nm == "vth_ref" else 79.5e-6, lsb / 2)
        print(f"  {nm:10s} startup -> {f0:.4f} V in {s0*1e6:5.2f} us (0.5 LSB); step -> {f1:.4f} V in {s1*1e6:5.2f} us")
