"""Generate the Tier-2 layouts adex_a1 (A1 AdEx) and scdend_s1 (S1 SC dendrite), gf180mcuD, reproducibly.

    scripts/eda.sh "bash layout/tier2/build.sh"            (devices -> place/route -> DRC -> LVS -> PEX)
    python3 t2gen.py <cell> [place|reuse|reuse!|devlist]

Same method and code as layout/dendrite/dendgen.py (itself from layout/slot/slotgen.py): one PDK device
cell per transistor (gf180mcu::*_draw, devices/), explicit row placement (CFG below), the gridded
Metal1/Metal2 PathFinder router (router.py, unchanged copy of layout/dendrite/router.py), morphological
notch fill, magic paint script. Only the per-cell configuration differs; MOM capacitors are generalised
to a list (Cfb, and S1's two SC capacitors with one comb on vss).

Inputs : cells/adex/adex.spice, cells/scdend/scdend.spice (+ library cells) via flatten.py.
Outputs: <cell>_base.mag, <cell>_paint.tcl, <cell>_lvs.spice, out/preview_<cell>.png.
All units um, origin = cell lower-left.
"""
import hashlib
import os
import time
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flatten                      # noqa: E402
from router import Router           # noqa: E402
sys.path.append(str(HERE.parent / "slot"))
import keptdev                      # noqa: E402  (layout/slot/keptdev.py)

U = 200
RING = 0.60
PITCH = 0.70
NTAP = 0.60
GAP = 0.90
ITERS = int(os.environ.get("T2ITERS", 40))
SCHEDULES = [(1.3, 0.5), (1.6, 0.3), (1.2, 0.7), (1.4, 0.4), (1.8, 0.6), (1.1, 0.3)]
# Route variants (run in parallel, each with its own T2TAG cache): T2SCHED = schedule indices to try ("3,1"),
# T2FIRST = nets routed right after ROUTE_FIRST ("XA.s,vbn_leak"), T2GRID = base grid pitch (0.70).
if os.environ.get("T2SCHED"):
    SCHEDULES = [SCHEDULES[int(k)] for k in os.environ["T2SCHED"].split(",")]
GRID_BASE = float(os.environ.get("T2GRID", 0.70))
ROUTE_LAST = ["vdd", "vss"]

# ============================================================================ per-cell configuration
# Keys: W H SPINE (vertical Metal2 lines, full height, pins at the top edge; vdd added last, 0.6 wide)
#       M3LINES [(net, [drop y])] Metal3 lines from the top edge with via2 drops; PIN_ONLY nets get no router
#       terminal (they only reach a keep-out); M3INT internal Metal3 jumpers; FEEDS [(net, x, y0, y1)] Metal2;
#       REGIONS routing bands; VSS_STRIPES; NWELLS (x0, y0, x1, y1[, rail mode]); KEEPOUT; PINS (Metal2 pads);
#       MOMS [dict(a=bottom-comb net, b=top-comb net, x, y, nf, lf)]; ROWS [(diff-bottom y, x0, [devices])];
#       FLIP (devices with drain on the left stripe); BIGCAPS {device: net}; ROUTE_FIRST; LABEL_NETS.
CFG = {}

