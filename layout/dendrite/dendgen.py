"""Generate the D1 dendritic-neuron layout dend_d1 (gf180mcuD) reproducibly.

    scripts/eda.sh "bash layout/dendrite/build.sh"     (devices -> place/route -> DRC -> LVS -> PEX)

Same method as layout/slot/slotgen.py (whose router.py / fill / output code this reuses):
one PDK device cell per transistor (gf180mcu::*_draw, devices/), row placement given below,
the gridded Metal1/Metal2 PathFinder router, morphological notch fill, magic paint script.

Inputs : cells/dendrite/dendrite.spice (+ library cells) via flatten.py.
Outputs: dend_d1_base.mag, dend_d1_paint.tcl, dend_d1_lvs.spice, preview.png.
All units um, origin = cell lower-left. Frame W x H = the floorplan's D1 box (docs/06).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flatten                      # noqa: E402
from router import Router           # noqa: E402

CELL = "dend_d1"
U = 200

# ============================================================================ frame
# 2026-11-19: the leak/axial OTAs grew (inputs 4/1, diodes 8/1 = 2 x 4/1 fingers) and the two gap trims
# moved into the cell; the old 62.5 um width (floorplan box x 132-194.5) no longer holds the rows, so the
# cell is DW wider (spine, feeds and wells move right with it). See README.
DW = float(__import__("os").environ.get("D1_DW", "7.5"))
W, H = 62.5 + DW, 104.0
RING = 0.60
XF = 47.9 + DW          # right end of the device field (n-wells)

# Spine: vertical Metal2 lines, full height, pins at the top edge (macro / CH_MID side).
# Bias / analog lines, plus the digital lines whose Metal3 version would fail the antenna rule
# (sel0, sel2, mreset: tiny gates far from the top). vdd last.
SPINE_X0, PITCH = 50.90 + DW, 0.70
SPINE = ["el", "vbn_leak", "vsrc", "vsrcp", "vbp_st", "vbn_ax", "vbn_ref", "vreset", "vbn_prb", None, "abus",
         "sel0", "sel2", "mreset", "spk"]           # None: free track (vbp_syn moved to Metal3, M3X)
COLS = [(n, round(SPINE_X0 + k * PITCH, 3), 0.30) for k, n in enumerate(SPINE) if n]
COLS.append(("vdd", round(SPINE_X0 + len(SPINE) * PITCH + 0.15, 3), 0.60))
# Metal3 digital lines over the device area: (net, [drop y]). Each runs from the top edge down to its
# lowest drop; at each drop a via2 lands on a small Metal2 pad that the router connects from.
M3_X0 = 30.0
M3LINES = [("en", [9.6, 50.4, 75.8]), ("pl_en", [47.6, 73.0]), ("chain", [16.6]), ("sel1", [75.2]),
           ("d1_bsel", [98.3]), ("sta", [48.2]), ("stb", [98.3]), ("hold", [29.0, 48.8, 74.8, 93.4]),
           ("ta0", [33.3]), ("ta1", [33.3]), ("ta2", [33.3]), ("ta3", [33.3]),
           ("tb0", [98.3]), ("tb1", [98.3]), ("tb2", [98.3]), ("tb3", [98.3])]
# Metal3 lines at their own x (net, x, [drop y]): vbp_syn runs down next to the two synapses
M3X = [("vbp_syn", 22.60, [48.4, 73.8])]
# nets that only reach a pin (no router terminal): none since the trims are drawn in the cell
PIN_ONLY = set()
# Internal Metal3 jumpers for the local nets that cross a routing region (all have a drain on them,
# so no antenna issue): (net, [drop y]); they sit right of the digital lines, between the drops only.
M3INT = [("b1", [49.4, 98.3]), ("la1", [33.3, 50.0]), ("dl1", [33.3, 47.6]),
         ("la2", [75.8, 93.4]), ("dl2", [75.2, 98.3])]
# Feeds: vertical Metal2 lines for the only local nets that cross compartment regions
# (net, x, y0, y1): d1 down to its axial pair in the soma region, vep up to the plateau OTAs,
# y2 (d2 pair's far end, at the top) down to the star/chain switches next to the soma.
FEEDS = [("vep", 48.60 + DW, 15.0, 87.0), ("y2", 49.30 + DW, 15.0, 91.0), ("d1", 50.00 + DW, 10.0, 58.0)]
# Routing regions (routed one after another; earlier wires become obstacles for later regions)
REGIONS = [(0.0, 38.3), (38.3, 63.7), (63.7, H)]

# horizontal p-tap (VSS) stripes between the compartments (latch-up taps + vss distribution)
VSS_STRIPES = [38.0, 63.4]
# n-wells (x0, y0, x1, y1[, rail]): an n-tap VDD rail runs along each well's bottom edge; rail 'full'
# (default) = whole cell width (reaches both edges and the spine vdd), 'local' = only under the well,
# 'none' = no rail (the well is an extension of the one below it).
NWELLS = [(1.40, 24.0, XF, 33.0),
          (1.40, 56.7, XF, 61.6), (1.40, 82.1, XF, 87.0), (1.40, 93.6, XF, 98.6),
          (9.90, 42.8, 21.9, 49.6, "local"), (9.90, 68.2, 21.9, 75.0, "local")]
NTAP = 0.60

KEEPOUT = {}
# compartment test pins (Metal2 pads)
PINS = {"d1": (9.45, 39.70), "d2": (9.45, 65.10)}

MOM = dict(x=42.10, y=1.60, nf=12, lf=3.6, pitch=0.58, fw=0.30)

GAP = 0.90


def ota(o, tail=True):
    """leak/axial OTA devices in row order (diodes as two W = 4 fingers)."""
    return [f"{o}.XM1", f"{o}.XD1_a", f"{o}.XD1_b", f"{o}.XD2_a", f"{o}.XD2_b", f"{o}.XM2"] + ([f"{o}.XMT"] if tail else [])


def trim(t, part):
    return {"pmos": [f"{t}.XP3", f"{t}.XP2", f"{t}.XP1", f"{t}.XP0"],
            "sw": [f"{t}.XN3", f"{t}.XN2", f"{t}.XN1", f"{t}.XN0"],
            "lad": [f"{t}.XRA", f"{t}.XRB", f"{t}.XL3", f"{t}.XR1", f"{t}.XL2", f"{t}.XR2", f"{t}.XL1",
                    f"{t}.XR3", f"{t}.XL0", f"{t}.XLT"]}[part]


# rows: (diffusion-bottom y, x0, [gap,] [device names])  -- packed left to right
ROWS = [
    # ---------------- soma region
    (1.6, 0.9, ["XS.XC.XC", "XT0.XMF", "XT0.XME", "XT0.XMB", "XT0.XSW", "XS.XR.XCR.XC", "XS.XR.XNR",
                "XS.XR.XSW", "XS.XR.Xi.XN", "XEP.XS"]),
    (11.6, 0.9, ota("XS.XL") + ota("XA1.XA") + ["XS.XD.Xi4.XN"]),
    (18.4, 0.9, ["XS.XD.XNI", "XS.XD.XN2", "XS.XD.XN3", "XWS", "XI.XN", "XWC", "XEP.XN", "XMR"] + ota("XA1.XB")),
    (25.6, 2.0, ["XS.XL.XP1", "XS.XL.XP2", "XA1.XA.XP1", "XA1.XA.XP2", "XA1.XA.XHO", "XA1.XB.XP1", "XA1.XB.XP2",
                 "XA1.XB.XHO", "XEP.XPD", "XEP.XPM", "XS.XD.XS3", "XS.XD.XK"]),
    (30.4, 2.0, ["XS.XD.XPS", "XS.XD.XPI", "XS.XD.XS2", "XS.XD.XP2", "XS.XD.XP3", "XS.XD.Xi4.XP",
                 "XS.XR.Xi.XP", "XS.XR.XPC", "XI.XP", "XS.XHL"] + trim("XR1", "pmos")),
    # trim 1 (d1, nibble 7): ladder + switches in one row in the free band above the soma well
    (34.8, 2.0, trim("XR1", "lad") + trim("XR1", "sw")),
    # ---------------- d2's axial pair + trim-2 switches, top well (d2 pair pmos, steering pmos, trim-2 pmos),
    # steering nmos + trim-2 ladder
    (88.6, 0.9, ota("XA2.XA") + ota("XA2.XB") + trim("XR2", "sw")),
    (94.8, 2.0, ["XA2.XA.XP1", "XA2.XA.XP2", "XA2.XA.XHO", "XA2.XB.XP1", "XA2.XB.XP2", "XA2.XB.XHO",
                 "XB.XI.XP", "XB.XP1", "XB.XP2"] + trim("XR2", "pmos")),
    (99.4, 0.9, ["XB.XI.XN", "XB.XN1", "XB.XD1", "XB.XN2", "XB.XD2"] + trim("XR2", "lad")),
]


def sub_rows(y0, P, L, C, T, Y):
    """d1/d2 compartment: cap, synapse (own n-well), timer/detector rows, leak+plateau OTA row, pmos row;
    the subunit's gap trim R fills the right side (switches after the timer, ladder in a row between timer and
    detector and after the detector, pmos switches in the short top pmos row)."""
    return [
        (y0, 0.9, [f"{C}.XC"]),
        (y0 + 0.6, 10.5, [f"{Y}.XNA", f"{Y}.XNB", f"{Y}.XMR"]),
        (y0 + 4.8, 10.5, [f"{Y}.XWA", f"{Y}.XWB"]),
        (y0 + 8.0, 10.5, [f"{Y}.XPH", f"{Y}.XQA", f"{Y}.XQB", f"{Y}.XHL"]),
        (y0, 22.5, [f"{P}.XCT.XC", f"{P}.XTI", f"{P}.XTS", f"{P}.XS1", f"{P}.XS2", f"{P}.XS3"]),
        (y0 + 6.0, 22.5, 1.5, [f"{P}.XDT.XNI", f"{P}.XDT.XN2", f"{P}.XDT.XN3", f"{P}.XDT.XON",
                               f"{P}.XDT.XNH", f"{P}.XDT.XNE"]),
        (y0 + 11.6, 0.9, ota(L) + [f"{P}.XOM1", f"{P}.XOM2",
                                   f"{P}.XOTA", f"{P}.XOTB", f"{T}.XMF", f"{T}.XME", f"{T}.XMB", f"{T}.XSW"]),
        (y0 + 18.8, 2.0, 0.9, [f"{L}.XP1", f"{L}.XP2", f"{P}.XOP1", f"{P}.XOP2", f"{P}.XHP", f"{P}.XTP",
                               f"{P}.XDT.XPS", f"{P}.XDT.XPI", f"{P}.XDT.XS2", f"{P}.XDT.XP2", f"{P}.XDT.XS3",
                               f"{P}.XDT.XP3", f"{P}.XDT.XOP"]),
        # detector reset keeper + pull-up: a short second pmos row in the top of the same well
        (y0 + 21.0, 44.5, [f"{P}.XDT.XK", f"{P}.XDT.XQ"]),
    ]


ROWS += sub_rows(39.4, "XP1", "XL1", "XC1", "XT2", "XY1")
ROWS += sub_rows(64.8, "XP2", "XL2", "XC2", "XT1", "XY2")
# source/drain stripe assignment (free for LVS): make neighbouring stripes share a net
FLIP = {f"{o}.{d}" for o in ("XS.XL", "XL1", "XL2", "XA1.XA", "XA1.XB", "XA2.XA", "XA2.XB")
        for d in ("XM1", "XD1_a", "XD2_b")}
FLIP |= {f"{p}.{d}" for p in ("XP1", "XP2") for d in ("XOM1", "XOTB")}


# gate-only nets that already ride a long Metal3 line: keep the router off Metal3 for them (antenna ANT.16:
# ta1 failed with 3 um^2 of routed Metal3 on top of its 71 um line)
NO_M3 = {f"t{s}{k}" for s in "ab" for k in range(4)}
# synapse internal nodes: route first and keep them short (charge sharing on da/db costs EPSP; a first
# M3 route let them wander 30-50 um and the post-layout EPSP dropped ~25 %)
SYN_LOCAL = [f"XY{k}.{n}" for k in (1, 2) for n in ("da", "db", "h")]
NO_M3 |= set(SYN_LOCAL)
ROUTE_FIRST = SYN_LOCAL + ["vs", "d1", "d2", "spk"]
ROUTE_LAST = ["vdd", "vss"]
ITERS = 40
SCHEDULES = [(1.3, 0.5), (1.6, 0.3), (1.2, 0.7), (1.45, 0.4), (1.3, 0.3)]
BIGCAPS = {"XS.XC.XC": "vs", "XC1.XC": "d1", "XC2.XC": "d2"}


# ============================================================================ device library
def devcell(d):
    f = lambda v: ("%g" % v).replace(".", "p")
    return f"{d['model'][0]}_w{f(d['W'])}_l{f(d['L'])}"


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


SPLIT_W = 4.0     # devices wider than this are drawn as parallel fingers of W <= SPLIT_W (netgen merges them)


def split_wide(devs):
    """W = 8 leak/axial degeneration diodes -> two W = 4 devices <name>_a, <name>_b (same d/g/s)."""
    out = []
    for d in devs:
        k = int(-(-d["W"] // SPLIT_W)) if d["W"] > SPLIT_W + 1e-9 and d["L"] <= 1.0 else 1
        if k == 1:
            out.append(d)
            continue
        for j in range(k):
            out.append(dict(d, name=f"{d['name']}_{'abcd'[j]}", W=round(d["W"] / k, 4)))
    return out


# Fixed-slot devices: name -> gate length of the slot they keep. A shorter device is right-aligned in that slot (pad
# on its left), so its drain stripe and every later device in the row stay where they were. Level 3 (schematic
# 387f708): the plateau detector input XNI went 1/1 -> 1/0.5; packing it tight shifted XN2..XNE 0.5 um west, and the
# region-1 trial route then stalled on a d1/vdd conflict (route_try.py 1), which the kept slot avoids.
SLOT_L = {f"{p}.XDT.XNI": 1.0 for p in ("XP1", "XP2")}


def placement(lib, devs):
    by = {d["name"]: lib[devcell(d)] for d in devs}
    dl_by = {d["name"]: d["L"] for d in devs}
    place = {}
    for row in ROWS:
        yb, x0, names = row[0], row[1], row[-1]
        gap = row[2] if len(row) == 4 else GAP
        x = x0
        for n in names:
            lc = by[n]
            dl, db, dr, dt = lc["diff"]
            x += max(0.0, SLOT_L.get(n, 0.0) - dl_by[n])     # diffusion length grows 1:1 with L
            cx = snap(x - dl)
            cy = snap(yb - db)
            place[n] = (cx, cy)
            x = cx + dr + gap
        print(f"  row y={yb:6.2f}: x {x0:5.2f} .. {x - gap:6.2f}  ({len(names)} devices)")
    missing = set(by) - set(place)
    if missing:
        raise SystemExit(f"no placement for {sorted(missing)}")
    return place


class Layout:
    def __init__(self):
        self.paint, self.labels, self.nets = [], [], {}
        self.m3 = []          # (m3|v2, rect, net): Metal3 / via2 drawn by the generator (router obstacles)

    def p(self, layer, r, net=None):
        r = tuple(snap(v) for v in r)
        self.paint.append((layer, r))
        if layer in ("metal3", "via2"):
            self.m3.append(({"metal3": "m3", "via2": "v2"}[layer], r, net))

    def term(self, net, shapes):
        self.nets.setdefault(net, []).append(shapes)


PLACE = {}


def build():
    ports, devs, caps = flatten.write_lvs(HERE / f"{CELL}_lvs.spice", CELL)
    devs = split_wide(devs)
    lib = {}
    for d in devs:
        c = devcell(d)
        if c not in lib:
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
    full = []
    for nw in NWELLS:
        mode = nw[4] if len(nw) == 5 else "full"
        nw = nw[:4]
        L.p("nwell", nw)
        if mode == "none":
            continue
        ry = (nw[1] + 0.12, nw[1] + 0.12 + NTAP)
        rails.append((ry, mode))
        # local (synapse) wells: tap stops 0.5 um short of the well's right edge so its N+ implant
        # keeps clear of the plateau-timer cap's N+ (NP.1 notch); the Metal1 rail is unchanged
        tap = (nw[0] + 0.12, ry[0], nw[2] - 0.12 - (0.5 if mode == "local" else 0.0), ry[1])
        L.p("nsubdiff", tap)
        L.p("nsubdiffcont", (tap[0] + c, tap[1] + c, tap[2] - c, tap[3] - c))
        rail = {"full": (0, ry[0], W, ry[1]), "left": (0, ry[0], nw[2] - 0.12, ry[1]),
                "local": (nw[0] + 0.12, ry[0], nw[2] - 0.12, ry[1])}[mode]
        L.p("metal1", rail)
        obst.append(("m1", rail, "vdd"))
        L.term("vdd", [("m1", rail)])
        if mode != "local":      # a local rail does not reach x = 0: a label there would sit on the vss ring
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
        r = (x - w / 2, RING + 0.4, x + w / 2, H)
        if net == "vdd":         # tied to every full-width VDD rail by drawn vias; not a router terminal
            L.p("metal2", r)
            obst.append(("m2", r, net))
        else:
            segs = spine_segments(L, net, x, r[1], H, obst)
            L.term(net, [("m2", g) for g in segs])
        colx[net] = x
        L.labels.append((net, "metal2", (r[0], H - 0.5, r[2], H - 0.1), "power" if net == "vdd" else "signal"))
    for ry, mode in rails:
        if mode == "full":
            via(L, colx["vdd"], (ry[0] + ry[1]) / 2, obst, "vdd", w=0.6)
    # Metal3 digital lines with via2 drops onto Metal2 pads (one router terminal per net)
    for k, (net, drops) in enumerate(M3LINES):
        x = round(M3_X0 + k * PITCH, 3)
        L.p("metal3", (x - 0.15, min(drops) - 0.30, x + 0.15, H), net)
        L.labels.append((net, "metal3", (x - 0.15, H - 0.5, x + 0.15, H - 0.1), "signal"))
        pads = []
        for y in drops:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14), net)
            L.p("metal3", pr, net)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
        if net not in PIN_ONLY:
            L.term(net, pads)
    for net, x, drops in M3X:
        L.p("metal3", (x - 0.15, min(drops) - 0.30, x + 0.15, H), net)
        L.labels.append((net, "metal3", (x - 0.15, H - 0.5, x + 0.15, H - 0.1), "signal"))
        pads = []
        for y in drops:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14), net)
            L.p("metal3", pr, net)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
        L.term(net, pads)
    for k, (net, drops) in enumerate(M3INT):
        x = round(M3_X0 + (len(M3LINES) + k) * PITCH, 3)
        L.p("metal3", (x - 0.15, min(drops) - 0.30, x + 0.15, max(drops) + 0.30), net)
        pads = []
        for y in drops:
            pr = (x - 0.19, y - 0.25, x + 0.19, y + 0.25)
            L.p("metal2", pr)
            L.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14), net)
            L.p("metal3", pr, net)
            obst.append(("m2", pr, net))
            pads.append(("m2", pr))
            if any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in KEEPOUT.values()):
                L.labels.append((net, "metal3", pr, "signal"))
        L.term(net, pads)
    for net, x, y0, y1 in FEEDS:
        r = (x - 0.15, y0, x + 0.15, y1)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])

    mom = mom_cap(L, obst)

    # ------------------------------------------------------------------ compartment pins
    for net, (x, y) in PINS.items():
        r = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", r, "signal"))
    # soma node label (test/synapse node): on the soma cap's pin, added after routing (any vs metal)
    for name, r in KEEPOUT.items():
        L.p("comment", r)
        L.labels.append((name, "comment", (r[0] + 0.5, r[3] - 1.0, r[0] + 0.5, r[3] - 1.0), None))
    obst += [(l, r, n) for l, r, n in L.m3]
    return L, insts, obst, mom, lib, devs, ports


BRIDGES = [20.0, 46.0, 72.0, 96.0]   # y of the Metal3 jumpers that cut each spine signal line


def spine_segments(L, net, x, y0, y1, obst):
    """Spine signal line as Metal2 segments joined by short Metal3 jumpers (via2 at both ends).
    Antenna: the lines are ~100 um of Metal2 on small switch gates (ratio ~500 > 400); cut into
    ~25 um pieces, each gate only sees its own piece while Metal2 is etched."""
    segs, y = [], y0
    gap, pad = 0.60, 0.50
    for yb in BRIDGES:
        segs.append((x - 0.15, y, x + 0.15, yb))
        y = yb + gap
        for vy in (yb - pad / 2, yb + gap + pad / 2):
            pr = (x - 0.19, vy - pad / 2, x + 0.19, vy + pad / 2)
            L.p("metal2", pr)
            obst.append(("m2", pr, net))
            L.p("via2", (x - 0.14, vy - 0.14, x + 0.14, vy + 0.14), net)
        L.p("metal3", (x - 0.19, yb - pad, x + 0.19, yb + gap + pad), net)
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


def mom_cap(L, obst):
    """Cfb (spk -> vs): interdigitated M1/M2/M3 fingers, as in the array slot (8.1 fF there)."""
    m = MOM
    x0, y0, nf, lf, pitch, fw = m["x"], m["y"], m["nf"], m["lf"], m["pitch"], m["fw"]
    width = (nf - 1) * pitch + fw
    bar, gapf = 0.50, 0.30
    bot = (x0, y0, x0 + width, y0 + bar)
    top = (x0, y0 + bar + gapf + lf + gapf, x0 + width, y0 + bar + gapf + lf + gapf + bar)
    shapes = {"spk": [bot], "vs": [top]}
    for k in range(nf):
        fx = x0 + k * pitch
        if k % 2 == 0:
            shapes["spk"].append((fx, bot[3], fx + fw, top[1] - gapf))
        else:
            shapes["vs"].append((fx, bot[3] + gapf, fx + fw, top[1]))
    for net, rs in shapes.items():
        for r in rs:
            for lay in ("metal1", "metal2", "metal3"):
                L.p(lay, r, net)
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
            L.p("via2", (vx - 0.14, vy - 0.14, vx + 0.14, vy + 0.14), net)
            obst.append(("v1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13), net))
        L.term(net, [("m1", b), ("m2", b)])
    return dict(box=(x0, y0, x0 + width, top[3]), shapes=shapes)


# ============================================================================ routing
def make_grid(L, base=0.70):
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


def add_forbids(R, mom):
    for name, r in KEEPOUT.items():
        R.add_forbid(("m1", "m2"), r)
    for n, net in BIGCAPS.items():
        cx, cy = PLACE[n]
        R.add_forbid(("m1", "m2"), (cx - 3.6, cy - 3.6, cx + 3.6, cy + 3.6), allowed={net, "vss"})
    R.add_forbid(("m1", "m2", "m3"), mom["box"], allowed={"vs", "spk"})
    for r in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        R.add_forbid(("m1",), r, allowed={"vss"})
    for r in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        R.add_forbid(("m2",), r)


def route(L, obst, mom):
    """Route region by region (REGIONS); each region's wires are static obstacles for the next."""
    xs, ys_all = make_grid(L)
    done = []            # (layer, rect, net) wires of finished regions
    failed_all = []
    for ri, (y0, y1) in enumerate(REGIONS):
        ys = [y for y in ys_all if y0 - 1e-6 <= y <= y1 + 1e-6]

        def fresh():
            R = Router(xs, ys)
            R.no_m3 = NO_M3
            for lay, r, net in list(obst) + done:
                R.add_shape(lay, r, net)
            add_forbids(R, mom)
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
        # per-region cache: key = this region's inputs (grid, terminals, nearby obstacles, earlier wires)
        import hashlib
        near = sorted((l, r, n) for l, r, n in list(obst) + done if r[3] >= y0 - 2 and r[1] <= y1 + 2)
        base = (xs, ys, sorted((k, sorted(map(sorted, v))) for k, v in nets.items()), near,
                [(k, v) for k, v in KEEPOUT.items()])
        # the router source is not part of the key (a routed region stays valid when only the router's
        # search/repair strategy changes); older caches keyed with it are still accepted
        rkey = hashlib.sha1(repr(base).encode()).hexdigest()
        rkey_old = hashlib.sha1(repr(base[:5] + (open(HERE / "router.py").read(),)).encode()).hexdigest()
        rc = HERE / "out" / f"route_region{ri}.json"
        import os
        force = str(ri) in os.environ.get("REUSE_REGIONS", "").split(",")   # trust an existing cache
        if rc.exists() and (force or json.loads(rc.read_text())["key"] in (rkey, rkey_old))                 and not json.loads(rc.read_text())["failed"]:
            c = json.loads(rc.read_text())
            done += [(l, tuple(r), n) for l, r, n in c["wires"]]
            failed_all += c["failed"]
            rc.write_text(json.dumps(dict(c, key=rkey)))
            print(f"  region {ri}: reusing {rc.name}", flush=True)
            continue
        for k, (pm, hs) in enumerate(SCHEDULES):
            R = fresh()
            print(f"  schedule {k}: pres_mult={pm} hist_step={hs}", flush=True)
            unrouted, bad = R.route_all(nets, order, iters=ITERS, pres_mult=pm, hist_step=hs,
                                        log=lambda s: print(s, flush=True))
            failed = sorted(unrouted | bad)
            if not failed:
                break
        for cf in R.conflict_list():
            print("  CONFLICT", cf)
        print("  UNROUTED", sorted(unrouted), flush=True)
        rw = R.wires()
        done += rw
        failed_all += [f"r{ri}:{n}" for n in failed]
        rc.write_text(json.dumps(dict(key=rkey, failed=[f"r{ri}:{n}" for n in failed], wires=rw)))
        if failed:
            print(f"  region {ri} FAILED after all schedules: {failed}", flush=True)

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
        if lay in ("m1", "m2", "m3") and net is not None:
            per.setdefault((lay, net), []).append(r)
    out = []
    for (lay, net), rs in per.items():
        reg = kdb.Region()
        for r in rs:
            reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
        reg.merge()
        d = int(round(SPACE[lay] / 2 / dbu)) + 1
        minw = int(round({"m1": 0.23, "m2": 0.28, "m3": 0.28}[lay] / dbu))
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
    # closing fills must keep spacing to other nets (a sliver can land next to another net's gate pad)
    from router import rgap as _rg
    allsh0 = {}
    for lay, r, net in list(obst) + list(wires):
        allsh0.setdefault(lay, []).append((r, net))
    keep = []
    for lay, f, net in out:
        bad = [n for r, n in allsh0.get(lay, []) if n != net and _rg(f, r) < SPACE[lay] - 1e-9]
        if bad:
            print(f"  !! closing fill {lay} {net} {f} dropped (too close to {bad[0]})")
        else:
            keep.append((lay, f, net))
    out = keep
    # Same-net spacing violations left after the closing (diagonal corner-to-corner gaps, which a
    # square-corner closing cannot bridge): bridge each with a small box over the gap, provided it
    # keeps spacing to every other net.
    from router import rgap
    allsh = {}
    for lay, r, net in list(obst) + list(wires) + out:
        if lay in ("m1", "m2", "m3"):
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
            f0 = (snap(g[0]), snap(g[1]), snap(g[2]), snap(g[3]))   # fallback: exactly the gap
            if all(n == net or rgap(f, r) >= sp - 1e-9 for r, n in allsh[lay]):
                out.append((lay, f, net))
                allsh[lay].append((f, net))
            elif min(f0[2] - f0[0], f0[3] - f0[1]) >= {"m1": 0.23, "m2": 0.28, "m3": 0.28}[lay] and all(
                    n == net or rgap(f0, r) >= sp - 1e-9 for r, n in allsh[lay]):
                out.append((lay, f0, net))
                allsh[lay].append((f0, net))
                print(f"  same-net gap on {net} {lay} at {g}: filled exactly")
            else:
                print(f"  !! same-net gap on {net} {lay} at {g} not fillable")
    # hand bridges for diagonal same-net corner gaps the automatic fill cannot take (checked for spacing)
    for lay, f, net in PATCHES:
        bad = [(r, n) for r, n in allsh.get(lay, []) if n != net and rgap(f, r) < SPACE[lay] - 1e-9]
        if bad:
            print(f"  !! patch {lay} {net} {f} violates spacing to {bad[:3]}")
        else:
            out.append((lay, f, net))
            allsh[lay].append((f, net))
    return out


