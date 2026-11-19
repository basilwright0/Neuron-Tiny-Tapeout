"""Headroom fix candidates for leak_ota_deg at cold slow-n (diagnosis: tail node t ~ 10 mV at ss/0).

usage: python3 sim/tb/dendrite/tb_leak_fix.py     -> sim/results/dendrite/leak_fix.txt
Variants keep the topology; only input-pair / degeneration-diode W/L (subthreshold: wider = less Vgs,
same gm per current, so VL is kept) and EL change. Does NOT modify cells/neuron/membrane.spice.
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

VAR = {"orig  in2/2 dio2/2": ("2u", "2u", "2u", "2u"),
       "A     in2/2 dio8/1": ("2u", "2u", "8u", "1u"),
       "B     in4/1 dio8/1": ("4u", "1u", "8u", "1u"),
       "C     in8/1 dio8/1": ("8u", "1u", "8u", "1u")}
L = ["variant              EL   corner  T  Ib(pA)  g/Ib   VL(mV) Isat+(pA) Isat-(pA)  t(V)"]
for name, (wi, li, wd, ld) in VAR.items():
    for el in (1.2, 1.3):
        for c, t in (("typical", 27), ("ss", 0), ("sf", 0), ("ss", 27), ("ff", 85), ("typical", 0)):
            for ib in (324e-12, 647e-12):
                body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {el}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {el}
Xl  vm el vbn vdd 0 leak_ota_deg wi={wi} li={li} wd={wd} ld={ld}
"""
                r = run(deck(body, f"dc Vm {el-0.4} {el+0.4} 2m", ["i(vm)", "v(xl.t)"], corner=c, temp=t),
                        f"dendrite/leakfix_{c}_{t}_{ib*1e12:.0f}")
                vm = r["_x"]
                iin = -r["i(vm)"]
                if iin[np.argmin(np.abs(vm - (el - 0.1)))] < 0:
                    iin = -iin
                k0 = np.argmin(np.abs(vm - el))
                g = -np.gradient(iin, vm)[k0]
                L.append(f"{name:20s} {el:.1f} {c:7s} {t:3d} {ib*1e12:5.0f}  {g/ib:5.2f}  {(iin[0]-iin[-1])/2/g*1e3:6.1f} "
                         f"{iin[0]*1e12:8.1f} {iin[-1]*1e12:8.1f}  {r['v(xl.t)'][k0]:.3f}")
                print(L[-1], flush=True)
(OUT / "leak_fix.txt").write_text("\n".join(L) + "\n")