# ---------------------------------------------------------------------------- A1
# 2026-11-19 floorplan shape: a column between the neuron array (left) and the control block (right), <= 38 um
# wide. Bias/analog lines: left Metal2 spine, pins at the BOTTOM edge. Digital lines (stim, hold, mreset, en,
# sel_adex, sub_raw) and spk: horizontal Metal3 lines with pins at the RIGHT edge (HM3).
_A1_SPINE = ["el", "vbn_leak", "vsrc", "vbp_st", "vbn_ref", "vreset", "vbn_prb", "vbp_syn", "vbp_w", "abus"]
CFG["adex_a1"] = dict(
    W=38.0, H=73.0,
    SPINE=_A1_SPINE, SPINE_SIDE="left", PIN_EDGE="bottom",
    M3LINES=[],
    HM3=[("sta", 9.7, [10.4]), ("spk", 10.5, [35.8]), ("stb", 14.0, [12.8]), ("en", 14.8, [18.0]),
         ("mreset", 26.0, [28.0]), ("sub0", 29.4, [24.3]), ("sel_adex", 30.2, [20.2]), ("sub1", 33.4, [18.1]),
         ("hold", 58.1, [35.2])],
    PIN_ONLY=set(),
    M3INT=[],
    FEEDS=[],
    REGIONS=[(0.0, 73.0)],
    VSS_STRIPES=[],
    NWELLS=[(9.0, 42.4, 36.6, 71.0)],
    KEEPOUT={},
    PINS={},
    MOMS=[dict(a="spk", b="vm", x=24.4, y=1.6, nf=12, lf=3.6)],
    # Level 3 (cells b283ae9): XPA 0.5/1 -> 0.5/2, XPB 4/0.5 -> 32/0.5 (4 fingers 8/0.5, top band right of Cw),
    # decay stack 3 x 0.22/15 -> 5 x 0.5/10 (4 rows at a 2.6 um pitch, XT3 + XT2 share one; XR1/XR2 next to XT1),
    # XW 0.22/8 -> 4/1 (2 fingers 2/1 in the y 39.4 row: a W 4 nfet there would reach the n-well).
    # Level 4 (cells aabada4): leak OTA XM1/XM2/XD1/XD2 L 1 -> 0.5 um, drawn in their L = 1 footprints (KEPT_L).
    # XD.XK = det_ah reset-state keeper (2026-11-19 fix, pfet 0.22/1 on pb gated by spk), at the end of the
    # y 59.0 pfet row next to the other detector devices. Detector and refractory-inverter nfets sit in the
    # row just below the n-well, under their pfets; the probe-mux nfets are grouped in the y 35.4 row.
    ROWS=[
        (1.6, 9.6, 1.3, ["XC.XC", "XR.XCR.XC"]),
        (1.6, 32.4, ["XP.XT0.XMF"]),
        (11.6, 9.6, 1.2, ["XS.XNA", "XS.XNB", "XS.XMR", "XR.XSW"]),
        (15.8, 9.6, ["XP.XT0.XMB", "XR.XNR", "XL.XMT", "XL.XM1", "XL.XD1", "XL.XD2", "XL.XM2"]),
        # the decay stack fills the space left of the tall leak diodes; y 33-39 stays free as a routing channel
        # stack chain vss-XT5-m4-XT4-m3-XT3-m2-XT2-m1-XT1-vw snakes up with the shared nodes at adjacent ends;
        # vw (XT1, XR1) ends at the top row next to the mreset pair
        (21.0, 9.6, ["XA.XT5"]),
        (23.6, 9.6, ["XA.XT4"]),
        (26.2, 9.6, ["XA.XT3", "XA.XT2"]),
        (28.8, 9.6, ["XA.XR2", "XA.XR1", "XA.XT1"]),
        # XA.Xi.XN (output vrb) stays away from the detector devices: vrb next to n1/p/pb made a runt on spk
        (31.4, 9.6, ["XA.Xi.XN", "XP.Xi0.XN", "XP.Xi1.XN", "XP.XSA", "XP.XSC", "XP.XS1", "XP.XT0.XME", "XP.XT0.XSW",
                     "XD.XN2"]),
        (39.4, 9.6, ["XE.XE1", "XA.XW_a", "XA.XW_b", "XD.XNI", "XD.XN3", "XD.Xi4.XN", "XR.Xi.XN"]),
        (44.6, 9.9, ["XL.XP1", "XL.XP2", "XS.XWA", "XS.XWB"]),
        (51.0, 9.9, ["XA.Xi.XS", "XA.XPW", "XS.XPH", "XP.XPB", "XD.XPS", "XD.XS2", "XD.XS3"]),
        (54.6, 9.9, ["XA.Xi.XP", "XA.XPS", "XP.XPE", "XP.XPF", "XE.XE3", "XE.XE2", "XA.XPA"]),
        (59.0, 9.9, 1.0, ["XS.XQA", "XS.XQB", "XS.XHL", "XP.Xi0.XP", "XP.Xi1.XP", "XR.Xi.XP", "XR.XPC", "XD.XPI",
                          "XD.XP2", "XD.XP3", "XD.Xi4.XP", "XD.XK"]),
        (62.8, 10.4, ["XA.XCW"]),
        (62.0, 23.0, ["XA.XPB_a", "XA.XPB_b", "XA.XPB_c", "XA.XPB_d"]),
    ],
    SPLIT={"XA.XPB": 4, "XA.XW": 2},
    KEPT_L={f"XL.{m}": 1.0 for m in ("XM1", "XM2", "XD1", "XD2")},
    FLIP={f"XL.{d}" for d in ("XM1", "XD1")} | {"XA.XT4", "XA.XT2", "XA.XT1"},
    BIGCAPS={"XC.XC": "vm", "XA.XCW": "vw"},
    BIGCAP_ALLOW={"XC.XC": {"vm", "vss"}, "XA.XCW": {"vw", "vdd"}},
    # level 3: XA.s (now 4 XPB fingers at the top + XPW + XPA) and vbn_leak (5 stack gates, 4 XPB fingers) right after
    # the critical nodes; route variant v5 of 6 (the default order stalled at 2-13 conflicts), work/adex_l3/route_v5.log
    ROUTE_FIRST=["vm", "vw", "spk", "XA.s", "vbn_leak"],
    LABEL_NETS=["vm", "vw"],
)
if os.environ.get("T2FIRST"):
    CFG["adex_a1"]["ROUTE_FIRST"] = CFG["adex_a1"]["ROUTE_FIRST"] + os.environ["T2FIRST"].split(",")

# ---------------------------------------------------------------------------- S1
_NOV_N = [f"XN.{d}" for d in ("Xi0.XN", "XO1.XN1", "XO1.XN2", "Xd1.XN", "Xd2.XN", "XO2.XN1", "XO2.XN2", "Xd3.XN",
                              "Xd4.XN")]
_NOV_P = [f"XN.{d}" for d in ("Xi0.XP", "XO1.XP1", "XO1.XP2", "Xd1.XP", "Xd2.XP", "XO2.XP1", "XO2.XP2", "Xd3.XP",
                              "Xd4.XP")]