# (layer, rect, net): the two diagonal corner gaps left by the current route cache
PATCHES = []


def write_outputs(L, insts, wires):
    base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
    for lc, name, cx, cy in insts:
        b = lc["bbox"]
        base += [f"use {lc['name']}  {name.replace('.', '_')}", f"timestamp {lc['ts']}",
                 f"transform 1 0 {round(cx * U)} 0 1 {round(cy * U)}",
                 f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
    base.append("<< end >>")
    (HERE / f"{CELL}_base.mag").write_text("\n".join(base) + "\n")
    tcl = ["# generated by dendgen.py -- do not edit", f"load {CELL}_base", f"cellname rename {CELL}_base {CELL}",
           "tech unlock *"]
    order = ["nwell", "psubdiff", "nsubdiff", "polysilicon", "metal1", "metal2", "metal3",
             "psubdiffcont", "nsubdiffcont", "polycontact", "via1", "via2", "comment"]
    lay = {"m1": "metal1", "m2": "metal2", "v1": "via1", "m3": "metal3", "v2": "via2"}
    # router via2 cuts are 0.26 (its spacing model); magic draws via2 at 0.28 minimum: grow them by 0.01 per side
    grow = lambda l, r: (r[0] - 0.01, r[1] - 0.01, r[2] + 0.01, r[3] + 0.01) if l == "v2" else r
    allp = list(L.paint) + [(lay[l], grow(l, r)) for l, r, n in wires]
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
    fig, ax = plt.subplots(figsize=(10, 16))
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
        ax.text(cx, cy, name, fontsize=3, ha="center", va="center")
    lay = {"m1": "metal1", "m2": "metal2", "m3": "metal3"}
    for l, r in list(L.paint) + [(lay.get(l, l), r) for l, r, n in wires]:
        if l in col:
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
    ax.set_xlim(-0.5, W + 0.5)
    ax.set_ylim(-0.5, H + 0.5)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=150, bbox_inches="tight")


