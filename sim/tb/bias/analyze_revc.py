#!/usr/bin/env python3
"""Summarise the B1 rev C DC suite (out/revc/*.log from run_revc_dc.sh)."""
import glob
import os
import re

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "revc")
LINES = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w"]


def parse(f):
    d, n, b, v = {}, {}, {}, {}
    for ln in open(f, errors="ignore"):
        t = ln.split()
        if not t:
            continue
        try:
            if t[0] == "D":
                d[(float(t[1]), int(t[2]))] = [abs(float(x)) for x in t[3:]]
            elif t[0] == "N":
                n[float(t[1])] = [float(x) for x in t[2:]]
            elif t[0] == "B":
                b[float(t[1])] = [float(x) for x in t[2:]]
            elif t[0] == "V":
                v[(float(t[1]), int(t[2]))] = [float(x) for x in t[3:]]
        except ValueError:
            pass
    return d, n, b, v


def key(f):
    m = re.match(r"(idac|vout)_(\w+?)_([\d.]+)_m(\d)", os.path.basename(f))
    return m.groups() if m else None


print("B1 rev C DC suite summary (sim/tb/bias/out/revc)\n")
print("== Current DACs, EXT /1: S = 10 / 100 / 1000 <-> Iref = 0.1 / 1 / 10 uA")
print("   LSB@S100 = I(16)/16 at Iref 1 uA [pA]; r10 = I16(S10)*10/I16(S100); r1000 = I16(S1000)/10/I16(S100);")
print("   c1/S10 = I(code 1) at S=10 / (I16(S10)/16)  (leakage check: 1.00 = clean); floor = code-0 current [fA]")
for f in sorted(glob.glob(os.path.join(D, "idac_*_m0.log"))):
    k = key(f)
    d, n, _, _ = parse(f)
    if (1e-6, 16) not in d:
        print(f"  {k}: incomplete"); continue
    print(f"  {k[1]} {k[2]:>2} C:")
    for j, ln in enumerate(LINES):
        lsb = d[(1e-6, 16)][j] / 16
        r10 = d[(1e-7, 16)][j] * 10 / d[(1e-6, 16)][j]
        r1k = d[(1e-5, 16)][j] / 10 / d[(1e-6, 16)][j]
        c1 = d[(1e-7, 1)][j] / (d[(1e-7, 16)][j] / 16)
        fl = max(d[(i, 0)][j] for i in (1e-7, 1e-6, 1e-5))
        codes = sorted(c for (i, c) in d if i == 1e-7)
        mono = all(d[(ir, a)][j] < d[(ir, b_)][j] for ir in (1e-7, 1e-6, 1e-5) for a, b_ in zip(codes, codes[1:]))
        print(f"    {ln:9s} LSB {lsb*1e12:8.1f} pA  FS {d[(1e-6, 31)][j]*1e9:7.2f} nA  r10 {r10:5.3f}  r1000 {r1k:5.3f}"
              f"  c1/S10 {c1:5.3f}  floor {fl*1e15:7.1f} fA  {'mono' if mono else 'NOT MONO'}")
    st = [d[(i, 0)][5] for i in (1e-7, 1e-6, 1e-5)]
    print(f"    vbp_st    I_nd/16 sink: {st[0]*1e9:.2f} / {st[1]*1e9:.2f} / {st[2]*1e9:.1f} nA;  "
          f"pad V {n[1e-7][1]:.3f} / {n[1e-6][1]:.3f} / {n[1e-5][1]:.3f} V")

print("\n== EXT /16 (Iref 1.6 / 16 / 160 uA) vs EXT /1 (0.1 / 1 / 10 uA), code 16, ratio per DAC; pad V")
for f in sorted(glob.glob(os.path.join(D, "idac_*_m1.log"))):
    k = key(f)
    f0 = f.replace("_m1", "_m0")
    if not os.path.exists(f0):
        continue
    d1, n1, _, _ = parse(f); d0, _, _, _ = parse(f0)
    out = []
    for i1, i0 in ((1.6e-6, 1e-7), (1.6e-5, 1e-6), (1.6e-4, 1e-5)):
        if (i1, 16) in d1 and (i0, 16) in d0:
            r = [d1[(i1, 16)][j] / d0[(i0, 16)][j] for j in range(5)]
            out.append(f"{min(r):.3f}-{max(r):.3f} (pad {n1[i1][1]:.2f} V)")
    print(f"  {k[1]} {k[2]} C: " + " | ".join(out))

print("\n== Internal reference (UA0 mode 2): equivalent S from vbn_leak code 16 vs EXT /1 at 1 uA")
for f in sorted(glob.glob(os.path.join(D, "idac_*_m2.log"))):
    k = key(f)
    f0 = f.replace("_m2", "_m0")
    d2, n2, _, _ = parse(f); d0, _, _, _ = parse(f0)
    if (0.0, 16) in d2 and (1e-6, 16) in d0:
        s = 100 * d2[(0.0, 16)][0] / d0[(1e-6, 16)][0]
        print(f"  {k[1]} {k[2]} C: S ~ {s:.0f}  (iint {n2[0.0][11] if len(n2[0.0]) > 11 else float('nan'):.3f} V node)")

print("\n== Voltage path (bias_b1): ranges [V], LSB [mV], DNL [LSB], max |dV| over Iref 0/0.1/1/10 uA [uV]")
for f in sorted(glob.glob(os.path.join(D, "vout_*.log"))):
    k = os.path.basename(f)[5:-4]
    _, _, b, v = parse(f)
    irefs = sorted({i for i, _ in v})
    if not irefs:
        print(f"  {k}: incomplete"); continue
    i0 = 1e-6 if 1e-6 in irefs else irefs[0]
    row = []
    for j, (nm, nb) in enumerate((("el", 5), ("vreset_src", 5), ("vth_cmp", 5), ("vth_ref", 6))):
        n = 2 ** nb
        if not all((i0, c) in v for c in range(n)):
            row.append(f"{nm}: incomplete"); continue
        vs = [v[(i0, c)][j] for c in range(n)]
        steps = [b_ - a for a, b_ in zip(vs, vs[1:])]
        lsb = (vs[-1] - vs[0]) / (n - 1)
        dnl = [s / lsb - 1 for s in steps]
        dv = max(abs(v[(i, c)][j] - v[(i0, c)][j]) for i in irefs for c in range(n) if (i, c) in v)
        row.append(f"{nm} {vs[0]:.3f}-{vs[-1]:.3f} LSB {lsb*1e3:5.2f} DNL {min(dnl):+.2f}/{max(dnl):+.2f}"
                   f"{'' if min(steps) > 0 else ' NOT MONO'} dI {dv*1e6:.0f}")
    bb = b.get(i0, [float("nan")] * 4)
    print(f"  {k}: vbn_prb {bb[0]:.3f} V, ib_r1 {abs(bb[1])*1e6:.2f} uA, vglp {bb[2]:.3f} V, I(vdd) {abs(bb[3])*1e6:.0f} uA")
    for r in row:
        print("      " + r)