CFG["scdend_s1"] = dict(
    W=56.0, H=47.0,
    SPINE=["el", "vbn_leak", "vsrc", "vbp_st", "vbn_ref", "vreset", "vbn_prb", "vbp_syn", "abus", "sel0", "sel2",
           "mreset", "spk"],
    M3LINES=[("en", [12.6], 17.4), ("sta", [12.6, 28.8], 27.0), ("stb", [12.6, 28.8], 28.4), ("hold", [28.8], 20.6),
             ("sc_clk", [21.9], 23.0)],
    PIN_ONLY=set(),
    M3INT=[],
    FEEDS=[],
    REGIONS=[(0.0, 47.0)],
    VSS_STRIPES=[],
    NWELLS=[(1.40, 22.8, 44.2, 37.6)],
    KEEPOUT={},
    PINS={},
    MOMS=[dict(a="spk", b="vs", x=2.0, y=40.0, nf=12, lf=3.6),
          dict(a="vss", b="ca", x=29.2, y=40.0, nf=14, lf=3.75, label=True),
          dict(a="vss", b="cl", x=38.0, y=40.0, nf=8, lf=3.5, label=True)],
    ROWS=[
        (1.6, 0.9, ["XS.XC.XC", "XCD.XC", "XS.XR.XCR.XC", "XT0.XMF", "XT2.XMF", "XT0.XMB", "XT2.XMB"]),
        (9.6, 18.6, 1.4, ["XT0.XME", "XT0.XSW", "XT2.XME", "XT2.XSW", "XY.XNA", "XY.XNB", "XY.XMR"]),
        (9.6, 36.4, 1.0, ["XL1", "XL2", "XA1", "XA2"]),
        (14.8, 0.9, ["XS.XL.XM1", "XS.XL.XD1", "XS.XL.XD2", "XS.XL.XM2", "XS.XL.XMT", "XS.XR.XNR"]),
        (19.8, 0.9, 1.2, ["XS.XD.XNI", "XS.XD.XN2", "XS.XD.XN3", "XS.XD.Xi4.XN", "XS.XR.Xi.XN", "XS.XR.XSW"]),
        (19.8, 22.0, 1.2, _NOV_N),
        (24.6, 2.0, ["XS.XL.XP1", "XS.XL.XP2", "XY.XWA", "XY.XWB", "XY.XPH", "XS.XD.XPS", "XS.XD.XS2"]),
        (30.8, 2.0, 1.1, ["XS.XD.XPI", "XS.XD.XP2", "XS.XD.XP3", "XS.XD.Xi4.XP", "XS.XR.Xi.XP", "XS.XR.XPC", "XY.XQA",
                          "XY.XQB", "XY.XHL"] + _NOV_P),
    ],
    FLIP={f"XS.XL.{d}" for d in ("XM1", "XD1")},
    BIGCAPS={"XS.XC.XC": "vs", "XCD.XC": "d"},
    KEPT_L={f"XS.XL.{m}": 1.0 for m in ("XM1", "XM2", "XD1", "XD2")},   # devlist only (S1 not rebuilt at level 4)
    BIGCAP_ALLOW={"XS.XC.XC": {"vs", "vss"}, "XCD.XC": {"d", "vss"}},
    ROUTE_FIRST=["vs", "d", "ca", "cl", "spk"],
    LABEL_NETS=["vs", "d"],
)

# S1, wide/low variant (same netlist): MOMs moved from the top band to the right of the capacitor row, so the
# cell is 72 x 40 and fits under the two A1s in the 112 x 90 Tier-2 zone (see docs/research/T2-area-estimate.md).
CFG["scdend_s1w"] = dict(CFG["scdend_s1"], cell="scdend_s1", W=72.0, H=40.0, REGIONS=[(0.0, 40.0)],
                         MOMS=[dict(a="spk", b="vs", x=39.0, y=1.6, nf=12, lf=3.6),
                               dict(a="vss", b="ca", x=46.6, y=1.6, nf=14, lf=3.75, label=True),
                               dict(a="vss", b="cl", x=55.4, y=1.6, nf=8, lf=3.5, label=True)])

CELL = None
SUBCKT = None


def select(cell):
    global CELL, SUBCKT
    CELL = cell
    c = CFG[cell]
    SUBCKT = c.get("cell", cell)
    g = globals()
    for k, v in c.items():
        g[k] = v
    g["HM3"] = c.get("HM3", [])
    g["SPLIT"] = c.get("SPLIT", {})
    g["KEPT_L"] = c.get("KEPT_L", {})
    g["SPINE_SIDE"] = c.get("SPINE_SIDE", "right")
    g["PIN_EDGE"] = c.get("PIN_EDGE", "top")
    n = len(SPINE)
    if SPINE_SIDE == "right":
        vx = round(W - RING - 0.55, 3)
        x0 = round(vx - 0.85 - (n - 1) * PITCH, 3)
        g["COLS"] = [(nm, round(x0 + k * PITCH, 3), 0.30) for k, nm in enumerate(SPINE)] + [("vdd", vx, 0.60)]
    else:                        # left spine: vdd outermost, then SPINE left to right
        vx = round(RING + 0.55, 3)
        x0 = round(vx + 0.85, 3)
        g["COLS"] = [("vdd", vx, 0.60)] + [(nm, round(x0 + k * PITCH, 3), 0.30) for k, nm in enumerate(SPINE)]


# ============================================================================ device library
def devcell(d):
    if d.get("slot"):
        return keptdev.kept_name(d["model"], d["W"], d["L"], d["slot"])
    f = lambda v: ("%g" % v).replace(".", "p")
    return f"{d['model'][0]}_w{f(d['W'])}_l{f(d['L'])}"


def prep_devs(devs, split, kept):
    """Layout-only device list: SPLIT devices as k parallel fingers <name>_a.. of W/k (the LVS reference keeps the
    single device; netgen adds parallel widths); KEPT_L devices shorter than their footprint get d['slot'] (keptdev)."""
    out = []
    for d in devs:
        if kept.get(d["name"], 0) > d["L"] + 1e-9:
            d = dict(d, slot=kept[d["name"]])
        k = split.get(d["name"], 1)
        out += [dict(d, name=f"{d['name']}_{'abcdefgh'[j]}", W=round(d["W"] / k, 4)) for j in range(k)] if k > 1 else [d]
    return out


def footprint(d):
    """The device cell as generated by gen_devices.tcl (kept-footprint devices: their footprint L)."""
    return dict(d, L=d["slot"], slot=0) if d.get("slot") else d


