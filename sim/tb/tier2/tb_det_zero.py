"""All-zero (bias off) check of the shared det_ah alone: vdd ramp, vm = 0, vsrc = 0, vbp_st = pmaster diode with
no current (B1 off state). Prints internal nodes and supply current. usage: python3 tb_det_zero.py"""
import sys
sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
for vbs in ("Xbs vbp_st vdd pmaster w=1u l=2u", "Vbs vbp_st 0 3.3"):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vsr vsrc 0 0
{vbs}
Vm vm 0 0
Xd vm spk vsrc vbp_st vdd 0 det_ah
"""
    r = run(deck(body, "tran 1u 1m", ["v(spk)", "v(xd.pb)", "v(xd.p)", "v(xd.n1)", "v(vbp_st)", "i(Vdd)"]),
            "tier2/detzero")
    print(vbs.split()[0], {k: round(float(v[-1]), 4) for k, v in r.items() if k not in ("_x", "time")},
          "Idd uA", round(float(-r["i(vdd)"][-1]) * 1e6, 3))
