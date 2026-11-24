"""Tile floorplan v2 for tt_um_basilwright0_analog_neurons (TTGF26c analog 1x2, gf180mcuD).

Single source of truth for block boxes, channels, power stripes, std-cell rows and the neuron-array slot map.
Used by layout/top (assembly), rtl/librelane/mkpins.py (macro pins) and test/regmap.py (slot table).
Run:  python floorplan/floorplan.py      (plain Python 3, no dependencies)
Writes docs/floorplan.svg and prints an area table plus geometry checks. Exit code 1 on any failure.
All units are microns, origin at the tile's lower-left corner. Frozen design: docs/08 Updated Plan.md section 10.
v2 (2026-11-19/20): boxes from the measured block frames (B1 rev C notched frame, R1 corner, D1 70 x 104,
AdEx 38 x 70, control macro rev E 166 x 166, slots 28 x 43.5, trim_tau4 37 x 11.8).
2026-11-20: CMP double slot (28 x 87 at column 3, rows 0-1; the dummy slot is gone), see DOUBLE below.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TILE_W, TILE_H = 346.64, 325.36          # mag/tt_analog_1x2.def DIEAREA
STRIPE_Y = (5.0, 320.36)                 # mag/init_project.tcl: every power port runs the full height
MIN_GAP = 2.0                            # block-to-block clearance unless the pair is declared abutting

# --------------------------------------------------------------------- tile pins (DEF, centres)
TOP_Y = 324.86
def _row(names, x0, pitch=-7.28):
    return {n: round(x0 + i * pitch, 2) for i, n in enumerate(names)}
PINS_TOP = {}                            # Metal4, 0.6 wide, y 324.36-325.36
PINS_TOP.update(_row([f"uio_oe[{i}]" for i in range(8)], 83.72))
PINS_TOP.update(_row([f"uio_out[{i}]" for i in range(8)], 141.96))
PINS_TOP.update(_row([f"uo_out[{i}]" for i in range(8)], 200.20))
PINS_TOP.update(_row([f"uio_in[{i}]" for i in range(8)], 258.44))
PINS_TOP.update(_row([f"ui_in[{i}]" for i in range(8)], 316.68))
PINS_TOP.update({"rst_n": 323.96, "clk": 331.24, "ena": 338.52})
PINS_BOT = {f"ua[{i}]": round(327.32 - 43.68 * i, 2) for i in range(8)}   # Metal4, 6 wide, y 0-1
ANALOG_USED = ("ua[0]", "ua[1]")

# --------------------------------------------------------------------- control macro (rev E, run revE2_166)
MACRO_X, MACRO_Y, MACRO_S = 170.0, 151.0, 166.0
MACRO_STRAPS = [(15.92, "VDD"), (19.22, "VSS"), (65.92, "VDD"), (69.22, "VSS"),
                (115.92, "VDD"), (119.22, "VSS")]                      # LEF, Metal4, 1.6 wide
EXTENDED_STRAP_PAIRS = (0, 2)            # macro strap pairs extended full height as tile power stripes

# --------------------------------------------------------------------- blocks (x0, y0, x1, y1)
# B1 is notched: its frame is the box minus B1_NOTCHES (R1 corner N1, bottom pocket NB).
# M3 (MIL-133, b1d/b1int): bias_b1 242 x 114.5 at (103, 12); the west trim removed notch N2 (tau col 2) and
# frees tile x 80-103 (RESERVED "RW"); pocket NB (local x 131-159, y 0-40) is empty in the GDS (RESERVED "RB").
# R2 (MIL-344, branch r2-b1-pack): C4 removed, bias_b1 214 x 114.5 at (131, 12); NB is gone, R1/N1, the corridor and
# the east group keep their tile positions.  Tile x 80-129, y 12-116 is one free bay (RESERVED "RW").
B1_BOX = (131.0, 12.0, 345.0, 126.5)                                  # bias_b1 214 x 114.5 at (131, 12)
B1_NOTCHES = {"R1": (262.0, 12.0, 302.0, 54.0)}
B1_CORRIDOR = (276.0, 54.0, 302.0, 55.5)    # R2: Metal3-free strip in B1 for the R1 jogs (feed-throughs are Metal4)
BLOCKS = {
    "C1 control macro":     (MACRO_X, MACRO_Y, MACRO_X + MACRO_S, MACRO_Y + MACRO_S),
    "NA neuron array 4x4":  (8.0, 140.0, 120.0, 140.0 + 2 * 45.74 + 29.42 + 34.29),  # M2 layout B: 155.19 tall
    "D1 dendrite":          (8.0, 12.0, 78.0, 116.0),
    "B1 bias generator":    B1_BOX,
    "R1 readout corner":    (262.0, 14.0, 302.0, 54.0),
    "A1 AdEx":              (129.0, 140.0, 167.0, 213.0),                  # rev 3: 38 x 73
    "TE0 tau trim col 0":   (8.0, 118.0, 45.0, 129.8),
    "TE2 tau trim col 2":   (64.0, 118.0, 101.0, 129.8),
}
ABUT = {("B1 bias generator", "R1 readout corner")}                   # R1 sits in B1's notch N1, pins abut
STRAP_UA1 = (280.64, 0.0, 286.64, 14.0)                               # r1_ua1: ua[1] Metal3 strap through CH_BOT
EST = {  # measured areas (um^2) of what goes in each box
    "C1 control macro": 166 * 166,
    "NA neuron array 4x4": 4 * 28.0 * (2 * 45.74 + 29.42 + 34.29),
    "D1 dendrite": 70 * 104,
    "B1 bias generator": 214.0 * 114.5 - 40 * 42,
    "R1 readout corner": 40 * 40,
    "A1 AdEx": 38 * 73,
    "TE0 tau trim col 0": 37 * 11.8,
    "TE2 tau trim col 2": 37 * 11.8,
}
CHANNELS = {  # routing-only regions (Metal2/Metal3; Metal4 may cross blocks between the stripes)
    "CH_BOT ua entry, R1 power, D1 lines": (8.0, 0.0, 199.5, 11.5),
    "CH_BIAS B1 -> array columns, D1 lines": (8.0, 130.3, 120.0, 139.7),
    "CH_MID B1 codes <-> macro S edge": (167.5, 127.0, 344.5, 150.5),
    "CH_MIDW B1 bias outputs, D1/AdEx lines": (120.5, 127.0, 167.5, 139.5),
    "CH_NAE row 0 lines past AdEx": (120.5, 140.0, 128.5, 213.0),
    "CH_ROW array rows -> macro W edge": (120.5, 213.5, 169.5, 317.0),
    "CH_TOP_A array power buses, uio_oe ties": (8.0, 314.5, 120.0, 324.3),
    "CH_TOP_M TT pin jogs to the macro N edge": (120.5, 317.5, 344.5, 324.3),
}

# Free areas kept for later use (M3 decap / test structures): the router may not put Metal2-4 there and no block
# may overlap them.  RW = B1's west bay (R2: old west trim + C4), RT = array-top strip (TOP-1), RG = CH_BOT west + H2 (TOP-4).
RESERVED = {
    "RW B1 west bay (R2)": (80.0, 12.0, 129.0, 116.0),
    "RT array-top strip": (8.0, 302.9, 120.0, 317.7),
    "RG CH_BOT east of the D1 lines": (199.5, 0.0, 280.0, 12.0),
}

# --------------------------------------------------------------------- power stripes (Metal4, y 5 -> 320.36)
STRIPES = [  # (net, x0, width)
    ("VDPWR", 1.0, 2.0), ("VGND", 4.0, 2.0),                 # template pair: array west, D1, tau col 0, rows
    ("VDPWR", 50.0, 1.6), ("VGND", 52.6, 1.6),               # array middle, D1 middle, tau cells
    ("VDPWR", 121.0, 1.6), ("VGND", 123.6, 1.6),             # array east / AdEx west
    ("VGND", 342.6, 0.8), ("VDPWR", 345.0, 0.8),             # B1 east-edge vdd/vss pins
]
for p in EXTENDED_STRAP_PAIRS:                                 # macro straps (and B1, R1, glue row below them)
    STRIPES += [("VDPWR", MACRO_X + MACRO_STRAPS[2 * p][0], 1.6),
                ("VGND", MACRO_X + MACRO_STRAPS[2 * p + 1][0], 1.6)]

# --------------------------------------------------------------------- std-cell rows (gf180mcu_fd_sc_mcu7t5v0)
TIE_ROW_Y = 318.4      # uio_oe tie-high cells (one tieh + filltie under each uio_oe pin), rails drawn across
# probe-enable / D1 tap-select glue (or4, 4x nor3, 3x inv, fillties): M3 (TOP-4) two R0 rows in hole H3 (CH_MID east,
# between the B1 code lines from the macro S edge (x <= 281.2) and bias_en (x 312)), lower-left corners; each row's
# rails are tied to the strap-pair-2 stripes (x 286.72 / 290.02). Was one row in CH_BOT at (170, 5.5).
GLUE_ROWS = [(282.6, 130.4), (282.6, 136.4)]

# --------------------------------------------------------------------- NA slot map
# M2 regrouped array, layout B (user decisions 2026-11-21 14:32 and 19:24 UTC, MIL-36 `array-regroup-plan`): the
# Latin square is replaced by two tall rows of trimmed slots at the bottom (layout/slot cells, 45.74 um per row,
# 23-track band) and two compact rows on top (layout/compact cells, 19-track band): row 2 at 29.42 um, row 3 at
# 34.29 um (AH400, MIL-127 N11: its extra cap sits in a 7.07 um cap row; it routes at CHAN 1.8 once its vr probe
# tap is dropped, user decision 2026-11-21 22:33 UTC; F2/F3/AH50 are built at the same height, cz* cells).
# Row 0 is the bottom row of the array. Tall rows at the bottom keep every neuron probeable: the macro's probe
# decoder (rev E, fixed: SEL = row x column) reads REF at (0,0) (PROBE_SUB = 3) and never selects (0,3), so REF
# (tall slot_ref) sits at (0,0) and the lower half of the CMP double slot at (0,3).
# Cost: row 0's band (y ~172-185, below AdEx's top at 213) has 3 trimmed slots, so its east lines squeeze through
# CH_NAE past AdEx.
# CMP is a double slot: map position (1,3) (probe row 1 / column 3, its rsel pad on the row-1 band), its cell spans
# rows 0-1 of column 3 (lower-left slot (0,3)); its other row pins (rt_out, sub/sub_b, spk, t0..t3) sit on the
# row-0 band (BAND_ROW). P2/P3 keep columns 0/2 (tau-trim cells), CMP keeps column 3 (aux = vth_cmp).
# The SEL -> neuron names follow this map (docs/regmap.md).
MAP = {(3, 0): "F2", (3, 1): "F3", (3, 2): "AH50", (3, 3): "AH400",
       (2, 0): "S1", (2, 1): "S2", (2, 2): "S3", (2, 3): "F1",
       (1, 0): "P2", (1, 1): "H2", (1, 2): "H3", (1, 3): "CMP",
       (0, 0): "REF", (0, 1): "H1", (0, 2): "P3"}
SPIKE_CH = {"S1": 0, "F1": 1, "H1": 2, "ADEX": 3, "S2": 4, "F2": 5, "H2": 6, "P2": 7,
            "S3": 8, "F3": 9, "H3": 10, "P3": 11, "CMP": 12, "D1": 13, "AH50": 14, "AH400": 15}
DOUBLE = {"CMP": (0, 3)}             # name -> lower-left slot of a 2-row cell
BAND_ROW = {"CMP": 0}                # row band of a double slot's row pins other than rsel
# Trim nibble assignment, fixed so it matches the control block's TRIM_MASK (nibbles 0,2-8,14,15).
TRIM_NIBBLES = {"H1.VTH": 0, "H2.VTH": 2, "P2.VTH": 3, "H3.VTH": 4, "P3.VTH": 5, "CMP.VTH": 6,
                "D1.PLAT1": 7, "D1.PLAT2": 8, "P2.TAU": 14, "P3.TAU": 15}
SLOT_W = 28.0
TALL_H, COMPACT_H, COMPACT_X_H = 45.74, 29.42, 34.29
ROW_H = (TALL_H, TALL_H, COMPACT_H, COMPACT_X_H)
ROW_NTRACK = (23, 23, 19, 19)        # row band tracks: 0-10 shared/spk, then 4 trim tracks per trimmed slot
TRKP = 0.56
SLOT_CELL = {"S": "cslot_ah", "F": "cslot_ah_f", "H": "slot_ah_h", "P": "slot_ah_p", "REF": "slot_ref",
             "CMP": "slot_cmp_h", "F2": "czslot_ah_f", "F3": "czslot_ah_f", "AH50": "czslot_ah_50",
             "AH400": "czslot_ah_400"}
# compact cells (layout/compact/final) and their heights; the others are tall layout/slot cells
COMPACT_CELLS = {"cslot_ah": COMPACT_H, "cslot_ah_f": COMPACT_H, "czslot_ah_f": COMPACT_X_H,
                 "czslot_ah_50": COMPACT_X_H, "czslot_ah_400": COMPACT_X_H}
TAU_COLS = {0: "TE0 tau trim col 0", 2: "TE2 tau trim col 2"}         # P2 in column 0, P3 in column 2


def row_y0(r):
    """Bottom of array row r (r = 4: top of the array)."""
    return round(BLOCKS["NA neuron array 4x4"][1] + sum(ROW_H[:r]), 3)


def row_trk0(r):
    """Track-0 centre of row r's band above the row bottom: tall cells 32.38 (band 32.24-44.84), compact cells
    H - 11.12 (band top 0.9 below the cell top, layout/compact/cgen.py)."""
    return 32.38 if ROW_H[r] == TALL_H else round(ROW_H[r] - 11.12, 3)


def slot_map():
    return dict(MAP)


def slot_origin(rc):
    """Lower-left slot (row, col) of the cell at map position rc (differs only for a double slot)."""
    return DOUBLE.get(slot_map()[rc], rc)


def slot_rows(name):
    return 2 if name in DOUBLE else 1


def cell_at(r, c):
    """(map position, name) of the slot cell that covers array position (r, c)."""
    for rc, n in slot_map().items():
        r0, c0 = DOUBLE.get(n, rc)
        if c0 == c and r0 <= r < r0 + slot_rows(n):
            return rc, n
    raise KeyError((r, c))


def cell_box(rc):
    """Box of the whole cell at map position rc (double slots: 28 x 87)."""
    n = slot_map()[rc]
    r0, c0 = slot_origin(rc)
    b = slot_box(r0, c0)
    return b[0], b[1], b[2], row_y0(r0 + slot_rows(n))


def slot_box(r, c):
    x0 = BLOCKS["NA neuron array 4x4"][0]
    return x0 + c * SLOT_W, row_y0(r), x0 + (c + 1) * SLOT_W, row_y0(r + 1)


def slot_cell(name):
    """Layout cell of a slot by its slot-map name (S1 -> slot_ah, CMP -> slot_cmp_h, ...)."""
    return SLOT_CELL.get(name) or SLOT_CELL[name[0]]


def trim_index():
    return dict(TRIM_NIBBLES)


def el_columns():
    """Column of each P slot: its leak-tail gate comes up that column's aux line from its tau-trim cell."""
    return {n: c for (r, c), n in slot_map().items() if n[0] == "P" and n[1:].isdigit()}