def load_dev(name):
    import re
    txt = (HERE / "devices" / f"{name}.mag").read_text()
    layer, R = None, {}
    ts = int(re.search(r"timestamp (\d+)", txt).group(1))
    for ln in txt.splitlines():
        m = re.match(r"<< (\w+) >>", ln)
        if m:
            layer = m.group(1)
            continue
        if ln.startswith("rect") and layer != "checkpaint":
            x1, y1, x2, y2 = (int(v) / U for v in ln.split()[1:5])
            R.setdefault(layer, []).append((x1, y1, x2, y2))
    bb = lambda rs: (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))
    diff = [r for k in ("ndiff", "pdiff", "ndiffc", "pdiffc") for r in R.get(k, [])]
    gate = bb(R.get("nmos", []) + R.get("pmos", []))
    cont = R.get("ndiffc", []) + R.get("pdiffc", [])
    m1 = cont + R.get("metal1", [])
    side = {"L": [r for r in m1 if (r[0] + r[2]) / 2 < 0], "R": [r for r in m1 if (r[0] + r[2]) / 2 > 0]}
    allr = [r for k, v in R.items() for r in v]
    return dict(name=name, ts=ts, R=R, diff=bb(diff), gate=gate, m1=side,
                stripe={k: bb(v) for k, v in side.items()}, bbox=bb(allr))


def snap(v, g=0.005):
    return round(round(v / g) * g, 4)


def shift(r, dx, dy):
    return (snap(r[0] + dx), snap(r[1] + dy), snap(r[2] + dx), snap(r[3] + dy))


def placement(lib, devs):
    by = {d["name"]: lib[devcell(d)] for d in devs}
    place = {}
    for row in ROWS:
        yb, x0, names = row[0], row[1], row[-1]
        gap = row[2] if len(row) == 4 else GAP
        x = x0
        for n in names:
            lc = by[n]
            dl, db, dr, dt = lc["diff"]
            cx = snap(x - dl)
            cy = snap(yb - db)
            place[n] = (cx, cy)
            x = cx + dr + gap
        if names:
            print(f"  row y={yb:6.2f}: x {x0:5.2f} .. {x - gap:6.2f}  ({len(names)} devices)")
    missing = set(by) - set(place)
    if missing:
        raise SystemExit(f"no placement for {sorted(missing)}")
    return place


class Layout:
    def __init__(self):
        self.paint, self.labels, self.nets = [], [], {}

    def p(self, layer, r):
        self.paint.append((layer, tuple(snap(v) for v in r)))

    def term(self, net, shapes):
        self.nets.setdefault(net, []).append(shapes)


PLACE = {}


