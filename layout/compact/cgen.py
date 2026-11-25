"""Compact slot generator (M2): row-based placement of shared-diffusion chains, P&R search scored by a trial route.

    scripts/eda.sh "cd layout/compact && CELL=slot_ah python3 cgen.py"        (then build.sh: magic / netgen / klayout)

Flow:
  1. flatten the slot (layout/slot/flatten.py), fold wide devices into parallel fingers, chain them (geom.py);
  2. frame: p-tap ring, row plan (n/p rows hanging from p-tap / n-tap strips; p rows share one n-well around their
     n-tap strip), the 12 Metal2 column lines, the Metal3 row band with its pads and straps (layout/slot/README.md);
  3. placement search: simulated annealing of chain order/row/orientation on weighted HPWL with hard penalties
     (vm out of the row band, row capacity), several seeds;
  4. trial route of the best placements in parallel (layout/slot/router.py, PathFinder on Metal1-3); the first
     clean route with the shortest wiring wins;
  5. notch fill, metal1 minimum area, paint script + LVS reference (out/<cell>_paint.tcl, out/<cell>_lvs.spice).
"""
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLOT = HERE.parent / "slot"
sys.path[:0] = [str(HERE), str(SLOT)]
import flatten                                   # noqa: E402
from geom import fold, build_chains, merge_chains, draw_chain, snap, DIFF_SP, Chain   # noqa: E402
from crouter import Router, rgap                 # noqa: E402

OUT = HERE / "out"
CELL = os.environ.get("CELL", "slot_ah")
NAME = os.environ.get("NAME", "c" + CELL)        # layout cell name while the compact cells are in development

# ============================================================================ frame (array contract)
W = 28.0
RING = 0.60
TAP = 0.60
TAP_GAP = 0.32          # tap strip edge to the diffusion edge of the row hanging from it
HEADS = 1.25            # gate heads above the diffusion (two staggered levels)
NW_ENC = 0.43           # n-well enclosure of p diffusion / n-well to n diffusion
NW_X = (0.90, W - 0.90)
COLS = [("vbp_syn", 19.05, 0.30), ("vdd", 19.85, 0.60), ("el", 20.65, 0.30), ("aux", 21.35, 0.30),
        ("vbn_leak", 22.05, 0.30), ("vsrc", 22.75, 0.30), ("vbp_st", 23.45, 0.30),
        ("vbn_prb", 24.15, 0.30), ("vbn_ref", 24.85, 0.30), ("en", 25.55, 0.30),
        ("vreset", 26.25, 0.30), ("abus", 26.95, 0.30)]
COLX = {n: x for n, x, _ in COLS}
NTRACK, TRACK_PITCH = 19, 0.56
BAND_H = round(TRACK_PITCH * (NTRACK - 1) + 0.28, 3)      # 10.36
BAND_TOP_GAP = 0.90                                       # band top below the cell top (as in the 43.5 slot)
TRACK = {"sta": 0, "stb": 1, "hold": 2, "mreset": 3, "rsel": 4, "sub": 5, "sub_b": 6, "grp_en": 8}
PINS = {"sta": 17.40, "stb": 15.30, "hold": 14.00, "mreset": 17.40, "rsel": 15.30, "sub": 14.00, "sub_b": 17.40,
        "grp_en": 10.0}
# E1 (e1_fb, MIL-362): grp_en on its own track 8; the top level drops a via2 at each pad x, so the grp_en pad keeps
# PIN_XSEP from every other row pin's x
PIN_XSEP = {"grp_en": 0.7}
STRAPS = {"spk": 16.60, "t0": 0, "t1": 0, "t2": 0, "t3": 0}      # x chosen in the strap lane (value unused)
STRAP_TRACKS = {"spk": (7, 10), "t0": (11, 18), "t1": (11, 18), "t2": (11, 18), "t3": (11, 18)}
SUPPLY = {"vdd", "vss"}

# row plan, bottom to top. ("ring"): p-tap ring edge; ("ptap"/"ntap"): tap strips; ("row", typ, dir, wmax, name):
# dir "up" hangs from the strip below, "down" from the strip above; ("chan", h): extra routing channel.
# The vm devices must sit below the Metal3 row band (no vm metal under the tracks): the cap row (membrane cap,
# vm probe follower, vm switches) and both p rows are below it; the band rows take the n devices without vm.
ROWPLAN = [("ring",), ("row", "n", "up", 4.0, "NC"), ("chan", 0.6), ("row", "p", "down", 2.0, "P0"), ("ntap",),
           ("row", "p", "up", 2.0, "P1"), ("chan", 0.6), ("row", "n", "down", 2.0, "N1"), ("ptap",),
           ("row", "n", "up", 2.0, "N2"), ("chan", 0.6), ("row", "n", "down", 2.0, "N3"), ("ring",)]
# cells with more n devices (gap-trim ladder): extra n rows on top
EXTRA_N = {"slot_ah_h": 1, "slot_ah_p": 1, "slot_cmp_h": 1}.get(CELL, int(os.environ.get("EXTRA_N", "0")))
if EXTRA_N:
    # two short rows (W <= 0.5: the ladder and the trim switches) around one more p-tap strip
    if os.environ.get("SHORT_ROWS", "low") == "top":
        ROWPLAN = ROWPLAN[:-1] + [("ptap",), ("row", "n", "up", 0.5, "N4"), ("chan", 0.6),
                                  ("row", "n", "down", 0.5, "N5"), ("ring",)]
    else:   # low (default): right above the cap row, below the Metal3-free band (Metal3 available for the ladder)
        i = ROWPLAN.index(("chan", 0.6))          # the channel above the cap row
        ROWPLAN = ROWPLAN[:i + 1] + [("row", "n", "down", 0.5, "N5"), ("ptap",), ("row", "n", "up", 0.5, "N4"),
                                     ("chan", 0.6)] + ROWPLAN[i + 1:]
# E1 (e1_fb): one short n row (W <= 0.5: switches, long-L mirror copies) on its own p-tap strip above the cap row
if (CELL == "e1_fb" and not EXTRA_N) or os.environ.get("SHORT_N") == "1":
    i = ROWPLAN.index(("chan", 0.6))
    ROWPLAN = ROWPLAN[:i + 1] + [("row", "n", "down", 0.5, "N5"), ("ptap",), ("chan", 0.6)] + ROWPLAN[i + 1:]
if os.environ.get("CHAN"):
    ROWPLAN = [("chan", float(os.environ["CHAN"])) if e[0] == "chan" else e for e in ROWPLAN]
