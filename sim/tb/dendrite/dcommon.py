"""Shared setup for the D1 dendrite testbenches (run inside the EDA container via scripts/eda.sh).

Bias point = the array's S = 100 point (tb_lif_fi.py): EL 1.30 V (2026-11-19, was 1.20), g_L = 2 nS (Ib_leak = 324 pA),
Vth 1.38 V (vsrc calibrated per corner, as on silicon), t_ref 2 ms bio.  Axial g_ax = 4 nS
(Iax = 647 pA) = the reference model's Compartments.star default.
"""
import os
import sys

import numpy as np

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/model")
from ngs import deck, run, include, crossings, rate, RESULTS, CORNERS, TEMPS  # noqa: E402,F401

G_PER_IB = 0.927e-9 / 150e-12          # leak_ota_deg g/Ib (tb_leak_iv), S/A
C = 200e-15
EL, VTH, VRESET = 1.30, 1.38, 1.30
OUT = RESULTS / "dendrite"
OUT.mkdir(parents=True, exist_ok=True)


def g_leak(S=100.0):
    return C * S / 10e-3


def cells():
    return include("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice",
                   "neuron/synapse.spice", "dendrite/dtrim.spice", "dendrite/dendrite.spice")


def ah_trip(vsrc, corner, temp, S=100.0, tag=""):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {100e-9 * max(1, S / 100)}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=corner, temp=temp),
            f"dendrite/ahtrip_{corner}_{temp}{tag}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


_CAL = {}
STIM0 = "Vsta sta 0 0\nVstb stb 0 0\n"


def cal_vsrc(corner, temp, S=100.0):
    """Per-die vsrc calibration (as on silicon): AH trip at VTH."""
    key = (corner, temp, S)
    if key not in _CAL:
        v = 0.60
        for _ in range(4):
            tr = ah_trip(v, corner, temp, S, tag=f"_{os.getpid()}")
            v = float(np.clip(v + (VTH - tr) / 1.27, 0.05, 1.2))
        _CAL[key] = v
    return _CAL[key]


def bias(S=100.0, gax=4e-9, vsrc=0.505, pl_en=1, chain=0, ib_leak=None, iax=None, vsrcp=None,
         bsel=0, hold=0, iw=0.0, trim=8, stim=True):
    """Bias network + supplies. Node names match dend_d1's ports."""
    g = g_leak(S)
    ibl = ib_leak if ib_leak is not None else g / G_PER_IB
    ibax = iax if iax is not None else gax / G_PER_IB
    i_ref = 50e-15 * (3.3 - 1.95) / (2e-3 / S)
    i_st = 100e-9 * max(1, S / 100)
    return f"""Vdd vdd 0 3.3
Vel el 0 {EL}
Vrs vrst 0 {VRESET}
Vsr vsrc 0 {vsrc}
Vsp vsrcp 0 {vsrc if vsrcp is None else vsrcp}
Ibl vdd vbl {ibl}
Xbl vbl 0 nmaster
Iba vdd vba {ibax}
Xba vba 0 nmaster
Ibr vdd vbr {i_ref}
Xbr vbr 0 nmaster
Ibs vbs 0 {i_st}
Xbs vbs vdd pmaster w=1u l=2u
Vpb vbp 0 0
Ven en 0 0
Vs0 sel0 0 0
Vs1 sel1 0 0
Vs2 sel2 0 0
Vab abus 0 0
Vpl plen 0 {3.3 * pl_en}
Vch chain 0 {3.3 * chain}
Vbsel bsel 0 {3.3 * bsel}
Vhold hold 0 {hold if isinstance(hold, str) else 3.3 * hold}
Vmrst mreset 0 0
Isyn vsyn 0 {iw}
Xsyn vsyn vdd pmaster w=2u l=4u
Vta ta 0 {3.3 if trim & 8 else 0}
""" + (STIM0 if stim else "")


# trim code 8 (mid-scale, bit 3 high) on both subunits; stim lines sta/stb default to 0 V sources
# named Vsta/Vstb unless a testbench defines its own (STIM=False)
DUT = ("XD vs d1 d2 spk sel0 sel1 sel2 plen chain bsel sta stb hold mreset vsyn 0 0 0 ta 0 0 0 ta "
       "el vsrc vsrcp vrst vbl vbs vbr vbp vba en abus vdd 0 dend_d1")