def build():
    ports, devs, caps = flatten.write_lvs(HERE / f"{CELL}_lvs.spice", SUBCKT)
    if SUBCKT != CELL:           # layout variant of the same netlist: reference subckt named after the layout cell
        f = HERE / f"{CELL}_lvs.spice"
        f.write_text(f.read_text().replace(f".subckt {SUBCKT} ", f".subckt {CELL} ").replace(f".ends {SUBCKT}", f".ends {CELL}"))
    devs = prep_devs(devs, SPLIT, KEPT_L)
    lib = {}
    for d in devs:
        c = devcell(d)
        if c not in lib:
            if d.get("slot"):
                keptdev.make(HERE / "devices", d["model"], d["W"], d["L"], d["slot"])
            lib[c] = load_dev(c)
    PLACE.clear()
    PLACE.update(placement(lib, devs))
    L = Layout()
    insts, obst = [], []

    for d in devs:
        lc = lib[devcell(d)]
        cx, cy = PLACE[d["name"]]
        insts.append((lc, d["name"], cx, cy))
        nL, nR = (d["d"], d["s"]) if d["name"] in FLIP else (d["s"], d["d"])
        for side, net in (("L", nL), ("R", nR)):
            for r in lc["m1"][side]:
                obst.append(("m1", shift(r, cx, cy), net))
            L.term(net, [("m1", shift(lc["stripe"][side], cx, cy))])
        g = lc["gate"]
        hcy = snap(lc["diff"][3] + 0.45)
        hx = max((g[2] - g[0]) / 2, 0.18)
        L.p("polysilicon", shift((g[0], g[3], g[2], hcy + 0.18), cx, cy))
        L.p("polysilicon", shift((-hx, hcy - 0.18, hx, hcy + 0.18), cx, cy))
        pad = shift((-0.19, hcy - 0.19, 0.19, hcy + 0.19), cx, cy)
        L.p("metal1", pad)
        L.p("polycontact", shift((-0.115, hcy - 0.115, 0.115, hcy + 0.115), cx, cy))
        obst.append(("m1", pad, d["g"]))
        L.term(d["g"], [("m1", pad)])

    c = (RING - 0.23) / 2
    # ------------------------------------------------------------------ VDD rails (n-tap at well bottoms)
    rails = []
    for nw in NWELLS:
        mode = nw[4] if len(nw) == 5 else "full"
        nw = nw[:4]
        L.p("nwell", nw)
        ry = (nw[1] + 0.12, nw[1] + 0.12 + NTAP)
        rails.append((ry, mode))
        tap = (nw[0] + 0.12, ry[0], nw[2] - 0.12, ry[1])
        L.p("nsubdiff", tap)
        L.p("nsubdiffcont", (tap[0] + c, tap[1] + c, tap[2] - c, tap[3] - c))
        rail = {"full": (0, ry[0], W, ry[1]), "left": (0, ry[0], nw[2] - 0.12, ry[1]),
                "local": (nw[0] + 0.12, ry[0], nw[2] - 0.12, ry[1])}[mode]
        L.p("metal1", rail)
        obst.append(("m1", rail, "vdd"))
        L.term("vdd", [("m1", rail)])
        if mode != "local":
            L.labels.append(("vdd", "metal1", (0.05, ry[0] + 0.1, 0.5, ry[1] - 0.1), "power"))
    # ------------------------------------------------------------------ p-tap ring + stripes (VSS)
    ring = [(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]
    for ys in VSS_STRIPES:
        ring.append((0, ys, W, ys + RING))
    for r in ring:
        L.p("psubdiff", r)
    m1ring = [(0, 0, W, RING), (0, H - RING, W, H)] + [(0, ys, W, ys + RING) for ys in VSS_STRIPES]
    for x0 in (0, W - RING):
        gaps = [(ry[0] - 0.30, ry[1] + 0.30) for ry, mode in rails if mode == "full" or (x0 == 0 and mode == "left")]
        y = 0
        for g0, g1 in gaps:
            m1ring.append((x0, y, x0 + RING, g0))
            y = g1
        m1ring.append((x0, y, x0 + RING, H))
    for r in m1ring:
        L.p("metal1", r)
        obst.append(("m1", r, "vss"))
        L.term("vss", [("m1", r)])
        if r[2] - r[0] > r[3] - r[1]:
            L.p("psubdiffcont", (r[0] + c, r[1] + c, r[2] - c, r[3] - c))
        else:
            L.p("psubdiffcont", (r[0] + c, r[1] + c + 0.1, r[2] - c, r[3] - c - 0.1))
    L.labels.append(("vss", "metal1", (2.0, 0.1, 3.0, 0.5), "ground"))

    # ------------------------------------------------------------------ spine (M2, full height)
    colx = {}
    for net, x, w in COLS:
        if PIN_EDGE == "bottom":     # pins at the bottom edge: the line runs from y = 0 to below the top ring
            r = (x - w / 2, 0, x + w / 2, H - RING - 0.4)
        else:
            r = (x - w / 2, RING + 0.4, x + w / 2, H)
        if net in BRIDGE_NETS:   # antenna: cut into short Metal2 pieces joined by Metal3 jumpers
            segs = spine_segments(L, net, x, r[1], H, obst)
            L.term(net, [("m2", g) for g in segs])
        else:
            L.p("metal2", r)
            obst.append(("m2", r, net))
            if net != "vdd":     # vdd: tied to every full-width VDD rail by drawn vias; not a router terminal
                L.term(net, [("m2", r)])
        colx[net] = x
        ly = (0.1, 0.5) if PIN_EDGE == "bottom" else (H - 0.5, H - 0.1)
        L.labels.append((net, "metal2", (r[0], ly[0], r[2], ly[1]), "power" if net == "vdd" else "signal"))
    for ry, mode in rails:
        if mode == "full":
            via(L, colx["vdd"], (ry[0] + ry[1]) / 2, obst, "vdd", w=0.6)
    # Metal3 digital lines with via2 drops onto Metal2 pads (one router terminal per net)
    for k, ln in enumerate(M3LINES):
        net, drops = ln[0], ln[1]
        x = ln[2] if len(ln) > 2 else round(M3_X0 + k * PITCH, 3)
        L.p("metal3", (x - 0.15, min(drops) - 0.30, x + 0.15, H))
        L.labels.append((net, "metal3", (x - 0.15, H - 0.5, x + 0.15, H - 0.1), "signal"))
        pads = []
        for y in drops:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14))
            L.p("metal3", pr)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
        if net not in PIN_ONLY:
            L.term(net, pads)
    # horizontal Metal3 lines from the RIGHT edge (pins there) with via2 drops onto Metal2 pads: (net, y, [drop x])
    for net, y, xs in HM3:
        L.p("metal3", (min(xs) - 0.30, y - 0.15, W, y + 0.15))
        L.labels.append((net, "metal3", (W - 0.5, y - 0.15, W - 0.1, y + 0.15), "signal"))
        pads = []
        for x in xs:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14))
            L.p("metal3", pr)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
        L.term(net, pads)
    for k, (net, drops) in enumerate(M3INT):
        x = round(M3_X0 + (len(M3LINES) + k) * PITCH, 3)
        L.p("metal3", (x - 0.15, min(drops) - 0.30, x + 0.15, max(drops) + 0.30))
        pads = []
        for y in drops:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14))
            L.p("metal3", pr)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
        L.term(net, pads)
    for net, x, y0, y1 in FEEDS:
        r = (x - 0.15, y0, x + 0.15, y1)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])

    moms = [mom_cap(L, obst, m) for m in MOMS]

    # ------------------------------------------------------------------ pins (Metal2 pads)
    for net, (x, y) in PINS.items():
        r = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", r, "signal"))
    for name, r in KEEPOUT.items():
        L.p("comment", r)
        L.labels.append((name, "comment", (r[0] + 0.5, r[3] - 1.0, r[0] + 0.5, r[3] - 1.0), None))
    return L, insts, obst, moms, lib, devs, ports


# Spine lines with tiny gate loads (mreset: one 0.5/0.28 nfet) fail the KLayout antenna rule ANT.3 as one
# full-height Metal2 line; they are cut every ~12 um and joined by Metal3 jumpers (as layout/dendrite does).
BRIDGE_NETS = {"mreset"}
BRIDGES = [12.0, 24.0, 36.0]