WFOLD = {"n": 2.0, "p": 2.0}
TALL = {"XC.XC": 3.54, "XPM.XMF": 4.0}         # devices folded for the tall cap row (finger W)
# AH800 (M2 layout B): its 11.7 x 11.6 mcap_r gets its own bottom row, 2 fingers of 5.85 x 11.6 (~25 um long)
XROW_W = float(os.environ.get("XROW_W", "5.85" if CELL == "slot_ah_800" else "0"))
if XROW_W:
    TALL["XC2.XC"] = XROW_W
    ROWPLAN = ROWPLAN[:1] + [("row", "n", "up", XROW_W, "NX"), ("ptap",)] + ROWPLAN[1:]
# AH400 (MIL-127 N11): no extra row; the cap row NC grows to NC_W (7.07) so XC is one 7.07 x 7.07 finger and the
# 5.85 x 11.6 mcap_r fits beside it (~21 um of the ~26 um row)
NC_W = float(os.environ.get("NC_W", "7.07" if CELL == "slot_ah_400" else "0"))
if NC_W:
    TALL.update({"XC.XC": NC_W, "XC2.XC": NC_W})
    if os.environ.get("NC_XMF", "0") != "1":     # the probe follower leaves the cap row (folded in the n rows)
        TALL.pop("XPM.XMF")
    ROWPLAN = [("row", "n", "up", NC_W, "NC") if e[:1] == ("row",) and e[4] == "NC" else e for e in ROWPLAN]
MEMCAP = "XC.XC"
CHAIN_LEN = float(os.environ.get("CHAIN_LEN", "0"))
CHAIN_MAX = float(os.environ.get("CHAIN_MAX", "0"))   # greedy chainer length cap (0: one row width)   # 0: greedy chainer; > 0: merge chainer, max chain length
CB_W = float(os.environ.get("CB_W", "6.0"))
CONG = float(os.environ.get("CONG", "0"))       # weight of the congestion (RUDY overflow) term     # column-band escape weight (per um)
NETW = {"vm": 4.0, "vr": 2.0, "spk": 1.5}         # HPWL weights
# Cfb MOM over the membrane cap's first finger (Metal1-3 fingers, spk/vm); value tuned by PEX
MOM = dict(nf=int(os.environ.get("MOM_NF", "11")))
ROUTE_FIRST = ["vm", "vr", "spk"]


# ============================================================================ netlist, chains
# the Cfb MOM is drawn only for cells whose schematic has the spk-vm feedback cap (AH detectors; not det_cmp)
HAS_CFB = any({c["a"], c["b"]} == {"spk", "vm"} for c in flatten.flatten(CELL)[2])


# Kept-slot devices: name -> footprint L (geom.pitch). Level 4 (cells aabada4): the leak OTA inputs XM1/XM2 and diodes
# XD1/XD2 went L 1 -> 0.5 um, same W. Drawn at their old 1 um gate pitch (channel narrowed about the centre, plain
# diffusion either side), every chain keeps its width, contacts and gate pads, so the same SEED/SWEEP reproduces the
# placement and the route of the level-3 finals. KEPT_L=0 in the environment draws them packed (new search needed).
KEPT_L = {} if os.environ.get("KEPT_L") == "0" else {f"XL.{m}": 1.0 for m in ("XM1", "XM2", "XD1", "XD2")}


def netlist():
    ports, devs, caps = flatten.flatten(CELL)
    devs = [dict(d, slot=KEPT_L[d["name"]]) if KEPT_L.get(d["name"], 0) > d["L"] + 1e-9 else d for d in devs]
    fingers = []
    for d in devs:
        if d["name"] in TALL:
            fingers += fold(d, TALL[d["name"]])
        else:
            fingers += fold(d, WFOLD[d["model"][0]])
    deg = {}
    for f in fingers:
        for n in (f.d, f.g, f.s):
            deg[n] = deg.get(n, 0) + 1
    for p in ports:
        deg[p] = deg.get(p, 0) + 10
    return ports, devs, fingers, deg


def make_chains(fingers, deg):
    chains = []
    for t in "np":
        fs = [f for f in fingers if f.typ == t]
        tall = [f for f in fs if f.dev in TALL]
        rest = [f for f in fs if f.dev not in TALL]
        for grp in ([f for f in tall if f.dev == k] for k in TALL):
            if grp:
                chains += build_chains(grp, deg)
        if CHAIN_LEN > 0:       # merge-based chaining, chains capped at CHAIN_LEN um
            chains += merge_chains(rest, deg, lambda n, i: deg.get(n, 0) != 2, CHAIN_LEN)
        else:
            chains += build_chains(rest, deg, maxlen=CHAIN_MAX or (W - 2 * RING - 2 * DIFF_SP - 2.0))
    return chains


# ============================================================================ rows
def plan_rows():
    """Row geometry from ROWPLAN: returns rows (dicts), strips [(kind, y0, y1)], H, nwell boxes."""
    def rh(e):
        return TAP_GAP + max(e[3], 0.36) + HEADS
    rows, strips, y = [], [], 0.0
    plan = list(ROWPLAN)
    if os.environ.get("CHANS"):      # per-channel heights in plan order (all on the 0.005 grid), e.g. a row height
        ch = iter(float(v) for v in os.environ["CHANS"].split(","))   # between the CHAN steps: 3.87,3.875,3.875
        plan = [("chan", next(ch)) if e[0] == "chan" else e for e in plan]
    for i, e in enumerate(plan):
        k = e[0]
        if k in ("ring", "ptap", "ntap"):
            h = RING if k == "ring" else TAP
            strips.append((k, snap(y), snap(y + h)))
            y += h
        elif k == "chan":
            y += e[1]
        else:
            h = rh(e)
            if e[2] == "up":
                assert plan[i - 1][0] in ("ring", "ptap", "ntap"), e
                rows.append(dict(name=e[4], typ=e[1], dir=1, wmax=e[3], base=y + TAP_GAP, y0=y, y1=y + h))
            else:
                assert plan[i + 1][0] in ("ring", "ptap", "ntap"), e
                rows.append(dict(name=e[4], typ=e[1], dir=-1, wmax=e[3], base=y + h - TAP_GAP, y0=y, y1=y + h))
            y += h
    H = snap(y)
    for r in rows:
        for k in ("base", "y0", "y1"):
            r[k] = snap(r[k])
        if r["typ"] == "p":
            r["x0"], r["x1"] = NW_X[0] + NW_ENC, NW_X[1] - NW_ENC
        else:
            r["x0"], r["x1"] = RING + DIFF_SP, W - RING - DIFF_SP
    # n-wells: one per ntap strip, spanning the p rows hanging from it
    wells = []
    for k, y0, y1 in strips:
        if k != "ntap":
            continue
        lo, hi = y0, y1
        for r in rows:
            if r["typ"] == "p" and (abs(r["base"] - (y0 - TAP_GAP)) < 1e-6 or abs(r["base"] - (y1 + TAP_GAP)) < 1e-6):
                lo = min(lo, r["base"] - r["wmax"] - NW_ENC) if r["dir"] < 0 else lo
                hi = max(hi, r["base"] + r["wmax"] + NW_ENC) if r["dir"] > 0 else hi
        wells.append((NW_X[0], snap(lo), NW_X[1], snap(hi)))
    return rows, strips, H, wells


