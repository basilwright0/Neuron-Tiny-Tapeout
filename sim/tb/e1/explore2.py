"""E1 exploration 2: (1) leak OTA (leak_ota_degx, and without degeneration) at EL = Vth - 80 mV with vsrc = 0;
(2) mcap C(V); (3) option B: vsrc from a local nfet diode."""
import sys
import numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings
TRIP = {"typical": 0.6265, "ss": 0.7695, "ff": 0.4425}
for corner, T in (("typical", 27), ("ss", 0), ("ff", 85)):
    el = TRIP[corner] - 0.08
    body = f"""{include('neuron/membrane.spice')}
.subckt leak_ota_degx vm el a vbn vdd vss
XMT  t   vbn vss vss nfet_03v3 W=2u L=4u
XM1  a   el  s1  vss nfet_03v3 W=4u L=0.5u
XD1  s1  s1  t   vss nfet_03v3 W=8u L=0.5u
XM2  vm  vm  s2  vss nfet_03v3 W=4u L=0.5u
XD2  s2  s2  t   vss nfet_03v3 W=8u L=0.5u
XP1  a   a   vdd vdd pfet_03v3 W=2u L=4u
XP2  vm  a   vdd vdd pfet_03v3 W=2u L=4u
.ends
.subckt ota_nodeg vm el vbn vdd vss
XMT  t   vbn vss vss nfet_03v3 W=2u L=4u
XM1  a   el  t   vss nfet_03v3 W=4u L=0.5u
XM2  vm  vm  t   vss nfet_03v3 W=4u L=0.5u
XP1  a   a   vdd vdd pfet_03v3 W=2u L=4u
XP2  vm  a   vdd vdd pfet_03v3 W=2u L=4u
.ends
.subckt ota_p vm el vbp vdd vss
XMT  t   vbp vdd vdd pfet_03v3 W=2u L=4u
XM1  a   el  t   vdd pfet_03v3 W=4u L=0.5u
XM2  vm  vm  t   vdd pfet_03v3 W=4u L=0.5u
XN1  a   a   vss vss nfet_03v3 W=2u L=4u
XN2  vm  a   vss vss nfet_03v3 W=2u L=4u
.ends
Vdd vdd 0 3.3
Vel el 0 {el}
Ib vdd vbn 320p
Xm vbn 0 nmaster
Ibp vbp 0 320p
Xmp vbp vdd pmaster
Vm1 vm1 0 {el}
Vm2 vm2 0 {el}
Vm3 vm3 0 {el}
Xa vm1 el a1 vbn vdd 0 leak_ota_degx
Xb vm2 el vbn vdd 0 ota_nodeg
Xc vm3 el vbp vdd 0 ota_p
"""
    res = {}
    for k, src in (("deg", "Vm1"), ("nodeg", "Vm2"), ("p", "Vm3")):
        body2 = body.replace(f"{src} vm", f"{src} vm")
        rr = run(deck(body, f"dc {src} {el-0.2:.4f} {el+0.2:.4f} 1m", [f"i({src})"], corner=corner, temp=T), f"e1x2{k}_{corner}")
        x, i = rr["_x"], rr[[k2 for k2 in rr if k2.startswith("i(")][0]]
        g = np.gradient(i, x)
        j0 = np.argmin(abs(x - el))
        j1 = np.argmin(abs(x - (el + 0.08)))
        res[k] = (g[j0] * 1e9, i[j1] * 1e12, i[0] * 1e12, i[-1] * 1e12)
    print(corner, T, f"EL={el:.3f}", " ".join(f"{k}: g(EL)={v[0]:.2f}nS I(EL+80m)={v[1]:.0f}p I(-200m)={v[2]:.0f}p I(+200m)={v[3]:.0f}p |" for k, v in res.items()))
    # mcap C-V
    body3 = f"""{include('neuron/membrane.spice')}
Vv v 0 PWL(0 0 1u 2)
Xc v 0 mcap wl=7.07u
"""
    r3 = run(deck(body3, "tran 1n 1u", ["i(Vv)", "v(v)"], corner=corner, temp=T), f"e1x2c_{corner}")
    v, ic = r3["v(v)"], -r3["i(vv)"]
    C = ic / 2e6
    print("   mcap C(fF) at V:", " ".join(f"{vv:.2f}:{np.interp(vv, v, C) * 1e15:.0f}" for vv in (0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8, 1.0, 1.3)))
    # option B: vsrc from nfet diode 1/0.5 fed by a 1/2 pfet copy of vbp_st
    body4 = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Ist vbs 0 62.5n
XD0 vbs vbs vdd vdd pfet_03v3 W=1u L=4u
XL vs vbs vdd vdd pfet_03v3 W=1u L=2u
XN vs vs 0 0 nfet_03v3 W=1u L=0.5u
Vm vm 0 1.0
Xd vm spk vs vbs vdd 0 det_ah
XL2 e1 vbs vdd vdd pfet_03v3 W=1u L=2u
XE1 e1 e1 e2 0 nfet_03v3 W=1u L=0.5u
XE2 e2 e2 0 0 nfet_03v3 W=1u L=0.5u
"""
    r4 = run(deck(body4, "dc Vm 0.6 2.2 1m", ["v(spk)", "v(vs)", "v(e1)"], corner=corner, temp=T), f"e1x2d_{corner}")
    x = crossings(r4["_x"], r4["v(spk)"], 1.65)
    print(f"   optB: trip {x[:1]} vsrc(idle) {r4['v(vs)'][0]:.3f} stackEL {r4['v(e1)'][0]:.3f}")
