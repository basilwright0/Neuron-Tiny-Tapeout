"""Python mirror of rtl/nc_regmap.vh (rev B, byte-addressed).

SPI frame: 16 bit {RW, ADDR[6:0], DATA[7:0]}, MSB first, RW=1 read.
"""

CHIP_ID = 0xA2
NREG = 20

A = dict(
    CTRL=0x00, RT=0x01, SEL0=0x02, SEL1=0x03, SEL2=0x04, SEL3=0x05,
    PROBE=0x06, GRP=0x07, DAC_LEAK=0x08, DAC_VTH=0x09, DAC_VRST=0x0A,
    DAC_WSYN=0x0B, SC=0x0C, ANA=0x0D, LIF0=0x0E, LIF1=0x0F,
    LIF_EL=0x10, LIF_VTH=0x11, LIF_VRST=0x12, LIF_W=0x13,
    CNT_L=0x14, CNT_H=0x15, LIFV_L=0x16, LIFV_H=0x17, STATUS=0x18, ID=0x19,
)

# stored bits per writable register (index = address)
REG_USED = [0x1F, 0xFF, 0x1F, 0x1F, 0x1F, 0x1F, 0xFF, 0xFF, 0xFF, 0xFF,
            0xFF, 0xFF, 0xCF, 0x07, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
assert len(REG_USED) == NREG


def ctrl(spk_mode=0, cnt_mode=0, cnt_src=0):
    return spk_mode | (cnt_mode << 1) | (cnt_src << 3)


def probe(sel=0, sub=0, en=0):
    return sel | (sub << 5) | (en << 7)


def lif0(en=0, src=0, step=0, presc=0):
    return en | (src << 1) | (step << 3) | (presc << 4)


def lif1(shift=0, refr=0):
    return shift | (refr << 4)


def wframe(addr, data):
    return (addr << 8) | data


def rframe(addr):
    return 0x8000 | (addr << 8)
