"""Tile floorplan for tt_um_basilwright0_analog_neurons (TTGF26c analog 1x2).

Single source of truth for block boxes, channels, power stripes and the neuron-array slot map.
Run:  python floorplan/floorplan.py      (plain Python 3, no dependencies)
Writes docs/floorplan.svg and prints an area table plus geometry checks. Exit code 1 on any failure.
All units are microns, origin at the tile's lower-left corner. See docs/06 Floorplan.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TILE_W, TILE_H = 346.64, 325.36          # mag/tt_analog_1x2.def DIEAREA
STRIPE_Y = (5.0, 320.36)                 # mag/init_project.tcl
MIN_GAP = 2.0                            # block-to-block / block-to-stripe clearance

# --------------------------------------------------------------------- tile pins (DEF)
TOP_Y = 324.86
def _row(names, x0, pitch=-14.56):
    return {n: round(x0 + i * pitch, 2) for i, n in enumerate(names)}
PINS_TOP = {}
PINS_TOP.update(_row([f"uio_oe[{i}]" for i in range(8)], 83.72))
PINS_TOP.update(_row([f"uio_out[{i}]" for i in range(8)], 141.96))
PINS_TOP.update(_row([f"uo_out[{i}]" for i in range(8)], 200.20))
PINS_TOP.update(_row([f"uio_in[{i}]" for i in range(8)], 258.44))
PINS_TOP.update(_row([f"ui_in[{i}]" for i in range(8)], 316.68))
PINS_TOP.update({"rst_n": 323.96, "clk": 331.24, "ena": 338.52})
PINS_BOT = {f"ua[{i}]": round(327.32 - 43.68 * i, 2) for i in range(8)}   # 6 um wide
ANALOG_USED = ("ua[0]", "ua[1]")

# --------------------------------------------------------------------- macro
MACRO_X, MACRO_Y, MACRO_S = 132.0, 134.0, 182.0
MACRO_STRAPS = [(15.92, "VDD"), (19.22, "VSS"), (65.92, "VDD"), (69.22, "VSS"),
                (115.92, "VDD"), (119.22, "VSS"), (165.92, "VDD"), (169.22, "VSS")]  # LEF, 1.6 wide
EXTENDED_STRAP_PAIR = 1        # macro strap pair (0..3) extended full height to the tile grid

# --------------------------------------------------------------------- power stripes (Metal4)
STRIPES = [  # (net, x0, width)
    ("VDPWR", 1.0, 2.0), ("VGND", 4.0, 2.0),                 # template pair, west edge
    ("VDPWR", 122.5, 2.0), ("VGND", 125.5, 2.0),             # NA east side / macro west gap
    ("VDPWR", 338.0, 2.0), ("VGND", 341.0, 2.0),             # east edge, B1+R1
]
p = EXTENDED_STRAP_PAIR
STRIPES += [("VDPWR", MACRO_X + MACRO_STRAPS[2 * p][0], 1.6),
            ("VGND", MACRO_X + MACRO_STRAPS[2 * p + 1][0], 1.6)]

# --------------------------------------------------------------------- blocks (x0, y0, x1, y1)
BLOCKS = {
    "C1 control macro":          (MACRO_X, MACRO_Y, MACRO_X + MACRO_S, MACRO_Y + MACRO_S),
    "NA neuron array 4x4":       (8.0, 136.0, 120.0, 310.0),
    "D1 dendrite":               (132.0, 14.0, 194.5, 118.0),
    "B1+R1 bias & pad driver":   (205.0, 14.0, 336.0, 118.0),
    "T2 Tier-2 zone":            (8.0, 14.0, 120.0, 104.0),
    "TE tau trims (P slots)":    (8.0, 106.0, 120.0, 118.0),
}
EST = {  # schematic-stage area estimates (um^2) for what must go in each block
    "C1 control macro": 33124,             # hardened, rev C
    "NA neuron array 4x4": 16 * 1218,      # S slot laid out at 28 x 43.5 (layout/slot), routing-bound
    "D1 dendrite": 6000,
    "B1+R1 bias & pad driver": 10200 + 1800 + 400,   # B1 core+DACs, pad follower+refs, Vreset buffer
    "T2 Tier-2 zone": 5000 + 5000,         # A1 AdEx x2 + S1 switched-cap dendrite (W1 if room)
    "TE tau trims (P slots)": 3 * 200,     # one leak-tau current trim per P slot, under its column
}
CHANNELS = {  # routing-only regions
    "CH_BOT bias/ua entry": (8.0, 2.0, 336.0, 12.0),
    "CH_MID bias->NA, probe bus, cfg codes": (8.0, 120.0, 336.0, 132.0),
    "CH_TOP TT pin jogs": (8.0, 317.0, 336.0, 324.0),
    "CH_E clk/rst_n": (315.0, 134.0, 336.0, 316.0),
}

# --------------------------------------------------------------------- NA slot map
# Latin square over groups F(fixed geometry) S(shared bias) H(hybrid: shared + threshold trim)
# P(programmable: gap trim + leak-tau trim; can be cut -> becomes H); its diagonal is a transversal and holds the singles.
# Row 0 is the bottom row of the array.
SQUARE = ["FSHP", "HPFS", "PHSF", "SFPH"]
SINGLES = {0: "REF", 1: "CMP", 2: "AH50", 3: "AH800"}
SPIKE_CH = {"S1": 0, "F1": 1, "H1": 2, "ADEX": 3, "S2": 4, "F2": 5, "H2": 6, "P2": 7,
            "S3": 8, "F3": 9, "H3": 10, "P3": 11, "CMP": 12, "D1": 13, "AH50": 14, "AH800": 15}
# AdEx replaced P1 (docs/08 Updated Plan.md): it sits outside the array; P1's slot is a dummy S slot.
DUMMY_SLOTS = {"P1"}
# Trim nibble assignment, fixed so it matches the control block's TRIM_MASK (nibbles 0,2-8,14,15).
TRIM_NIBBLES = {"H1.VTH": 0, "H2.VTH": 2, "P2.VTH": 3, "H3.VTH": 4, "P3.VTH": 5, "CMP.VTH": 6,
                "D1.PLAT1": 7, "D1.PLAT2": 8, "P2.TAU": 14, "P3.TAU": 15}


def slot_map():
    count, grid = {}, {}
    for r, row in enumerate(SQUARE):
        for c, g in enumerate(row):
            if r == c:
                grid[(r, c)] = SINGLES[r]
            else:
                count[g] = count.get(g, 0) + 1
                n = f"{g}{count[g]}"
                grid[(r, c)] = "DUMMY" if n in DUMMY_SLOTS else n
    return grid


def slot_box(r, c):
    x0, y0, x1, y1 = BLOCKS["NA neuron array 4x4"]
    w, h = (x1 - x0) / 4, (y1 - y0) / 4
    return x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h


def trim_index():
    return dict(TRIM_NIBBLES)


def el_columns():
    """Column of each P slot: its leak-tail gate voltage comes up that column's aux track from the TE strip."""
    return {n: c for (r, c), n in slot_map().items() if n[0] == "P" and n[1:].isdigit()}


