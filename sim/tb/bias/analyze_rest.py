#!/usr/bin/env python3
"""Summaries for settling, vdac and trim runs (run from sim/tb/bias)."""
import glob, os
import numpy as np


def dat(fn):
    a = np.loadtxt(fn, skiprows=1)
    return a[:, 0], a[:, 1:]


print("== settling (idac_n range 3, step at t=0.2 ms; current seen by one trim4_p at 1.00x)")
for fn in sorted(glob.glob("out/settle/*.dat")):
    t, y = dat(fn); y = y[:, 0]
    pre = np.interp(0.19e-3, t, y); fin = y[-1]
    res = []
    for tol in (0.05, 0.01):
        bad = np.where(np.abs(y - fin) > tol * abs(fin - pre) + 1e-30)[0]
        bad = bad[t[bad] > 0.2e-3]
        res.append((t[bad[-1]] - 0.2e-3) * 1e6 if len(bad) else 0.0)
    pk = y[(t > 0.2e-3)]
    print(f"{os.path.basename(fn):18s} I before {pre:.3e}  after {fin:.3e}  t5% {res[0]:7.1f} us  t1% {res[1]:7.1f} us"
          f"  peak {pk.max():.3e} min {pk.min():.3e}")

print("\n== vdac DC (code 0..63, out1 of 3 trees on one string)")
for fn in sorted(glob.glob("out/vdac/dc_*.log")):
    D = []
    for l in open(fn):
        t = l.split()
        if t and t[0] == "D": D.append((int(t[1]), float(t[2]), float(t[3])))
    if len(D) < 64: print(fn, "incomplete", len(D)); continue
    v = np.array([d[1] for d in D]); tap = np.array([d[2] for d in D])
    vdd = 3.3
    if "_v" in fn: vdd = float(fn.split("_v")[-1][:-4])
    ideal = vdd * (0.3 + np.arange(64) * 1.7 / 63) / 3.3
    lsb = (v[63] - v[0]) / 63; dnl = np.diff(v) / lsb - 1
    print(f"{os.path.basename(fn)[3:-4]:14s} V0 {v[0]:.4f} V63 {v[63]:.4f}  maxerr {1e3*np.abs(v-ideal).max():5.1f} mV"
          f"  DNL {dnl.min():+.3f}/{dnl.max():+.3f}  mono {'Y' if np.all(np.diff(v)>0) else 'N'}"
          f"  out-tap {1e6*np.abs(v-tap).max():.1f} uV")

print("\n== vdac transient (1 pF + 20 gates), steps at 5/15/25 us: 0->63->32->31")
for fn in sorted(glob.glob("out/vdac/tran_*.dat")):
    t, y = dat(fn); y = y[:, 0]
    for t0, t1 in ((5e-6, 15e-6), (15e-6, 25e-6), (25e-6, 35e-6)):
        m = (t > t0) & (t < t1); tt_ = t[m]; yy = y[m]; fin = yy[-1]
        out = []
        for tol in (13.5e-3, 1e-3):
            bad = np.where(np.abs(yy - fin) > tol)[0]
            out.append((tt_[bad[-1]] - t0) * 1e9 if len(bad) else 0)
        print(f"{os.path.basename(fn):14s} step@{t0*1e6:.0f}us final {fin:.4f} V  t(0.5LSB) {out[0]:6.0f} ns  t(1mV) {out[1]:6.0f} ns")
for fn in sorted(glob.glob("out/vdac/reset_*.dat")):
    t, y = dat(fn); vl = y[:, 0]; vm = y[:, 1]
    base = np.interp(9.9e-6, t, vl)
    print(f"reset load: line {base:.4f} V, peak {vl.max():.4f} V (+{1e3*(vl.max()-base):.0f} mV), "
          f"v(line) at end of 2 us pulse {np.interp(11.99e-6, t, vl):.4f}, membrane at end {np.interp(11.99e-6, t, vm):.4f} V, "
          f"line at 13 us {np.interp(13e-6, t, vl):.4f}, 16 us {np.interp(16e-6, t, vl):.4f}")

print("\n== trim4_p: gain = I(code)/I_ref ; corners (nt=1)")
for i in ("100p", "1n", "1u"):
    for fn in sorted(glob.glob(f"out/trim/t_*_{i}.log")):
        I = []
        for l in open(fn):
            t = l.split()
            if t and t[0] == "D": I.append(abs(float(t[2])))
        if len(I) < 16: print(fn, "incomplete"); continue
        iref = {"100p": 1e-10, "1n": 1e-9, "1u": 1e-6}[i]
        g = np.array(I) / iref
        print(f"{os.path.basename(fn)[2:-4]:14s} g(0) {g[0]:.3f} g(8) {g[8]:.3f} g(15) {g[15]:.3f} "
              f"mono {'Y' if np.all(np.diff(g)>0) else 'N'}  step min/max {np.diff(g).min():.4f}/{np.diff(g).max():.4f}")
print("\n== trim4_p MC (50 dies x 4 cells, tt 27 C): sigma of gain")
for i in ("100p", "1n", "1u"):
    A = []
    for fn in glob.glob(f"out/trim/mc_{i}_*.log"):
        rows = [l.split() for l in open(fn) if l.startswith("D ")]
        if len(rows) == 16: A.append([[abs(float(x)) for x in r[2:]] for r in rows])
    if not A: continue
    A = np.array(A)  # die, code, cell
    iref = {"100p": 1e-10, "1n": 1e-9, "1u": 1e-6}[i]
    g = A / iref
    mono = sum(np.all(np.diff(g[d, :, k]) > 0) for d in range(g.shape[0]) for k in range(g.shape[2]))
    rel = g / g[:, 8:9, :]   # gain normalised to own code-8 value
    s = " ".join(f"c{c}:{100*g[:, c, :].std()/g[:, c, :].mean():.1f}%" for c in (0, 4, 8, 12, 15))
    print(f"Iref {i}: {A.shape[0]} dies, mean g0 {g[:,0].mean():.3f} g8 {g[:,8].mean():.3f} g15 {g[:,15].mean():.3f}; "
          f"sigma(g)/g {s}; monotonic {mono}/{g.shape[0]*g.shape[2]}; "
          f"sigma of LSB step {100*np.diff(rel,axis=1).std():.2f}% (nominal 6.25%)")
