#!/usr/bin/env python3
"""Summary of run_recheck_rails.sh (rail AC / VDD step / aggressor glitch, and 150 pA settling)."""
import glob, os
import numpy as np

NUT = 0.035   # n*U_T: 1 mV of unit Vgs ~ 2.9 % of a subthreshold unit current


def dat(fn):
    a = np.loadtxt(fn, skiprows=1)
    return a[:, 0], a[:, 1:]


print("== rail AC: VDD carries 1 V AC; victims idac_n / idac_p range 3 code 19 (outputs held at 1 V)")
print("   dVgs = unit gate-source disturbance (V per V of VDD) -> dI/I ~ dVgs / 35 mV;  vsn/vsp = rail swing (V/V)")
for fn in sorted(glob.glob("out/recheck/rails/ac_*.log")):
    F, pk, dc = {}, None, None
    for ln in open(fn):
        t = ln.split()
        if t and t[0] == "F":
            F[float(t[1])] = [float(x) for x in t[2:]]
        elif t and t[0] == "PK":
            pk = [float(x) for x in t[1:]]
        elif t and t[0] == "DC":
            dc = [float(x) for x in t[1:]]
    if not F or pk is None:
        print(os.path.basename(fn), "NO DATA"); continue
    name = os.path.basename(fn)[3:-4]
    s = f"{name:24s} I {dc[2]*1e12:5.0f}p/{dc[3]*1e12:5.0f}p  dVgs n/p @1k {F[1e3][4]:.3f}/{F[1e3][5]:.3f}"
    s += f" @100k {F[1e5][4]:.3f}/{F[1e5][5]:.3f} @10M {F[1e7][4]:.3f}/{F[1e7][5]:.3f}  peak {pk[0]:.3f}/{pk[1]:.3f}"
    s += f"  -> {pk[0]/NUT*0.1:.2f}/{pk[1]/NUT*0.1:.2f} % per mV VDD;  vsn/vsp @10M {F[1e7][2]:.3f}/{F[1e7][3]:.3f}"
    print(s)

for mode, what in (("tran", "VDD +50 mV step (1 ns) at 20 us, back at 120 us"),
                   ("glitch", "6 aggressor idacs (range 0) code 0->31 at 20 us, back at 120 us")):
    print(f"\n== rail {mode}: {what}; victims range 3 code 19 held at 1 V")
    print("   unit gate-source disturbance dVgs (mV, n/p): peak after the edge and time until |dVgs| < 0.35 mV")
    print("   (~1 % of a subthreshold current) w.r.t. the final value; |dI/I| 20 us after the edge; rail peaks (mV)")
    for fn in sorted(glob.glob(f"out/recheck/rails/{mode}_*.dat")):
        t, y = dat(fn)
        In, Ip, vsn, vsp, vgn, vgp = (y[:, k] for k in range(6))
        gn, gp = vgn - vsn, vsp - vgp
        res = []
        for te in (20e-6, 120e-6):
            fin = (t > te + 90e-6) & (t < te + 99e-6) if te + 99e-6 < t[-1] else (t > t[-1] - 5e-6)
            w2 = (t > te) & (t < te + 100e-6)
            o = []
            for g, I in ((gn, In), (gp, Ip)):
                dv = 1e3 * (g - g[fin].mean())
                pk = np.abs(dv[w2]).max()
                bad = np.where(np.abs(dv) > 0.35)[0]
                bad = bad[(t[bad] > te) & (t[bad] < te + 100e-6)]
                ts = (t[bad[-1]] - te) * 1e6 if len(bad) else 0.0
                a = (t > te + 19e-6) & (t < te + 21e-6)
                o.append((pk, ts, abs(I[a].mean() / I[fin].mean() - 1)))
            sn = 1e3 * np.abs(vsn[w2] - vsn[fin].mean()).max()
            sp = 1e3 * np.abs(vsp[w2] - vsp[fin].mean()).max()
            res.append((o, sn, sp))
        (o, sn, sp) = res[0]
        print(f"{os.path.basename(fn)[len(mode)+1:-4]:24s} dVgs {o[0][0]:5.2f}/{o[1][0]:5.2f} mV  <1% after {o[0][1]:5.1f}/{o[1][1]:5.1f} us"
              f"  dI/I@+20us {100*o[0][2]:4.2f}/{100*o[1][2]:4.2f} %  vsn {sn:5.2f} vsp {sp:5.2f} mV"
              f"  | return: {res[1][0][0][0]:5.2f}/{res[1][0][1][0]:5.2f} mV, <1% after {res[1][0][0][1]:5.1f}/{res[1][0][1][1]:5.1f} us")

print("\n== settling at 150 pA (range 3, step at t=0.2 ms) -- rev B cells")
print("   n: idac_n -> 16-unit pfet diode + 1 pF + 20 trim4_p (current of one trim);  p: idac_p -> rx_n4 + 1 pF + 16 tails (one tail)")
for fn in sorted(glob.glob("out/recheck/settle/*.dat")):
    t, y = dat(fn); y = y[:, 0]
    pre = np.interp(0.19e-3, t, y); fin = y[t > t[-1] - 0.2e-3].mean()
    res = []
    for tol in (0.05, 0.01):
        bad = np.where(np.abs(y - fin) > tol * abs(fin - pre) + 1e-30)[0]
        bad = bad[t[bad] > 0.2e-3]
        res.append((t[bad[-1]] - 0.2e-3) * 1e6 if len(bad) else 0.0)
    pk = y[(t > 0.2e-3)]
    print(f"{os.path.basename(fn):18s} I before {pre:.3e}  after {fin:.3e}  t5% {res[0]:7.1f} us  t1% {res[1]:7.1f} us"
          f"  peak {pk.max():.3e} min {pk.min():.3e}")