# --------------------------------------------------------------------- checks
def area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def overlap(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def checks():
    errs = []
    for n, b in {**BLOCKS, **CHANNELS}.items():
        if not (0 <= b[0] < b[2] <= TILE_W and 0 <= b[1] < b[3] <= TILE_H):
            errs.append(f"{n} outside tile")
    names = list(BLOCKS)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if overlap(BLOCKS[a], BLOCKS[b], MIN_GAP - 1e-9):
                errs.append(f"{a} and {b} closer than {MIN_GAP} um")
        for cn, cb in CHANNELS.items():
            if overlap(BLOCKS[a], cb):
                errs.append(f"{a} overlaps channel {cn}")
    macro = BLOCKS["C1 control macro"]
    for net, x, w in STRIPES:
        sb = (x, STRIPE_Y[0], x + w, STRIPE_Y[1])
        for n, b in BLOCKS.items():
            inside_macro = n.startswith("C1") and any(abs(x - (MACRO_X + s)) < 1e-6 for s, _ in MACRO_STRAPS)
            if not inside_macro and overlap(sb, b, MIN_GAP - 1e-9):
                errs.append(f"{net} stripe at x={x} too close to {n}")
        if x + w > TILE_W - 0.5:
            errs.append(f"stripe at {x} too close to tile edge")
    for (_, x, w), (_, x2, _) in zip(sorted(STRIPES, key=lambda s: s[1]), sorted(STRIPES, key=lambda s: s[1])[1:]):
        if x2 - (x + w) < 1.0:
            errs.append(f"stripes at {x} and {x2} closer than 1 um")
    # analog pins must enter the block that uses them and not hit a stripe
    for pin in ANALOG_USED:
        x = PINS_BOT[pin]
        pb = (x - 3, 0, x + 3, 14)
        for net, sx, w in STRIPES:
            if overlap(pb, (sx, STRIPE_Y[0], sx + w, STRIPE_Y[1])):
                errs.append(f"{pin} collides with {net} stripe at {sx}")
        b = BLOCKS["B1+R1 bias & pad driver"]
        if not b[0] + 3 <= x <= b[2] - 3:
            errs.append(f"{pin} (x={x}) not under B1+R1")
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
    for g, cells in groups.items():
        k = 2 if g == "P" else 3
        if len(cells) != k or len({r for r, _ in cells}) != k or len({c for _, c in cells}) != k:
            errs.append(f"group {g} not spread over its own rows and columns: {cells}")
    ti = trim_index()
    if len(ti) > 16 or max(ti.values()) > 15 or len(set(ti.values())) != len(ti):
        errs.append("trim nibbles collide or exceed NTRIM=16")
    cols = el_columns()
    if len(set(cols.values())) != len(cols):
        errs.append(f"two P slots share a column, so one aux track can't carry both ELs: {cols}")
    return errs


# --------------------------------------------------------------------- drawing
COL = {"C1": "#9aa7c7", "NA": "#f2c48d", "D1": "#b9dba0", "B1": "#e8a2a2", "T2": "#dddddd", "TE": "#f7e08a"}


def svg(path):
    s, H = 2.4, TILE_H
    X = lambda x: x * s
    Y = lambda y: (H - y) * s
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TILE_W*s+20:.0f}" height="{TILE_H*s+20:.0f}" '
         f'viewBox="-10 -10 {TILE_W*s+20:.0f} {TILE_H*s+20:.0f}" font-family="sans-serif">',
         f'<rect x="0" y="0" width="{X(TILE_W)}" height="{TILE_H*s}" fill="white" stroke="black"/>']
    for n, b in CHANNELS.items():
        o.append(f'<rect x="{X(b[0])}" y="{Y(b[3])}" width="{X(b[2]-b[0])}" height="{(b[3]-b[1])*s}" '
                 f'fill="#f4f4ff" stroke="#aab" stroke-dasharray="4 3"/>')
    for n, b in BLOCKS.items():
        o.append(f'<rect x="{X(b[0])}" y="{Y(b[3])}" width="{X(b[2]-b[0])}" height="{(b[3]-b[1])*s}" '
                 f'fill="{COL[n[:2]]}" stroke="#333"/>')
        if not n.startswith("NA"):
            o.append(f'<text x="{X((b[0]+b[2])/2)}" y="{Y((b[1]+b[3])/2)}" font-size="13" text-anchor="middle">{n.replace("&", "&amp;")}</text>')
            o.append(f'<text x="{X((b[0]+b[2])/2)}" y="{Y((b[1]+b[3])/2)+16}" font-size="11" text-anchor="middle">'
                     f'{area(b)/1000:.1f}k um² (need ~{EST[n]/1000:.1f}k)</text>')
    for (r, c), n in slot_map().items():
        b = slot_box(r, c)
        o.append(f'<rect x="{X(b[0])}" y="{Y(b[3])}" width="{X(b[2]-b[0])}" height="{(b[3]-b[1])*s}" fill="none" stroke="#a66"/>')
        ch = SPIKE_CH.get(n)
        lab = n + (f" ch{ch}" if ch is not None else "")
        o.append(f'<text x="{X((b[0]+b[2])/2)}" y="{Y((b[1]+b[3])/2)+4}" font-size="11" text-anchor="middle">{lab}</text>')
    for net, x, w in STRIPES:
        o.append(f'<rect x="{X(x)}" y="{Y(STRIPE_Y[1])}" width="{max(w*s,2)}" height="{(STRIPE_Y[1]-STRIPE_Y[0])*s}" '
                 f'fill="{"#d33" if net=="VDPWR" else "#333"}" opacity="0.7"/>')
    for n, x in PINS_TOP.items():
        o.append(f'<rect x="{X(x-0.3)}" y="{Y(TILE_H)}" width="3" height="5" fill="#36c"/>')
    for n, x in PINS_BOT.items():
        used = n in ANALOG_USED
        o.append(f'<rect x="{X(x-3)}" y="{Y(1)}" width="{6*s}" height="{s*1.5}" fill="{"#c30" if used else "#bbb"}"/>')
        if used:
            o.append(f'<text x="{X(x)}" y="{Y(-3.5)}" font-size="11" text-anchor="middle">{n.replace("&", "&amp;")}</text>')
    o.append(f'<text x="{X(60)}" y="{Y(TILE_H)-3}" font-size="10">uio_oe / uio_out</text>')
    o.append(f'<text x="{X(180)}" y="{Y(TILE_H)-3}" font-size="10">uo_out</text>')
    o.append(f'<text x="{X(290)}" y="{Y(TILE_H)-3}" font-size="10">ui_in, rst, clk</text>')
    o.append("</svg>")
    path.write_text("\n".join(o), encoding="utf-8")


