"""leak_ota_deg g/Ib at cold slow corners for higher S (Ib scales with S): orig @ EL 1.2 vs fix B @ EL 1.3.
usage: python3 sim/tb/dendrite/tb_leak_hiS.py  -> sim/results/dendrite/leak_hiS.txt"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
L = ["variant EL corner T S Ib(pA) g/Ib Isat+(%Ib) t(V)"]
for name, el, (wi, li, wd, ld) in (("orig", 1.2, ("2u", "2u", "2u", "2u")), ("B", 1.3, ("4u", "1u", "8u", "1u"))):
    for c, t in (("ss", 0), ("sf", 0), ("ss", 27), ("typical", 27)):
        for S in (100, 300, 1000):
            ib = 324e-12 * S / 100
            body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {el}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {el}
Xl  vm el vbn vdd 0 leak_ota_deg wi={wi} li={li} wd={wd} ld={ld}
"""
            r = run(deck(body, f"dc Vm {el-0.5:.3f} {el+0.5:.3f} 1m", ["i(vm)", "v(xl.t)"], corner=c, temp=t), f"dendrite/leakhis_{c}_{t}")
            vm = r["_x"]; iin = -r["i(vm)"]
            if iin[np.argmin(np.abs(vm - (el - 0.1)))] < 0:
                iin = -iin
            k0 = np.argmin(np.abs(vm - el)); g = -np.gradient(iin, vm)[k0]
            L.append(f"{name:4s} {el:.1f} {c:7s} {t:3d} {S:5d} {ib*1e12:7.0f} {g/ib:5.2f} {100*iin[0]/ib:5.0f} {r['v(xl.t)'][k0]:.3f}")
            print(L[-1], flush=True)
(OUT / "leak_hiS.txt").write_text("\n".join(L) + "\n")
