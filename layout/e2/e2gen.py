"""E2 leakage test cell `e2_leak` (MIL-362 R2): generator (magic paint tcl + LVS reference + preview).

Two floating ~200 fF nodes (nMOS gate caps, as the array's vm cap):
  na: reset through ONE 1/0.5 nMOS switch (vreset -> na, gate grp_en)
  nb: reset through TWO stacked 1/0.5 switches; the mid node is clamped to vreset by a pMOS 1/0.28 gated by
      grp_en itself (on while grp_en = 0, off while grp_en = 1): no inverter, no crossing current, no grp_en_b.
Each node has a probe tap copied from the array (XPM_*: SF 4/2, bias 2/2 from vbn_prb enabled by en, then
en / rsel / sub -> abus; last switch gated by `sub`).

Plan (x right, y up; cell 0..W x 0..H, p-tap ring 0.6):
  cap A (left) | row A: vdd|MFA|pa|MEA|sa|MBA|vss|MBB|sb|MEB|pb|MFB|vdd (top)  | cap B (right)
               | row B: T chain pa..abus..pb, R chain na|SA|vreset|SB1|mid|SB2|nb, pMOS clamp + n-tap (bottom)
  Gates escape up (heads / poly bars), diffusion terminals escape down to via1 pads; M2 vertical, M3 horizontal.
  The cap gates join the SF gates by a poly bridge over the top of the cap / row A.

Run:  python3 e2gen.py [outdir]   (default out/) -> e2_leak_paint.tcl, e2_leak_lvs.spice, e2_leak_shapes.json
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "compact"))
from geom import Finger, Chain, draw_chain, snap, CONT  # noqa: E402

NAME = "e2_leak"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
LC = float(os.environ.get("E2_LC", "5.84"))     # cap gate length (x); W = cap diffusion height
RING = 0.60
H = 11.8
YB = 1.70            # row B diffusion bottom
YA = 5.50            # row A diffusion bottom
CAP_Y0 = 0.94
GAP = 0.40           # diffusion gap cap <-> row A
X0 = RING + 0.34     # cap A diffusion left

shapes = []          # (layer, (x0, y0, x1, y1), net)
labels = []          # (text, layer, rect, use)


def R(layer, r, net=None):
    shapes.append((layer, tuple(snap(v) for v in r), net))


def via1(x, y, net, wx=0.4, wy=0.4):
    R("metal1", (x - wx / 2, y - wy / 2, x + wx / 2, y + wy / 2), net)
    R("metal2", (x - 0.2, y - 0.2, x + 0.2, y + 0.2), net)
    R("via1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net)


def via2(x, y, net):
    R("metal2", (x - 0.2, y - 0.2, x + 0.2, y + 0.2), net)
    R("metal3", (x - 0.2, y - 0.2, x + 0.2, y + 0.2), net)
    R("via2", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net)


def wire(layer, pts, net, w=None):
    """Manhattan polyline of rectangles, width w (M1 0.23, M2/M3 0.28 by default)."""
    w = w or (0.23 if layer == "metal1" else 0.28)
    h = w / 2
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        assert xa == xb or ya == yb, (net, pts)
        R(layer, (min(xa, xb) - h, min(ya, yb) - h, max(xa, xb) + h, max(ya, yb) + h), net)


def polycon(x, y, net):
    """poly contact with 0.36 poly head and 0.38 metal1 pad (as geom.draw_chain heads)."""
    R("polysilicon", (x - 0.18, y - 0.18, x + 0.18, y + 0.18), net)
    R("polycontact", (x - 0.115, y - 0.115, x + 0.115, y + 0.115), net)
    R("metal1", (x - 0.19, y - 0.19, x + 0.19, y + 0.19), net)


def chain(typ, items, x0, y0, contacted=None):
    """items: net, (name, W, L, gate), net, ... ; returns dict(regions {idx: (net, xa, xb, con)}, gates {name: (xa, xb, W)})."""
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
    return dict(regions=regs, gates=gates, width=d["width"], y0=y0, stripes=stripes)


# ------------------------------------------------------------------ devices
DEV = []   # LVS reference lines: (name, d, g, s, b, model, W, L)


def dev(nm, d, g, s, b, model, W, L):
    DEV.append((nm, d, g, s, b, model, W, L))


# row A: F chain (both probe followers + bias legs), mirrored about the shared vss
itemsA = ["vdd", ("MFA", 4.0, 2.0, "na"), "pa", ("MEA", 1.0, 0.28, "en_a"), "sa", ("MBA", 2.0, 2.0, "vbn_prb"),
          "vss", ("MBB", 2.0, 2.0, "vbn_prb"), "sb", ("MEB", 1.0, 0.28, "en_b"), "pb", ("MFB", 4.0, 2.0, "nb"), "vdd"]
capw = 0.44 + LC + 0.44
XA = snap(X0 + capw + GAP)
A = chain("n", itemsA, XA, YA, contacted={0, 1, 2, 3, 4, 5, 6})
W = snap(XA + A["width"] + GAP + capw + 0.34 + RING)
XCB = snap(XA + A["width"] + GAP)                     # cap B diffusion left
for nm, d_, g, s in (("MFA", "vdd", "na", "pa"), ("MEA", "pa", "en_a", "sa"), ("MBA", "sa", "vbn_prb", "vss"),
                     ("MBB", "sb", "vbn_prb", "vss"), ("MEB", "pb", "en_b", "sb"), ("MFB", "vdd", "nb", "pb")):
    w, l = {"MF": (4, 2), "ME": (1, 0.28), "MB": (2, 2)}[nm[:2]]
    dev(nm, d_, g, s, "vss", "nfet_03v3", w, l)

# row B: T chain (probe switches of both taps, shared abus contact)
itemsT = ["pa", ("SCA", 1.0, 0.28, "en_a"), "mca", ("SWA", 1.0, 0.28, "rsel"), "ma", ("SBA", 1.0, 0.28, "sub"),
          "abus", ("SBB", 1.0, 0.28, "sub"), "mb", ("SWB", 1.0, 0.28, "rsel"), "mcb", ("SCB", 1.0, 0.28, "en_b"), "pb"]
XT = XA
T = chain("n", itemsT, XT, YB, contacted={0, 3, 6})
for nm, d_, g, s in (("SCA", "pa", "en_a", "mca"), ("SWA", "mca", "rsel", "ma"), ("SBA", "ma", "sub", "abus"),
                     ("SBB", "mb", "sub", "abus"), ("SWB", "mcb", "rsel", "mb"), ("SCB", "pb", "en_b", "mcb")):
    dev(nm, d_, g, s, "vss", "nfet_03v3", 1, 0.28)

# row B: R chain (reset switches)
itemsR = ["na", ("SA", 1.0, 0.5, "grp_en"), "vreset", ("SB1", 1.0, 0.5, "grp_en"), "mid", ("SB2", 1.0, 0.5, "grp_en"), "nb"]
XR = snap(XT + T["width"] + 0.40)
Rc = chain("n", itemsR, XR, YB, contacted={0, 1, 2, 3})
dev("SA", "vreset", "grp_en", "na", "vss", "nfet_03v3", 1, 0.5)
dev("SB1", "vreset", "grp_en", "mid", "vss", "nfet_03v3", 1, 0.5)
dev("SB2", "mid", "grp_en", "nb", "vss", "nfet_03v3", 1, 0.5)

# row B: pMOS mid clamp (vreset -> mid while grp_en = 0), in an n-well with its own n-tap (vdd)
NW_ENC = 0.43
XP = snap(XR + Rc["width"] + 2 * NW_ENC + 0.02)
P = chain("p", ["mid", ("PC", 1.0, 0.28, "grp_en"), "vreset"], XP, YB, contacted={0, 1})
dev("PC", "vreset", "grp_en", "mid", "vdd", "pfet_03v3", 1, 0.28)
XNT = snap(XP + P["width"] + 0.34)           # n-tap
NT = (XNT, YB, XNT + 0.42, YB + 1.0)
R("nsubdiff", NT, "vdd")
R("nsubdiffcont", (XNT + 0.095, YB + 0.065, XNT + 0.325, YB + 0.935), "vdd")
R("metal1", (XNT + 0.095, YB + 0.01, XNT + 0.325, YB + 0.99), "vdd")
NWELL = (XP - NW_ENC, YB - NW_ENC, NT[2] + 0.16, YB + 1.0 + NW_ENC)
R("nwell", NWELL)

# caps: nfet, gate = node, S/D = vss (contact columns both sides), poly up to the bridge
CAP_TOP = YA + 4.0                     # cap diffusion top = row A diffusion top (bridge above both)
BR = (CAP_TOP + 0.12, CAP_TOP + 0.63)  # bridge poly y range
caps = {}
for nm, node, xd in (("CA", "na", X0), ("CB", "nb", XCB)):
    R("ndiff", (xd, CAP_Y0, xd + capw, CAP_TOP))
    for xc in (xd + 0.065, xd + capw - 0.295):
        R("ndiffc", (xc, CAP_Y0 + 0.065, xc + CONT, CAP_TOP - 0.065))
        R("metal1", (xc, RING, xc + CONT, CAP_TOP - 0.01), "vss")       # down to the ring
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
# cap A left column joins the left ring directly
R("metal1", (RING, RING, X0 + 0.295, CAP_TOP - 0.01), "vss")
R("metal1", (XCB + capw - 0.295, RING, W - RING, CAP_TOP - 0.01), "vss")

# ------------------------------------------------------------------ gate poly: stems, bars, heads
TERMS = {}           # net -> [[(router layer, rect)], ...]


def term(net, lay, r):
    TERMS.setdefault(net, []).append([(lay, tuple(snap(v) for v in r))])


def pad_of(x, y):
    return (x - 0.19, y - 0.19, x + 0.19, y + 0.19)


def gstem(chainy0, g, ytop, net):
    xa, xb, w = g
    R("polysilicon", (xa, chainy0 + w, xb, ytop), net)


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
# R chain + pMOS: one grp_en bar
Rg = dict(Rc["gates"]); Rg["PC"] = P["gates"]["PC"]
for nm in Rg:
    gstem(YB, Rg[nm], tB + 0.63, "grp_en")
R("polysilicon", (Rg["SA"][0], tB + 0.27, Rg["PC"][1], tB + 0.63), "grp_en")
xg = (Rg["SA"][0] + Rg["SA"][1]) / 2
polycon(xg, tB + 0.45, "grp_en"); term("grp_en", "m1", pad_of(xg, tB + 0.45))
# row A
tA = YA + 4.0
HY = tA + 0.45
Ag = A["gates"]
for nm, net in (("MEA", "en_a"), ("MEB", "en_b")):
    gstem(YA, Ag[nm], HY + 0.18, net)
    xc = (Ag[nm][0] + Ag[nm][1]) / 2
    polycon(xc, HY, net); term(net, "m1", pad_of(xc, HY))
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
NODE_PAD = {"na": (caps["CA"][1] - 0.6, HY), "nb": (caps["CB"][0] + 0.6, HY)}
for net, (x, y) in NODE_PAD.items():
    polycon(x, y, net); term(net, "m1", pad_of(x, y))

# diffusion terminals
for ch in (A, T, Rc, P):
    for net, r in ch["stripes"]:
        if net in ("sa", "sb"):
            continue
        term(net, "m1", r)
term("vdd", "m1", (XNT + 0.095, YB + 0.01, XNT + 0.325, YB + 0.99))
# ring and cap columns are drawn vss metal: one vss terminal (the ring)
term("vss", "m1", (0, 0, W, RING))

# ------------------------------------------------------------------ pins (labels on the cell edge)
PIN_X = {"en_a": 2.0, "rsel": 3.2, "sub": 4.4, "abus": 5.6, "vbn_prb": 22.4, "grp_en": 23.6, "vreset": 24.8, "en_b": 26.0}
PIN_X = {k: float(os.environ.get("E2_PIN_" + k, v)) for k, v in PIN_X.items()}
PINS = []            # (net, layer, rect, use)
for net, x in PIN_X.items():
    r = (x - 0.15, 0, x + 0.15, 0.75)
    R("metal2", r, net); term(net, "m2", r)
    PINS.append((net, "metal2", r, "signal"))
YS = 6.0             # supply pins on the side edges (Metal2)
r = (0, YS - 0.2, 0.6, YS + 0.2)
R("metal2", r, "vss"); R("via1", (0.17, YS - 0.13, 0.43, YS + 0.13), "vss")
PINS.append(("vss", "metal2", r, "ground"))
r = (W - 0.8, YS - 0.15, W, YS + 0.15)
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
    sys.path.insert(0, str(HERE.parent / "compact"))
    from crouter import Router
    xs, ys = grid()
    Rt = Router(xs, ys, layers=("m1", "m2", "m3"), hw=0.14)
    for lay, r, net in shapes:
        if lay in LAY:
            Rt.add_shape(LAY[lay], r, net if net else "__obst")

    def nodes(t):
        out = set()
        for lay, r in t:
            ii = [i for i, x in enumerate(xs) if r[0] - 1e-6 <= x <= r[2] + 1e-6]
            jj = [j for j, y in enumerate(ys) if r[1] - 1e-6 <= y <= r[3] + 1e-6]
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
    order = ["na", "nb", "pa", "pb", "abus", "en_a", "en_b", "rsel", "sub", "vbn_prb", "grp_en", "vreset", "mid",
             "vdd", "vss"]
    order = [n for n in order if n in nets] + [n for n in nets if n not in order]
    unrouted, bad = Rt.route_all(nets, order, iters=60, log=log)
    return Rt.wires(), sorted(unrouted | bad)


def lvs_ref(path):
    ports = "vdd vss vreset abus vbn_prb grp_en en_a en_b rsel sub"
    L = [f"* LVS reference for {NAME} (layout/e2/e2gen.py): E2 leakage test cell, MIL-362",
         f".subckt {NAME} {ports}"]
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
        c, a = col.get(lay, ("#888888", 0.3))
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=c, alpha=a, lw=0))
    for net, lay, r, use in PINS:
        ax.text((r[0] + r[2]) / 2, r[1] - 0.25, net, ha="center", fontsize=7)
    ax.set_xlim(-0.5, W + 0.5); ax.set_ylim(-0.7, H + 0.3); ax.set_aspect("equal")
    ax.set_xticks([i for i in range(int(W) + 1)]); ax.set_yticks(range(int(H) + 1)); ax.grid(lw=0.2)
    fig.savefig(path, dpi=70, bbox_inches="tight")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    wires, failed = route()
    print("FAILED", failed) if failed else print("routed all nets")
    sys.path.insert(0, str(HERE.parent / "slot"))
    from slotgen_fill import fill_notches, fix_min_area
    obst = [(LAY[l], r, n) for l, r, n in shapes if l in LAY and n]
    fills = fill_notches(obst, wires)
    allp = [(l, r) for l, r, n in shapes] + [(RLAY[l], r) for l, r, n in wires] + [(RLAY[l], r) for l, r, n in fills]
    allp += [(RLAY[l], r) for l, r in fix_min_area(obst + wires + fills)]
    order = ["nwell", "psubdiff", "nsubdiff", "ndiff", "pdiff", "nmos", "pmos", "polysilicon", "ndiffc", "pdiffc",
             "psubdiffcont", "nsubdiffcont", "polycontact", "metal1", "via1", "metal2", "via2", "metal3"]
    tcl = ["# generated by layout/e2/e2gen.py -- do not edit", "tech unlock *", f"load {NAME}"]
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
    for net, (x, y) in NODE_PAD.items():      # internal test labels (not ports)
        tcl.append(f"box values {x - 0.1:.3f}um {y - 0.1:.3f}um {x + 0.1:.3f}um {y + 0.1:.3f}um")
        tcl.append(f"label {net} FreeSans 0.25um 0 0 0 c metal1")
    tcl.append(f"box values 0um 0um {W}um {H}um")
    tcl.append(f"save {NAME}")
    (OUT / f"{NAME}_paint.tcl").write_text("\n".join(tcl) + "\n")
    lvs_ref(OUT / f"{NAME}_lvs.spice")
    preview(OUT / f"{NAME}_preview.png", allp)
    (OUT / f"{NAME}_pins.json").write_text(json.dumps(
        dict(W=W, H=H, pins=[dict(net=n, layer=l, rect=r) for n, l, r, u in PINS]), indent=1))
    print(f"{NAME}: {W} x {H} = {W * H:.1f} um2, {len(wires)} wire shapes")
