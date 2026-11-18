import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings
var = sys.argv[1]
common = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Vth vth 0 1.28
Vrs vrst 0 1.2
Vsr vsrc 0 0.505
Ibl vdd vbl 324p
Xbl vbl 0 nmaster
Ibr vdd vbr 3.37n
Xbr vbr 0 nmaster
Ibs vbs 0 100n
Xbs vbs vdd pmaster w=1u l=2u
Iin vdd vm 320p
.ic v(vm)=1.2
"""
if var == "cmp":
    cell = "Xn vm spk el vth vrst vbl vbs vbr vdd 0 lif_cmp"; nodes = ["v(xn.xd.o)", "v(xn.xd.ob)"]
else:
    cell = "Xn vm spk el vsrc vrst vbl vbs vbr vdd 0 lif_ah"; nodes = ["v(xn.xd.n1)", "v(xn.xd.n1)"]
d = deck(common + cell, "tran 0.05u 0.6m uic", ["v(vm)", "v(spk)"] + nodes + ["v(xn.vr)", "v(xn.xr.spkb)", "i(vdd)"])
r = run(d, f"diag2_{var}")
t = r["_x"]; iv = -r["i(vdd)"]
print("spk max", r["v(spk)"].max(), "mean Ivdd(uA)", iv[t > 0.2e-3].mean() * 1e6)
# find vm resets as event markers
ev = crossings(t, -r["v(vm)"], -1.25)   # vm falling through 1.25
print("vm resets", len(ev))
if len(ev) > 2:
    t0 = ev[2]
    for dt in np.array([-30, -10, -3, -1, -0.3, -0.1, 0, 0.1, 0.3, 1, 3, 10, 20, 30, 50]) * 1e-6:
        k = np.argmin(abs(t - (t0 + dt)))
        print(f"{dt*1e6:6.1f}us vm={r['v(vm)'][k]:.3f} a={r[nodes[0]][k]:.3f} b={r[nodes[1]][k]:.3f} spk={r['v(spk)'][k]:.3f} vr={r['v(xn.vr)'][k]:.3f} spkb={r['v(xn.xr.spkb)'][k]:.3f} I={iv[k]*1e6:8.3f}uA")
    # charge per inter-spike interval
    seg = (t > ev[1]) & (t < ev[2])
    q = np.trapz(iv[seg], t[seg]); print("charge per spike interval nC", q * 1e9, " energy nJ", q * 3.3e9)
