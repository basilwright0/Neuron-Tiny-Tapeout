import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings
# one AH neuron at 2x rheobase; save branch currents of every vdd-connected device via probes
body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Vrs vrst 0 1.2
Vsr vsrc 0 0.505
Ibl vdd vbl 324p
Xbl vbl 0 nmaster
Ibr vdd vbr 3.37n
Xbr vbr 0 nmaster
Ibs vbs 0 100n
Xbs vbs vdd pmaster w=1u l=2u
Iin vdd vm 320p
Vsrcm vsrc vsrcx 0
Xn vm spk el vsrcx vrst vbl vbs vbr vdd 0 lif_ah
.ic v(vm)=1.2
"""
d = deck(body, "tran 0.2u 1m uic", ["v(vm)", "v(spk)", "v(xn.xd.n1)", "v(xn.vr)", "i(vdd)", "i(vsrcm)", "i(vrs)"])
r = run(d, "diag_power_ah")
t = r["_x"]; iv = -r["i(vdd)"]
st = crossings(t, r["v(spk)"], 1.65)
print("spikes", len(st), "mean Ivdd", iv[t>0.3e-3].mean()*1e9, "nA; mean I(vsrc)", r["i(vsrcm)"][t>0.3e-3].mean()*1e9, "nA; mean I(vreset)", r["i(vrs)"][t>0.3e-3].mean()*1e9)
# current profile around the 3rd spike
t0 = st[3]
for dt in (-20e-6,-5e-6,-1e-6,0,0.5e-6,1e-6,2e-6,5e-6,10e-6,20e-6,40e-6):
    k = np.argmin(abs(t-(t0+dt)))
    print(f"t-t0={dt*1e6:6.1f}us vm={r['v(vm)'][k]:.3f} n1={r['v(xn.xd.n1)'][k]:.3f} spk={r['v(spk)'][k]:.3f} vr={r['v(xn.vr)'][k]:.3f} Ivdd={iv[k]*1e6:8.3f}uA")
