"""Shared setup for the Tier-2 testbenches (A1 AdEx, S1 SC dendrite). Run inside the EDA container:

    scripts/eda.sh "python3 sim/tb/tier2/tb_adex.py"

Bias point = the array's S = 100 point (sim/tb/dendrite/dcommon.py): EL 1.30 V (2026-11-19), Ib_leak 324 pA
AH trip 1.38 V (vsrc calibrated per corner), t_ref 2 ms bio.
"""
import sys

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/model")
sys.path.insert(0, "/work/sim/tb/dendrite")
from ngs import deck, run, include, crossings, rate, RESULTS  # noqa: E402,F401
from dcommon import G_PER_IB, C, EL, VTH, VRESET, g_leak  # noqa: E402,F401
import os  # noqa: E402
import numpy as np  # noqa: E402

OUT = RESULTS / "tier2"
OUT.mkdir(parents=True, exist_ok=True)


def ah_trip(vsrc, corner, temp, S=100.0, tag=""):
    """AH detector trip point (same as sim/tb/dendrite/dcommon.py, results kept under tier2/)."""
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {100e-9 * max(1, S / 100)}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=corner, temp=temp),
            f"tier2/ahtrip_{corner}_{temp}{tag}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


_CAL = {}
_TOK = os.urandom(3).hex()      # concurrent containers share pids: make the cal file names unique


def cal_vsrc(corner, temp, S=100.0):
    """Per-die vsrc calibration (as on silicon): AH trip at VTH."""
    key = (corner, temp, S)
    if key not in _CAL:
        v = 0.60
        for _ in range(4):
            tr = ah_trip(v, corner, temp, S, tag=f"_{os.getpid()}_{_TOK}")
            v = float(np.clip(v + (VTH - tr) / 1.27, 0.05, 1.2))
        _CAL[key] = v
    return _CAL[key]


def cells(*extra):
    return include("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice",
                   "neuron/synapse.spice", *extra)


def bias(S=100.0, vsrc=0.505, i_adw=0.0, hold=0, iw=0.0):
    """Supplies + bias masters; node names = the A1/S1 port names."""
    ibl = g_leak(S) / G_PER_IB
    i_ref = 50e-15 * (3.3 - 1.95) / (2e-3 / S)
    i_st = 100e-9 * max(1, S / 100)
    return f"""Vdd vdd 0 3.3
Vel el 0 {EL}
Vrs vreset 0 {VRESET}
Vsr vsrc 0 {vsrc}
Ibl vdd vbn_leak {ibl}
Xbl vbn_leak 0 nmaster
Ibr vdd vbn_ref {i_ref}
Xbr vbn_ref 0 nmaster
Ibs vbp_st 0 {i_st}
Xbs vbp_st vdd pmaster w=1u l=2u
Iad vbp_w 0 {i_adw}
Xad vbp_w vdd pmaster w=1u l=2u
Rad vbp_w vdd 1e12
Vpb vbn_prb 0 0
Ven en 0 0
Vs0 sel0 0 0
Vs1 sel1 0 0
Vs2 sel2 0 0
Vsa sel_adex 0 0
Vsb0 sub0 0 0
Vsb1 sub1 0 0
Vab abus 0 0
Vhold hold 0 {3.3 * hold}
Vmrst mreset 0 0
Isyn vbp_syn 0 {iw}
Xsyn vbp_syn vdd pmaster w=2u l=4u
Rsyn vbp_syn vdd 1e12
"""