def main():
    total = TILE_W * TILE_H
    print(f"tile {TILE_W} x {TILE_H} = {total:,.0f} um^2")
    print(f"{'block':28s} {'box (um)':>22s} {'area':>8s} {'need':>8s} {'margin':>7s}")
    used = 0
    for n, b in BLOCKS.items():
        a = area(b); used += a
        print(f"{n:28s} {f'{b[2]-b[0]:.1f} x {b[3]-b[1]:.1f}':>22s} {a:8,.0f} {EST[n]:8,.0f} {100*(a/EST[n]-1):6.0f}%")
    print(f"{'blocks total':28s} {'':>22s} {used:8,.0f}   ({100*used/total:.0f}% of tile; rest is channels, stripes, gaps)")
    sw, sh = slot_box(0, 0)[2] - slot_box(0, 0)[0], slot_box(0, 0)[3] - slot_box(0, 0)[1]
    print(f"NA slot {sw:.1f} x {sh:.1f} = {sw*sh:,.0f} um^2")
    print("slot map (top row first):")
    g = slot_map()
    for r in range(3, -1, -1):
        print("   " + "  ".join(f"{g[(r, c)]:6s}" for c in range(4)))
    print("P slot columns (aux track carries leak-tau bias):", el_columns())
    print("trim nibbles:", ", ".join(f"{k}->{v}" for k, v in trim_index().items()))
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
