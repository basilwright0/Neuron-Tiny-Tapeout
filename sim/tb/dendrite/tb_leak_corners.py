"""leak_ota_deg I-V over all corners x 0/27/85 C at the S = 100 currents (Ib 324 pA leak, 647 pA axial).

usage: python3 sim/tb/dendrite/tb_leak_corners.py
DC sweep of vm (el = 1.2 V); g = -dI/dvm at vm = el; VL = (Isat+ - Isat-)/2/g; plus internal node
voltages at balance (tail t, degeneration sources s1, mirror node a, master gate vbn).
Writes sim/results/dendrite/leak_corners.txt.
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

L = ["leak_ota_deg, el = 1.2 V, master nmaster 2/4 (Ib into the master)",
     "corner  T  Ib(pA)  g/Ib(S/A)  VL(mV)  Isat+(pA) Isat-(pA) offset(pA) | vbn   t     s1    a     (V at balance)"]
for c in CORNERS:
    for t in TEMPS:
        for ib in (324e-12, 647e-12):
            body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 1.2
Xl  vm el vbn vdd 0 leak_ota_deg
"""
            sv = ["i(vm)", "v(vbn)", "v(xl.t)", "v(xl.s1)", "v(xl.a)"]
            r = run(deck(body, "dc Vm 0.8 1.6 2m", sv, corner=c, temp=t), f"dendrite/leakc_{c}_{t}_{ib*1e12:.0f}")
            vm = r["_x"]
            iin = -r["i(vm)"]                     # current pushed into vm by the OTA
            if iin[np.argmin(np.abs(vm - 1.1))] < 0:
                iin = -iin
            k0 = np.argmin(np.abs(vm - 1.2))
            g = -np.gradient(iin, vm)[k0]
            VL = (iin[0] - iin[-1]) / 2 / g
            nodes = " ".join(f"{r[n][k0]:.3f}" for n in sv[1:])
            L.append(f"{c:7s} {t:3d} {ib*1e12:5.0f}   {g/ib:7.2f}   {VL*1e3:6.1f}  {iin[0]*1e12:8.1f} {iin[-1]*1e12:8.1f} "
                     f"{iin[k0]*1e12:+8.2f}   | {nodes}")
            print(L[-1], flush=True)
(OUT / "leak_corners.txt").write_text("\n".join(L) + "\n")
