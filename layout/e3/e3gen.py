"""E3 synaptic-weight test cell `e3_syn` (MIL-452 / MIL-362 R2): generator (magic paint tcl + LVS reference + preview).

Adapted from layout/e2/e2gen.py (same helpers, caps, probe taps, crouter M1-M3, bottom-edge pins, side supplies).

Two floating ~200 fF vm-like nodes na / nb (nMOS gate caps, as the array's vm cap):
  reset : vreset -[SA / SB nMOS 1/0.5, gate gb]- node; gb = NOT grp_en (local CMOS inverter PI / NI 1/0.28), so the
          nodes are held at vreset while grp_en = 0 and released when grp_en = 1.
  taps  : as E2 (XPM_*: SF 4/2, bias 2/2 from vbn_prb enabled by en, then en / rsel / sub -> abus).
  synapse legs (copied from the array slot's syn_in leg, cells/neuron, cslot_ah XS_*):
          vdd -[PH 1/2, gate gb]- h -[W pMOS 2/L, gate vbp_syn]- d -[XN nMOS 0.5/0.28, gate st]- node
                                                                  d -[XQ pMOS 1/0.28, gate st]- vss   (dump while st = 0)
          The array's header (XPH, gate hold) is gated by gb here: grp_en = 0 -> no current from vdd.
          node A: sta leg 1 unit (WAa), stb leg 3 parallel units (WAb1..3, one switch pair)
          node B: sta leg 1 unit (WBa), stb leg 1 wide device 3W/L (WBb)
          Unit = 2/L (array 2/4, L scaled: E3_L, default 6.4 um).
Plan (x right): ring | cap A | row A taps (top) / row B T chain, XN A, reset, XN B, NI (bottom) | cap B |
                n-well: smalls row (XQ A, PI, n-tap, PH, XQ B) at the bottom, mirror columns above (vertical gates,
                one vbp_syn poly plate across all columns) | ring.

Run:  python3 e3gen.py [outdir]   (default out/) -> e3_syn_paint.tcl, e3_syn_lvs.spice, e3_syn_pins.json, preview
      E3_NOFILL=1 skips the KLayout notch fill (host python without klayout: routing check only).
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "compact"), str(HERE.parent / "slot")]   # slotgen_fill needs slot/router.py (as cgen.py)
from geom import Finger, Chain, draw_chain, snap, CONT  # noqa: E402

NAME = "e3_syn"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
LC = float(os.environ.get("E3_LC", "5.2"))      # cap gate length (x)
LM = float(os.environ.get("E3_L", "6.4"))       # synapse unit L (array: 4)
WU = 2.0                                        # synapse unit W (array)
RING = 0.60
H = 12.0
YB = 1.70            # row B diffusion bottom
YA = 5.50            # row A diffusion bottom
CAP_Y0 = 0.94
CAP_TOP = 10.45
GAP = 0.40           # diffusion gap between chains / cap <-> rows
X0 = RING + 0.34     # cap A diffusion left
NW_ENC = 0.43
YS0 = 1.33           # smalls row (pMOS) diffusion bottom: n-well 0.90 = ring + 0.30
YM0 = 3.30           # mirror columns diffusion bottom

shapes = []          # (layer, (x0, y0, x1, y1), net)


def R(layer, r, net=None):
    shapes.append((layer, tuple(snap(v) for v in r), net))


def polycon(x, y, net):
    """poly contact with 0.36 poly head and 0.38 metal1 pad (as geom.draw_chain heads)."""
    R("polysilicon", (x - 0.18, y - 0.18, x + 0.18, y + 0.18), net)
    R("polycontact", (x - 0.115, y - 0.115, x + 0.115, y + 0.115), net)
    R("metal1", (x - 0.19, y - 0.19, x + 0.19, y + 0.19), net)


def chain(typ, items, x0, y0, contacted=None):
    """items: net, (name, W, L, gate), net, ... ; returns dict(regions, gates {name: (xa, xb, W)}, width, stripes)."""
    ch = Chain(typ)
    nets = items[0::2]
    for i, (nm, W, L, g) in enumerate(items[1::2]):
        ch.items.append((Finger(nm, nm, typ, W, L, d=nets[i + 1], g=g, s=nets[i]), False))
    con = contacted or set()
    d = draw_chain(ch, lambda net, i: i in con)
    top = d["top"]
    for layer, r in d["shapes"]:
        if layer in ("polycontact", "metal1") or (layer == "polysilicon" and r[3] > 1e-6):
            continue                       # gate heads / stems: drawn by the caller; stripes below with nets
        R(layer, (r[0] + x0, r[1] + y0, r[2] + x0, r[3] + y0))
    stripes = []
    for net, lay, r in d["terms"]:
        if r[1] < top:                     # contact stripe (gate pads sit above the diffusion)
            rr = (r[0] + x0, r[1] + y0, r[2] + x0, r[3] + y0)
            R("metal1", rr, net)
            stripes.append((net, rr))
    regs = [(n, xa + x0, xb + x0, c) for n, xa, xb, c in d["regions"]]
    gates = {f.name: (xa + x0, xb + x0, f.W) for f, xa, xb in d["gates"]}
    return dict(regions=regs, gates=gates, width=d["width"], y0=y0, stripes=stripes, top=top)


# ------------------------------------------------------------------ devices
DEV = []   # LVS reference lines: (name, d, g, s, b, model, W, L)


def dev(nm, d, g, s, b, model, W, L):
    DEV.append((nm, d, g, s, b, model, W, L))


# row A: F chain (both probe followers + bias legs), as E2
itemsA = ["vdd", ("MFA", 4.0, 2.0, "na"), "pa", ("MEA", 1.0, 0.28, "en_a"), "sa", ("MBA", 2.0, 2.0, "vbn_prb"),
          "vss", ("MBB", 2.0, 2.0, "vbn_prb"), "sb", ("MEB", 1.0, 0.28, "en_b"), "pb", ("MFB", 4.0, 2.0, "nb"), "vdd"]
capw = 0.44 + LC + 0.44
XA = snap(X0 + capw + GAP)
A = chain("n", itemsA, XA, YA, contacted={0, 1, 2, 3, 4, 5, 6})
for nm, d_, g, s in (("MFA", "vdd", "na", "pa"), ("MEA", "pa", "en_a", "sa"), ("MBA", "sa", "vbn_prb", "vss"),
                     ("MBB", "sb", "vbn_prb", "vss"), ("MEB", "pb", "en_b", "sb"), ("MFB", "vdd", "nb", "pb")):
    w, l = {"MF": (4, 2), "ME": (1, 0.28), "MB": (2, 2)}[nm[:2]]
    dev(nm, d_, g, s, "vss", "nfet_03v3", w, l)

# row B: T chain (probe switches of both taps, shared abus contact), as E2
itemsT = ["pa", ("SCA", 1.0, 0.28, "en_a"), "mca", ("SWA", 1.0, 0.28, "rsel"), "ma", ("SBA", 1.0, 0.28, "sub"),
          "abus", ("SBB", 1.0, 0.28, "sub"), "mb", ("SWB", 1.0, 0.28, "rsel"), "mcb", ("SCB", 1.0, 0.28, "en_b"), "pb"]
XT = XA
T = chain("n", itemsT, XT, YB, contacted={0, 3, 6})
for nm, d_, g, s in (("SCA", "pa", "en_a", "mca"), ("SWA", "mca", "rsel", "ma"), ("SBA", "ma", "sub", "abus"),
                     ("SBB", "mb", "sub", "abus"), ("SWB", "mcb", "rsel", "mb"), ("SCB", "pb", "en_b", "mcb")):
    dev(nm, d_, g, s, "vss", "nfet_03v3", 1, 0.28)

# row B: synapse pass switches of node A (array XN 0.5/0.28), the reset pair, node B's switches, inverter nMOS
x = snap(XT + T["width"] + GAP)
XNA = chain("n", ["dbA", ("XNAb", 0.5, 0.28, "stb"), "na", ("XNAa", 0.5, 0.28, "sta"), "daA"], x, YB, contacted={0, 1, 2})
dev("XNAa", "daA", "sta", "na", "vss", "nfet_03v3", 0.5, 0.28)
dev("XNAb", "dbA", "stb", "na", "vss", "nfet_03v3", 0.5, 0.28)
x = snap(x + XNA["width"] + GAP)
Rc = chain("n", ["na", ("SA", 1.0, 0.5, "gb"), "vreset", ("SB", 1.0, 0.5, "gb"), "nb"], x, YB, contacted={0, 1, 2})
dev("SA", "vreset", "gb", "na", "vss", "nfet_03v3", 1, 0.5)
dev("SB", "vreset", "gb", "nb", "vss", "nfet_03v3", 1, 0.5)
x = snap(x + Rc["width"] + GAP)
XNB = chain("n", ["daB", ("XNBa", 0.5, 0.28, "sta"), "nb", ("XNBb", 0.5, 0.28, "stb"), "dbB"], x, YB, contacted={0, 1, 2})
dev("XNBa", "daB", "sta", "nb", "vss", "nfet_03v3", 0.5, 0.28)
dev("XNBb", "dbB", "stb", "nb", "vss", "nfet_03v3", 0.5, 0.28)
x = snap(x + XNB["width"] + GAP)
NI = chain("n", ["vss", ("NI", 1.0, 0.28, "grp_en"), "gb"], x, YB, contacted={0, 1})
dev("NI", "gb", "grp_en", "vss", "vss", "nfet_03v3", 1, 0.28)
XCB = snap(max(XA + A["width"], x + NI["width"]) + GAP)     # cap B diffusion left

# ------------------------------------------------------------------ n-well block (right)
XNW = snap(XCB + capw + 0.45)          # n-well left edge (0.45 from cap B's diffusion)
XM = snap(XNW + NW_ENC)                # first pMOS diffusion
# smalls row: XQ A | PI | n-tap | PH (both headers) | XQ B
x = XM
XQA = chain("p", ["daA", ("XQAa", 1.0, 0.28, "sta"), "vss", ("XQAb", 1.0, 0.28, "stb"), "dbA"], x, YS0, contacted={0, 1, 2})
dev("XQAa", "vss", "sta", "daA", "vdd", "pfet_03v3", 1, 0.28)
dev("XQAb", "vss", "stb", "dbA", "vdd", "pfet_03v3", 1, 0.28)
x = snap(x + XQA["width"] + 0.46)        # 0.46: Pplus hole to the ring >= 0.35 um2 (PP.8b)
PIc = chain("p", ["vdd", ("PI", 1.0, 0.28, "grp_en"), "gb"], x, YS0, contacted={0, 1})
dev("PI", "gb", "grp_en", "vdd", "vdd", "pfet_03v3", 1, 0.28)
x = snap(x + PIc["width"] + 0.34)
NT = (x, YS0, x + 0.42, YS0 + 1.0)
R("nsubdiff", NT, "vdd")
R("nsubdiffcont", (x + 0.095, YS0 + 0.065, x + 0.325, YS0 + 0.935), "vdd")
R("metal1", (x + 0.095, YS0 + 0.01, x + 0.325, YS0 + 0.99), "vdd")
x = snap(x + 0.42 + 0.34)
PH = chain("p", ["hA", ("PHA", 1.0, 2.0, "gb"), "vdd", ("PHB", 1.0, 2.0, "gb"), "hB"], x, YS0, contacted={0, 1, 2})
dev("PHA", "hA", "gb", "vdd", "vdd", "pfet_03v3", 1, 2)
dev("PHB", "hB", "gb", "vdd", "vdd", "pfet_03v3", 1, 2)
x = snap(x + PH["width"] + 0.46)         # as above

# mirror: vertical columns (W along x, L along y), drain row at the bottom, source row at the top
COLS = [("WAa", WU, "daA", "hA"), ("WAb1", WU, "dbA", "hA"), ("WAb2", WU, "dbA", "hA"), ("WAb3", WU, "dbA", "hA"),
        ("WBa", WU, "daB", "hB"), ("WBb", 3 * WU, "dbB", "hB")]
CGAP = [0.34, 0.34, 0.34, 0.90, 0.34]  # the 0.90 gap holds the vbp_syn poly contact
MH = 0.44 + LM + 0.44                  # column diffusion height
GY0, GY1 = YM0 + 0.44, YM0 + 0.44 + LM
colx = []
xc = XM
for i, (nm, w, d_, s_) in enumerate(COLS):
    colx.append((xc, xc + w))
    xc = snap(xc + w + (CGAP[i] if i < len(CGAP) else 0))
XME = colx[-1][1]                      # mirror right edge
XQB_X = max(x, snap(colx[4][0]))
XQB = chain("p", ["daB", ("XQBa", 1.0, 0.28, "sta"), "vss", ("XQBb", 1.0, 0.28, "stb"), "dbB"], XQB_X, YS0,
            contacted={0, 1, 2})
dev("XQBa", "vss", "sta", "daB", "vdd", "pfet_03v3", 1, 0.28)
dev("XQBb", "vss", "stb", "dbB", "vdd", "pfet_03v3", 1, 0.28)
XRE = max(XME, XQB_X + XQB["width"])   # rightmost pMOS diffusion
NWELL = (XNW, YS0 - NW_ENC, snap(XRE + NW_ENC), snap(YM0 + MH + NW_ENC))
R("nwell", NWELL)
W = snap(NWELL[2] + 0.30 + RING)

MTERM = []           # mirror contact rows: (net, rect)
for (nm, w, d_, s_), (xa, xb) in zip(COLS, colx):
    R("pdiff", (xa, YM0, xb, YM0 + MH))
    R("pmos", (xa, GY0, xb, GY1))
    for net, yc in ((d_, YM0 + 0.065), (s_, YM0 + MH - 0.295)):
        R("pdiffc", (xa + 0.065, yc, xb - 0.065, yc + CONT))
        rr = (xa + 0.01, yc, xb - 0.01, yc + CONT)
        R("metal1", rr, net)
        MTERM.append((net, rr))
    dev(nm, d_, "vbp_syn", s_, "vdd", "pfet_03v3", w, LM)
# straps over the gaps: hA (cols 0-3 top), dbA (cols 1-3 bottom), hB (cols 4-5 top)
yb, yt = YM0 + 0.065, YM0 + MH - 0.295
R("metal1", (colx[0][0] + 0.01, yt, colx[3][1] - 0.01, yt + CONT), "hA")
R("metal1", (colx[1][0] + 0.01, yb, colx[3][1] - 0.01, yb + CONT), "dbA")
R("metal1", (colx[4][0] + 0.01, yt, colx[5][1] - 0.01, yt + CONT), "hB")
# vbp_syn poly plate: end caps and the gaps between columns (the columns' gate regions are `pmos`)
R("polysilicon", (colx[0][0] - 0.22, GY0, colx[0][0], GY1), "vbp_syn")
for (a0, a1), (b0, b1) in zip(colx, colx[1:]):
    R("polysilicon", (a1, GY0, b0, GY1), "vbp_syn")
R("polysilicon", (colx[-1][1], GY0, colx[-1][1] + 0.22, GY1), "vbp_syn")
VBP_PAD = (snap((colx[3][1] + colx[4][0]) / 2), snap((GY0 + GY1) / 2))
polycon(*VBP_PAD, "vbp_syn")

# caps: nfet, gate = node, S/D = vss (contact columns both sides), poly up to the bridge
BR = (CAP_TOP + 0.12, CAP_TOP + 0.63)  # bridge poly y range (above cap and row A)
caps = {}
for nm, node, xd in (("CA", "na", X0), ("CB", "nb", XCB)):
    R("ndiff", (xd, CAP_Y0, xd + capw, CAP_TOP))
    for xcol in (xd + 0.065, xd + capw - 0.295):
        R("ndiffc", (xcol, CAP_Y0 + 0.065, xcol + CONT, CAP_TOP - 0.065))
        R("metal1", (xcol, RING, xcol + CONT, CAP_TOP - 0.01), "vss")       # down to the ring
    gx0, gx1 = xd + 0.44, xd + 0.44 + LC
    R("nmos", (gx0, CAP_Y0, gx1, CAP_TOP))
    R("polysilicon", (gx0, CAP_Y0 - 0.22, gx1, CAP_Y0))
    R("polysilicon", (gx0, CAP_TOP, gx1, BR[1]), node)
    caps[nm] = (gx0, gx1)
    dev(nm, "vss", node, "vss", "vss", "nfet_03v3", round(CAP_TOP - CAP_Y0, 3), LC)

# ------------------------------------------------------------------ ring (vss)
c = (RING - 0.23) / 2
for i, rr in enumerate([(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]):
    R("psubdiff", rr, "vss")
    R("metal1", rr, "vss")
    if i < 2:
        R("psubdiffcont", (rr[0] + c, rr[1] + c, rr[2] - c, rr[3] - c), "vss")
    else:
        R("psubdiffcont", (rr[0] + c, rr[1] + c + 0.1, rr[2] - c, rr[3] - c - 0.1), "vss")
R("metal1", (RING, RING, X0 + 0.295, CAP_TOP - 0.01), "vss")     # cap A left column joins the left ring

# ------------------------------------------------------------------ gate poly: stems, bars, heads
TERMS = {}           # net -> [[(router layer, rect)], ...]


def term(net, lay, r):
    TERMS.setdefault(net, []).append([(lay, tuple(snap(v) for v in r))])


def pad_of(x, y):
    return (x - 0.19, y - 0.19, x + 0.19, y + 0.19)


def gstem(chainy0, g, ytop, net):
    xa, xb, w = g
    R("polysilicon", (xa, chainy0 + w, xb, ytop), net)


def head(chainy0, g, hy, net):
    gstem(chainy0, g, hy + 0.18, net)
    xh = (g[0] + g[1]) / 2
    polycon(xh, hy, net)
    term(net, "m1", pad_of(xh, hy))


tB = YB + 1.0
Tg = T["gates"]
gstem(YB, Tg["SBA"], tB + 0.63, "sub")
gstem(YB, Tg["SBB"], tB + 0.63, "sub")
R("polysilicon", (Tg["SBA"][0], tB + 0.27, Tg["SBB"][1], tB + 0.63), "sub")
xab = (Tg["SBA"][1] + Tg["SBB"][0]) / 2
polycon(xab, tB + 0.45, "sub"); term("sub", "m1", pad_of(xab, tB + 0.45))
gstem(YB, Tg["SWA"], tB + 1.23, "rsel")
gstem(YB, Tg["SWB"], tB + 1.23, "rsel")
R("polysilicon", (Tg["SWA"][0] - 0.04, tB + 0.87, Tg["SWB"][1] + 0.04, tB + 1.23), "rsel")
xr = (Tg["SWA"][0] + Tg["SWA"][1]) / 2
polycon(xr, tB + 1.05, "rsel"); term("rsel", "m1", pad_of(xr, tB + 1.05))
for nm, net in (("SCA", "en_a"), ("SCB", "en_b")):
    gstem(YB, Tg[nm], tB + 1.85, net)
    xc = (Tg[nm][0] + Tg[nm][1]) / 2
    polycon(xc, tB + 1.67, net); term(net, "m1", pad_of(xc, tB + 1.67))
# synapse switches, inverter nMOS: one head each
for ch, nm, net in ((XNA, "XNAb", "stb"), (XNA, "XNAa", "sta"), (XNB, "XNBa", "sta"), (XNB, "XNBb", "stb"),
                    (NI, "NI", "grp_en")):
    head(YB, ch["gates"][nm], tB + 0.45, net)
# reset pair: one gb bar
Rg = Rc["gates"]
gstem(YB, Rg["SA"], tB + 0.63, "gb")
gstem(YB, Rg["SB"], tB + 0.63, "gb")
R("polysilicon", (Rg["SA"][0], tB + 0.27, Rg["SB"][1], tB + 0.63), "gb")
xg = (Rg["SA"][1] + Rg["SB"][0]) / 2
polycon(xg, tB + 0.45, "gb"); term("gb", "m1", pad_of(xg, tB + 0.45))
# smalls row (n-well)
tS = YS0 + 1.0
for ch, nm, net in ((XQA, "XQAa", "sta"), (XQA, "XQAb", "stb"), (XQB, "XQBa", "sta"), (XQB, "XQBb", "stb"),
                    (PIc, "PI", "grp_en")):
    head(YS0, ch["gates"][nm], tS + 0.45, net)
Pg = PH["gates"]
gstem(YS0, Pg["PHA"], tS + 0.63, "gb")
gstem(YS0, Pg["PHB"], tS + 0.63, "gb")
R("polysilicon", (Pg["PHA"][0], tS + 0.27, Pg["PHB"][1], tS + 0.63), "gb")
xp = (Pg["PHA"][0] + Pg["PHA"][1]) / 2
polycon(xp, tS + 0.45, "gb"); term("gb", "m1", pad_of(xp, tS + 0.45))
term("vbp_syn", "m1", pad_of(*VBP_PAD))
# row A
tA = YA + 4.0
HY = tA + 0.45
Ag = A["gates"]
for nm, net in (("MEA", "en_a"), ("MEB", "en_b")):
    head(YA, Ag[nm], HY, net)
gstem(YA, Ag["MBA"], HY + 0.18, "vbn_prb")
gstem(YA, Ag["MBB"], HY + 0.18, "vbn_prb")
R("polysilicon", (Ag["MBA"][0], HY - 0.18, Ag["MBB"][1], HY + 0.18), "vbn_prb")
xv = (Ag["MBA"][1] + Ag["MBB"][0]) / 2
polycon(xv, HY, "vbn_prb"); term("vbn_prb", "m1", pad_of(xv, HY))
# SF gates: stem + bridge to the cap poly; node contact on the cap poly
gstem(YA, Ag["MFA"], BR[1], "na")
gstem(YA, Ag["MFB"], BR[1], "nb")
R("polysilicon", (caps["CA"][1], BR[0], Ag["MFA"][0], BR[1]), "na")
R("polysilicon", (Ag["MFB"][1], BR[0], caps["CB"][0], BR[1]), "nb")
NODE_PAD = {"na": (caps["CA"][1] - 0.6, CAP_TOP + 0.45), "nb": (caps["CB"][0] + 0.6, CAP_TOP + 0.45)}
for net, (x_, y_) in NODE_PAD.items():
    polycon(x_, y_, net); term(net, "m1", pad_of(x_, y_))

# diffusion terminals
for ch in (A, T, XNA, Rc, XNB, NI, XQA, PIc, PH, XQB):
    for net, r in ch["stripes"]:
        if net in ("sa", "sb"):
            continue
        term(net, "m1", r)
for net, r in MTERM:
    term(net, "m1", r)
term("vdd", "m1", (NT[0] + 0.095, YS0 + 0.01, NT[0] + 0.325, YS0 + 0.99))
term("vss", "m1", (0, 0, W, RING))     # ring and cap columns are drawn vss metal: one vss terminal

# ------------------------------------------------------------------ pins (labels on the cell edge)
def _cx(g):
    return snap((g[0] + g[1]) / 2)


PIN_X = {"en_a": 2.0, "rsel": 3.2, "sub": 4.4, "abus": 5.6, "vbn_prb": 6.8,
         "sta": snap(XNA["gates"]["XNAa"][0] - 0.5), "stb": snap(XNA["gates"]["XNAa"][0] + 0.7),
         "vreset": snap(Rc["regions"][1][1] + 0.26), "grp_en": snap(NI["regions"][0][2] + 0.6),
         "en_b": snap(XCB + 1.0), "vbp_syn": snap(VBP_PAD[0])}
PIN_X = {k: float(os.environ.get("E3_PIN_" + k, v)) for k, v in PIN_X.items()}
_px = sorted(PIN_X.values())
assert all(b - a >= 1.2 - 1e-6 for a, b in zip(_px, _px[1:])), sorted(PIN_X.items(), key=lambda kv: kv[1])
PINS = []            # (net, layer, rect, use)
for net, x_ in PIN_X.items():
    r = (x_ - 0.15, 0, x_ + 0.15, 0.75)
    R("metal2", r, net); term(net, "m2", r)
    PINS.append((net, "metal2", r, "signal"))
YSP = 6.0            # supply pins on the side edges (Metal2)
r = (0, YSP - 0.2, 0.6, YSP + 0.2)
R("metal2", r, "vss"); R("via1", (0.17, YSP - 0.13, 0.43, YSP + 0.13), "vss")
PINS.append(("vss", "metal2", r, "ground"))
r = (W - 0.8, YSP - 0.15, W, YSP + 0.15)
R("metal2", r, "vdd"); term("vdd", "m2", r)
PINS.append(("vdd", "metal2", r, "power"))

LAY = {"metal1": "m1", "metal2": "m2", "metal3": "m3", "via1": "v1", "via2": "v2"}
RLAY = {v: k for k, v in LAY.items()}


def grid(base=0.28):
    rx, ry = set(), set()
    for net, ts in TERMS.items():
        for t in ts:
            for lay, r in t:
                if r[2] - r[0] < 1.0:
                    rx.add(snap((r[0] + r[2]) / 2))
                if r[3] - r[1] < 1.0:
                    ry.add(snap((r[1] + r[3]) / 2))

    def merge(req, lo, hi):
        req = sorted(v for v in req if lo <= v <= hi)
        out = list(req)
        v = lo
        while v <= hi + 1e-9:
            if all(abs(v - q) >= base * 0.5 for q in req):
                out.append(snap(v))
            v += base
        return sorted(set(out))
    return merge(rx, 0.50, W - 0.50), merge(ry, 0.50, H - 0.50)


def route(log=print):
    from crouter import Router
    xs, ys = grid()
    Rt = Router(xs, ys, layers=("m1", "m2", "m3"), hw=0.14)
    for lay, r, net in shapes:
        if lay in LAY:
            Rt.add_shape(LAY[lay], r, net if net else "__obst")

    def nodes(t):
        out = set()
        for lay, r in t:
            ii = [i for i, x_ in enumerate(xs) if r[0] - 1e-6 <= x_ <= r[2] + 1e-6]
            jj = [j for j, y_ in enumerate(ys) if r[1] - 1e-6 <= y_ <= r[3] + 1e-6]
            out |= {(lay, i, j) for i in ii for j in jj}
        return out
    for rr in ((0, 0, W, 0.36), (0, H - 0.36, W, H), (0, 0, 0.36, H), (W - 0.36, 0, W, H)):
        Rt.add_forbid(("m2", "m3"), rr)          # no routed metal along the cell edge (top-level stubs)
    nets = {}
    for net, ts in TERMS.items():
        tn = [nodes(t) for t in ts]
        for t, n in zip(ts, tn):
            if not n:
                log(f"  !! {net}: terminal {t} without a grid node")
        nets[net] = [n for n in tn if n]
    order = ["na", "nb", "daA", "dbA", "daB", "dbB", "hA", "hB", "pa", "pb", "abus", "sta", "stb", "gb", "vbp_syn",
             "en_a", "en_b", "rsel", "sub", "vbn_prb", "grp_en", "vreset", "vdd", "vss"]
    order = [n for n in order if n in nets] + [n for n in nets if n not in order]
    unrouted, bad = Rt.route_all(nets, order, iters=80, log=log)
    return Rt.wires(), sorted(unrouted | bad)


PORTS = "vdd vss vreset abus vbn_prb grp_en en_a en_b rsel sub sta stb vbp_syn"


def lvs_ref(path):
    L = [f"* LVS reference for {NAME} (layout/e3/e3gen.py): E3 synaptic-weight test cell, MIL-452 / MIL-362",
         f"* synapse unit pfet {WU:g}/{LM:g} (array 2/4), caps nfet {CAP_TOP - CAP_Y0:.3f}/{LC:g}",
         f".subckt {NAME} {PORTS}"]
    for nm, d_, g, s, b, model, w, l in DEV:
        L.append(f"X{nm} {d_} {g} {s} {b} {model} W={w:g}u L={l:g}u")
    L.append(f".ends {NAME}")
    Path(path).write_text("\n".join(L) + "\n")


def preview(path, allp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    col = {"nwell": ("#cfe8cf", 0.5), "psubdiff": ("#e8c070", 0.6), "nsubdiff": ("#70c0e8", 0.7),
           "ndiff": ("#40a040", 0.6), "pdiff": ("#c08040", 0.6), "nmos": ("#207020", 0.6), "pmos": ("#805020", 0.6),
           "polysilicon": ("#d03030", 0.5), "polycontact": ("#000000", 0.8), "ndiffc": ("#000000", 0.8),
           "pdiffc": ("#000000", 0.8), "psubdiffcont": ("#000000", 0.5), "nsubdiffcont": ("#000000", 0.5),
           "metal1": ("#3060ff", 0.35), "via1": ("#000080", 0.9), "metal2": ("#ff40ff", 0.35),
           "via2": ("#600060", 0.9), "metal3": ("#00c0c0", 0.35)}
    fig, ax = plt.subplots(figsize=(W * 0.9, H * 0.9))
    for lay, r in allp:
        c_, a = col.get(lay, ("#888888", 0.3))
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=c_, alpha=a, lw=0))
    for net, lay, r, use in PINS:
        ax.text((r[0] + r[2]) / 2, r[1] - 0.25, net, ha="center", fontsize=7)
    ax.set_xlim(-0.5, W + 0.5); ax.set_ylim(-0.7, H + 0.3); ax.set_aspect("equal")
    ax.set_xticks([i for i in range(int(W) + 1)]); ax.set_yticks(range(int(H) + 1)); ax.grid(lw=0.2)
    fig.savefig(path, dpi=70, bbox_inches="tight")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    lvs_ref(OUT / f"{NAME}_lvs.spice")          # first: the schematic bench needs it even if routing fails
    print(f"{NAME}: {W} x {H} (max 48.0 x 12.0); XCB {XCB}, n-well {NWELL}, mirror x {XM}..{XME}, L {LM}")
    assert W <= 48.0 + 1e-6 and H <= 12.0 + 1e-6, (W, H)
    wires, failed = route()
    print("FAILED", failed) if failed else print("routed all nets")
    obst = [(LAY[l], r, n) for l, r, n in shapes if l in LAY and n]
    if os.environ.get("E3_NOFILL"):
        fills, extra = [], []
    else:
        from slotgen_fill import fill_notches, fix_min_area
        fills = fill_notches(obst, wires)
        extra = fix_min_area(obst + wires + fills)
    allp = [(l, r) for l, r, n in shapes] + [(RLAY[l], r) for l, r, n in wires] + [(RLAY[l], r) for l, r, n in fills]
    allp += [(RLAY[l], r) for l, r in extra]
    order = ["nwell", "psubdiff", "nsubdiff", "ndiff", "pdiff", "nmos", "pmos", "polysilicon", "ndiffc", "pdiffc",
             "psubdiffcont", "nsubdiffcont", "polycontact", "metal1", "via1", "metal2", "via2", "metal3"]
    tcl = ["# generated by layout/e3/e3gen.py -- do not edit", "tech unlock *", f"load {NAME}"]
    for layer in order:
        for l, r in allp:
            if l == layer:
                tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
    k = 1
    for net, lay, r, use in PINS:
        tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
        tcl.append(f"label {net} FreeSans 0.25um 0 0 0 c {lay}")
        tcl.append(f"port make {k}; port use {use}; port class bidirectional")
        k += 1
    for net, (x_, y_) in NODE_PAD.items():    # internal test labels (not ports)
        tcl.append(f"box values {x_ - 0.1:.3f}um {y_ - 0.1:.3f}um {x_ + 0.1:.3f}um {y_ + 0.1:.3f}um")
        tcl.append(f"label {net} FreeSans 0.25um 0 0 0 c metal1")
    tcl.append(f"box values 0um 0um {W}um {H}um")
    tcl.append(f"save {NAME}")
    (OUT / f"{NAME}_paint.tcl").write_text("\n".join(tcl) + "\n")
    try:
        preview(OUT / f"{NAME}_preview.png", allp)
    except ImportError:
        pass
    (OUT / f"{NAME}_pins.json").write_text(json.dumps(
        dict(W=W, H=H, pins=[dict(net=n, layer=l, rect=r) for n, l, r, u in PINS]), indent=1))
    print(f"{NAME}: {W} x {H} = {W * H:.1f} um2, {len(wires)} wire shapes, {len(DEV)} devices")
    if failed:
        sys.exit(1)
