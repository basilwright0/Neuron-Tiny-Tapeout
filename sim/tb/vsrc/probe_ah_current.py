"""Characterise the current a det_ah detector draws through vsrc around a spike (ideal vsrc).

  python3 sim/tb/vsrc/probe_ah_current.py [corner] [temp] [S] [vsrc]
One lif_ah neuron (200 fF), Iin = 3 x rheobase, vsrc = ideal source through a 0 V ammeter.
Prints peak / mean current and charge per spike into the vsrc line.
"""
import sys
import numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
S = float(sys.argv[3]) if len(sys.argv) > 3 else 1000.0
VS = float(sys.argv[4]) if len(sys.argv) > 4 else 0.505
C = 200e-15
g = C * S / 10e-3
IB = g / (0.927e-9 / 150e-12)
tau = C / g
rheo = g * 0.08
I_REF = 50e-15 * 1.35 / (2e-3 / S)
I_ST = 100e-9 * max(1, S / 100)
body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Vrs vrst 0 1.2
Vsr vsrc0 0 {VS}
Vam vsrc0 vsrc 0
Ibl vdd vbl {IB}
Xbl vbl 0 nmaster
Ibr vdd vbr {I_REF}
Xbr vbr 0 nmaster
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Iin vdd vm {3 * rheo}
Xn vm spk el vsrc vrst vbl vbs vbr vdd 0 lif_ah
.ic v(vm)=1.2
"""
T = 6 * tau
d = deck(body, f"tran 0.2n {T} uic", ["v(vm)", "v(spk)", "i(vam)", "v(xn.xd.p)", "v(xn.xd.n1)"],
         corner=corner, temp=temp)
r = run(d, f"vsrc_probe_{corner}_{temp}_S{S:g}")
t, i = r["_x"], r["i(vam)"]          # current from vsrc0 into the cell (negative = cell injects)
st = crossings(t, r["v(spk)"], 1.65)
print(f"S={S:g} tau={tau*1e6:.2f}us I_st={I_ST*1e9:.0f}nA spikes={len(st)} at {np.round(st*1e6,3)} us")
iin = -i   # current injected by the detector into vsrc
for k, ts in enumerate(st[:3]):
    m = (t > ts - 0.5e-6) & (t < ts + 3e-6)
    tt, ii = t[m], iin[m]
    q = np.trapezoid(ii, tt)
    print(f" spike {k}: peak in {ii.max()*1e6:7.2f} uA  peak out {ii.min()*1e6:7.2f} uA  "
          f"net Q {q*1e15:8.1f} fC  Q+ {np.trapezoid(np.clip(ii,0,None),tt)*1e15:7.1f} fC")
t1 = st[1]
for tq in list(np.arange(t1 - 0.3e-6, t1 + 0.3e-6, 0.02e-6)) + list(np.arange(t1 + 0.3e-6, t1 + 4e-6, 0.2e-6)):
    j = np.searchsorted(t, tq)
    w = (t >= tq - 0.01e-6) & (t <= tq + 0.01e-6)
    print(f"  t-ts {(tq-t1)*1e6:5.2f} us  I_in(avg) {iin[w].mean()*1e6:8.3f} uA  max {iin[w].max()*1e6:8.3f}  vm {r['v(vm)'][j]:.3f}  p {r['v(xn.xd.p)'][j]:.2f} n1 {r['v(xn.xd.n1)'][j]:.2f}")
print(f"idle current (between spikes): {iin[(t > st[1] + 5e-6) & (t < st[2] - 1e-6)].mean()*1e9:.2f} nA")
