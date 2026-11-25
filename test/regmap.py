"""Python mirror of rtl/nc_regmap.vh (rev E, write-only config).

Frame: 13 bit {ADDR[4:0], DATA[7:0]}, MSB first on SCK rising edges, then a
LOAD pulse. Only the last 13 bits before LOAD count.
"""
import os
import re

AW = 5
FW = AW + 8
NREG = 24
N_SPK = 24                            # spike inputs (OUT_BANK selects uo = ch 7..0 or 23..16)
TRIM_MASK_DEFAULT = 0xC1FD            # nibbles 0, 2-8, 14, 15

A = dict(
    IDAC=0x00, VDAC=0x05, ANA=0x06, PROBE=0x07, MODE=0x08, LIF_CTL=0x09,
    LIF_SR=0x0A, LIF_EL=0x0B, LIF_VTH=0x0C, LIF_VRST=0x0D, LIF_W=0x0E,
    TRIM0=0x0F, OUT=0x17,
)

_USED = [0xFF] * 5 + [0x3F, 0xFF, 0xFF, 0xFF, 0x07] + [0xFF] * 5 + [0xFF] * 8 + [0x01]
assert len(_USED) == NREG


def reg_used(ntrim=16, mask=TRIM_MASK_DEFAULT):
    """Stored bits per byte (index = address) for a given NTRIM / TRIM_MASK."""
    u = list(_USED)
    for t in range(8):
        m = 0
        if 2 * t < ntrim and (mask >> (2 * t)) & 1:
            m |= 0x0F
        if 2 * t + 1 < ntrim and (mask >> (2 * t + 1)) & 1:
            m |= 0xF0
        u[A["TRIM0"] + t] = m
    return u


# cfg_out packing (nc_regmap.vh CFG_*): GRP_EN, PLATEAU_EN, D1_CHAIN, D1_BSEL, trims
CFG_GRP, CFG_PLAT, CFG_CHAIN, CFG_BSEL, CFG_TRIM = 0, 4, 5, 6, 7


