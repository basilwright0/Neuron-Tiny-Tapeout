"""D1 hold (freeze): load the compartments with synaptic charge (stim A into d1, I_w = 0.5 nA, 100 us),
then hold = 1 for 5 ms; report the drift of soma, d1, d2 during hold and the step at hold on/off.
usage: python3 sim/tb/dendrite/tb_hold.py [corner] [temp]
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
vsrc = cal_vsrc(corner, temp)
TA0, TA1, TH0, TH1 = 2.0e-3, 2.1e-3, 2.1e-3, 7.1e-3
IW, PL = 0.5e-9, 0     # 50 fC into d1 (sub-threshold, no plateau), plateau off
body = f"""{cells()}
{bias(vsrc=vsrc, pl_en=PL, iw=IW, stim=False, hold=f"pwl(0 0 {TH0 - 1e-6} 0 {TH0} 3.3 {TH1} 3.3 {TH1 + 1e-6} 0)")}
Vsta sta 0 pwl(0 0 {TA0} 0 {TA0 + 0.2e-6} 3.3 {TA1} 3.3 {TA1 + 0.2e-6} 0)
Vstb stb 0 0
"""
body += DUT + "\n"
r = run(deck(body, "tran 1u 8e-3", ["v(vs)", "v(d1)", "v(d2)", "v(spk)"], corner=corner, temp=temp),
        f"dendrite/hold_{corner}_{temp}")
t = r["_x"]
for n in ("vs", "d1", "d2"):
    v = r[f"v({n})"]
    a, b = np.interp(TH0 + 20e-6, t, v), np.interp(TH1 - 1e-6, t, v)
    print(f"[{corner}_{temp}] {n}: at hold start {a:.4f} V, after 5 ms hold {b:.4f} V, drift {1e3*(b-a):+.2f} mV "
          f"({1e3*(b-a)/5:+.3f} mV/ms); rest {np.interp(1.9e-3, t, v):.4f}")
print("spikes during hold:", len(crossings(t[(t > TH0) & (t < TH1)], r["v(spk)"][(t > TH0) & (t < TH1)], 1.65)))
