"""Python mirror of rtl/nc_regmap.vh (rev E, write-only config).

Frame: 13 bit {ADDR[4:0], DATA[7:0]}, MSB first on SCK rising edges, then a
LOAD pulse. Only the last 13 bits before LOAD count.
"""
import os
import re

AW = 5
FW = AW + 8
NREG = 23
TRIM_MASK_DEFAULT = 0xC1FD            # nibbles 0, 2-8, 14, 15

A = dict(
    IDAC=0x00, VDAC=0x05, ANA=0x06, PROBE=0x07, MODE=0x08, LIF_CTL=0x09,
    LIF_SR=0x0A, LIF_EL=0x0B, LIF_VTH=0x0C, LIF_VRST=0x0D, LIF_W=0x0E,
    TRIM0=0x0F,
)

_USED = [0xFF] * 5 + [0x3F, 0xFF, 0x7F, 0xFF, 0x07] + [0xFF] * 5 + [0xFF] * 8
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


def probe_lines(sel, sub, en):
    """Expected (probe_rsel, probe_en_c, probe_sel_d1, probe_sel_adex, probe_sub, probe_sub_b, probe_sub_raw)."""
    slot = REF_SLOT if sub == 3 else SLOT.get(sel)
    rsel = (1 << slot[0]) if slot else 0
    enc = (1 << slot[1]) if (slot and en) else 0
    d1 = int(bool(en) and sub != 3 and sel == D1_CH)
    adex = int(bool(en) and sub != 3 and sel == ADEX_CH)
    return rsel, enc, d1, adex, sub & 1, 1 - (sub & 1), sub


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
    return sel | (sub << 4) | (en << 6)


def mode(ua0=0, out_mux=0, rt_en=0, ib_x2=0):
    return ua0 | (out_mux << 2) | (ib_x2 << 3) | (rt_en << 4)


def lif_ctl(lif_en=0, lif_src=0):
    return lif_en | (lif_src << 1)


def lif_sr(shift=0, refr=0):
    return shift | (refr << 4)


def frame(addr, data):
    return ((addr & 0x1F) << 8) | (data & 0xFF)
