"""D1 passive steady-state transfer matrix R[i,j] = dV_i/dI_j vs model/reference.py Compartments.

usage: python3 sim/tb/dendrite/tb_transfer.py [corner] [temp] [topo star|chain] [gax_nS]
Transient: +20 pA step into each compartment (soma, d1, d2), settled response after 1.5 ms.
Detectors parked (vsrc = vsrcp = 1.4 V) so the DC solution is unique; the leak/axial path is unaffected.
"""
import json
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
from reference import Compartments

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
topo = sys.argv[3] if len(sys.argv) > 3 else "star"
gax = float(sys.argv[4]) * 1e-9 if len(sys.argv) > 4 else 4e-9
S = 100.0
nodes = ["vs", "d1", "d2"]
R = np.zeros((3, 3))
rest = None
IST = 20e-12           # small step (|dV| < 6 mV: leak tanh linear to < 0.1 %)
TS, TM = 2e-3, 3.5e-3  # step time, read time (slowest mode tau = C/gL = 100 us -> 15 tau)
for j, nj in enumerate(nodes):
    # transient, not .dc: the DC solver can land on different solutions of the switch/timer/detector
    # nodes (seen at typical 0 C); a settled transient is unambiguous.
    body = f"""{cells()}
{bias(S=S, gax=gax, vsrc=1.4, pl_en=0, chain=int(topo == 'chain'))}
Iin vdd {nj} pwl(0 0 {TS} 0 {TS + 1e-6} {IST})
{DUT}
"""
    r = run(deck(body, f"tran 2u {TM}", [f"v({n})" for n in nodes], corner=corner, temp=temp),
            f"dendrite/xfer_{corner}_{temp}_{topo}_{gax*1e9:g}_{j}")
    x = r["_x"]
    for i, ni in enumerate(nodes):
        v = r[f"v({ni})"]
        R[i, j] = (v[-1] - np.interp(TS - 1e-6, x, v)) / IST
    rest = [float(np.interp(TS - 1e-6, x, r[f"v({n})"])) for n in nodes]
g = g_leak(S)
if topo == "star":
    m = Compartments.star(2, C=C, gL=g, g_ax=gax)
    perm = [0, 1, 2]
else:
    m = Compartments.chain(3, C=C, gL=g, g_ax=gax)   # chain order soma-d1-d2 = model 0-1-2
    perm = [0, 1, 2]
Rm = m.steady_state_transfer()
print(f"{corner} {temp}C {topo} g_ax={gax*1e9:g} nS: rest vs,d1,d2 = " + ", ".join(f"{v:.4f}" for v in rest))
print("R spice (MOhm):\n", np.round(R / 1e6, 1))
print("R model (MOhm):\n", np.round(Rm / 1e6, 1))
print("ratio spice/model:\n", np.round(R / Rm, 3))
att = R[0, 1] / R[1, 1]; attm = Rm[0, 1] / Rm[1, 1]
print(f"attenuation d1->soma: spice {att:.3f} model {attm:.3f}")
(OUT / f"xfer_{corner}_{temp}_{topo}_{gax*1e9:g}.json").write_text(json.dumps(
    dict(corner=corner, temp=temp, topo=topo, gax=gax, R=R.tolist(), Rm=Rm.tolist(), rest=rest)))