# --------------------------------------------------------------------- checks
def area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def overlap(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def b1_rects():
    """B1 frame as rectangles (box minus notches)."""
    x0, y0, x1, y1 = B1_BOX
    n1 = B1_NOTCHES["R1"]
    assert n1[1] == y0
    return [(x0, y0, n1[0], y1), (n1[0], n1[3], n1[2], y1), (n1[2], y0, x1, y1)]


def frames():
    """Every block as a list of rectangles (B1 notched)."""
    return {n: (b1_rects() if n.startswith("B1") else [b]) for n, b in BLOCKS.items()}


def checks():
    errs = []
    fr = frames()
    for n, b in {**BLOCKS, **CHANNELS}.items():
        if not (0 <= b[0] < b[2] <= TILE_W and 0 <= b[1] < b[3] <= TILE_H):
            errs.append(f"{n} outside tile")
    names = list(BLOCKS)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            gap = 0.0 if (a, b) in ABUT or (b, a) in ABUT else MIN_GAP - 1e-9
            for ra in fr[a]:
                for rb in fr[b]:
                    if (gap == 0.0 and overlap(ra, rb, -1e-9)) or (gap > 0 and overlap(ra, rb, gap)):
                        errs.append(f"{a} and {b} closer than {gap or 0} um")
    for rn, rb in RESERVED.items():
        for n, rs in fr.items():
            if any(overlap(r, rb, -1e-9) for r in rs):
                errs.append(f"{n} overlaps reserved area {rn}")
    for cn, cb in CHANNELS.items():
        for n, rs in fr.items():
            if any(overlap(r, cb, -1e-9) for r in rs):
                errs.append(f"{n} overlaps channel {cn}")
    # R1 must sit inside B1's notch N1, the tau cell of column 2 inside notch N2 (plus its overhang above B1)
    r1, n1 = BLOCKS["R1 readout corner"], B1_NOTCHES["R1"]
    if not (n1[0] <= r1[0] and r1[2] <= n1[2] and n1[1] <= r1[1] and r1[3] <= n1[3]):
        errs.append("R1 not inside B1 notch N1")
    # power stripes: Metal4 crosses any block except the macro (only on its own straps), full height, >= 0.8 wide
    macro = BLOCKS["C1 control macro"]
    straps = {round(MACRO_X + s, 3) for s, _ in MACRO_STRAPS}
    for net, x, w in STRIPES:
        if w < 0.8:
            errs.append(f"{net} stripe at {x} narrower than 0.8 um")
        if overlap((x, STRIPE_Y[0], x + w, STRIPE_Y[1]), macro) and round(x, 3) not in straps:
            errs.append(f"{net} stripe at x={x} crosses the macro off its straps")
        if x < 0.5 or x + w > TILE_W - 0.02:
            errs.append(f"stripe at {x} outside the tile")
        for pn, px in {**PINS_BOT}.items():
            if overlap((x, STRIPE_Y[0], x + w, STRIPE_Y[1]), (px - 3, 0, px + 3, 1)):
                errs.append(f"{net} stripe at {x} on {pn}")
    ss = sorted(STRIPES, key=lambda s: s[1])
    for (_, x, w), (_, x2, _) in zip(ss, ss[1:]):
        if x2 - (x + w) < 1.0:
            errs.append(f"stripes at {x} and {x2} closer than 1 um")
    # analog pins must land on the block pad that uses them
    ua0 = PINS_BOT["ua[0]"]
    if not (324.3 - 1e-6 <= ua0 - 3 and ua0 + 3 <= 330.3 + 0.05):
        errs.append("ua[0] not on B1's pad (tile x 324.3-330.3)")
    if abs(PINS_BOT["ua[1]"] - 3 - STRAP_UA1[0]) > 1e-6:
        errs.append("ua[1] not on R1's strap")
    # bias channel between the tau cells and the array
    ch = BLOCKS["NA neuron array 4x4"][1] - BLOCKS["TE0 tau trim col 0"][3]
    if ch < 7.0:
        errs.append(f"bias channel under the array only {ch:.1f} um")
    # spike channels and slots
    grid = slot_map()
    placed = set(grid.values()) | {"D1", "ADEX"}
    for name in SPIKE_CH:
        if name not in placed:
            errs.append(f"spike channel {name} has no slot")
    if len(set(SPIKE_CH.values())) != 16:
        errs.append("spike channel numbers not unique 0..15")
    groups = {}
    for (r, c), n in grid.items():
        if n[0] in "FSHP" and n[1:].isdigit():
            groups.setdefault(n[0], []).append((r, c))
    for g, k in {"S": 3, "F": 3, "H": 3, "P": 2}.items():
        if len(groups.get(g, [])) != k:
            errs.append(f"group {g} has {len(groups.get(g, []))} slots, not {k}")
    if abs(row_y0(4) - BLOCKS["NA neuron array 4x4"][3]) > 1e-6:
        errs.append(f"array box top {BLOCKS['NA neuron array 4x4'][3]} != rows top {row_y0(4)}")
    for (r, c), n in grid.items():   # a row's cells share its height (column lines abut through them)
        h = COMPACT_CELLS.get(slot_cell(n), TALL_H)
        for rr in range(slot_origin((r, c))[0], slot_origin((r, c))[0] + slot_rows(n)):
            if abs(h - ROW_H[rr]) > 1e-6:
                errs.append(f"{n} ({slot_cell(n)}) in row {rr} of height {ROW_H[rr]}")
    ti = trim_index()
    if len(ti) > 16 or max(ti.values()) > 15 or len(set(ti.values())) != len(ti):
        errs.append("trim nibbles collide or exceed NTRIM=16")
    cols = el_columns()
    if len(set(cols.values())) != len(cols):
        errs.append(f"two P slots share a column, so one aux line can't carry both: {cols}")
    if set(cols.values()) != set(TAU_COLS):
        errs.append(f"tau-trim cells in columns {sorted(TAU_COLS)} but P slots in {sorted(cols.values())}")
    # every array position covered by exactly one cell
    try:
        cov = {(r, c): cell_at(r, c)[0] for r in range(4) for c in range(4)}
        for rc, n in grid.items():
            if sum(1 for v in cov.values() if v == rc) != slot_rows(n):
                errs.append(f"slot {n} does not cover {slot_rows(n)} positions")
    except KeyError as e:
        errs.append(f"array position {e} not covered by a slot")
    if "CMP" in grid and grid_col(grid, "CMP") in TAU_COLS:
        errs.append("CMP's aux line (vth_cmp) would collide with a tau-trim column")
    for r in range(4):     # row band: tracks 11.. carry 4 trim bits per trimmed slot
        nt = sum(1 for rc, n in grid.items()
                 if ((n[0] in "HP" and n[1:].isdigit()) or n == "CMP") and BAND_ROW.get(n, rc[0]) == r)
        if 11 + 4 * nt > ROW_NTRACK[r]:
            errs.append(f"row {r} has {nt} trimmed slots (> {(ROW_NTRACK[r] - 11) // 4})")
    return errs


def grid_col(grid, name):
    return [c for (r, c), n in grid.items() if n == name][0]


# --------------------------------------------------------------------- drawing
COL = {"C1": "#9aa7c7", "NA": "#f2c48d", "D1": "#b9dba0", "B1": "#e8a2a2", "R1": "#d77", "A1": "#c9b3e6",
       "TE": "#f7e08a"}


def svg(path):
    s, H = 2.4, TILE_H
    X = lambda x: x * s
    Y = lambda y: (H - y) * s
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TILE_W*s+20:.0f}" height="{TILE_H*s+20:.0f}" '
         f'viewBox="-10 -10 {TILE_W*s+20:.0f} {TILE_H*s+20:.0f}" font-family="sans-serif">',
         f'<rect x="0" y="0" width="{X(TILE_W)}" height="{TILE_H*s}" fill="white" stroke="black"/>']
    rect = lambda b, fill, extra="": (f'<rect x="{X(b[0]):.1f}" y="{Y(b[3]):.1f}" width="{X(b[2]-b[0]):.1f}" '
                                      f'height="{(b[3]-b[1])*s:.1f}" fill="{fill}" {extra}/>')
    for n, b in CHANNELS.items():
        o.append(rect(b, "#f4f4ff", 'stroke="#aab" stroke-dasharray="4 3"'))
    for n, b in RESERVED.items():
        o.append(rect(b, "#dff5df", 'stroke="#4a4" stroke-dasharray="2 2"'))
    for n, rs in frames().items():
        for b in rs:
            o.append(rect(b, COL[n[:2]], 'stroke="#333"'))
        b = BLOCKS[n]
        if not n.startswith("NA"):
            fs = 13 if area(b) > 5000 else 8
            o.append(f'<text x="{X((b[0]+b[2])/2):.1f}" y="{Y((b[1]+b[3])/2):.1f}" font-size="{fs}" '
                     f'text-anchor="middle">{n.split()[0]}</text>')
    o.append(rect(STRAP_UA1, "#d77"))
    for (r, c), n in slot_map().items():
        b = cell_box((r, c))
        o.append(rect(b, "none", 'stroke="#a66"'))
        ch = SPIKE_CH.get(n)
        lab = n + (f" ch{ch}" if ch is not None else "")
        o.append(f'<text x="{X((b[0]+b[2])/2):.1f}" y="{Y((b[1]+b[3])/2)+4:.1f}" font-size="11" '
                 f'text-anchor="middle">{lab}</text>')
    for net, x, w in STRIPES:
        o.append(f'<rect x="{X(x):.1f}" y="{Y(STRIPE_Y[1]):.1f}" width="{max(w*s,2):.1f}" '
                 f'height="{(STRIPE_Y[1]-STRIPE_Y[0])*s:.1f}" fill="{"#d33" if net=="VDPWR" else "#333"}" opacity="0.6"/>')
    for n, x in PINS_TOP.items():
        o.append(f'<rect x="{X(x-0.3):.1f}" y="{Y(TILE_H):.1f}" width="2" height="5" fill="#36c"/>')
    for n, x in PINS_BOT.items():
        used = n in ANALOG_USED
        o.append(f'<rect x="{X(x-3):.1f}" y="{Y(1):.1f}" width="{6*s:.1f}" height="{s*1.5:.1f}" '
                 f'fill="{"#c30" if used else "#bbb"}"/>')
        if used:
            o.append(f'<text x="{X(x):.1f}" y="{Y(-3.5):.1f}" font-size="11" text-anchor="middle">{n}</text>')
    o.append(f'<text x="{X(40)}" y="{Y(TILE_H)-3}" font-size="10">uio_oe (tie-high)</text>')
    o.append(f'<text x="{X(120)}" y="{Y(TILE_H)-3}" font-size="10">uio_out / uo_out</text>')
    o.append(f'<text x="{X(230)}" y="{Y(TILE_H)-3}" font-size="10">uio_in, ui_in, rst_n, clk</text>')
    o.append("</svg>")
    path.write_bytes("\n".join(o).encode("utf-8"))      # LF on every host