def spine_segments(L, net, x, y0, y1, obst):
    segs, y = [], y0
    gap, pad = 0.60, 0.50
    for yb in BRIDGES:
        segs.append((x - 0.15, y, x + 0.15, yb))
        y = yb + gap
        for vy in (yb - pad / 2, yb + gap + pad / 2):
            pr = (x - 0.19, vy - pad / 2, x + 0.19, vy + pad / 2)
            L.p("metal2", pr)
            obst.append(("m2", pr, net))
            L.p("via2", (x - 0.14, vy - 0.14, x + 0.14, vy + 0.14))
        L.p("metal3", (x - 0.19, yb - pad, x + 0.19, yb + gap + pad))
    segs.append((x - 0.15, y, x + 0.15, y1))
    for g in segs:
        L.p("metal2", g)
        obst.append(("m2", g, net))
    return segs


def via(L, x, y, obst, net, w=0.4):
    pad = (x - w / 2, y - 0.2, x + w / 2, y + 0.2)
    L.p("metal1", pad)
    L.p("metal2", pad)
    L.p("via1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13))
    obst.append(("m1", pad, net))
    obst.append(("m2", pad, net))
    obst.append(("v1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net))


def mom_cap(L, obst, m):
    """Interdigitated M1/M2/M3 finger capacitor between nets m['a'] (bottom bar) and m['b'] (top bar)."""
    x0, y0, nf, lf = m["x"], m["y"], m["nf"], m["lf"]
    pitch, fw = m.get("pitch", 0.58), m.get("fw", 0.30)
    width = (nf - 1) * pitch + fw
    bar, gapf = 0.50, 0.30
    bot = (x0, y0, x0 + width, y0 + bar)
    top = (x0, y0 + bar + gapf + lf + gapf, x0 + width, y0 + bar + gapf + lf + gapf + bar)
    shapes = {m["a"]: [bot], m["b"]: [top]}
    for k in range(nf):
        fx = x0 + k * pitch
        if k % 2 == 0:
            shapes[m["a"]].append((fx, bot[3], fx + fw, top[1] - gapf))
        else:
            shapes[m["b"]].append((fx, bot[3] + gapf, fx + fw, top[1]))
    for net, rs in shapes.items():
        for r in rs:
            for lay in ("metal1", "metal2", "metal3"):
                L.p(lay, r)
            obst.append(("m1", r, net))
            obst.append(("m2", r, net))
        b = rs[0]
        nv = int((b[2] - b[0] - 0.1) // 0.6)
        for k in range(nv):
            vx = b[0] + 0.30 + k * 0.6
            vy = (b[1] + b[3]) / 2
            if vx + 0.14 > b[2] - 0.06:
                break
            L.p("via1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13))
            L.p("via2", (vx - 0.14, vy - 0.14, vx + 0.14, vy + 0.14))
            obst.append(("v1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13), net))
        L.term(net, [("m1", b), ("m2", b)])
    if m.get("label"):           # name the (internal) top-comb net so PEX reports it
        L.labels.append((m["b"], "metal1", top, None))
    return dict(box=(x0, y0, x0 + width, top[3]), shapes=shapes, nets={m["a"], m["b"]})


# ============================================================================ routing
def make_grid(L, base=None):
    base = base or GRID_BASE
    req_x, req_y = set(), set()
    for net, terms in L.nets.items():
        for t in terms:
            for lay, r in t:
                if r[2] - r[0] < 1.0:
                    req_x.add(snap((r[0] + r[2]) / 2, 0.005))
                if r[3] - r[1] < 1.0:
                    req_y.add(snap((r[1] + r[3]) / 2, 0.005))
    for net, x, w in COLS:
        req_x.add(x)
    for net, x, y0, y1 in FEEDS:
        req_x.add(x)

    def merge(req, lo, hi):
        req = sorted(v for v in req if lo <= v <= hi)
        out = list(req)
        v = base
        while v <= hi + 1e-9:
            if all(abs(v - q) >= base * 0.55 for q in req):
                out.append(snap(v, 0.005))
            v += base
        return sorted(set(out))
    return merge(req_x, 0.30, W - 0.30), merge(req_y, 0.30, H - 0.30)


def add_forbids(R, moms):
    for name, r in KEEPOUT.items():
        R.add_forbid(("m1", "m2"), r)
    for n, net in BIGCAPS.items():
        cx, cy = PLACE[n]
        R.add_forbid(("m1", "m2"), (cx - 3.6, cy - 3.6, cx + 3.6, cy + 3.6), allowed=BIGCAP_ALLOW[n])
    for m in moms:
        R.add_forbid(("m1", "m2"), m["box"], allowed=m["nets"])
    for r in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        R.add_forbid(("m1",), r, allowed={"vss"})
    for r in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        R.add_forbid(("m2",), r)


T0 = time.time()


def route(L, obst, moms):
    """Route region by region (REGIONS); each region's wires are static obstacles for the next."""
    xs, ys_all = make_grid(L)
    done = []
    failed_all = []
    for ri, (y0, y1) in enumerate(REGIONS):
        ys = [y for y in ys_all if y0 - 1e-6 <= y <= y1 + 1e-6]

        def fresh():
            R = Router(xs, ys)
            for lay, r, net in list(obst) + done:
                R.add_shape(lay, r, net)
            add_forbids(R, moms)
            return R

        def nodes(shapes):
            out = set()
            for lay, r in shapes:
                for i, x in enumerate(xs):
                    if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                        for j, y in enumerate(ys):
                            if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                                out.add((lay, i, j))
            return out

        nets = {}
        for net, terms in L.nets.items():
            tn = [nodes(t) for t in terms]
            tn = [t for t in tn if t]
            if len(tn) >= 2:
                nets[net] = tn
        order = [n for n in ROUTE_FIRST if n in nets]
        order += sorted((n for n in nets if n not in ROUTE_FIRST + ROUTE_LAST), key=lambda n: (n.count(".") == 0, n))
        order += [n for n in ROUTE_LAST if n in nets]
        print(f"region {ri} y {y0}..{y1}: {len(nets)} nets, grid {len(xs)} x {len(ys)}", flush=True)
        best = None
        for k, (pm, hs) in enumerate(SCHEDULES):
            R = fresh()
            print(f"  schedule {k}: pres_mult={pm} hist_step={hs}", flush=True)
            unrouted, bad = R.route_all(nets, order, iters=ITERS, pres_mult=pm, hist_step=hs,
                                        log=lambda s: print(f"{time.time() - T0:6.0f}s {s}", flush=True))
            failed = sorted(unrouted | bad)
            ncf = len(R.conflict_list()) + 100 * len(unrouted)
            if best is None or ncf < best[0]:
                best = (ncf, R, unrouted, failed)
            if not failed:
                break
        ncf, R, unrouted, failed = best          # keep the schedule with the fewest conflicts
        print(f"  using schedule result with {ncf} conflict pairs", flush=True)
        for cf in R.conflict_list():
            print("  CONFLICT", cf)
        print("  UNROUTED", sorted(unrouted), flush=True)
        done += R.wires()
        failed_all += [f"r{ri}:{n}" for n in failed]

    class Res:
        pass
    R = Res()
    R.wire_list = done
    return R, failed_all


def fill_notches(obst, wires):
    import klayout.db as kdb
    from router import SPACE
    dbu = 0.005
    per = {}
    for lay, r, net in list(obst) + list(wires):
        if lay in ("m1", "m2") and net is not None:
            per.setdefault((lay, net), []).append(r)
    out = []
    for (lay, net), rs in per.items():
        reg = kdb.Region()
        for r in rs:
            reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
        reg.merge()
        d = int(round(SPACE[lay] / 2 / dbu)) + 1
        minw = int(round({"m1": 0.23, "m2": 0.28}[lay] / dbu))
        closed = reg.dup()
        for _ in range(3):
            closed = closed.sized(d, d, 2).sized(-d, -d, 2)
            eps = list(closed.width_check(minw).each())
            for ep in eps:
                bb = ep.bbox()
                cx, cy = bb.center().x, bb.center().y
                w2 = max(bb.width(), minw) // 2 + 1
                h2 = max(bb.height(), minw) // 2 + 1
                closed.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
            closed.merge()
            if not eps:
                break
        add = (closed - reg)
        for bx in add.each_merged():
            for t in kdb.Region(bx).decompose_trapezoids(1):
                pts = [p for p in t.each_point_hull()]
                xs = [p.x * dbu for p in pts]
                ys = [p.y * dbu for p in pts]
                out.append((lay, (snap(min(xs)), snap(min(ys)), snap(max(xs)), snap(max(ys))), net))
    from router import rgap
    allsh = {}
    for lay, r, net in list(obst) + list(wires) + out:
        if lay in ("m1", "m2"):
            allsh.setdefault(lay, []).append((r, net))
    for (lay, net), rs in per.items():
        reg = kdb.Region()
        for r in rs + [r for l, r, n in out if l == lay and n == net]:
            reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
        reg.merge()
        sp = SPACE[lay]
        for ep in reg.space_check(int(round(sp / dbu)), False, kdb.Metrics.Square).each():
            bb = ep.bbox()
            g = (bb.left * dbu, bb.bottom * dbu, bb.right * dbu, bb.top * dbu)
            cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
            hx = (g[2] - g[0]) / 2 + 0.30
            hy = (g[3] - g[1]) / 2 + 0.30
            f = (snap(cx - hx), snap(cy - hy), snap(cx + hx), snap(cy + hy))
            if all(n == net or rgap(f, r) >= sp - 1e-9 for r, n in allsh[lay]):
                out.append((lay, f, net))
                allsh[lay].append((f, net))
            else:
                print(f"  !! same-net gap on {net} {lay} at {g} not fillable")
    return out


def write_outputs(L, insts, wires):
    base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
    for lc, name, cx, cy in insts:
        b = lc["bbox"]
        base += [f"use {lc['name']}  {name.replace('.', '_')}", f"timestamp {lc['ts']}",
                 f"transform 1 0 {round(cx * U)} 0 1 {round(cy * U)}",
                 f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
    base.append("<< end >>")
    (HERE / f"{CELL}_base.mag").write_text("\n".join(base) + "\n")
    tcl = ["# generated by t2gen.py -- do not edit", f"load {CELL}_base", f"cellname rename {CELL}_base {CELL}",
           "tech unlock *"]
    order = ["nwell", "psubdiff", "nsubdiff", "polysilicon", "metal1", "metal2", "metal3",
             "psubdiffcont", "nsubdiffcont", "polycontact", "via1", "via2", "comment"]
    lay = {"m1": "metal1", "m2": "metal2", "v1": "via1"}
    allp = list(L.paint) + [(lay[l], r) for l, r, n in wires]
    for layer in order:
        for l, r in allp:
            if l == layer:
                tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
    k = 1
    for text, layer, r, use in L.labels:
        tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
        tcl.append(f"label {text} FreeSans 0.25um 0 0 0 c {layer}")
        if use:
            tcl.append(f"port make {k}; port use {use}; port class bidirectional")
            k += 1
    tcl.append(f"box values 0um 0um {W}um {H}um")
    tcl.append(f"save {CELL}")
    (HERE / f"{CELL}_paint.tcl").write_text("\n".join(tcl) + "\n")


def preview(L, insts, wires, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(10, 10 * H / W + 0.5))
    col = {"nwell": ("#cfe8cf", 0.6), "psubdiff": ("#e8c070", 0.7), "nsubdiff": ("#70c0e8", 0.7),
           "polysilicon": ("#d04040", 0.5), "metal1": ("#3050d0", 0.35), "metal2": ("#d020d0", 0.35),
           "metal3": ("#20a020", 0.35), "comment": ("#999999", 0.25)}
    for lc, name, cx, cy in insts:
        for k, rs in lc["R"].items():
            c = {"ndiff": "#40a040", "pdiff": "#a08040", "nmos": "#c03030", "pmos": "#c03030",
                 "polysilicon": "#d04040", "ndiffc": "#3050d0", "pdiffc": "#3050d0", "metal1": "#3050d0"}.get(k)
            if c:
                for r in rs:
                    ax.add_patch(Rectangle((r[0] + cx, r[1] + cy), r[2] - r[0], r[3] - r[1], fc=c, alpha=0.5, lw=0))
        ax.text(cx, cy, name, fontsize=4, ha="center", va="center")
    lay = {"m1": "metal1", "m2": "metal2"}
    for l, r in list(L.paint) + [(lay.get(l, l), r) for l, r, n in wires]:
        if l in col:
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
    ax.set_xlim(-0.5, W + 0.5)
    ax.set_ylim(-0.5, H + 0.5)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=150, bbox_inches="tight")


def check_overlaps(insts):
    """Placement sanity: device diffusion+gate-head boxes must not overlap or crowd (< 0.3 um)."""
    boxes = []
    for lc, name, cx, cy in insts:
        d = lc["diff"]
        top = d[3] + 0.64
        boxes.append((name, (d[0] + cx, d[1] + cy - 0.25, d[2] + cx, top + cy)))
    bad = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a[0] < b[2] + 0.3 and b[0] < a[2] + 0.3 and a[1] < b[3] + 0.3 and b[1] < a[3] + 0.3:
                print("  CROWD", boxes[i][0], boxes[j][0])
                bad += 1
    if SPINE_SIDE == "right":
        xmin, xmax = RING + 0.3, min(x for n, x, w in COLS) - 1.0
    else:
        xmin, xmax = max(x for n, x, w in COLS) + 1.0, W - RING - 0.3
    for n, b in boxes:
        if b[0] < xmin or b[2] > xmax or b[3] > H - RING - 0.3:
            print("  OUTSIDE", n, b)
            bad += 1
        for k, r in KEEPOUT.items():
            if b[0] < r[2] and r[0] < b[2] and b[1] < r[3] and r[1] < b[3]:
                print("  IN KEEPOUT", n, k)
                bad += 1
    return bad


def write_devlist():
    cells = {}
    for k, cfg in CFG.items():
        ports, devs, caps = flatten.flatten(cfg.get("cell", k))
        for d in map(footprint, prep_devs(devs, cfg.get("SPLIT", {}), cfg.get("KEPT_L", {}))):
            cells[devcell(d)] = d
    (HERE / "devices").mkdir(exist_ok=True)
    (HERE / "devices" / "devlist.tcl").write_text("".join(
        f"mk {c} {d['model']} [dict merge $common {{w {d['W']:g} l {d['L']:g}}}]\n"
        for c, d in sorted(cells.items())))


def main():
    write_devlist()
    if "devlist" in sys.argv:
        return 0
    select(sys.argv[1])
    L, insts, obst, moms, lib, devs, ports = build()
    nbad = check_overlaps(insts)
    print(f"placement issues: {nbad}")
    (HERE / "out").mkdir(exist_ok=True)
    if "place" in sys.argv:
        preview(L, insts, [], HERE / "out" / f"preview_place_{CELL}.png")
        return 0
    key = hashlib.sha1(repr((PLACE, COLS, HM3, PIN_EDGE, sorted(BRIDGE_NETS), BRIDGES, M3LINES, M3INT, FEEDS, REGIONS, KEEPOUT, NWELLS, VSS_STRIPES, MOMS, W, H,
                             PINS, open(HERE / "router.py").read())).encode()).hexdigest()
    cache = HERE / "out" / f"route_cache_{CELL}{os.environ.get('T2TAG', '')}.json"
    if cache.exists() and ("reuse!" in sys.argv or ("reuse" in sys.argv and json.loads(cache.read_text())["key"] == key)):
        c = json.loads(cache.read_text())
        wires = [(l, tuple(r), n) for l, r, n in c["wires"]]
        failed = c["failed"]
        print("  reusing routing from", cache.name)
    else:
        R, failed = route(L, obst, moms)
        wires = [w for w in R.wire_list if w[0] != "fill"]
        cache.write_text(json.dumps(dict(key=key, failed=failed, wires=wires)))
        if "routeonly" in sys.argv:
            print("FAILED:", failed if failed else "none")
            return 1 if failed else 0
    fills = fill_notches(obst, wires)
    print(f"  notch fillers: {len(fills)}")
    wires = list(wires) + fills
    for net in LABEL_NETS:
        ws = [w for w in wires if w[2] == net and w[0] in ("m1", "m2")]
        if ws:
            l, r, _ = sorted(ws, key=lambda w: (w[0] != "m2", w[1][1]))[0]
            L.labels.append((net, {"m1": "metal1", "m2": "metal2"}[l], r, "signal"))
    write_outputs(L, insts, wires)
    preview(L, insts, wires, HERE / "out" / f"preview_{CELL}.png")
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