def cfg_pack(regs, ntrim=16):
    """Expected cfg_out from the byte image regs[0..NREG-1]."""
    ana = regs[A["ANA"]]
    c = (ana & 0xF) << CFG_GRP
    c |= ((ana >> 4) & 1) << CFG_PLAT
    c |= ((ana >> 5) & 1) << CFG_CHAIN
    c |= ((ana >> 7) & 1) << CFG_BSEL
    for n in range(ntrim):
        c |= ((regs[A["TRIM0"] + n // 2] >> (4 * (n % 2))) & 0xF) << (CFG_TRIM + 4 * n)
    return c


def ana(grp=0, plat=0, chain=0, bias=0, bsel=0):
    return grp | (plat << 4) | (chain << 5) | (bias << 6) | (bsel << 7)


# --------------------------------------------------------------- probe model
# spike channel -> (row, col) in the 4x4 array (row 0 = bottom), from floorplan/floorplan.py
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _slot_table():
    import importlib.util
    spec = importlib.util.spec_from_file_location("floorplan", os.path.join(ROOT, "floorplan", "floorplan.py"))
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    where = {n: rc for rc, n in fp.slot_map().items()}
    return ({ch: where[n] for n, ch in fp.SPIKE_CH.items() if n in where},
            fp.SPIKE_CH["D1"], fp.SPIKE_CH["ADEX"], where["REF"], fp, where)


PHYS, D1_CH, ADEX_CH, REF_SLOT, _fp, _where = _slot_table()
# Probe decoder of the control macro (rev E, hardened): SEL -> (row, col), frozen (docs/regmap.md section 3.1).
SLOT = {0: (0, 1), 1: (1, 2), 2: (0, 2), 4: (1, 3), 5: (2, 3), 6: (1, 0), 7: (2, 0),
        8: (3, 0), 9: (3, 1), 10: (2, 1), 11: (3, 2), 12: (1, 1), 14: (2, 2), 15: (3, 3)}
# M2 layout B (2026-11-21): the slots moved, the decoder did not. Every decoded address must hold a probe tap and
# every array neuron must sit at a decoded address; SEL k then reads the neuron at SLOT[k] (PROBE_NAME, docs/regmap.md).
assert set(PHYS.values()) == set(SLOT.values()), PHYS
PROBE_NAME = {k: _fp.slot_map()[rc] for k, rc in SLOT.items()}
# (0,3) is CMP's lower half (formerly the dummy slot): no tap, never selected
DUMMY_SLOT = (0, 3)
assert _fp.cell_at(*DUMMY_SLOT)[0] == _where["CMP"] and DUMMY_SLOT not in _where
assert (D1_CH, ADEX_CH, REF_SLOT) == (13, 3, (0, 0))


# PROBE_SEL[4] = 1 (SEL 16..31, PROBE[7]): 16..18 bay neurons 0..2 (probe_sel_bay[k], outside the array),
# 22 / 23 column 4 rows 2 / 3 (probe_en_c4 + probe_rsel); every other value selects nothing.
SLOT_HI = {22: (2, 4), 23: (3, 4)}
BAY_SEL = {16: 0, 17: 1, 18: 2}


def probe_lines_old(sel, sub, en):
    """Rev E (fdcf2ad) decoder, 4-bit SEL: (rsel, en_c, d1, adex, sub, sub_b, sub_raw). Frozen regression table."""
    slot = REF_SLOT if sub == 3 else SLOT.get(sel)
    rsel = (1 << slot[0]) if slot else 0
    enc = (1 << slot[1]) if (slot and en) else 0
    d1 = int(bool(en) and sub != 3 and sel == D1_CH)
    adex = int(bool(en) and sub != 3 and sel == ADEX_CH)
    return rsel, enc, d1, adex, sub & 1, 1 - (sub & 1), sub


def probe_lines(sel, sub, en):
    """Expected (probe_rsel, probe_en_c, probe_sel_d1, probe_sel_adex, probe_sub, probe_sub_b, probe_sub_raw,
    probe_sel_bay, probe_en_c4) for a 5-bit SEL."""
    if sel < 16:
        return probe_lines_old(sel, sub, en) + (0, 0)
    slot = REF_SLOT if sub == 3 else SLOT_HI.get(sel)
    rsel = (1 << slot[0]) if slot else 0
    enc = (1 << slot[1]) if (slot and en and slot[1] < 4) else 0
    c4 = int(bool(slot and en and slot[1] == 4))
    bay = (1 << BAY_SEL[sel]) if (en and sub != 3 and sel in BAY_SEL) else 0
    return rsel, enc, 0, 0, sub & 1, 1 - (sub & 1), sub, bay, c4


# --------------------------------------------------------------- bias_b1 model
def bias_port_names():
    """bias_b1 control ports in port order, as declared in rtl/nc_bias_ports.vh (generated)."""
    with open(os.path.join(ROOT, "rtl", "nc_bias_ports.vh")) as f:
        src = f.read()
    return re.findall(r"output wire (\w+),", src)


BIAS_PORTS = bias_port_names()
IDACS = list(dict.fromkeys(n[:-3] for n in BIAS_PORTS if re.match(r"^\w+_b\d$", n)))
VDACS = list(dict.fromkeys(n[:-3] for n in BIAS_PORTS if re.match(r"^\w+_c\d$", n)))
assert len(IDACS) == 8 and len(VDACS) == 1, (IDACS, VDACS)


def idac_word(codes):
    """Bytes A_IDAC..+4 for eight 5-bit codes (code k at word bits [5k+4:5k])."""
    w = 0
    for k, c in enumerate(codes):
        w |= (c & 0x1F) << (5 * k)
    return [(w >> (8 * i)) & 0xFF for i in range(5)]


def bias_lines(regs):
    """Expected value of every bias_b1 control port, by name."""
    out = {}
    w = sum(regs[A["IDAC"] + i] << (8 * i) for i in range(5))
    for k, p in enumerate(IDACS):
        for j in range(5):
            out[f"{p}_b{j}"] = (w >> (5 * k + j)) & 1
    for j in range(6):
        out[f"{VDACS[0]}_c{j}"] = (regs[A["VDAC"]] >> j) & 1
    bias_en = (regs[A["ANA"]] >> 6) & 1
    m = regs[A["MODE"]] & 3
    out.update(ua0_s0=int(m in (0, 3)), ua0_s1=int(m == 1), ua0_stim=int(m == 2),
               ua0_int=int((m >> 1) & bias_en), bias_en=bias_en, ib_x2=(regs[A["MODE"]] >> 3) & 1)
    assert set(out) == set(BIAS_PORTS)
    return out


def probe(sel=0, sub=0, en=0):
    """PROBE byte for a 5-bit SEL: SEL[3:0] at [3:0], SEL[4] at [7]."""
    return (sel & 0xF) | (sub << 4) | (en << 6) | (((sel >> 4) & 1) << 7)


def probe_fields(byte):
    """(sel5, sub, en) from a PROBE byte."""
    return (byte & 0xF) | (((byte >> 7) & 1) << 4), (byte >> 4) & 3, (byte >> 6) & 1


def mode(ua0=0, out_mux=0, rt_en=0, ib_x2=0):
    return ua0 | (out_mux << 2) | (ib_x2 << 3) | (rt_en << 4)


def lif_ctl(lif_en=0, lif_src=0):
    return lif_en | (lif_src << 1)


def lif_sr(shift=0, refr=0):
    return shift | (refr << 4)


def frame(addr, data):
    return ((addr & 0x1F) << 8) | (data & 0xFF)


# --------------------------------------------------------------- R2 (MIL-362) firmware view, docs/info.md "R2 additions"
GRP_E2_LEAK, GRP_E1_EN = 0, 1             # ANA GRP_EN bits (cfg_out[0], cfg_out[1]); bits 2-3 spare (latched, unconnected)
BAY_NAME = {16: "S4", 17: "F4", 18: "E1"}   # bay column, spike channel = SEL (spk_in[16..18]); spk_in[19..23] tied low
assert {BAY_NAME[s]: s for s in BAY_SEL} == {n: _fp.SPIKE_CH[n] for n in ("S4", "F4", "E1")}
# E2 leakage nodes: PROBE_SUB = 1 position of array row 3, columns 2 / 3 (AH50 / AH400 slots, no SUB = 1 tap of their own)
E2_SLOT = {"E2a": (3, 2), "E2b": (3, 3)}
E2_SEL = {n: next(k for k, rc in SLOT.items() if rc == s) for n, s in E2_SLOT.items()}
assert E2_SEL == {"E2a": 11, "E2b": 15} and (PROBE_NAME[11], PROBE_NAME[15]) == ("AH50", "AH400"), E2_SEL
