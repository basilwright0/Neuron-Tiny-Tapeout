"""Python mirror of rtl/nc_regmap.vh (rev C, write-only config).

Frame: 13 bit {ADDR[4:0], DATA[7:0]}, MSB first on SCK rising edges, then a
LOAD pulse. Only the last 13 bits before LOAD count.
"""

AW = 5
FW = AW + 8
NREG = 26

A = dict(
    IDAC0=0x00, IDAC1=0x01, IDAC2=0x02, IDAC3=0x03, IDAC4=0x04, IDAC5=0x05,
    VDAC0=0x06, VDAC1=0x07, VDAC2=0x08,
    ANA=0x09, PROBE=0x0A, MODE=0x0B, CLKD=0x0C,
    LIF_SR=0x0D, LIF_EL=0x0E, LIF_VTH=0x0F, LIF_VRST=0x10, LIF_W=0x11,
    TRIM0=0x12,
)

_USED = [0xFF] * 6 + [0x3F] * 3 + [0x7F, 0x7F, 0xF7, 0x7F] + [0xFF] * 5 + [0xFF] * 8
assert len(_USED) == NREG


def reg_used(ntrim=16):
    """Stored bits per byte (index = address) for a given NTRIM."""
    u = list(_USED)
    for t in range(8):
        m = 0
        if 2 * t < ntrim:
            m |= 0x0F
        if 2 * t + 1 < ntrim:
            m |= 0xF0
        u[A["TRIM0"] + t] = m
    return u


# cfg_out packing (nc_regmap.vh CFG_*)
CFG_IDAC, CFG_VDAC, CFG_PSUB, CFG_PEN, CFG_GRP, CFG_PLAT, CFG_BIAS, CFG_UA0, CFG_TRIM = \
    0, 48, 66, 68, 69, 73, 75, 76, 78


def cfg_pack(regs, ntrim=16):
    """Expected cfg_out from the byte image regs[0..NREG-1]."""
    c = 0
    for k in range(6):
        c |= regs[A["IDAC0"] + k] << (CFG_IDAC + 8 * k)
    for k in range(3):
        c |= (regs[A["VDAC0"] + k] & 0x3F) << (CFG_VDAC + 6 * k)
    ana, pr, mode = regs[A["ANA"]], regs[A["PROBE"]], regs[A["MODE"]]
    c |= ((pr >> 4) & 3) << CFG_PSUB
    c |= ((pr >> 6) & 1) << CFG_PEN
    c |= (ana & 0xF) << CFG_GRP
    c |= ((ana >> 4) & 3) << CFG_PLAT
    c |= ((ana >> 6) & 1) << CFG_BIAS
    c |= (mode & 3) << CFG_UA0
    for n in range(ntrim):
        c |= ((regs[A["TRIM0"] + n // 2] >> (4 * (n % 2))) & 0xF) << (CFG_TRIM + 4 * n)
    return c


def ana(grp=0, plat=0, bias=0):
    return grp | (plat << 4) | (bias << 6)


def probe(sel=0, sub=0, en=0):
    return sel | (sub << 4) | (en << 6)


def mode(ua0=0, out_mux=0, rt_en=0):
    return ua0 | (out_mux << 2) | (rt_en << 4)


def clkd(sc_div=0, lif_en=0, lif_src=0):
    return sc_div | (lif_en << 4) | (lif_src << 5)


def lif_sr(shift=0, refr=0):
    return shift | (refr << 4)


def idac(fine=0, rng=0):
    return fine | (rng << 5)


def frame(addr, data):
    return ((addr & 0x1F) << 8) | (data & 0xFF)