def check_overlaps(insts):
    """Placement sanity: device diffusion+gate-head boxes must not overlap or crowd (< 0.5 um)."""
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
    for n, b in boxes:
        if b[2] > W - RING - 0.3 or b[3] > H - RING - 0.3:
            print("  OUTSIDE", n, b)
            bad += 1
        for k, r in KEEPOUT.items():
            if b[0] < r[2] and r[0] < b[2] and b[1] < r[3] and r[1] < b[3]:
                print("  IN KEEPOUT", n, k)
                bad += 1
    return bad


def write_devlist():
    ports, devs, caps = flatten.flatten(CELL)
    devs = split_wide(devs)
    (HERE / "devices").mkdir(exist_ok=True)
    (HERE / "devices" / "devlist.tcl").write_text("".join(
        f"mk {c} {d['model']} [dict merge $common {{w {d['W']:g} l {d['L']:g}}}]\n"
        for c, d in sorted({devcell(d): d for d in devs}.items())))


def main():
    write_devlist()
    if "devlist" in sys.argv:
        return 0
    L, insts, obst, mom, lib, devs, ports = build()
    nbad = check_overlaps(insts)
    print(f"placement issues: {nbad}")
    if "place" in sys.argv:
        preview(L, insts, [], HERE / "preview_place.png")
        return 0
    key = hashlib.sha1(repr((PLACE, COLS, M3LINES, M3INT, M3X, BRIDGES, FEEDS, REGIONS, KEEPOUT, NWELLS, VSS_STRIPES, MOM, W, H, PINS,
                             open(HERE / "router.py").read())).encode()).hexdigest()
    cache = HERE / "out" / f"route_cache_{CELL}.json"
    (HERE / "out").mkdir(exist_ok=True)
    if cache.exists() and ("reuse!" in sys.argv or ("reuse" in sys.argv and json.loads(cache.read_text())["key"] == key)):
        c = json.loads(cache.read_text())
        wires = [(l, tuple(r), n) for l, r, n in c["wires"]]
        failed = c["failed"]
        print("  reusing routing from", cache.name)
    else:
        R, failed = route(L, obst, mom)
        wires = [w for w in R.wire_list if w[0] != "fill"]
        cache.write_text(json.dumps(dict(key=key, failed=failed, wires=wires)))
    fills = fill_notches(obst, wires)
    print(f"  notch fillers: {len(fills)}")
    wires = list(wires) + fills
    # soma pin label on a routed vs wire segment (Metal2 if any, else Metal1)
    vsw = [w for w in wires if w[2] == "vs" and w[0] in ("m1", "m2")]
    if vsw:
        l, r, _ = sorted(vsw, key=lambda w: (w[0] != "m2", w[1][1]))[0]
        L.labels.append(("vs", {"m1": "metal1", "m2": "metal2"}[l], r, "signal"))
    write_outputs(L, insts, wires)
    preview(L, insts, wires, HERE / "preview.png")
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
