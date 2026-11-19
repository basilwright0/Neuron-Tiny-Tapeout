"""Trim ladder-input sizing sweep for trim_gap4w (lr = L of XRA/XRB): range/step at typical 0/27/85, ss/0, sf/0.
usage: python3 sim/tb/dendrite/tb_trim_lr.py lr1 lr2 ...
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
for lr in sys.argv[1:]:
    for c, t in (("typical", 27), ("typical", 0), ("typical", 85), ("ss", 0), ("sf", 0), ("ff", 0)):
        sh = []
        for code in range(16):
            bits = [3.3 * ((code >> k) & 1) for k in range(4)]
            body = f"""{include('neuron/membrane.spice', 'dendrite/dtrim.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Ib  vdd vbn 324p
Xm  vbn 0 nmaster
""" + "".join(f"Vb{k} b{k} 0 {bits[k]}\n" for k in range(4)) + f"""XL vm el a vbn vdd 0 leak_ota_dega
XT a vm vbn b0 b1 b2 b3 vdd 0 trim_gap4w lr={lr}
"""
            r = run(deck(body, "op", ["v(vm)"], corner=c, temp=t), f"dendrite/trimlr_{c}_{t}_{code}")
            sh.append(float(r["v(vm)"][0]))
        sh = (np.array(sh) - sh[8]) * 1e3
        st = np.diff(sh)
        print(f"lr={lr} {c:7s} {t:3d}: code0 {sh[0]:+6.1f} code15 {sh[-1]:+6.1f} (rel. code 8), span {sh[-1]-sh[0]:5.1f}, "
              f"step mean {st.mean():.2f} max {st.max():.2f}, mono {bool((st > 0).all())}", flush=True)
