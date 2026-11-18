"""Leak OTA I-V: current into vm vs (vm - el), with and without degeneration.
Fits I = Ib*tanh((el-vm)/VL) -> reports Ib_sat, small-signal g, VL, and linearity at given swing."""
import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include

IB = 150e-12
res = {}
for cell in ("leak_ota", "leak_ota_deg"):
    for corner, temp in (("typical", 27), ("ff", 27), ("ss", 27), ("typical", 85)):
        body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Ib  vdd vbn {IB}
Xm  vbn 0 nmaster
Vm  vm 0 1.2
Xl  vm el vbn vdd 0 {cell}
"""
        d = deck(body, "dc Vm 0.9 1.5 2m", ["i(Vm)"], corner=corner, temp=temp)
        r = run(d, f"leakiv_{cell}_{corner}_{temp}")
        vm = r["_x"]; i = r["i(vm)"]          # i(Vm) = current flowing out of + terminal of Vm source
        # current into vm node from OTA = -(source current) sign check: at vm<el OTA pushes current in
        iin = i  # ngspice: positive i(V) flows from + to - through the source, i.e. into node vm from the source... normalize below
        if iin[np.argmin(np.abs(vm - 1.1))] < 0:
            iin = -iin
        isat_p = iin[0]; isat_n = iin[-1]
        k0 = np.argmin(np.abs(vm - 1.2))
        g = -np.gradient(iin, vm)[k0]
        VL = (isat_p - isat_n) / 2 / g
        out = {}
        for sw in (0.04, 0.06, 0.08, 0.1, 0.15):
            k = np.argmin(np.abs(vm - (1.2 + sw)))
            out[sw] = (-iin[k]) / (g * sw)      # 1.0 = perfectly linear
        res[(cell, corner, temp)] = (isat_p, isat_n, g, VL, out)
        print(f"{cell:13s} {corner:7s} {temp:3d}C  Isat+={isat_p*1e12:7.1f}p Isat-={isat_n*1e12:7.1f}p "
              f"g={g*1e9:6.3f}nS VL={VL*1e3:6.1f}mV  lin@40/60/80/100/150mV: "
              + " ".join(f"{out[s]:.3f}" for s in out) + f"  offset I@el={iin[k0]*1e12:+.2f}p")
