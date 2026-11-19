"""Quick functional check: current pulses into d1 (plateau on), soma spiking suppressed (vsrc=1.3)."""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *
corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
vsrc = float(sys.argv[2]) if len(sys.argv) > 2 else 1.3
amps = [100e-12, 200e-12, 300e-12, 400e-12, 600e-12]
pw = []
t = 0.2e-3
for a in amps:
    pw.append(f"{t} 0 {t+1e-6} {a} {t+0.4e-3} {a} {t+0.4e-3+1e-6} 0")
    t += 2.0e-3
src = "Iin vdd d1 pwl(0 0 " + " ".join(pw) + ")"
body = f"""{cells()}
{bias(vsrc=vsrc)}
{src}
{DUT}
"""
sv = ["v(vs)", "v(d1)", "v(d2)", "v(spk)", "v(xd.vep)", "v(xd.xp1.vt)", "v(xd.xp1.xb)", "v(xd.xp1.x)", "i(vdd)"]
r = run(deck(body, f"tran 1u {t} ", sv, corner=corner, temp=27), f"dendrite/quick_{corner}_{vsrc}")
import numpy as np
tt = r["_x"]
print("vep", r["v(xd.vep)"][-1])
for k, a in enumerate(amps):
    t0 = 0.2e-3 + 2e-3 * k
    m = (tt > t0) & (tt < t0 + 2e-3)
    d1 = r["v(d1)"][m]; vs = r["v(vs)"][m]
    above = tt[m][d1 > EL + 0.25]
    dur = (above[-1] - above[0]) if len(above) else 0
    print(f"I={a*1e12:4.0f}p d1max={d1.max():.3f} vsmax={vs.max():.3f} d2max={r['v(d2)'][m].max():.3f} "
          f"d1@end-step={np.interp(t0+0.39e-3, tt, r['v(d1)']):.3f} vs@end={np.interp(t0+0.39e-3, tt, r['v(vs)']):.3f} plateau(>EL+0.25) {dur*1e6:.0f}us "
          f"vtmin={r['v(xd.xp1.vt)'][m].min():.2f} nspk={len(crossings(tt[m], r['v(spk)'][m], 1.65))}")
print("Ivdd rest (nA)", -r["i(vdd)"][tt < 0.19e-3].mean() * 1e9)
