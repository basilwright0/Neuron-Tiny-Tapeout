"""Plateau detector pdet: charge drawn from vsrc per threshold crossing, old (unstarved stage 3) vs
new (XS3 starve, cells/dendrite/dendrite.spice). vd ramps EL -> EL+0.4 V in 20 us and back.
usage: python3 sim/tb/dendrite/tb_pdet_q.py [corner] [temp]"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
src = open("/work/cells/dendrite/dendrite.spice").read()
i0 = src.index(".subckt pdet "); new = src[i0:src.index(".ends pdet", i0) + len(".ends pdet")]
old = new.replace(".subckt pdet ", ".subckt pdet_old ").replace(".ends pdet", ".ends pdet_old")
old = "\n".join(l for l in old.splitlines() if not l.startswith("XS3")).replace("XP3 pb  p   s3  vdd", "XP3 pb  p   vdd vdd")
vs = cal_vsrc(corner, temp)
for name in ("pdet_old", "pdet"):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
{old}
{new}
Vdd vdd 0 3.3
Vsr vsrc 0 {vs}
Ibs vbs 0 100n
Xbs vbs vdd pmaster w=1u l=2u
Vd vd 0 pwl(0 {EL} 5u {EL} 25u {EL+0.4} 45u {EL})
X1 vd xb vsrc vbs vdd 0 {name}
"""
    r = run(deck(body, "tran 2n 50u", ["i(vsr)", "v(xb)"], corner=corner, temp=temp), f"dendrite/pdetq_{name}_{corner}_{temp}")
    t, i = r["_x"], np.abs(r["i(vsr)"])
    q = np.trapezoid(i, t)
    idle = float(np.median(i[t < 4e-6]))
    print(f"[{corner}_{temp}] {name:8s} vsrc {vs:.3f}: peak |I(vsrc)| {i.max()*1e6:7.2f} uA, charge over up+down crossing "
          f"{q*1e12:8.2f} pC (idle {idle*1e9:.1f} nA -> {idle*40e-6*1e12:.2f} pC of it)", flush=True)