def main():
    total = TILE_W * TILE_H
    print(f"tile {TILE_W} x {TILE_H} = {total:,.0f} um^2  (floorplan v2)")
    print(f"{'block':24s} {'box (um)':>16s} {'frame':>8s} {'drawn':>8s}")
    used = 0
    fr = frames()
    for n, b in BLOCKS.items():
        a = sum(area(r) for r in fr[n])
        used += a
        print(f"{n:24s} {f'{b[2]-b[0]:.1f} x {b[3]-b[1]:.1f}':>16s} {a:8,.0f} {EST[n]:8,.0f}")
    print(f"{'blocks total':24s} {'':>16s} {used:8,.0f}   ({100*used/total:.0f}% of tile; "
          f"rest is channels, stripes, gaps)")
    ch = BLOCKS["NA neuron array 4x4"][1] - BLOCKS["TE0 tau trim col 0"][3]
    print(f"bias channel under the array: {ch:.1f} um (tau cells to array); B1 top to array "
          f"{BLOCKS['NA neuron array 4x4'][1]-B1_BOX[3]:.1f} um")
    print("slot map (top row first):")
    g = slot_map()
    for r in range(3, -1, -1):
        print("   " + "  ".join(f"{(g.get((r, c)) or cell_at(r, c)[1] + '*'):6s}" for c in range(4)))
    print("   (* = lower half of a double slot)")
    print("P slot columns (aux line carries leak-tau bias):", el_columns())
    print("trim nibbles:", ", ".join(f"{k}->{v}" for k, v in trim_index().items()))
    print("stripes:", ", ".join(f"{n}@{x:g}" for n, x, w in sorted(STRIPES, key=lambda s: s[1])))
    errs = checks()
    svg(ROOT / "docs" / "floorplan.svg")
    print("wrote docs/floorplan.svg")
    if errs:
        print("CHECK FAILURES:"); [print("  -", e) for e in errs]
        return 1
    print("all geometry checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
