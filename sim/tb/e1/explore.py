"""E1 exploration: AH trip with vsrc = 0 (starve from the chip's vbp_st line), nfet diode Vgs at the leg current."""
import sys
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings
for corner, T in (("typical", 27), ("ss", 0), ("ff", 85)):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Ist vbs 0 62.5n
XD0 vbs vbs vdd vdd pfet_03v3 W=1u L=4u
Vm vm 0 1.0
Xd vm spk 0 vbs vdd 0 det_ah
* leg copies: pfet 1/2 from vbs into nfet diodes of several sizes
XL1 a1 vbs vdd vdd pfet_03v3 W=1u L=2u
XN1 a1 a1 0 0 nfet_03v3 W=1u L=0.5u
XL2 a2 vbs vdd vdd pfet_03v3 W=1u L=2u
XN2 a2 a2 0 0 nfet_03v3 W=1u L=4u
XL3 a3 vbs vdd vdd pfet_03v3 W=1u L=2u
XN3 a3 a3 b3 0 nfet_03v3 W=1u L=4u
XN4 b3 b3 0 0 nfet_03v3 W=1u L=4u
XL5 a5 vbs vdd vdd pfet_03v3 W=1u L=2u
XP5 0 a5 a5 vdd pfet_03v3 W=1u L=4u
"""
    r = run(deck(body, "dc Vm 0.3 1.6 1m", ["v(spk)", "v(a1)", "v(a2)", "v(a3)", "v(b3)", "v(a5)", "v(vbs)", "@m.xl1.m0[id]"], corner=corner, temp=T), f"e1x_{corner}{T}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    print(corner, T, "trip", x[:1], " diode1/0.5", r["v(a1)"][0], " 1/4", r["v(a2)"][0], " stack 1/4x2", r["v(a3)"][0], r["v(b3)"][0], " pdiode", r["v(a5)"][0], "vbs", r["v(vbs)"][0])