# ============================================================================ placement state
class Placement:
    """rows[r] = list of (chain index, mirrored)."""

    def __init__(self, chains, geo, rows, H, rng):
        self.chains, self.geo, self.rows, self.H = chains, geo, rows, H
        self.band = (snap(H - BAND_TOP_GAP - BAND_H), snap(H - BAND_TOP_GAP))
        self.rng = rng
        self.fixed = {}          # net -> list of (x or None, y or None) fixed pin points
        for n, x in COLX.items():
            self.fixed.setdefault(n, []).append((x, None))
        for n in PINS:
            self.fixed.setdefault(n, []).append((None, self.track_y(TRACK[n])))
        self.assign = [[] for _ in rows]
        self.memcap = next((i for i, ch in enumerate(chains) if any(f.dev == MEMCAP for f, _ in ch.items)), None)
        # a single-finger cap (AH50) stays west of the column band so the Cfb MOM can sit on it
        self.cap_east = self.memcap is not None and len(chains[self.memcap].items) >= 2
        # strap lane: the band straps (spk over tracks 7-10; trim bits over 11-18) run in a reserved x lane just west
        # of the column lines; chains in the rows they cross skip it
        self.straps = [n for n in STRAPS if n in PORTS]
        self.lane = None
        if self.straps:
            lx1 = snap(COLS[0][1] - COLS[0][2] / 2)
            self.strap_x = [snap(lx1 - 0.28 - 0.15 - 0.58 * k) for k in range(len(self.straps))]
            # each strap pins its net at its lane x (pulls the spike output and the trim-switch gates towards it)
            for k, n in enumerate(self.straps):
                a, b = STRAP_TRACKS[n]
                self.fixed.setdefault(n, []).append((self.strap_x[k], self.track_y((a + b) / 2)))
            lx0 = snap(self.strap_x[-1] - 0.15 - 0.62)
            y0 = min(self.track_y(STRAP_TRACKS[n][0]) for n in self.straps) - 0.7
            y1 = max(self.track_y(STRAP_TRACKS[n][1]) for n in self.straps) + 0.7
            self.lane = (lx0, lx1)
            for r in rows:
                r["lane"] = self.lane if (r["y0"] < y1 and r["y1"] > y0) else None

    def track_y(self, k):
        return snap(self.band[0] + 0.14 + TRACK_PITCH * k)

    def fits(self, ci, r):
        ch, row = self.chains[ci], self.rows[r]
        return ch.typ == row["typ"] and max(f.W for f, _ in ch.items) <= row["wmax"] + 1e-9 and \
            (all(f.dev in TALL for f, _ in ch.items) or row["wmax"] <= 2.0 + 1e-9 or True)

    def initial(self):
        order = sorted(range(len(self.chains)), key=lambda i: -self.geo[i]["width"])
        used = [0.0] * len(self.rows)
        for ci in order:
            cand = [r for r in range(len(self.rows)) if self.fits(ci, r)]
            # tall chains to the tallest-fitting row first
            cand.sort(key=lambda r: (self.rows[r]["wmax"] if any(f.dev in TALL for f, _ in self.chains[ci].items)
                                     else 0, used[r]))
            if any(f.dev in TALL for f, _ in self.chains[ci].items):
                cand.sort(key=lambda r: -self.rows[r]["wmax"])
            r = cand[0]
            self.assign[r].append((ci, False))
            used[r] += self.geo[ci]["width"] + DIFF_SP
        for a in self.assign:
            self.rng.shuffle(a)

    # positions
    def layout(self):
        """chain index -> (x, row index, mirrored)."""
        pos = {}
        self.ends = []
        for r, a in enumerate(self.assign):
            x = self.rows[r]["x0"]
            lane = self.rows[r].get("lane")
            for ci, m in a:
                if ci == self.memcap and self.cap_east:   # multi-finger cap: flush east, under the column band
                    pos[ci] = (snap(self.rows[r]["x1"] - self.geo[ci]["width"]), r, m)
                    continue
                w = self.geo[ci]["width"]
                if lane and x < lane[1] and x + w > lane[0]:
                    x = lane[1]
                pos[ci] = (x, r, m)
                x += w + DIFF_SP
            self.ends.append(x - DIFF_SP + (self.geo[self.memcap]["width"] + DIFF_SP
                                            if self.cap_east and any(ci == self.memcap for ci, _ in a) else 0))
        return pos

    def overflow(self):
        self.layout()
        return sum(max(0.0, e - self.rows[r]["x1"]) for r, e in enumerate(self.ends))

    def term_points(self, pos=None):
        pos = pos or self.layout()
        pts = {}
        for ci, (x, r, m) in pos.items():
            g, row = self.geo[ci], self.rows[r]
            for net, lay, rc in g["terms"]:
                cx, cy = (rc[0] + rc[2]) / 2, (rc[1] + rc[3]) / 2
                if m:
                    cx = g["width"] - cx
                pts.setdefault(net, []).append((x + cx, row["base"] + row["dir"] * cy))
        return pts

    def cost(self):
        pos = self.layout()
        pts = self.term_points(pos)
        c = 0.0
        for net, ps in pts.items():
            if net in SUPPLY:
                continue
            xs = [p[0] for p in ps] + [f[0] for f in self.fixed.get(net, []) if f[0] is not None]
            ys = [p[1] for p in ps] + [f[1] for f in self.fixed.get(net, []) if f[1] is not None]
            c += NETW.get(net, 1.0) * ((max(xs) - min(xs)) + (max(ys) - min(ys)))
            if net == "vm":
                c += 2000.0 * sum(1 for p in ps if p[1] > self.band[0] - 0.6)
        # terminals under the Metal2 column band can only escape on Metal1 (or via1 straight onto their own column
        # line): cost them by their Metal1 escape length to the band's west edge
        cb0 = COLS[0][1] - 0.75
        for net, ps in pts.items():
            if net in SUPPLY:
                continue
            for x, y in ps:
                if x > cb0 and not (net in COLX and abs(x - COLX[net]) < 0.3):
                    c += CB_W * (x - cb0)
        # supply S/D in a row of the other supply must be routed: mild penalty
        if self.memcap is not None and not self.cap_east:
            x, r, m = pos[self.memcap]
            c += 200.0 * max(0.0, x + self.geo[self.memcap]["width"] - (COLS[0][1] - 0.9))
        c += 400.0 * self.overflow()
        if CONG > 0:
            c += CONG * self.congestion(pts)
        return c

    def congestion(self, pts, BIN=2.0):
        """RUDY-style routing overflow: each signal net's bbox spreads 1/h horizontal and 1/w vertical tracks over
        its area; capacity per um: Metal3 (horizontal) only below the row band, Metal2 (vertical) only west of the
        column lines, plus a little Metal1 everywhere."""
        nx, ny = int(math.ceil(W / BIN)), int(math.ceil(self.H / BIN))
        dh = [[0.0] * nx for _ in range(ny)]
        dv = [[0.0] * nx for _ in range(ny)]
        for net, ps in pts.items():
            if net in SUPPLY or len(ps) < 2:
                continue
            xs = [p[0] for p in ps]
            ys = [p[1] for p in ps]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            w, h = max(x1 - x0, 0.6), max(y1 - y0, 0.6)
            for j in range(int(y0 // BIN), min(ny, int(y1 // BIN) + 1)):
                fy = (min(y1 + 0.3, (j + 1) * BIN) - max(y0 - 0.3, j * BIN)) / BIN
                for i in range(int(x0 // BIN), min(nx, int(x1 // BIN) + 1)):
                    fx = (min(x1 + 0.3, (i + 1) * BIN) - max(x0 - 0.3, i * BIN)) / BIN
                    f = max(0.0, fx) * max(0.0, fy)
                    dh[j][i] += f * BIN / h
                    dv[j][i] += f * BIN / w
        ov = 0.0
        cb = COLS[0][1] - 0.3
        for j in range(ny):
            yc = (j + 0.5) * BIN
            ch = BIN * (0.4 + (1.0 / 0.56 if yc < self.band[0] - 0.3 else 0.0))
            for i in range(nx):
                cv = BIN * (0.4 + (1.0 / 0.56 if (i + 0.5) * BIN < cb else 0.0))
                ov += max(0.0, dh[j][i] - ch * 0.5) + max(0.0, dv[j][i] - cv * 0.5)
        return ov

    def move(self):
        """Random move; returns an undo closure."""
        R = len(self.assign)
        k = self.rng.random()
        if k < 0.35:                       # swap two chains
            r1, r2 = self.rng.randrange(R), self.rng.randrange(R)
            if not self.assign[r1] or not self.assign[r2]:
                return None
            i1, i2 = self.rng.randrange(len(self.assign[r1])), self.rng.randrange(len(self.assign[r2]))
            c1, c2 = self.assign[r1][i1], self.assign[r2][i2]
            if r1 != r2 and not (self.fits(c1[0], r2) and self.fits(c2[0], r1)):
                return None
            self.assign[r1][i1], self.assign[r2][i2] = c2, c1

            def undo():
                self.assign[r1][i1], self.assign[r2][i2] = c1, c2
            return undo
        if k < 0.65:                       # move a chain to another row / position
            r1 = self.rng.randrange(R)
            if not self.assign[r1]:
                return None
            i1 = self.rng.randrange(len(self.assign[r1]))
            c1 = self.assign[r1][i1]
            r2 = self.rng.randrange(R)
            if not self.fits(c1[0], r2):
                return None
            del self.assign[r1][i1]
            i2 = self.rng.randrange(len(self.assign[r2]) + 1)
            self.assign[r2].insert(i2, c1)

            def undo():
                del self.assign[r2][i2]
                self.assign[r1].insert(i1, c1)
            return undo
        r1 = self.rng.randrange(R)         # mirror a chain
        if not self.assign[r1]:
            return None
        i1 = self.rng.randrange(len(self.assign[r1]))
        c1 = self.assign[r1][i1]
        self.assign[r1][i1] = (c1[0], not c1[1])

        def undo():
            self.assign[r1][i1] = c1
        return undo

    def anneal(self, steps=30000, t0=20.0, t1=0.05):
        cur = self.cost()
        best, best_a = cur, [list(a) for a in self.assign]
        for s in range(steps):
            T = t0 * (t1 / t0) ** (s / steps)
            u = self.move()
            if u is None:
                continue
            c = self.cost()
            if c <= cur or self.rng.random() < math.exp((cur - c) / T):
                cur = c
                if c < best:
                    best, best_a = c, [list(a) for a in self.assign]
            else:
                u()
        self.assign = best_a
        return best


# ============================================================================ geometry
class Geo:
    def __init__(self):
        self.paint = []           # (layer, rect)
        self.obst = []            # (router layer, rect, net)
        self.terms = {}           # net -> [ [(layer, rect)], ... ]
        self.labels = []          # (text, layer, rect, use)

    def p(self, layer, r, net=None, rl=None):
        r = tuple(snap(v) for v in r)
        self.paint.append((layer, r))
        if rl:
            self.obst.append((rl, r, net))
        return r

    def term(self, net, shapes):
        self.terms.setdefault(net, []).append(shapes)


def via1(G, x, y, net, w=0.4):
    pad = (x - w / 2, y - 0.2, x + w / 2, y + 0.2)
    G.p("metal1", pad, net, "m1")
    G.p("metal2", pad, net, "m2")
    G.p("via1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net, "v1")


def build_geometry(pl):
    rows, H = pl.rows, pl.H
    _, strips, _, wells = plan_rows()
    G = Geo()
    pl.termxy = {}
    pos = pl.layout()
    capbox = None
    # ------------------------------------------------ chains
    for ci, (x, r, m) in pos.items():
        g, row = pl.geo[ci], rows[r]
        base, d = row["base"], row["dir"]

        def tf(rc):
            x0, x1 = (g["width"] - rc[2], g["width"] - rc[0]) if m else (rc[0], rc[2])
            y0, y1 = (base + rc[1], base + rc[3]) if d > 0 else (base - rc[3], base - rc[1])
            return (x + x0, y0, x + x1, y1)
        for lay, rc in g["shapes"]:
            G.p(lay, tf(rc))
        for net, lay, rc in g["terms"]:
            R = tf(rc)
            G.obst.append(("m1", tuple(snap(v) for v in R), net))
            G.term(net, [("m1", tuple(snap(v) for v in R))])
            pl.termxy.setdefault(net, []).append(R)
            # supply contact in a row hanging from the same supply: metal1 stub straight to the strip
            rail_net = "vss" if row["typ"] == "n" else "vdd"
            is_gate = rc[3] - rc[1] < 0.39 and abs((rc[2] - rc[0]) - 0.38) < 1e-6
            if net == rail_net and not is_gate:
                rail = base - d * TAP_GAP
                stub = (R[0], min(R[1], rail), R[2], max(R[3], rail)) if d > 0 else (R[0], min(R[1], rail), R[2], max(R[3], rail))
                G.p("metal1", stub, net, "m1")
        if any(f.dev == MEMCAP for f, _ in pl.chains[ci].items):
            gx = [tf((x0, 0, x1, f.W)) for (f, x0, x1) in g["gates"]]
            capbox = (min(b[0] for b in gx), min(b[1] for b in gx), max(b[2] for b in gx), max(b[3] for b in gx))
            G.capgates = sorted(gx)
    # ------------------------------------------------ ring, strips, wells
    ring = [(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]
    c = (RING - 0.23) / 2
    for i, rr in enumerate(ring):
        G.p("psubdiff", rr)
        G.p("metal1", rr, "vss", "m1")
        G.term("vss", [("m1", rr)])
        if i < 2:
            G.p("psubdiffcont", (rr[0] + c, rr[1] + c, rr[2] - c, rr[3] - c))
        else:
            G.p("psubdiffcont", (rr[0] + c, rr[1] + c + 0.1, rr[2] - c, rr[3] - c - 0.1))
    G.labels.append(("vss", "metal1", (2.0, 0.1, 3.0, 0.5), "ground"))
    for k, y0, y1 in strips:
        if k == "ptap":
            rr = (0, y0, W, y1)
            G.p("psubdiff", rr)
            G.p("metal1", rr, "vss", "m1")
            G.term("vss", [("m1", rr)])
            G.p("psubdiffcont", (RING + 0.2, y0 + c, W - RING - 0.2, y1 - c))
        elif k == "ntap":
            rr = (NW_X[0] + 0.12, y0, NW_X[1] - 0.12, y1)
            G.p("nsubdiff", rr)
            G.p("metal1", rr, "vdd", "m1")
            G.term("vdd", [("m1", rr)])
            G.p("nsubdiffcont", (rr[0] + c, y0 + c, rr[2] - c, y1 - c))
            via1(G, COLX["vdd"], (y0 + y1) / 2, "vdd", w=0.6)
    for wb in wells:
        G.p("nwell", wb)
    # ------------------------------------------------ column lines, band pads, straps
    for net, x, w in COLS:
        rr = (x - w / 2, 0, x + w / 2, H)
        G.p("metal2", rr, net, "m2")
        G.term(net, [("m2", rr)])
        G.labels.append((net, "metal2", (rr[0], H - 0.6, rr[2], H - 0.2), "power" if net == "vdd" else "signal"))
    ports = set(PORTS)
    # band pads / straps: x chosen here (free per variant; the top-level row router reads the labels). A pin may
    # not cover another net's contact (it would block that contact's via1), keeps the Metal2 spacing to the
    # others' via pads, and stays west of the column band; nearest to its own net's terminals wins.
    mterms = [(n, r) for n, ts in G.terms.items() for t in ts for l, r in t if l == "m1" and r[2] - r[0] < 1.0]
    placed = []

    def free(rr, net):
        for n, r in mterms:
            if n == net:
                continue
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            vp = (cx - 0.2, max(r[1], cy - 0.2), cx + 0.2, min(r[3], cy + 0.2))      # its via1 M2 pad
            if rgap(rr, (vp[0], r[1] - 0.2 if r[3] - r[1] < 0.4 else r[1], vp[2], r[3] + 0.2 if r[3] - r[1] < 0.4 else r[3])) < 0.28:
                return False
        return all(rgap(rr, q) >= 0.28 for q in placed)

    def pick(net, mk):
        own = [((r[0] + r[2]) / 2) for n, r in mterms if n == net] or [9.0]
        tgt = sum(own) / len(own)
        sep = PIN_XSEP.get(net, 0.0)
        for x in sorted((snap(1.0 + 0.05 * k) for k in range(int((COLS[0][1] - 1.8) / 0.05))),
                        key=lambda x: abs(x - tgt)):
            rr = mk(x)
            if sep and any(abs(x - qx) < sep for qx in [(q[0] + q[2]) / 2 for q in placed] + list(pl.strap_x if pl.straps else [])):
                continue
            if free(rr, net):
                return rr
        raise RuntimeError(f"no free spot for pin {net}")
    for net in PINS:
        if net not in ports:
            continue
        y = pl.track_y(TRACK[net])
        rr = pick(net, lambda x: (x - 0.2, y - 0.2, x + 0.2, y + 0.2))
        placed.append(rr)
        G.p("metal2", rr, net, "m2")
        G.term(net, [("m2", rr)])
        G.labels.append((net, "metal2", rr, "signal"))
    for k, net in enumerate(pl.straps):
        a, b = STRAP_TRACKS[net]
        y0, y1 = snap(pl.track_y(a) - 0.2), snap(pl.track_y(b) + 0.2)
        x = pl.strap_x[k]
        rr = (x - 0.15, y0, x + 0.15, y1)
        placed.append(rr)
        G.p("metal2", rr, net, "m2")
        G.term(net, [("m2", rr)])
        G.labels.append((net, "metal2", (rr[0], rr[3] - 0.5, rr[2], rr[3] - 0.2), "signal"))
    # ------------------------------------------------ MOM Cfb over the membrane cap's first finger
    G.capbox, G.mom = capbox, None
    if capbox and HAS_CFB and MOM["nf"]:
        gb = G.capgates[0]
        G.mom = mom_cap(G, gb)
    # Metal1 vss shield over the cap gate under the Metal2 column lines (no bias/switching line couples to vm),
    # covering the vss contact stripes beside the gate, clear of the MOM
    if capbox:
        for b in G.capgates:
            x0 = max(b[0], COLS[0][1] - 0.6)
            if G.mom and G.mom["box"][2] > b[0]:
                x0 = max(x0, G.mom["box"][2] + 0.3)
            if x0 < b[2] - 0.5:
                G.p("metal1", (x0 - 0.375 if x0 == b[0] else x0, b[1], b[2] + 0.375, b[3]), "vss", "m1")
    # static short check: no two nets' drawn metal may touch (DRC cannot see a same-layer short)
    sh = [(l, r, n) for l, r, n in G.obst if l in ("m1", "m2", "m3") and n]
    for i, (l, r, n) in enumerate(sh):
        for l2, r2, n2 in sh[:i]:
            if l == l2 and n != n2 and r[0] <= r2[2] and r2[0] <= r[2] and r[1] <= r2[3] and r2[1] <= r[3]:
                raise RuntimeError(f"static short {l} {n}/{n2} at {r} {r2}")
    return G


def mom_cap(G, gb):
    """Interdigitated Metal1-3 fingers over the cap gate box gb (spk bottom bar, vm top bar), clear of the vss
    contact stripes and of the first Metal2 column line.
    MOM_STYLE=gate (default, routes clean): inside the gate, 0.25 um margins, pitch 0.58 (Cfb 5.0 fF in PEX).
    MOM_STYLE=tall: from the rail spacing below the gate to the gate top, pitch 0.56 (more Cfb, harder to route);
    MOM_STYLE=head: tall + through the cap's head zone (top bar vm, as the head pad)."""
    style = os.environ.get("MOM_STYLE", "gate")
    if style == "gate":
        nf, pitch, fw, bar = MOM["nf"], 0.58, 0.30, 0.50
        width = (nf - 1) * pitch + fw
        x0 = snap((gb[0] + gb[2]) / 2 - width / 2)
        y0, y1 = snap(gb[1] + 0.25), snap(gb[3] - 0.25)
    else:
        pitch, fw, bar = 0.56, 0.28, 0.40
        xa = gb[0] + 0.1
        xb = min(gb[2] - 0.1, COLS[0][1] - COLS[0][2] / 2 - 0.28)
        nf = int((xb - xa - fw) / pitch) + 1
        width = (nf - 1) * pitch + fw
        x0 = snap(xb - width)
        y0 = snap(gb[1] - TAP_GAP + 0.23)
        y1 = snap(gb[3] + (0.45 + 0.19 if style == "head" else 0.0))
    gapf = 0.30
    bot = (x0, y0, x0 + width, y0 + bar)
    top = (x0, y1 - bar, x0 + width, y1)
    shapes = {"spk": [bot], "vm": [top]}
    for k in range(nf):
        fx = x0 + k * pitch
        if k % 2 == 0:
            shapes["spk"].append((fx, bot[3], fx + fw, top[1] - gapf))
        else:
            shapes["vm"].append((fx, bot[3] + gapf, fx + fw, top[1]))
    for net, rs in shapes.items():
        for rr in rs:
            for lay, rl in (("metal1", "m1"), ("metal2", "m2"), ("metal3", "m3")):
                G.p(lay, rr, net, rl)
        b = rs[0]
        nv = int((b[2] - b[0] - 0.1) // 0.6)
        vy = (b[1] + b[3]) / 2
        for k in range(nv):
            vx = b[0] + 0.30 + k * 0.6
            if vx + 0.14 > b[2] - 0.06:
                break
            G.p("via1", (vx - 0.13, vy - 0.13, vx + 0.13, vy + 0.13), net, "v1")
            G.p("via2", (vx - 0.14, vy - 0.14, vx + 0.14, vy + 0.14), net, "v2")
        G.term(net, [("m1", b), ("m2", b)])
    return dict(box=(x0, y0, x0 + width, y1), shapes=shapes)


# ============================================================================ routing
def make_grid(G, H, base=0.56):
    req_x, req_y = set(), set()
    for net, terms in G.terms.items():
        for t in terms:
            for lay, r in t:
                if r[2] - r[0] < 1.0:
                    req_x.add(snap((r[0] + r[2]) / 2))
                if r[3] - r[1] < 1.0:
                    req_y.add(snap((r[1] + r[3]) / 2))
    for _, x, _ in COLS:
        req_x.add(x)

    def merge(req, lo, hi):
        req = sorted(v for v in req if lo <= v <= hi)
        out = list(req)
        v = lo
        while v <= hi + 1e-9:
            if all(abs(v - q) >= base * 0.5 for q in req):
                out.append(snap(v))
            v += base
        return sorted(set(out))
    return merge(req_x, 0.30, W - 0.30), merge(req_y, 0.30, H - 0.30)


def add_forbids(R, G, pl):
    H, band = pl.H, pl.band
    # Metal3: never in or next to the row band, never near the cell edge
    R.add_forbid(("m3",), (0, band[0] - 0.3, W, H))
    for rr in ((0, 0, W, 0.3), (0, 0, 0.3, H), (W - 0.3, 0, W, H)):
        R.add_forbid(("m3",), rr)
    # vm stays out of the band (no vm metal under any track)
    R.add_forbid(("m1", "m2"), (0, band[0] - 0.3, W, H), only={"vm"})
    # membrane cap: only vm / vss (and the MOM's spk) over its gate
    if G.capbox:
        b = G.capbox
        R.add_forbid(("m1", "m2", "m3"), (b[0] - 0.3, b[1] - 0.3, b[2] + 0.3, b[3] + 0.3), allowed={"vm", "vss", "spk"})
    if G.mom:
        R.add_forbid(("m1", "m2", "m3"), G.mom["box"], allowed={"vm", "spk"})
    for rr in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        R.add_forbid(("m1",), rr, allowed={"vss"})
    for rr in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        R.add_forbid(("m2",), rr)


SCHEDULES = [(1.3, 0.5), (1.6, 0.3), (1.2, 0.7)]
MAXEXP = int(os.environ.get("MAXEXP", "80000"))


class CRouter(Router):
    """router.Router with a smaller A* expansion cap (blocked terminals fail fast in the trial routes)."""
    def route_net(self, net, terminals, max_expand=None):
        return super().route_net(net, terminals, max_expand or MAXEXP)


def touch(a, b):
    return a[0] <= b[2] + 1e-6 and b[0] <= a[2] + 1e-6 and a[1] <= b[3] + 1e-6 and b[1] <= a[3] + 1e-6


def merge_terms(G):
    """Merge the terminals of a net that its drawn metal already connects (supply stubs to the rails, the rails and
    the ring, via stacks): the router then only joins the separate groups."""
    cut = {"v1": ("m1", "m2"), "v2": ("m2", "m3")}
    out = {}
    for net, terms in G.terms.items():
        shapes = [(l, r) for l, r, n in G.obst if n == net]
        for t in terms:
            shapes += t
        par = list(range(len(shapes)))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i, (li, ri) in enumerate(shapes):
            for j in range(i):
                lj, rj = shapes[j]
                if not touch(ri, rj):
                    continue
                if li == lj or (li in cut and lj in cut[li]) or (lj in cut and li in cut[lj]):
                    par[find(i)] = find(j)
        groups = {}
        for t in terms:
            k = find(shapes.index(t[0]))
            groups.setdefault(k, []).extend(t)
        out[net] = list(groups.values())
    return out


def route(G, pl, iters=40, schedules=SCHEDULES, log=print):
    xs, ys = make_grid(G, pl.H)

    def nodes(shapes):
        out = set()
        for lay, r in shapes:
            ii = [i for i, x in enumerate(xs) if r[0] - 1e-6 <= x <= r[2] + 1e-6]
            jj = [j for j, y in enumerate(ys) if r[1] - 1e-6 <= y <= r[3] + 1e-6]
            out |= {(lay, i, j) for i in ii for j in jj}
        return out
    nets = {}
    for net, terms in merge_terms(G).items():
        tn = [nodes(t) for t in terms]
        if any(not t for t in tn):
            log(f"  !! {net}: terminal without a grid node")
        nets[net] = [t for t in tn if t]
    order = [n for n in ROUTE_FIRST if n in nets]
    order += sorted((n for n in nets if n not in order and n not in SUPPLY), key=lambda n: (n.count(".") == 0, n))
    order += [n for n in ("vdd", "vss") if n in nets]
    best = None
    for k, (pm, hs) in enumerate(schedules):
        R = CRouter(xs, ys, layers=("m1", "m2", "m3"), hw=0.14)
        for lay, r, net in G.obst:
            R.add_shape(lay, r, net)
        add_forbids(R, G, pl)
        unrouted, bad = R.route_all(nets, order, iters=iters, pres_mult=pm, hist_step=hs, log=log)
        failed = sorted(unrouted | bad)
        wl = sum((r[2] - r[0]) + (r[3] - r[1]) for l, r, n in R.wires() if l in ("m1", "m2", "m3"))
        if best is None or (len(failed), wl) < (len(best[1]), best[2]):
            best = (R, failed, wl)
        if not failed:
            break
    R, failed, wl = best
    R.wire_list = R.wires()
    return R, failed, wl


# ============================================================================ search
PORTS = []


def place_one(seed, steps):
    ports, devs, fingers, deg = netlist()
    PORTS[:] = ports
    chains = make_chains(fingers, deg)
    contacted = lambda net, i: deg.get(net, 0) != 2
    geo = [draw_chain(ch, contacted) for ch in chains]
    rows, strips, H, wells = plan_rows()
    pl = Placement(chains, geo, rows, H, random.Random(seed))
    pl.initial()
    c = pl.anneal(steps)
    return pl, c


def set_params(params):
    """Search knobs per trial: CB_W (column-band escape weight), CHAN (routing channel height), NETW_vm ..."""
    global ROWPLAN, CB_W, CHAIN_LEN, CONG, CHAIN_MAX
    for k, v in (params or {}).items():
        if k == "CHAIN_MAX":
            CHAIN_MAX = v
        elif k == "CONG":
            CONG = v
        elif k == "CHAIN_LEN":
            CHAIN_LEN = v
        elif k == "CHAN":
            ROWPLAN = [("chan", v) if e[0] == "chan" else e for e in ROWPLAN]
        elif k == "CB_W":
            CB_W = v
        else:
            raise KeyError(k)


def trial(args):
    try:
        return _trial(args)
    except Exception as e:          # a failed trial never stops the search
        return dict(seed=args[0], params=args[3], cost=0, failed=[f"error: {e}"], wl=0, t=0)


def _trial(args):
    seed, steps, iters, params = args
    set_params(params)
    t0 = time.time()
    pl, c = place_one(seed, steps)
    if pl.overflow() > 0:
        return dict(seed=seed, params=params, cost=c, failed=["overflow"], wl=0, t=time.time() - t0)
    G = build_geometry(pl)
    import access
    blocked = access.check(pl, G, verbose=False)
    if not blocked:
        import solo
        blocked = solo.check(pl, G)
    if blocked:
        return dict(seed=seed, params=params, cost=c, failed=["blocked:" + b[0] for b in blocked], wl=0,
                    t=time.time() - t0)
    logs = []
    R, failed, wl = route(G, pl, iters=iters, schedules=SCHEDULES[:1], log=logs.append)
    return dict(seed=seed, params=params, cost=c, failed=failed, wl=wl, t=time.time() - t0, H=pl.H)


def sweep():
    """SWEEP="CB_W=2,4,6;CHAN=0.6,1.0" -> list of parameter dicts (cartesian product)."""
    import itertools
    spec = os.environ.get("SWEEP", "")
    if not spec:
        return [{}]
    keys, vals = [], []
    for part in spec.split(";"):
        k, v = part.split("=")
        keys.append(k)
        vals.append([float(x) for x in v.split(",")])
    return [dict(zip(keys, combo)) for combo in itertools.product(*vals)]


def search(nseeds, steps, iters, jobs):
    s0 = int(os.environ.get("SEED0", "0"))
    tasks = [(s, steps, iters, p) for p in sweep() for s in range(s0, s0 + nseeds)]
    res = []
    with Pool(jobs) as pool:
        for r in pool.imap_unordered(trial, tasks):
            res.append(r)
            print(f"  done seed {r['seed']:3d} {r['params']}  failed {len(r['failed']):2d}  wl {r['wl']:7.1f}  "
                  f"{r['t']:5.0f} s", flush=True)
    res.sort(key=lambda r: (len(r["failed"]), r.get("H", 99), r["wl"], r["cost"]))
    for r in res:
        print(f"seed {r['seed']:3d} {r['params']}  H {r.get('H', 0):6.2f}  cost {r['cost']:8.1f}  "
              f"failed {len(r['failed']):2d} {r['failed'][:6]}  wl {r['wl']:7.1f}  {r['t']:6.0f} s")
    json.dump(res, open(OUT / f"{NAME}_search.json", "w"))
    return res


# ============================================================================ outputs
def write_outputs(G, R, pl, lvs_ports):
    from slotgen_fill import fill_notches, fix_min_area
    wires = [(l, r, n) for l, r, n in R.wire_list]
    fills = fill_notches(G.obst, wires)
    lay = {"m1": "metal1", "m2": "metal2", "v1": "via1", "m3": "metal3", "v2": "via2"}
    allp = list(G.paint) + [(lay[l], r) for l, r, n in wires] + [(lay[l], r) for l, r, n in fills]
    allp += [(lay[l], r) for l, r in fix_min_area(G.obst + wires + fills)]
    order = ["nwell", "psubdiff", "nsubdiff", "ndiff", "pdiff", "nmos", "pmos", "polysilicon", "ndiffc", "pdiffc",
             "psubdiffcont", "nsubdiffcont", "polycontact", "metal1", "via1", "metal2", "via2", "metal3"]
    tcl = ["# generated by layout/compact/cgen.py -- do not edit", "tech unlock *", f"load {NAME}"]
    for layer in order:
        for l, r in allp:
            if l == layer:
                tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
    k = 1
    labels = list(G.labels)
    if "vm" in lvs_ports:       # vm port on the membrane cap's gate pad
        pads = [t[0][1] for t in G.terms["vm"] if abs((t[0][1][2] - t[0][1][0]) - 0.38) < 1e-6]
        labels.append(("vm", "metal1", pads[0], "signal"))
    for text, layer, r, use in labels:
        tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
        tcl.append(f"label {text} FreeSans 0.25um 0 0 0 c {layer}")
        if use:
            tcl.append(f"port make {k}; port use {use}; port class bidirectional")
            k += 1
    tcl.append(f"box values 0um 0um {W}um {pl.H}um")
    tcl.append(f"save {NAME}")
    (OUT / f"{NAME}_paint.tcl").write_text("\n".join(tcl) + "\n")
    # LVS reference (unfolded devices; netgen merges the parallel fingers), renamed to the layout cell
    ref = OUT / f"{NAME}_lvs.spice"
    flatten.write_lvs(ref, CELL)
    ref.write_text(ref.read_text().replace(f".subckt {CELL} ", f".subckt {NAME} ").replace(f".ends {CELL}", f".ends {NAME}"))


def preview(G, R, pl, path, marks=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(9, 9 * pl.H / W))
    col = {"nwell": ("#cfe8cf", 0.6), "psubdiff": ("#e8c070", 0.7), "nsubdiff": ("#70c0e8", 0.7),
           "ndiff": ("#40a040", 0.6), "pdiff": ("#a08040", 0.6), "nmos": ("#c03030", 0.6), "pmos": ("#c03030", 0.6),
           "polysilicon": ("#d04040", 0.5), "metal1": ("#3050d0", 0.35), "metal2": ("#d020d0", 0.35),
           "metal3": ("#20a020", 0.35)}
    lay = {"m1": "metal1", "m2": "metal2", "m3": "metal3"}
    for l, r in list(G.paint) + [(lay.get(l, l), r) for l, r, n in R.wire_list]:
        if l in col:
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
    ax.add_patch(Rectangle((0, pl.band[0]), W, pl.band[1] - pl.band[0], fill=False, ec="green", ls="--"))
    for r in marks:
        ax.add_patch(Rectangle((r[0] - 0.3, r[1] - 0.3), r[2] - r[0] + 0.6, r[3] - r[1] + 0.6, fill=False, ec="red", lw=1))
    ax.set_xlim(-0.5, W + 0.5)
    ax.set_ylim(-0.5, pl.H + 0.5)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=150, bbox_inches="tight")


def main():
    OUT.mkdir(exist_ok=True)
    nseeds = int(os.environ.get("SEEDS", "8"))
    steps = int(os.environ.get("STEPS", "30000"))
    iters = int(os.environ.get("ITERS", "30"))
    jobs = min(int(os.environ.get("JOBS", "4")), int(os.environ.get("MAX_LOCAL_JOBS", "4")) if not os.environ.get("ON_BOAT") else 64)
    rows, strips, H, wells = plan_rows()
    print(f"{CELL} -> {NAME}: W {W} H {H}  rows {[r['name'] for r in rows]}")
    if "place" in sys.argv:          # placement only (no routing): cost and overflow per seed
        for s in range(nseeds):
            pl, c = place_one(s, steps)
            print(f"seed {s} cost {c:.1f} overflow {pl.overflow():.2f}")
        return 0
    if "noroute" in sys.argv:        # frame + placed devices only (DRC check of the placement geometry)
        pl, c = place_one(int(os.environ.get("SEED", "0")), steps)
        G = build_geometry(pl)

        class _R:
            wire_list = []
        write_outputs(G, _R, pl, PORTS)
        preview(G, _R, pl, OUT / f"{NAME}_preview.png")
        return 0
    if "trial" in sys.argv:          # one placement, one routing schedule, preview with wires
        seed = int(os.environ.get("SEED", "0"))
        set_params(sweep()[0])
        pl, c = place_one(seed, steps)
        G = build_geometry(pl)
        t0 = time.time()
        R, failed, wl = route(G, pl, iters=iters, schedules=SCHEDULES[:1])
        print(f"TRIAL seed {seed} H {pl.H} failed {len(failed)} {failed} wl {wl:.1f} {time.time() - t0:.0f} s")
        json.dump(dict(H=pl.H, band=pl.band, paint=G.paint, wires=R.wire_list, failed=failed,
                       conflicts=[c[:3] + (c[3],) for c in R.conflict_list()]),
                  open(OUT / f"{NAME}_trial{seed}.json", "w"))
        try:
            preview(G, R, pl, OUT / f"{NAME}_trial{seed}.png")
        except ImportError:
            print("no matplotlib: render with  python3 cgen.py render out/<name>_trial<seed>.json  in the container")
        return 0
    if "render" in sys.argv:         # preview of a saved trial (in the container, which has matplotlib)
        d = json.load(open(sys.argv[-1]))

        class _P:
            H, band = d["H"], d["band"]

        class _G:
            paint = [(l, tuple(r)) for l, r in d["paint"]]

        class _R:
            wire_list = [(l, tuple(r), n) for l, r, n in d["wires"]]
        preview(_G, _R, _P, Path(sys.argv[-1]).with_suffix(".png"), marks=[c[3] for c in d["conflicts"]])
        return 0
    if "final" in sys.argv:         # skip the search: SEED and SWEEP (one value per knob) give the placement
        best = dict(seed=int(os.environ.get("SEED", "0")), params=sweep()[0])
    else:
        res = search(nseeds, steps, iters, jobs)
        if "searchonly" in sys.argv:
            return 0
        best = res[0]
    # final: re-place the winning seed and route with all schedules and more iterations
    set_params(best["params"])
    pl, c = place_one(best["seed"], steps)
    G = build_geometry(pl)
    R, failed, wl = route(G, pl, iters=int(os.environ.get("FINAL_ITERS", "60")))
    print(f"FINAL seed {best['seed']} failed {failed} wl {wl:.1f}")
    for cf in R.conflict_list():
        print("  CONFLICT", cf)
    write_outputs(G, R, pl, PORTS)
    preview(G, R, pl, OUT / f"{NAME}_preview.png")
    json.dump(dict(seed=best["seed"], params=best["params"], H=pl.H, failed=failed, wl=wl, assign=pl.assign), open(OUT / f"{NAME}_place.json", "w"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
