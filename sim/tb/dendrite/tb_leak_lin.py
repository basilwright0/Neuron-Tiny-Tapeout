"""leak_ota_deg g/Ib and linear range, all 5 corners x 0/27/85 C, S = 100 currents (324 pA leak,
647 pA axial), for the current cell and the headroom-fix candidates (tb_leak_fix.py variants).

usage: python3 sim/tb/dendrite/tb_leak_lin.py   -> sim/results/dendrite/leak_lin.txt
Linear range: |dV| (vm - el) at which the OTA current has fallen 10 % below g*dV, separately for
vm below el (OTA sources current: lin-) and above el (OTA sinks: lin+). g = small-signal at vm = el.
Isat+/Isat- = current sourced at el-0.5 V / sunk at el+0.5 V, as % of Ib.
Does NOT modify cells/neuron/membrane.spice (variants via its W/L parameters).
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

VAR = [("orig in2/2 dio2/2", 1.2, ("2u", "2u", "2u", "2u")),
       ("C    in8/1 dio8/1", 1.2, ("8u", "1u", "8u", "1u")),
       ("orig in2/2 dio2/2", 1.3, ("2u", "2u", "2u", "2u")),
       ("B    in4/1 dio8/1", 1.3, ("4u", "1u", "8u", "1u"))]
L = [__doc__.strip().splitlines()[0],
     "variant            EL   corner  T  Ib(pA) g/Ib(S/A) lin-(mV) lin+(mV) Isat+(%Ib) Isat-(%Ib)  t(V)"]
for name, el, (wi, li, wd, ld) in VAR:
    for c in CORNERS:
        for t in TEMPS:
            for ib in (324e-12, 647e-12):
                body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {el}
Ib  vdd vbn {ib}
Xm  vbn 0 nmaster
Vm  vm 0 {el}
Xl  vm el vbn vdd 0 leak_ota_deg wi={wi} li={li} wd={wd} ld={ld}
"""
                r = run(deck(body, f"dc Vm {el-0.5:.3f} {el+0.5:.3f} 1m", ["i(vm)", "v(xl.t)"], corner=c, temp=t),
                        f"dendrite/leaklin_{c}_{t}_{ib*1e12:.0f}")
                vm = r["_x"]
                iin = -r["i(vm)"]
                if iin[np.argmin(np.abs(vm - (el - 0.1)))] < 0:
                    iin = -iin
                k0 = np.argmin(np.abs(vm - el))
                g = -np.gradient(iin, vm)[k0]
                dv = vm - el
                ilin = -g * dv
                # first |dV| where |I| < 0.9 |g dV| (each side)
                lo = [k for k in range(k0 - 5, -1, -1) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
                hi = [k for k in range(k0 + 5, len(vm)) if abs(iin[k] - iin[k0]) < 0.9 * abs(ilin[k])]
                lm = -dv[lo[0]] * 1e3 if lo else float("nan")
                lp = dv[hi[0]] * 1e3 if hi else float("nan")
                L.append(f"{name} {el:.1f} {c:7s} {t:3d} {ib*1e12:5.0f}  {g/ib:7.2f}  {lm:7.0f}  {lp:7.0f}  "
                         f"{100*iin[0]/ib:8.0f}  {-100*iin[-1]/ib:8.0f}    {r['v(xl.t)'][k0]:.3f}")
                print(L[-1], flush=True)
(OUT / "leak_lin.txt").write_text("\n".join(L) + "\n")
