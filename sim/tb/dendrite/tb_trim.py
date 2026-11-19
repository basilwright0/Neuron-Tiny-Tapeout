"""D1 trim (trim_gap4w) step and range on a subunit leak (leak_ota_dega + trim, vm held by a 200 fF
cap, no input): rest shift vs code, all codes, at typical/ss/ff x 0/27/85 (S = 100, Ib 324 pA).
usage: python3 sim/tb/dendrite/tb_trim.py   -> sim/results/dendrite/trim.txt
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
L = ["trim_gap4w on leak_ota_dega, Ib = 324 pA, el = 1.2 V: rest shift (mV) vs code 0..15"]
for c in CORNERS:
    for t in TEMPS:
        sh = []
        for code in range(16):
            bits = [3.3 * ((code >> k) & 1) for k in range(4)]
            body = f"""{include('neuron/membrane.spice', 'dendrite/dtrim.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Ib  vdd vbn 324p
Xm  vbn 0 nmaster
""" + "".join(f"Vb{k} b{k} 0 {bits[k]}\n" for k in range(4)) + """XL vm el a vbn vdd 0 leak_ota_dega
XT a vm vbn b0 b1 b2 b3 vdd 0 trim_gap4w
"""
            r = run(deck(body, "op", ["v(vm)"], corner=c, temp=t), f"dendrite/trim_{c}_{t}_{code}")
            sh.append(float(r["v(vm)"][0]))
        sh = np.array(sh) - 1.2
        steps = np.diff(sh) * 1e3
        L.append(f"{c:7s} {t:3d}: range {sh[0]*1e3:+6.1f} .. {sh[-1]*1e3:+6.1f} mV, step mean {steps.mean():.2f} "
                 f"min {steps.min():.2f} max {steps.max():.2f} mV, monotonic {bool((steps > 0).all() or (steps < 0).all())}")
        print(L[-1], flush=True)
(OUT / "trim.txt").write_text("\n".join(L) + "\n")
