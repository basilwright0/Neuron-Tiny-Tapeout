"""Ep generator options across corners: nfet diode from el (vep = el + Vgs) at Ib_leak."""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
opts = [("4u", "1u"), ("2u", "2u"), ("1u", "4u")]
for c in CORNERS:
    for t in TEMPS:
        body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 1.2
Ibl vdd vbl 324p
Xbl vbl 0 nmaster
""" + "\n".join(f"""XS{k} m{k} vbl 0 0 nfet_03v3 W=2u L=4u
XPD{k} m{k} m{k} vdd vdd pfet_03v3 W=1u L=2u
XPM{k} v{k} m{k} vdd vdd pfet_03v3 W=1u L=2u
XN{k} v{k} v{k} el 0 nfet_03v3 W={w} L={l}""" for k, (w, l) in enumerate(opts))
        r = run(deck(body, "op", [f"v(v{k})" for k in range(len(opts))], corner=c, temp=t), f"dendrite/vep_{c}_{t}")
        print(c, t, " ".join(f"{float(r[f'v(v{k})'][0]) - 1.2:.3f}" for k in range(len(opts))))
