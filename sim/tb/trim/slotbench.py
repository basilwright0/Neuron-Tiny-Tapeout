"""Shared test-bench pieces for the neuron-array slot cells (cells/neuron/slot.spice).

Used by sim/tb/trim/*, sim/tb/synapse/*, sim/tb/tb_lif_mc.py (trim mode) and tb_slot_fi.py.
Biasing follows tb_lif_fi.py / tb_slot_fi.py: tau_bio = 10 ms, S = speed-up, 200 fF membrane,
EL = Vreset = 1.30 V, AH threshold calibrated to 1.38 V per die/temperature through vsrc.
"""
import sys

import numpy as np

sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings   # noqa: E402,F401

C = 200e-15
G_PER_IB = 6.33                     # leak_ota_deg g / I_b, typical 27 C, EL 1.30 (4/1 inputs, 8/1 diodes; was 6.18)
EL, VTH, VRESET = 1.30, 1.38, 1.30         # 2026-11-19: +0.1 V with the leak OTA fix
TREF_BIO = 2e-3
LIBS = ("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice",
        "neuron/synapse.spice", "trim/trim_gap.spice", "neuron/slot.spice")
PORTS = {
    "slot_ah": "vm spk rsel sub sub_b el vsrc vreset vbn_leak vbp_st vbn_ref vbn_prb en abus vdd vss aux "
               "vbp_syn sta stb hold mreset".split(),
}
PORTS["slot_ah_h"] = PORTS["slot_ah"] + "t0 t1 t2 t3".split()
PORTS["slot_ah_p"] = PORTS["slot_ah_h"]
for _c in ("slot_ah_f", "slot_ah_50", "slot_ah_400", "slot_ah_800"):
    PORTS[_c] = PORTS["slot_ah"]
PORTS["slot_cmp_h"] = PORTS["slot_ah_h"]        # gap trim back since the double slot (2026-11-20)
PORTS["slot_dummy"] = [p for p in PORTS["slot_ah"] if p not in ("spk", "rsel", "sub", "sub_b")]
PORTS["slot_ref"] = "rsel sub el vsrc vreset vbn_leak vbp_st vbn_ref vbn_prb en abus vdd vss aux vbp_syn".split()
# per-variant scale factors vs the S slot: membrane C (AH50 / AH400 / AH800) and leak g (F: tail W/L halved)
CFAC = {"slot_ah_50": 50.1 / 200.0, "slot_ah_400": (200.0 + 4.0 * 7.07 * 9.6) / 200.0,
        "slot_ah_800": (200.0 + 4.0 * 11.7 * 11.6) / 200.0}
GFAC = {"slot_ah_f": 0.5}
# testbench net for each port
NETS = dict(vm="vm", spk="spk", rsel="0", sub="0", sub_b="0", el="el", vsrc="vsrc", vreset="vrst", vbn_leak="vbl",
            vbp_st="vbs", vbn_ref="vbr", vbn_prb="vbp", en="0", abus="abus", vdd="vdd", vss="0", aux="el",
            vbp_syn="vsyn", sta="sta", stb="stb", hold="hold", mreset="mrst",
            t0="b0", t1="b1", t2="b2", t3="b3", VSUBS="0")


def nets(cell):
    """Port -> bench net. The P slot's aux is its leak tail gate: tie it to the vbn_leak bias (tau code 8).
    The CMP slot's aux is its threshold vth_cmp (VTH = 1.38 V)."""
    n = dict(NETS)
    if cell == "slot_ah_p":
        n["aux"] = "vbl"
    if cell == "slot_cmp_h":            # aux = vth_cmp (column 3): the comparator threshold, VTH
        n["aux"] = "vthc"
    return n


class Bias:
    def __init__(self, S=100.0):
        self.S = S
        self.g = C * S / 10e-3
        self.ib = self.g / G_PER_IB
        self.tau = C / self.g
        self.rheo = self.g * (VTH - EL)
        self.i_ref = 50e-15 * (3.3 - 1.95) / (TREF_BIO / S)
        self.i_st = 100e-9 * max(1, S / 100)


def ah_trip(vsrc, corner, temp, S, tag):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {100e-9 * max(1, S / 100)}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=corner, temp=temp), f"trip_{tag}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


def cal_vsrc(corner="typical", temp=27, S=100.0, tag=None):
    """Per-die/temperature global calibration of the AH threshold (schematic detector, no mismatch)."""
    tag = tag or f"{corner}_{temp}_S{S:g}"
    v = 0.505
    for _ in range(4):
        v = float(np.clip(v + (VTH - ah_trip(v, corner, temp, S, tag)) / 1.27, 0.05, 1.2))
    return v


def bits(code):
    return [3.3 * ((int(code) >> k) & 1) for k in range(4)]


MASTERS = """Ibl vdd vbl {ib}
Xbl vbl 0 nmaster
Ibr vdd vbr {i_ref}
Xbr vbr 0 nmaster
Ibs vbs 0 {i_st}
Xbs vbs vdd pmaster w=1u l=2u
Ibp vdd vbp 1u
Xbp vbp 0 nmaster w=2u l=2u
Isy vsyn 0 {i_syn}
Xsy vsyn vdd pmaster w=2u l=4u"""
BIAS_NETS = ("vbl", "vbr", "vbs", "vbp", "vsyn")


def bias_voltages(b, corner="typical", temp=27, i_syn=1e-15, tag=None):
    """Gate voltages of the shared bias lines from mismatch-free masters (for mismatch MC: a master's
    mismatch is common to every neuron on the die and is removed by the per-die calibration)."""
    body = f"""{include('neuron/membrane.spice')}
Vdd vdd 0 3.3
{MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=i_syn)}
Vdum dum 0 0
"""
    r = run(deck(body, "dc Vdum 0 0 1", [f"v({n})" for n in BIAS_NETS], corner=corner, temp=temp),
            f"biasv_{tag or f'{corner}_{temp}_S{b.S:g}'}")
    return {n: float(r[f"v({n})"][0]) for n in BIAS_NETS}


def slot_body(cell, b, vsrc, iin=0.0, i_syn=0.0, code=8, sta="0", stb="0", hold="0", mrst="0",
              extra="", inst=None, include_libs=True, vm_src=None, vbias=None):
    """Bench body around one slot instance. sta/stb/hold/mrst: SPICE source values (e.g. '0', '3.3',
    'PULSE(...)'). code: trim code (int) or a node expression handled by the caller via extra."""
    ports = PORTS[cell]
    inst = inst or ("Xn " + " ".join(nets(cell)[p] for p in ports) + f" {cell}")
    bv = bits(code) if isinstance(code, (int, np.integer)) else [None] * 4
    bsrc = "\n".join(f"Vb{k} b{k} 0 {v}" for k, v in enumerate(bv) if v is not None)
    vm_line = f"Vvm vm 0 {vm_src}" if vm_src is not None else ""
    masters = (MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=i_syn) if vbias is None else
               "\n".join(f"V{n} {n} 0 {v}" for n, v in vbias.items()))
    return f"""{include(*LIBS) if include_libs else include('neuron/membrane.spice')}
Vdd vdd 0 3.3
Vel el 0 {EL}
Vrs vrst 0 {VRESET}
Vsr vsrc 0 {vsrc}
Vthc vthc 0 {VTH}
Vab abus 0 0.6
{masters}
Vsa sta 0 {sta}
Vsb stb 0 {stb}
Vho hold 0 {hold}
Vmr mrst 0 {mrst}
{bsrc}
{"Iin vdd vm " + str(iin) if iin else ""}
{vm_line}
{inst}
{extra}
"""
