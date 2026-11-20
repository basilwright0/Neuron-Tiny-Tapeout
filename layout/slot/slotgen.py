"""Generate the neuron-array slot layouts slot_ah / slot_ah_h / slot_ah_p (gf180mcuD) reproducibly.

    scripts/eda.sh "cd layout/slot && python3 slotgen.py"      (then build.sh runs magic / netgen / klayout)

Inputs : cells/neuron/slot.spice (+ library cells) via flatten.py; PDK device cells in devices/
         (made by gen_devices.tcl with gf180mcu::{n,p}fet_03v3_draw).
Outputs: slot_ah_base.mag (device placements), slot_ah_paint.tcl (all drawn geometry, labels,
         ports), slot_ah_lvs.spice (LVS reference), preview.png, slot_report.json.

All units um, origin = slot lower-left. Cell is W x H; see PLAN below and README.md.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flatten                      # noqa: E402
from router import Router, HW, PAD  # noqa: E402

import os
CELL = os.environ.get("SLOT_CELL", "slot_ah")   # slot_ah (S), slot_ah_h (H: + gap trim), slot_ah_p (P: + trim, EL from aux)
# all slot variants (cells/neuron/slot.spice); same frame, column lines and row-band track assignment
SLOTS = ("slot_ah", "slot_ah_h", "slot_ah_p", "slot_ah_f", "slot_cmp_h", "slot_ah_50", "slot_ah_800",
         "slot_ref", "slot_dummy")
TRIM = CELL in ("slot_ah_h", "slot_ah_p")          # slot_cmp_h has no gap trim since 2026-11-20
CMP = CELL == "slot_cmp_h"            # comparator LIF: det_cmp instead of det_ah, no Cfb MOM
HAS_MOM = CELL not in ("slot_cmp_h", "slot_ref")
_SUB = flatten.parse()
PORTSET = set(_SUB[CELL]["ports"]) if CELL in SLOTS else None      # pins/straps only for ports the cell has


def has(net):
    return PORTSET is None or net in PORTSET
U = 200                              # magic internal units per um in device files (magscale 1 10)

# ============================================================================ cell frame
W, H = 28.0, 43.5
RING = 0.60                          # p-tap (VSS) ring width, on the cell edge (merges with neighbours)

# column lines: vertical Metal2, full height, connect by abutment (x centre, width)
COLS = [("vbp_syn", 19.05, 0.30), ("vdd", 19.85, 0.60), ("el", 20.65, 0.30), ("aux", 21.35, 0.30),
        ("vbn_leak", 22.05, 0.30), ("vsrc", 22.75, 0.30), ("vbp_st", 23.45, 0.30),
        ("vbn_prb", 24.15, 0.30), ("vbn_ref", 24.85, 0.30), ("en", 25.55, 0.30),
        ("vreset", 26.25, 0.30), ("abus", 26.95, 0.30)]
# VSS needs no Metal2 column: the p-tap ring's Metal1 left/right edges abut top-to-bottom.
# Metal3 feed-through band (row digital lines): no cell metal3 inside, vm kept out of it.
# 19 tracks at the Metal3 minimum pitch (0.28 + 0.28): centres 32.38 + 0.56 k, k = 0..18 (top 42.46).
NTRACK = 19
TRACK_PITCH = 0.56
TRACK_Y0 = 32.38
BAND = (0.0, round(TRACK_Y0 - 0.14, 3), W, 42.60)
# Fixed track assignment of the row signals (docs: layout/slot/README.md):
#   k = 0 sta, 1 stb, 2 hold, 3 mreset (rt_out, shared by every slot), 4 rsel (probe row select),
#   5 sub, 6 sub_b (PROBE_SUB[0] and its complement), 7..10 spk of the slots in columns 0..3,
#   11..18 trim bits (4 per trimmed slot, at most 2 trimmed slots per row).
TRACK = {"sta": 0, "stb": 1, "hold": 2, "mreset": 3, "rsel": 4, "sub": 5, "sub_b": 6}
def track_y(k):
    return round(TRACK_Y0 + TRACK_PITCH * k, 3)
# per-slot digital pins: Metal2 vertical straps crossing the whole band (row router drops a via2
# onto whichever track it assigns)
# rt_out (stim A/B, hold, membrane reset) are shared by all slots; t0..t3 are the gap-trim bits (H/P).
# per-slot signals whose track depends on the slot's column (spk, trim bits): Metal2 straps over the
# whole band; shared row signals: one Metal2 pad under their fixed track (PINS: net -> pad centre x).
STRAPS = [("spk", 16.60)] if has("spk") else []     # slot_dummy / slot_ref: no spike output
PINS = {"sta": 17.40, "stb": 15.30, "hold": 14.00, "mreset": 17.40, "rsel": 15.30, "sub": 14.00, "sub_b": 17.40}
if TRIM:    # trimmed slots: unstack the x = 17.4 column next to the synapse switches
    PINS.update({"mreset": 18.30, "sub_b": 15.30})
PINS = {k: v for k, v in PINS.items() if has(k)}
# gap trim (H/P) is laid out as 4 bit slices at x = SLICE[k]: vm-side pfet switch XP_k (y 31.3) under
# the la-side nfet switch XN_k (y 33.8), o_k on their right stripes (Metal2 up to the leg), and the
# trim-bit strap t_k 0.9 um left of the slice, running from the switch gates up over tracks 11..18.
SLICE = {3: 4.00, 2: 6.80, 1: 9.60, 0: 12.40}
if TRIM:
    STRAPS += [(f"t{k}", round(x - 0.9, 3)) for k, x in SLICE.items()]
STRAP_Y = (BAND[1], BAND[3] - 0.1)
# a strap only spans the tracks its signal may be assigned to (spk: k 7..10, trim bits: k 11..18)
STRAP_BOTTOM = {n: (31.95 if n.startswith("t") else round(track_y(7) - 0.2, 3)) for n, _ in STRAPS}
STRAP_TOP = {n: round(track_y(10 if n == "spk" else 18) + 0.2, 3) for n, _ in STRAPS}
KEEPOUT = {}       # the former trim / synapse keep-outs now hold the synapse and the gap trim
# n-well island for all PMOS, with its own n-tap (VDD) ring; VDD rail = ring's bottom edge
NWELL = (0.90, 21.20, 21.60, 29.80)
# n-well extensions above the island (merged with it, tapped by its ring):
#   synapse pfets (under the column band) and the hold switch / trim vm-side pfet switches
NWELL_EXT = [(19.45, 29.30, 26.90, 38.90), (14.75, 32.50, 19.45, 35.10)]
if TRIM:
    NWELL_EXT += [(0.90, 29.60, 13.50, 32.60)]
elif CELL != "slot_ah_800":     # AH800: the hold switch moves into the main n-well (row A), its old spot holds XC2
    NWELL_EXT += [(8.80, 29.60, 11.40, 32.60)]
if CMP:                         # det_cmp hysteresis source XH2 (1/6) in a bump under the VDD rail (former MOM area)
    NWELL_EXT += [(0.90, 18.65, 8.75, 21.25)]
VM_PIN = (17.85, 29.35, 18.25, 29.75)
NTAP = 0.60
# Routing metals. Metal3 is used for local routing below the feed-through band only (forbidden in
# y >= BAND[1] - 0.3 and within 0.3 um of the cell edge); the band itself stays free of cell Metal3.
LAYERS = ("m1", "m2", "m3")
# Fine routing (0.28 um wires on a 0.56 um base grid, ~25 % more tracks) for all slots: the slot
# upper half is the densest part of the array; ROUTE_FINE=0 gives the old 0.30 / 0.70.
FINE = os.environ.get("ROUTE_FINE", "1") == "1"
WIRE_HW, GRID = (0.14, 0.56) if FINE else (0.15, 0.70)
# MOM feedback capacitor Cfb (spk -> vm), Metal1..Metal3 interdigitated fingers
MOM = dict(x=1.20, y=15.60, nf=12, lf=3.6, pitch=0.58, fw=0.30)      # y 15.6: clears the taller leak row

# ============================================================================ placement
# device centre (x, y) of the diffusion; flip=True swaps which stripe is source/drain.
# XPM tap chain prb -> XSC -> XSW -> XSB -> abus. PROBE_CHAIN=1 (2026-11-19, after slot_ah_800 failed to route
# with XSC at (21.3, 2.6)): the three switches in order along the y = 8 row, shared nets facing each other.
PROBE_CHAIN = os.environ.get("PROBE_CHAIN", "1") == "1"
PROBE_XPM = ({"XSC": (18.20, 8.00), "XSW": (20.00, 8.00), "XSB": (21.80, 8.00)} if PROBE_CHAIN else
             {"XSC": (21.30, 2.60), "XSW": (18.20, 8.00), "XSB": (20.00, 8.00)})
PLACE = {
    # membrane cap: quiet bottom-left corner
    "XC.XC": (5.00, 5.00),
    # leak OTA nmos (2026-11-19: inputs 4/1, degeneration diodes 8/1 drawn as two parallel 4/1 halves a/b;
    # netgen merges parallel devices): one row D1a D1b M1 M2 D2a D2b, tail to the right
    "XL.XD1a": (1.94, 12.70), "XL.XD1b": (4.18, 12.70), "XL.XM1": (6.42, 12.70), "XL.XM2": (8.66, 12.70),
    "XL.XD2a": (10.90, 12.70), "XL.XD2b": (13.14, 12.70), "XL.XMT": (16.88, 12.70),
    # detector chain: each stage's pmos (row A, in the n-well) right above its nmos
    "XD.XNI": (9.30, 17.60), "XD.XN2": (11.80, 17.60), "XD.XN3": (14.20, 17.60), "XD.Xi4.XN": (16.10, 17.60),
    "XR.Xi.XN": (17.80, 17.60), "XR.XSW": (12.80, 8.20),
    "XD.XS3": (6.60, 22.90), "XD.XPI": (9.30, 22.90),
    # det_ah keeper XK (2026-11-19 reset fix): mid-row of the main n-well between XP3/Xi4 (row A) and row B
    "XD.XK": (15.20, 25.00), "XD.XP2": (11.80, 22.90), "XD.XP3": (14.20, 22.90), "XD.Xi4.XP": (16.10, 22.90),
    "XR.Xi.XP": (17.80, 22.90), "XR.XPC": (19.40, 22.90),
    # row B: leak pmos mirror + detector starve sources (vbp_st)
    "XL.XP1": (4.40, 27.10), "XL.XP2": (10.00, 27.10), "XD.XPS": (14.20, 27.10), "XD.XS2": (17.40, 27.10),
    # probe followers (left of the column band; drains on the vdd line side)
    "XPR.XMF": (14.60, 3.40), "XPM.XMF": (18.20, 3.40),
    # probe switch / enable / sink stacks under the column band, gates on their own lines
    "XPM.XME": (25.05, 2.20), "XPM.XMB": (24.09, 5.20),
    "XPR.XME": (25.05, 8.60), "XPR.XMB": (24.09, 11.60),
    "XPR.XSW": (14.60, 8.00), "XPM.XSW": PROBE_XPM["XSW"], "XPR.XSB": (16.40, 8.00), "XPM.XSB": PROBE_XPM["XSB"],
    # column-select series switches XSC (gate en; 2026-11-18 probe fix: prb -> XSC -> XSW -> XSB -> abus)
    "XPM.XSC": PROBE_XPM["XSC"], "XPR.XSC": (11.90, 5.00),
    # refractory discharge (gate on vbn_ref) and Cr under the band, vss side against the ring
    "XR.XNR": (24.15, 19.40), "XR.XCR.XC": (24.25, 25.00),
    # ---- input synapse (cells/neuron/synapse.spice): weight pfets (drains da/db on the left, shared
    # source h on the right) and the hold pfet in the n-well extension under the column band; the
    # steering switches (dump pfets XQ in an n-well bump, vm-side nfets XN below the Metal3 band) in the
    # free strip left of the column band, where Metal2/Metal3 are available below the straps
    "XS.XWA": (22.40, 31.30), "XS.XWB": (22.40, 34.40), "XS.XPH": (24.80, 37.60), "XS.XMR": (22.40, 40.90),
    "XS.XNA": (18.00, 31.30), "XS.XNB": (15.80, 31.30),
    "XS.XQA": (18.00, 33.90), "XS.XQB": (15.80, 33.90),
    "XS.XHL": (10.20, 31.30),
}
if TRIM:
    PLACE.update({
        # ---- gap trim (cells/trim/trim_gap.spice): vm-side pfet switches in the n-well extension,
        # R-2R ladder rows and a-side nfet switches above it
        **{f"XT.XP{k}": (x, 31.30) for k, x in SLICE.items()},
        **{f"XT.XN{k}": (x, 33.80) for k, x in SLICE.items()},
        # legs, flipped so o_k (drain) is the left stripe, right above the slice's o_k column
        "XT.XL3": (SLICE[3] + 2.165, 36.00), "XT.XL1": (SLICE[1] + 2.165, 36.00),
        "XT.XL2": (SLICE[2] + 2.165, 38.20), "XT.XL0": (SLICE[0] + 2.165, 38.20),
        "XT.XR3": (2.30, 36.00), "XT.XLT": (3.00, 38.20),
        "XT.XRA": (3.40, 40.40), "XT.XRB": (8.84, 40.40), "XT.XR1": (12.97, 40.40), "XT.XR2": (15.65, 40.40),
        "XS.XHL": (1.80, 31.30),
    })
if CELL == "slot_ah_800":
    # 2nd membrane cap (mcap_r 11.7 x 11.6; was 12.4 long until the 2026-11-19 reroute: XS.db had no room) in the S slot's former trim space, gate head DOWN (below the row
    # band, y 30.15), Metal1 vss shield over it; the hold switch XHL moves to row A of the main n-well.
    PLACE.update({"XC2.XC": (7.24, 36.45), "XS.XHL": (3.40, 22.90)})
if CMP:
    # det_cmp: input pair (2/1) in row A raised to y 23.4, hysteresis switch XH1 left of it over XH2 (bump),
    # tail XPT / inverter starve Xi1.XS in row B (the det_ah XPS / XS2 spots), nfet mirror XN1/XN2 in the
    # former MOM area, the inverters where det_ah's last stages were.
    # 2026-11-19 re-placement (the first one never routed): input pair at the right end of row A next to the
    # aux (vth_cmp) column, nfet mirror right under it, tail XPT right above it; inverters, hysteresis switch
    # and the refractory pfets shifted left in row A; XH2 stays in the bump under the rail.
    PLACE.update({
        "XD.XM1": (16.10, 23.40), "XD.XM2": (18.60, 23.40),
        "XD.XH1": (7.30, 22.90), "XD.Xi1.XP": (9.00, 22.90), "XD.Xi2.XP": (10.70, 22.90),
        "XR.Xi.XP": (12.40, 22.90), "XR.XPC": (14.10, 22.90),
        "XD.XPT": (17.40, 27.10), "XD.Xi1.XS": (14.20, 27.10),
        "XD.Xi1.XN": (8.60, 17.60), "XD.Xi2.XN": (10.30, 17.60), "XR.Xi.XN": (12.00, 17.60),
        "XD.XN1": (14.60, 17.60), "XD.XN2": (18.00, 17.60), "XD.XH2": (4.84, 19.85),
    })
HEAD_DOWN = {"XC2.XC"}                # devices whose gate head is drawn below the diffusion
# Metal1 vss shield plates (AH800: over XC2, from above its gate head to the top ring)
# y0 30.66: the plate is "wide metal" (> 10 um), so M1.2b needs 0.30 um to the XC2 gate-head pad (top 30.34)
PLATES = [(0.60, 30.66, 13.48, 43.50)] if CELL == "slot_ah_800" else []
FLIP = {"XPM.XSW", "XPR.XSW", "XR.XNR", "XS.XWA", "XS.XWB", "XS.XPH", "XS.XQA", "XS.XQB"}
if PROBE_CHAIN:
    FLIP |= {"XPM.XSC", "XPM.XSB", "XPR.XSB"}
if CMP:
    FLIP |= {"XD.XN1"}
if TRIM:
    FLIP |= {f"XT.X{t}{k}" for t in ("P", "N", "L") for k in range(4)}

ROUTE_FIRST = ["vm", "vr", "spk"]
ROUTE_LAST = ["vdd", "vss"]
ITERS = int(os.environ.get("ROUTE_ITERS", "60"))      # negotiation iterations per schedule
SCHEDULES = [(1.3, 0.5), (1.6, 0.3), (1.2, 0.7), (1.45, 0.4), (1.3, 0.3)]
if os.environ.get("SCHED_ROTATE"):          # try the negotiation schedules in a different order
    _k = int(os.environ["SCHED_ROTATE"]) % len(SCHEDULES)
    SCHEDULES = SCHEDULES[_k:] + SCHEDULES[:_k]
if os.environ.get("MAX_SCHED"):            # try only the first n schedules (with a larger ROUTE_ITERS)
    SCHEDULES = SCHEDULES[:int(os.environ["MAX_SCHED"])]


# ============================================================================ device library
def devcell(d):
    f = lambda v: ("%g" % v).replace(".", "p")
    return f"{d['model'][0]}_w{f(d['W'])}_l{f(d['L'])}"


def load_dev(name):
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
    raw = (HERE / "devices" / f"{name}.mag").read_text()
    allr = [r for k, v in R.items() for r in v]
    return dict(name=name, ts=ts, R=R, diff=bb(diff), gate=gate, m1=side,
                stripe={k: bb(v) for k, v in side.items()}, bbox=bb(allr),
                well=bb(R.get("pwell", []) + R.get("nwell", [])))


def split_devs(devs):
    """Layout-only: draw every W >= 8 um, L <= 1 um device (the leak OTA's 8/1 diodes) as two parallel halves
    <name>a / <name>b of W/2 (the LVS reference keeps the single device; netgen adds parallel widths)."""
    out = []
    for d in devs:
        if d["W"] >= 8 and d["L"] <= 1.0:
            out += [dict(d, name=d["name"] + k, W=round(d["W"] / 2, 4)) for k in "ab"]
        else:
            out.append(d)
    return out


def snap(v, g=0.005):
    return round(round(v / g) * g, 4)


def shift(r, dx, dy):
    return (snap(r[0] + dx), snap(r[1] + dy), snap(r[2] + dx), snap(r[3] + dy))


# ============================================================================ build
class Layout:
    def __init__(self):
        self.paint = []        # (layer, rect)   drawn in the parent cell
        self.labels = []       # (text, layer, rect, port_use or None)
        self.nets = {}         # net -> list of terminals; terminal = list of (layer, rect)

    def p(self, layer, r):
        self.paint.append((layer, tuple(snap(v) for v in r)))

    def term(self, net, shapes):
        self.nets.setdefault(net, []).append(shapes)


def build():
    ports, devs, caps = flatten.write_lvs(HERE / f"{CELL}_lvs.spice", CELL)
    devs = split_devs(devs)
    DEVNAMES.clear()
    DEVNAMES.update(d["name"] for d in devs)
    DEVS_KEY[:] = [repr(sorted((d["name"], d["model"], d["d"], d["g"], d["s"], d["W"], d["L"]) for d in devs))]
    lib = {}
    for d in devs:
        c = devcell(d)
        if c not in lib:
            lib[c] = load_dev(c)
    L = Layout()
    insts = []
    obst = []              # (layer, rect, net) device metal for the router

    # ------------------------------------------------------------------ devices + gate heads
    for d in devs:
        lc = lib[devcell(d)]
        if d["name"] not in PLACE:
            raise SystemExit(f"no placement for {d['name']}")
        cx, cy = PLACE[d["name"]]
        insts.append((lc, d["name"], cx, cy))
        nL, nR = (d["d"], d["s"]) if d["name"] in FLIP else (d["s"], d["d"])
        for side, net in (("L", nL), ("R", nR)):
            shapes = [("m1", shift(r, cx, cy)) for r in lc["m1"][side]]
            for s in shapes:
                obst.append(s + (net,))
            L.term(net, [("m1", shift(lc["stripe"][side], cx, cy))])
        # gate head: poly extension of the whole gate + 0.36 poly head, contact, 0.38 metal1 pad
        g = lc["gate"]
        hx = max((g[2] - g[0]) / 2, 0.18)
        if d["name"] in HEAD_DOWN:
            hcy = snap(lc["diff"][1] - 0.45)
            L.p("polysilicon", shift((g[0], hcy - 0.18, g[2], g[1]), cx, cy))
        else:
            hcy = snap(lc["diff"][3] + 0.45)
            L.p("polysilicon", shift((g[0], g[3], g[2], hcy + 0.18), cx, cy))
        L.p("polysilicon", shift((-hx, hcy - 0.18, hx, hcy + 0.18), cx, cy))
        pad = shift((-0.19, hcy - 0.19, 0.19, hcy + 0.19), cx, cy)
        L.p("metal1", pad)
        L.p("polycontact", shift((-0.115, hcy - 0.115, 0.115, hcy + 0.115), cx, cy))
        obst.append(("m1", pad, d["g"]))
        L.term(d["g"], [("m1", pad)])

    # ------------------------------------------------------------------ p-tap ring (VSS)
    nw = NWELL
    rail_y = (nw[1] + 0.12, nw[1] + 0.12 + NTAP)           # VDD rail = n-tap ring bottom edge
    gap = (rail_y[0] - 0.30, rail_y[1] + 0.30)              # VSS metal gap where the VDD rail crosses
    ring = [(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]
    for r in ring:
        L.p("psubdiff", r)
    c = (RING - 0.23) / 2
    m1ring = [(0, 0, W, RING), (0, H - RING, W, H)]
    for x0 in (0, W - RING):
        m1ring += [(x0, 0, x0 + RING, gap[0]), (x0, gap[1], x0 + RING, H)]
    for r in m1ring:
        L.p("metal1", r)
        obst.append(("m1", r, "vss"))
        L.term("vss", [("m1", r)])
        # contact strip inset so metal1 surrounds it
        if r[2] - r[0] > r[3] - r[1]:
            L.p("psubdiffcont", (r[0] + c, r[1] + c, r[2] - c, r[3] - c))
        else:
            L.p("psubdiffcont", (r[0] + c, r[1] + c + 0.1, r[2] - c, r[3] - c - 0.1))

    L.labels.append(("vss", "metal1", (2.0, 0.1, 3.0, 0.5), "ground"))

    # ------------------------------------------------------------------ n-well + n-tap ring (VDD)
    L.p("nwell", nw)
    for r in NWELL_EXT:
        L.p("nwell", r)
    t = (nw[0] + 0.12, nw[1] + 0.12, nw[2] - 0.12, nw[3] - 0.12)
    nring = [(t[0], t[1], t[2], t[1] + NTAP), (t[0], t[3] - NTAP, t[2], t[3]),
             (t[0], t[1], t[0] + NTAP, t[3]), (t[2] - NTAP, t[1], t[2], t[3])]
    for k, r in enumerate(nring):
        L.p("nsubdiff", r)
        if k == 3:          # right edge: diffusion only (lets Metal1 cross into the column band)
            continue
        L.p("metal1", r)
        obst.append(("m1", r, "vdd"))
        L.term("vdd", [("m1", r)])
        L.p("nsubdiffcont", (r[0] + c, r[1] + c, r[2] - c, r[3] - c))
    # VDD rail: extends the ring's bottom edge to both cell edges (left-right abutment)
    rail = (0, rail_y[0], W, rail_y[1])
    L.p("metal1", rail)
    obst.append(("m1", rail, "vdd"))
    L.term("vdd", [("m1", rail)])

    # ------------------------------------------------------------------ column lines (M2)
    colx = {}
    for net, x, w in COLS:
        r = (x - w / 2, 0, x + w / 2, H)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        colx[net] = x
        COLX[net] = x
        L.labels.append((net, "metal2", (r[0], H - 0.6, r[2], H - 0.2), "power" if net in ("vdd", "vss") else "signal"))
    # vss column <-> ring (bottom, top); vdd column <-> rail
    for net, ys in (("vdd", ((rail_y[0] + rail_y[1]) / 2,)),):
        x = colx[net]
        for y in ys:
            via(L, x, y, obst, net, w=0.6)

    # ------------------------------------------------------------------ straps (per-slot pins)
    for net, x in STRAPS:
        r = (x - 0.15, STRAP_BOTTOM[net], x + 0.15, STRAP_TOP[net])
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", (r[0], r[3] - 0.5, r[2], r[3] - 0.2), "signal"))

    # ------------------------------------------------------------------ fixed-track pads (shared row signals)
    for net, x in PINS.items():
        y = track_y(TRACK[net])
        r = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", r, "signal"))

    # ------------------------------------------------------------------ MOM Cfb
    mom = mom_cap(L, obst) if HAS_MOM else None

    # ------------------------------------------------------------------ Metal1 vss shield plates
    for r in PLATES:
        L.p("metal1", r)
        obst.append(("m1", r, "vss"))
        L.term("vss", [("m1", r)])

    # ------------------------------------------------------------------ vm pin
    if has("vm"):
        vmpin = VM_PIN
        L.p("metal2", vmpin)
        obst.append(("m2", vmpin, "vm"))
        L.term("vm", [("m2", vmpin)])
        L.labels.append(("vm", "metal2", vmpin, "signal"))

    # ------------------------------------------------------------------ keep-outs (comment layer)
    for name, r in KEEPOUT.items():
        L.p("comment", r)
        L.labels.append((name, "comment", (r[0] + 0.5, r[3] - 1.0, r[0] + 0.5, r[3] - 1.0), None))

    return L, insts, obst, mom, lib, devs, ports


def via(L, x, y, obst, net, w=0.4):
    pad = (x - w / 2, y - 0.2, x + w / 2, y + 0.2)
    L.p("metal1", pad)
    L.p("metal2", pad)
    L.p("via1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13))
    obst.append(("m1", pad, net))
    obst.append(("m2", pad, net))
    obst.append(("v1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net))


def mom_cap(L, obst):
    """Interdigitated fingers on M1, M2, M3 (same polarity stacked). Bottom bar = spk, top bar = vm."""
    m = MOM
    x0, y0, nf, lf, pitch, fw = m["x"], m["y"], m["nf"], m["lf"], m["pitch"], m["fw"]
    width = (nf - 1) * pitch + fw
    bar = 0.50
    gapf = 0.30
    bot = (x0, y0, x0 + width, y0 + bar)
    top = (x0, y0 + bar + gapf + lf + gapf, x0 + width, y0 + bar + gapf + lf + gapf + bar)
    shapes = {"spk": [bot], "vm": [top]}
    for k in range(nf):
        fx = x0 + k * pitch
        if k % 2 == 0:   # spk fingers from the bottom bar
            shapes["spk"].append((fx, bot[3], fx + fw, top[1] - gapf))
        else:            # vm fingers from the top bar
            shapes["vm"].append((fx, bot[3] + gapf, fx + fw, top[1]))
    for net, rs in shapes.items():
        for r in rs:
            for lay in ("metal1", "metal2", "metal3"):
                L.p(lay, r)
            obst.append(("m1", r, net))
            obst.append(("m2", r, net))
            obst.append(("m3", r, net))
        b = rs[0]
        # via1 + via2 rows along each bar
        nv = int((b[2] - b[0] - 0.1) // 0.6)
        for k in range(nv):
            vx = b[0] + 0.30 + k * 0.6
            vy = (b[1] + b[3]) / 2
            if vx + 0.14 > b[2] - 0.06:
                break
            L.p("via1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13))
            L.p("via2", (vx - 0.14, vy - 0.14, vx + 0.14, vy + 0.14))
            obst.append(("v1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13), net))
            obst.append(("v2", (vx - 0.14, vy - 0.14, vx + 0.14, vy + 0.14), net))
        L.term(net, [("m1", b), ("m2", b)])
    box = (x0, y0, x0 + width, top[3])
    return dict(box=box, shapes=shapes)


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
    for net, x in STRAPS:
        req_x.add(x)
    req_y.update({1.00, snap(H - 1.00)})
    # free Metal2 tracks between column lines
    cx = sorted(x for _, x, _ in COLS)
    for a, b in zip(cx, cx[1:]):
        if b - a > 1.2:
            req_x.add(snap((a + b) / 2, 0.005))

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
    # keep-outs: nothing may enter (spacing to the box is not needed: comment layer only)
    for name, r in KEEPOUT.items():
        R.add_forbid(("m1", "m2"), r)
    # membrane cap gate: only vm may run over it (no aggressors on the membrane)
    if "XC.XC" in DEVNAMES:
        cap = PLACE["XC.XC"]
        R.add_forbid(("m1", "m2", "m3"), (cap[0] - 3.6, cap[1] - 3.6, cap[0] + 3.6, cap[1] + 3.6), allowed={"vm", "vss"})
    # Metal3: never in or next to the row feed-through band, never near the cell edge
    R.add_forbid(("m3",), (0, BAND[1] - 0.3, W, H))
    for r in ((0, 0, W, 0.3), (0, 0, 0.3, H), (W - 0.3, 0, W, H)):
        R.add_forbid(("m3",), r)
    # vm must stay out of the metal3 feed-through band
    R.add_forbid(("m1", "m2"), (BAND[0], BAND[1] - 0.3, BAND[2], BAND[3]), only={"vm"})
    # wide-metal (M1.2b, 0.30 um) halo right of the Metal1 shield plates
    for pl in PLATES:
        R.add_forbid(("m1",), (pl[2], pl[1], pl[2] + 0.32, pl[3]), allowed={"vss"})
    # MOM: only its own nets
    if mom:
        R.add_forbid(("m1", "m2", "m3"), mom["box"], allowed={"vm", "spk"})
    # bottom channel under the probe stacks is reserved for the probe outputs leaving westwards
    R.add_forbid(("m1",), (19.6, 0.0, 27.0, 1.6), only={"vss"})
    R.add_forbid(("m1",), (19.6, 6.9, 27.0, 7.8), only={"vss"})
    # cell perimeter: routed metal stays >= 0.15 um inside the ring so abutting cells never touch
    # (ring Metal1 itself is vss; vss may land on it)
    for r in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        R.add_forbid(("m1",), r, allowed={"vss"})
    for r in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        R.add_forbid(("m2",), r)


OBST_CACHE = []
DEVNAMES = set()
DEVS_KEY = []
COLX = {n: x for n, x, _ in COLS}


def route(L, obst, mom):
    OBST_CACHE[:] = obst
    xs, ys = make_grid(L, GRID)
    R = Router(xs, ys, layers=LAYERS, hw=WIRE_HW)
    for lay, r, net in obst:
        R.add_shape(lay, r, net)
    add_forbids(R, mom)

    def nodes(net, shapes):
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
        tn = [nodes(net, t) for t in terms]
        empty = [i for i, t in enumerate(tn) if not t]
        if empty:
            print(f"  !! {net}: terminal(s) {empty} have no grid node")
        nets[net] = [t for t in tn if t]
    order = [n for n in ROUTE_FIRST if n in nets]
    if os.environ.get("ROUTE_FIRST_PREFIX"):     # e.g. "XT." routes the trim-internal nets right after vm/vr/spk
        order += sorted(n for n in nets if n.startswith(os.environ["ROUTE_FIRST_PREFIX"]) and n not in order)
    order += sorted((n for n in nets if n not in ROUTE_FIRST + ROUTE_LAST and n not in order), key=lambda n: (n.count(".") == 0, n))
    order += [n for n in ROUTE_LAST if n in nets]
    # negotiated-congestion schedules tried in turn until one converges with no conflicts
    for k, (pm, hs) in enumerate(SCHEDULES):
        if k:
            R = Router(xs, ys, layers=LAYERS, hw=WIRE_HW)
            for lay, r, net in obst:
                R.add_shape(lay, r, net)
            add_forbids(R, mom)
        print(f"  schedule {k}: pres_mult={pm} hist_step={hs}")
        unrouted, bad = R.route_all(nets, order, iters=ITERS, pres_mult=pm, hist_step=hs)
        failed = sorted(unrouted | bad)
        if not failed:
            break
    for c in R.conflict_list():
        print("  CONFLICT", c)
    print("  UNROUTED", sorted(unrouted))
    R.wire_list = R.wires()
    return R, failed


# ============================================================================ notch fill
def fill_notches(obst, wires):
    """Same-net metal closer than min spacing (slots/notches between a wire end and a pad or
    stripe) is a DRC error. Per net and layer, take the union of all its metal and apply a
    morphological closing (grow by s/2, shrink by s/2, square corners): that fills exactly the
    sub-spacing gaps. The added area is returned as filler rectangles."""
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
        d = int(round(SPACE[lay] / dbu))          # also bridges diagonal (corner-to-corner) same-net gaps
        minw = int(round({"m1": 0.23, "m2": 0.28, "m3": 0.28}[lay] / dbu))
        closed = reg.dup()
        for _ in range(3):
            # close sub-spacing gaps, then widen min-width necks the fill may leave
            closed = closed.sized(d, d, 2).sized(-d, -d, 2)
            # same-net corner-to-corner gaps the closing leaves (2026-11-19): bridge each remaining same-net
            # spacing violation with a box over the gap, at least min-width in both directions
            for ep in closed.space_check(d).each():
                bb = ep.bbox()
                cx, cy = bb.center().x, bb.center().y
                w2 = max(bb.width(), minw) // 2 + 1
                h2 = max(bb.height(), minw) // 2 + 1
                closed.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
            closed.merge()
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
        # never let a filler come closer than min spacing to another net's metal on this layer
        others = kdb.Region()
        for (l2, n2), rs2 in per.items():
            if l2 == lay and n2 != net:
                for r in rs2:
                    others.insert(kdb.Box(*(round(v / dbu) for v in r)))
        sp = int(round(SPACE[lay] / dbu))
        add = add - others.sized(sp, sp, 2)
        # clipping can leave a min-width neck in net + fill: widen it where that stays clear of other nets
        fin = (reg + add).merged()
        for ep in fin.width_check(minw).each():
            bb = ep.bbox()
            cx, cy = bb.center().x, bb.center().y
            w2 = max(bb.width(), minw) // 2 + 1
            h2 = max(bb.height(), minw) // 2 + 1
            add.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
        add = (add - others.sized(sp, sp, 2)).merged()
        for bx in add.each_merged():
            for t in kdb.Region(bx).decompose_trapezoids(1):
                pts = [p for p in t.each_point_hull()]
                xs = [p.x * dbu for p in pts]
                ys = [p.y * dbu for p in pts]
                out.append((lay, (snap(min(xs)), snap(min(ys)), snap(max(xs)), snap(max(ys))), net))
    return out


# ============================================================================ output
def write_outputs(L, insts, R, mom, lib):
    base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
    for lc, name, cx, cy in insts:
        b = lc["bbox"]
        base += [f"use {lc['name']}  {name.replace('.', '_')}", f"timestamp {lc['ts']}",
                 f"transform 1 0 {round(cx * U)} 0 1 {round(cy * U)}",
                 f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
    base.append("<< end >>")
    (HERE / f"{CELL}_base.mag").write_text("\n".join(base) + "\n")

    tcl = ["# generated by slotgen.py -- do not edit", f"load {CELL}_base", f"cellname rename {CELL}_base {CELL}",
           "tech unlock *"]
    order = ["nwell", "psubdiff", "nsubdiff", "polysilicon", "metal1", "metal2", "metal3",
             "psubdiffcont", "nsubdiffcont", "polycontact", "via1", "via2", "comment"]
    lay = {"m1": "metal1", "m2": "metal2", "v1": "via1", "m3": "metal3", "v2": "via2"}
    allp = list(L.paint) + [(lay[l], r) for l, r, n in R.wire_list]
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


def preview(L, insts, R, mom, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(9, 14))
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
    lay = {"m1": "metal1", "m2": "metal2", "m3": "metal3"}
    for l, r in list(L.paint) + [(lay.get(l, l), r) for l, r, n in R.wire_list]:
        if l in col:
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
    ax.add_patch(Rectangle(BAND[:2], BAND[2] - BAND[0], BAND[3] - BAND[1], fill=False, ec="green", ls="--"))
    ax.set_xlim(-0.5, W + 0.5)
    ax.set_ylim(-0.5, H + 0.5)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=150, bbox_inches="tight")


def write_devlist():
    """One PDK device cell per unique (model, W, L) over all slot variants (input to gen_devices.tcl)."""
    sizes = {}
    for cell in SLOTS + ("trim_el4", "trim_tau4"):
        for d in split_devs(flatten.flatten(cell)[1]):
            sizes[devcell(d)] = d
    (HERE / "devices" / "devlist.tcl").write_text("".join(
        f"mk {c} {d['model']} [dict merge $common {{w {d['W']:g} l {d['L']:g}}}]\n" for c, d in sorted(sizes.items())))


def main():
    if "devlist" in sys.argv:
        write_devlist()
        return 0
    L, insts, obst, mom, lib, devs, ports = build()
    if "place" in sys.argv:          # placement preview only (no routing)

        class R0:
            wire_list = []
        preview(L, insts, R0, mom, HERE / "out" / f"place_{CELL}.png")
        return 0
    import hashlib
    key = hashlib.sha1(repr((DEVS_KEY, sorted(HEAD_DOWN), PLATES, PLACE, sorted(FLIP), COLS, STRAPS, STRAP_BOTTOM, STRAP_TOP, KEEPOUT, NWELL, NWELL_EXT, VM_PIN, LAYERS, WIRE_HW, GRID, PINS, SLICE, TRACK, BAND, MOM, W, H,
                             open(HERE / "router.py").read())).encode()).hexdigest()
    cache = HERE / "out" / f"route_cache_{CELL}.json"
    hcache = HERE / "out" / "route_cache_slot_ah_h.json"
    if CELL == "slot_ah_p" and os.environ.get("P_FROM_H", "1") == "1" and hcache.exists():
        # The P slot differs from H only in which column line feeds the leak-tail / ladder gates
        # (aux at x 21.35 instead of vbn_leak at 22.05). Take H's routing, rename that tree to aux
        # and move its landings from the vbn_leak column to the aux column; DRC/LVS check the result.
        c = json.loads(hcache.read_text())
        dx = COLX["aux"] - COLX["vbn_leak"]
        lo, hi = COLX["vbn_leak"] - 0.25, COLX["vbn_leak"] + 0.25
        wires = []
        for l, r, n in c["wires"]:
            if n == "vbn_leak":
                n = "aux"
                cx, w = (r[0] + r[2]) / 2, r[2] - r[0]
                if lo <= cx <= hi and (l in ("v1", "v2", "m2") or w <= 0.41):
                    # landing via + pads move to aux, centred on the aux column (H's pads may sit off the
                    # vbn_leak centre; shifted as-is they came 0.25 um from el's pads)
                    r = (round(COLX["aux"] - w / 2, 3), r[1], round(COLX["aux"] + w / 2, 3), r[3])
                elif l in ("m1", "m3") and r[2] > COLX["aux"] + 0.2:
                    if r[0] >= COLX["aux"] + 0.2:
                        continue
                    r = (r[0], r[1], round(COLX["aux"] + 0.2, 3), r[3])
            wires.append((l, tuple(r), n))

        class R:
            pass
        R.wire_list = wires
        failed = c["failed"]
        OBST_CACHE[:] = obst
        cache.write_text(json.dumps(dict(key=key, failed=failed, wires=wires, derived_from="slot_ah_h")))
        print("  routing derived from route_cache_slot_ah_h.json (vbn_leak tree -> aux)")
    elif cache.exists() and ("reuse!" in sys.argv or ("reuse" in sys.argv and json.loads(cache.read_text())["key"] == key)):
        c = json.loads(cache.read_text())

        class R:
            pass
        R.wire_list = [(l, tuple(r), n) for l, r, n in c["wires"]]
        failed = c["failed"]
        OBST_CACHE[:] = obst
        print("  reusing routing from", cache.name)
    else:
        R, failed = route(L, obst, mom)
        R.wire_list = [w for w in R.wire_list if w[0] != "fill"]
        (HERE / "out").mkdir(exist_ok=True)
        cache.write_text(json.dumps(dict(key=key, failed=failed, wires=R.wire_list)))
        R.wire_list = list(R.wire_list)
    # via2 cuts are 0.28 um squares in magic (older caches stored 0.26)
    R.wire_list = [(l, ((r[0] + r[2]) / 2 - 0.14, (r[1] + r[3]) / 2 - 0.14, (r[0] + r[2]) / 2 + 0.14,
                        (r[1] + r[3]) / 2 + 0.14), n) if l == "v2" else (l, r, n) for l, r, n in R.wire_list]
    fills = fill_notches(obst, R.wire_list)
    print(f"  notch fillers: {len(fills)}")
    R.wire_list = list(R.wire_list) + fills
    write_outputs(L, insts, R, mom, lib)
    preview(L, insts, R, mom, HERE / ("preview.png" if CELL == "slot_ah" else f"preview_{CELL}.png"))
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
