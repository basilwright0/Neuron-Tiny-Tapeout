"""Deterministic top-level geometry (plain Python): everything that is drawn by rule, not by the router.

  - Metal4 power stripes (ports), ua[0] hookup
  - neuron array: 4 row bands x 19 Metal3 tracks with via2 drops on the slot pads, west joins of the shared
    row lines, east fan-outs (Metal2 verticals at 0.7 um pitch) that end on router-grid terminals,
    column-bottom terminals, the power buses above the array
  - power hookups of B1, R1, D1, AdEx and the tau cells
  - std-cell rows: uio_oe tie-high row (above the array) and the glue row (CH_BOT)

fixed() returns dict(shapes=[(layer, rect, net)], cells=[(inst, cell, x, y)], terms={net: [group, ...]},
ports=[(name, layer, rect, use)]).  A group is a list of (layer, rect): one connection point of a net.
"""
import json
import config as C

fp = C.fp
G, OX, OY = 0.14, 0.03, 0.04            # router grid (tile um): x = OX + G*i, y = OY + G*j


def gx(x):
    return round(OX + G * round((x - OX) / G), 3)


def gy(y):
    return round(OY + G * round((y - OY) / G), 3)


def R(x0, y0, x1, y1):
    return (round(min(x0, x1), 3), round(min(y0, y1), 3), round(max(x0, x1), 3), round(max(y0, y1), 3))


class Fix:
    def __init__(self):
        self.shapes, self.cells, self.terms, self.ports = [], [], {}, []

    def p(self, layer, r, net):
        self.shapes.append((layer, R(*r), net))

    def via(self, kind, x, y, net, pads=("both",), pad=0.4):
        """kind: via1/via2/via3. pads: which metals get a 0.4 pad ('lo', 'hi', 'both', none)."""
        lo, hi = {"via1": ("metal1", "metal2"), "via2": ("metal2", "metal3"), "via3": ("metal3", "metal4")}[kind]
        c = 0.13 if kind == "via1" else 0.14
        self.p(kind, (x - c, y - c, x + c, y + c), net)
        h = pad / 2
        if "both" in pads or "lo" in pads:
            self.p(lo, (x - h, y - h, x + h, y + h), net)
        if "both" in pads or "hi" in pads:
            self.p(hi, (x - h, y - h, x + h, y + h), net)

    def stack(self, x, y, net, top="via3"):
        for v in ("via1", "via2", "via3")[: {"via1": 1, "via2": 2, "via3": 3}[top]]:
            self.via(v, x, y, net)

    def term(self, net, group):
        self.terms.setdefault(net, []).append([(l, R(*r)) for l, r in group])


def geo(cell):
    return json.loads((C.WORK / "geo" / f"{cell}.json").read_text())


def pin_pt(cell, name):
    return geo(cell)["pins"][name][0]["pt"]


# ======================================================================== array
TRKP = 0.56                                    # row band: track k centre at fp.row_y0(r) + fp.row_trk0(r) + 0.56 k
SHARED = {0: "rt_out[0]", 1: "rt_out[1]", 2: "rt_out[2]", 3: "rt_out[3]", 5: "probe_sub", 6: "probe_sub_b"}
SHARED_EAST_ROW = 2                            # row whose shared tracks continue east to the macro (rt_out y)
PINTRK = {"sta": 0, "stb": 1, "hold": 2, "mreset": 3, "rsel": 4, "sub": 5, "sub_b": 6}


def array(F):
    grid = fp.slot_map()
    tn = fp.TRIM_NIBBLES
    ax0, ay0, ax1, ay1 = fp.BLOCKS["NA neuron array 4x4"]
    jumps = {}
    xoff = 0                                # fan-out columns used by lower rows below AdEx's top (CH_NAE)
    for r in range(4):
        y0, TRK0 = fp.row_y0(r), fp.row_trk0(r)
        net_of = {k: n for k, n in SHARED.items()}
        net_of[4] = f"probe_rsel[{r}]"
        vias = []                                              # (k, x)

        def here(c):
            """Pins of the cell covering (r, c) whose label lies on row r's band (double slots have two)."""
            rc, name = fp.cell_at(r, c)
            pins = geo(fp.slot_cell(name))["pins"]
            off = fp.row_y0(r) - fp.row_y0(fp.slot_origin(rc)[0])
            return name, {pn: p for pn, p in pins.items() if off <= p[0]["pt"][1] < off + fp.ROW_H[r]}
        trims = [c for c in range(4) if "t0" in here(c)[1] and (here(c)[0] != "CMP" or C.CMP_TRIM)]
        for c in range(4):
            name, pins = here(c)
            sx = ax0 + c * fp.SLOT_W
            for pn, k in PINTRK.items():
                if pn in pins:
                    vias.append((k, sx + pins[pn][0]["pt"][0]))
            if "spk" in pins:
                k = 7 + c
                net_of[k] = f"spk_in[{fp.SPIKE_CH[name]}]"
                vias.append((k, sx + pins["spk"][0]["pt"][0]))
            if c in trims:
                base = 11 + 4 * trims.index(c)
                bits = C.nib_bits(tn[f"{name}.VTH"])
                for j in range(4):
                    net_of[base + j] = bits[j]
                    vias.append((base + j, sx + pins[f"t{j}"][0]["pt"][0]))
        # tracks: west end (shared: to the join line), east end (to the fan-out)
        east = [k for k in sorted(net_of) if k not in SHARED or r == SHARED_EAST_ROW]
        xe = {k: gx(ax1 + 0.71 + 0.7 * (xoff + j)) for j, k in enumerate(east)}
        if fp.row_y0(r + 1) < fp.BLOCKS["A1 AdEx"][3]:   # this row's lines run north past AdEx: keep the columns
            xoff += len(east)
        xw = {k: gx(ax0 - 0.69 - 0.7 * j) for j, k in enumerate(sorted(SHARED))}
        for k, net in net_of.items():
            ty = y0 + TRK0 + TRKP * k
            xa = xw[k] - 0.2 if k in SHARED else ax0 + 0.3
            xb = xe[k] + 0.2 if k in xe else ax1 - 0.3
            F.p("metal3", (xa, ty - 0.14, xb, ty + 0.14), net)
            if k in xe:              # east fan-out: via2 + Metal2 to the terminal (row 0 up, rows 1-3 down)
                F.p("via2", (xe[k] - 0.14, ty - 0.14, xe[k] + 0.14, ty + 0.14), net)
                if r == 0:              # up: 0.7 above the row top (row 1's band is far above)
                    yt = gy(y0 + fp.ROW_H[0] + 0.7)
                    F.p("metal2", (xe[k] - 0.14, ty - 0.2, xe[k] + 0.14, yt + 0.14), net)
                    F.term(net, [("metal2", (xe[k] - 0.14, yt - 0.42, xe[k] + 0.14, yt + 0.14))])
                else:
                    yt = gy(y0 + TRK0 - 1.38)
                    F.p("metal2", (xe[k] - 0.14, yt - 0.14, xe[k] + 0.14, ty + 0.2), net)
                    F.term(net, [("metal2", (xe[k] - 0.14, yt - 0.14, xe[k] + 0.14, yt + 0.42))])
            if k in SHARED:
                F.p("via2", (xw[k] - 0.14, ty - 0.14, xw[k] + 0.14, ty + 0.14), net)
        for k, x in vias:
            ty = y0 + TRK0 + TRKP * k
            F.p("via2", (x - 0.14, ty - 0.14, x + 0.14, ty + 0.14), net_of[k])
        jumps[r] = [(k, ax0 + c * fp.SLOT_W + 12.3, y0 + TRK0 + TRKP * k)
                    for c in trims for k in range(11 + 4 * trims.index(c), 15 + 4 * trims.index(c))]
    # trim-track jumpers (antenna): Metal3 gap 1.2 um bridged on Metal4 just east of the trimmed slot
    for r, lst in jumps.items():
        for k, jx, jy in lst:
            gap = (jx, jy - 0.14, jx + 1.0, jy + 0.14)
            for idx, (lay, rr, net) in enumerate(F.shapes):
                if lay == "metal3" and rr[1] == round(jy - 0.14, 3) and rr[0] < gap[0] and rr[2] > gap[2]:
                    vl, vr = gap[0], gap[2]                 # via centres; 0.06 end enclosure on both metals
                    F.shapes[idx] = (lay, (rr[0], rr[1], round(vl + 0.19, 3), rr[3]), net)
                    F.shapes.append((lay, (round(vr - 0.19, 3), rr[1], rr[2], rr[3]), net))
                    F.p("metal4", (vl - 0.19, jy - 0.14, vr + 0.19, jy + 0.14), net)
                    for vx in (vl, vr):
                        F.p("via3", (vx - 0.14, jy - 0.14, vx + 0.14, jy + 0.14), net)
                    break
    # stim A (track 0) on Metal4 across the array (PEX: its Metal3 ran 0.74 um from the slots' vm Metal3, 8-19 mV
    # kick per edge); back on Metal3 only under the x 50 / 52.6 stripes; sta drops become via2 + via3 stacks
    keep = [(x - 0.6, x + w + 0.6) for _, x, w in fp.STRIPES if x < ax1 and x + w > ax0]
    hops, xa = [], ax0 + 0.6
    for ka, kb in sorted(keep):
        if ka > xa:
            hops.append((xa, ka))
        xa = max(xa, kb)
    hops.append((xa, ax1 - 0.6))
    for r in range(4):
        jy = round(fp.row_y0(r) + fp.row_trk0(r), 3)
        idx = [i for i, (lay, rr, net) in enumerate(F.shapes) if lay == "metal3" and rr[1] == round(jy - 0.14, 3)]
        assert len(idx) == 1, (r, idx)
        lay, rr, net = F.shapes.pop(idx[0])
        cuts = [rr[0]] + [v for a, b in hops for v in (a, b)] + [rr[2]]
        for xl, xr in zip(cuts[0::2], cuts[1::2]):                # Metal3 pieces: track ends and stripe gaps
            xl = xl if xl == rr[0] else xl - 0.19
            xr = max(xr, xl + 0.6) if xr == rr[2] else xr + 0.19     # east end stub: >= 0.6 long (Metal3 min area)
            F.p("metal3", (xl, rr[1], xr, rr[3]), net)
        for a, b in hops:
            F.p("metal4", (a - 0.19, jy - 0.14, b + 0.19, jy + 0.14), net)
            for vx in (a, b):
                F.p("via3", (vx - 0.14, jy - 0.14, vx + 0.14, jy + 0.14), net)
        for i, (lay2, q, n2) in enumerate(list(F.shapes)):
            cx = round((q[0] + q[2]) / 2, 3)
            if lay2 == "via2" and n2 == net and q[1] == round(jy - 0.14, 3) and any(a < cx < b for a, b in hops):
                F.p("metal3", (cx - 0.3, jy - 0.14, cx + 0.3, jy + 0.14), net)
                F.p("via3", q, net)
    # west join lines (Metal2) of the shared nets, row 0 track -> row 3 track
    xw = {k: gx(ax0 - 0.69 - 0.7 * j) for j, k in enumerate(sorted(SHARED))}
    d1y = C.instances()["d1"][2]
    for k, net in SHARED.items():
        ya = ay0 + fp.row_trk0(0) + TRKP * k
        if k <= 3 and C.PH_MOVE.get("dend_d1"):     # rt_out joins continue down to west-edge D1 inputs
            ya = d1y + 99.5
        yb = fp.row_y0(3) + fp.row_trk0(3) + TRKP * k
        F.p("metal2", (xw[k] - 0.14, ya - 0.2, xw[k] + 0.14, yb + 0.2), net)
    # column-bottom terminals (row 0 cells): column lines enter from below on Metal2
    for c in range(4):
        cell = fp.slot_cell(fp.cell_at(0, c)[1])
        pins = geo(cell)["pins"]
        sx = ax0 + c * fp.SLOT_W
        # en_c enters at the TOP of the array (keeps the bias channel for the analog lines)
        q = [q for q in geo(fp.slot_cell(fp.cell_at(3, c)[1]))["pins"]["en"][0]["rects"] if q[3] >= fp.ROW_H[3] - 0.01][0]
        yt3 = ay1
        F.p("metal2", (sx + q[0], yt3 - 0.02, sx + q[2], yt3 + 0.7), f"en_c{c}")
        F.term(f"en_c{c}", [("metal2", (sx + q[0], yt3 + 0.42, sx + q[2], yt3 + 0.7))])
        for ln in C.COLUMN_NETS + ["aux"]:
            rr = pins[ln][0]["rects"]
            xs = [q for q in rr if q[1] <= 0.01]
            q = min(xs, key=lambda q: q[2] - q[0])
            net = {"en": f"en_c{c}", "aux": f"aux{c}"}.get(ln, ln)
            if net in C.FLOAT_AUX:
                continue
            F.p("metal2", (sx + q[0], ay0 - 0.7, sx + q[2], ay0 + 0.02), net)      # stub below the array
            F.term(net, [("metal2", (sx + q[0], ay0 - 0.7, sx + q[2], ay0 - 0.42))])
    # ---- power above the array: Metal1 VSS strip on the row-3 ring, vdd column stubs, Metal3 buses
    yt = ay1
    F.p("metal1", (ax0, yt - 0.1, ax1, yt + 0.6), "VGND")
    VDDB, VSSB = (315.1, 315.9), (316.2, 317.0)
    F.p("metal3", (1.3, VDDB[0], 125.0, VDDB[1]), "VDPWR")
    F.p("metal3", (4.3, VSSB[0], 125.0, VSSB[1]), "VGND")
    for c in range(4):
        cell = fp.slot_cell(fp.cell_at(3, c)[1])
        q = geo(cell)["pins"]["vdd"][0]["rects"][0]
        sx = ax0 + c * fp.SLOT_W
        F.p("metal2", (sx + q[0], yt, sx + q[2], VDDB[1]), "VDPWR")
        F.via("via2", sx + (q[0] + q[2]) / 2, sum(VDDB) / 2, "VDPWR")
        for xo in (5.0, 12.0):                                    # VSS drops from the ring strip
            x = sx + xo
            F.via("via1", x, yt + 0.25, "VGND")
            F.p("metal2", (x - 0.14, yt + 0.05, x + 0.14, VSSB[1]), "VGND")
            F.via("via2", x, sum(VSSB) / 2, "VGND")
    for net, x, w in fp.STRIPES:
        if x < 126:
            yb = VDDB if net == "VDPWR" else VSSB
            F.via("via3", x + w / 2, sum(yb) / 2, net)
    return VDDB, VSSB


# ======================================================================== std cells
def stdcells(F, VDDB, VSSB):
    sc = json.loads((C.WORK / "geo" / "stdcells.json").read_text())
    S = C.std_cells()
    for inst, (cell, x, y) in S.items():
        F.cells.append((inst, C.SC + cell, x, y))
    # ---- tie row: continuous rails, drops into the array power buses, Z landing pads
    ty = fp.TIE_ROW_Y
    xs = [x for (cell, x, y) in S.values() if y == ty]
    x0, x1 = min(xs), max(x for (cell, x, y) in S.values() if y == ty) + C.SC_W["filltie"]
    F.p("metal1", (x0, ty - 0.3, x1, ty + 0.3), "VGND")
    F.p("metal1", (x0, ty + 3.62, x1, ty + 4.22), "VDPWR")
    for i in range(8):
        _, x, _ = S[f"tie{i}"]
        xv = x + 0.40                                            # VSS drop (tieh west end)
        F.via("via1", xv, ty, "VGND")
        F.p("metal2", (xv - 0.14, sum(VSSB) / 2 - 0.2, xv + 0.14, ty + 0.2), "VGND")
        F.via("via2", xv, sum(VSSB) / 2, "VGND")
        xd = x + C.SC_W["tieh"] + 0.84                          # VDD drop (filltie)
        F.via("via1", xd, ty + 3.92, "VDPWR")
        F.p("metal2", (xd - 0.14, sum(VDDB) / 2 - 0.2, xd + 0.14, ty + 4.12), "VDPWR")
        F.via("via2", xd, sum(VDDB) / 2, "VDPWR")
        landing(F, sc, "tieh", x, ty, "Z", f"uio_oe[{i}]", (1.40, 2.85))
    # ---- glue row: rails, stacks to the macro strap-pair stripes, pin landing pads
    gx0, gy0 = fp.GLUE_ROW
    gxs = [x + C.SC_W[cell] for (cell, x, y) in S.values() if y == gy0]
    gx1 = max(gxs)
    F.p("metal1", (gx0, gy0 - 0.3, gx1, gy0 + 0.3), "VGND")
    F.p("metal1", (gx0, gy0 + 3.62, gx1, gy0 + 4.22), "VDPWR")
    for net, x, w in fp.STRIPES:
        if gx0 + 0.5 < x + w / 2 < gx1 - 0.5:
            F.stack(x + w / 2, gy0 + (3.92 if net == "VDPWR" else 0.0), net)
    nets = C.nets()
    conn = {}
    for net, lst in nets.items():
        for inst, pin in lst:
            conn[(inst, pin)] = net
    PICK = {"or4_1": {"A1": (0.84, 2.6), "A2": (2.02, 1.9), "A3": (3.14, 2.9), "A4": (4.26, 1.9), "Z": (6.32, 2.9)},
            "nor3_1": {"A3": (0.80, 1.975), "A2": (1.96, 2.9), "A1": (3.08, 1.9), "ZN": (3.69, 2.95)},
            "inv_1": {"I": (0.87, 1.7), "ZN": (1.43, 2.9)}}
    for inst, (cell, x, y) in S.items():
        if y != gy0 or cell not in PICK:
            continue
        for pin, pt in PICK[cell].items():
            landing(F, sc, cell, x, y, pin, conn[(inst, pin)], pt)


def landing(F, sc, cell, x, y, pin, net, pt):
    """via1 + Metal2 pad on a std-cell Metal1 pin at cell-local point pt; Metal1 pad clipped to the pin."""
    px, py = pt
    rr = sc[C.SC + cell]["pins"][pin]
    q = [r for r in rr if r[0] - 1e-6 <= px <= r[2] + 1e-6 and r[1] - 1e-6 <= py <= r[3] + 1e-6]
    assert q, (cell, pin, pt)
    q = q[0]
    m1 = (max(q[0], px - 0.2), max(q[1], py - 0.2), min(q[2], px + 0.2), min(q[3], py + 0.2))
    assert m1[2] - m1[0] >= 0.30 and m1[3] - m1[1] >= 0.30, (cell, pin, m1)
    X, Y = x + px, y + py
    F.p("metal1", (x + m1[0], y + m1[1], x + m1[2], y + m1[3]), net)
    F.p("via1", (X - 0.13, Y - 0.13, X + 0.13, Y + 0.13), net)
    F.p("metal2", (X - 0.2, Y - 0.2, X + 0.2, Y + 0.2), net)
    F.term(net, [("metal2", (X - 0.2, Y - 0.2, X + 0.2, Y + 0.2))])


# ======================================================================== block power, analog pins
def stripes(F):
    for net, x, w in fp.STRIPES:
        r = (x, fp.STRIPE_Y[0], x + w, fp.STRIPE_Y[1])
        F.p("metal4", r, net)
        F.ports.append((net, "metal4", R(*r), "ground" if net == "VGND" else "power"))


def stripe_at(net, xc):
    for n, x, w in fp.STRIPES:
        if n == net and x <= xc <= x + w:
            return x + w / 2
    raise ValueError((net, xc))


def blocks_power(F):
    I = C.instances()
    # ---- B1: VGND stripe over its east vss pin (Metal3), vdd pin stubbed east to the VDPWR stripe
    bx, by = I["b1"][1:]
    g = geo("bias_b1")["pins"]
    vss = g["vss"][0]["rects"]; vdd = g["vdd"][0]["rects"]
    # its vss pin is a 0.3 um Metal3 wire at local x 262.45-262.75 (tile 342.45-342.75), y 58.75-64.8
    vx = bx + 262.6
    F.p("metal4", (vx - 0.25, by + 58.9, stripe_at("VGND", 343.0), by + 64.6), "VGND")
    for yy in (by + 59.5, by + 61.0, by + 62.5, by + 64.0):
        F.p("via3", (vx - 0.14, yy - 0.14, vx + 0.14, yy + 0.14), "VGND")
    vy = by + (vdd[0][1] + vdd[0][3]) / 2
    xr = stripe_at("VDPWR", 345.4)
    F.p("metal3", (bx + 263.41, vy - 0.2, xr + 0.25, vy + 0.2), "VDPWR")
    F.via("via3", xr, vy, "VDPWR")
    # B1 west power entry (PEX IR drop: receivers ~22 mV / 14 mV off with east-edge-only power): via3 drops from the
    # x 121.0 VDPWR / 123.6 VGND stripes onto B1's 0.4 um Metal3 via pads under them (net trace of the 946cd68 GDS)
    for (lx, ly), net in (((41.6, 28.2), "VDPWR"), ((41.6, 33.0), "VDPWR"), ((44.55, 37.65), "VGND"),
                          ((44.2, 43.7), "VGND")):
        F.p("via3", (bx + lx - 0.14, by + ly - 0.14, bx + lx + 0.14, by + ly + 0.14), net)
    # ---- R1: vdd/vss Metal3 rails extended down into CH_BOT, jogs to the strap-pair-2 / east stripes
    rx, ry = I["r1"][1:]
    gr = geo("r1_ua1")["pins"]
    bb = lambda rs: (min(q[0] for q in rs), min(q[1] for q in rs), max(q[2] for q in rs), max(q[3] for q in rs))
    vd, vs = bb(gr["vdd"][0]["rects"]), bb(gr["vss"][0]["rects"])
    yv, ys = 9.6, 7.0
    F.p("metal3", (rx + vd[0], yv - 0.6, rx + vd[2], ry + 14.5), "VDPWR")
    F.p("metal3", (rx + vs[0], ys - 0.6, rx + vs[2], ry + 14.5), "VGND")
    xa = stripe_at("VDPWR", 286.7)
    F.p("metal3", (xa + 0.35, yv - 0.6, rx + vd[2], yv + 0.6), "VDPWR")
    F.via("via3", xa + 0.53, yv - 0.25, "VDPWR", pads=("hi",))
    F.via("via3", xa + 0.53, yv + 0.3, "VDPWR", pads=("hi",))
    xb = stripe_at("VGND", 343.0)
    F.p("metal3", (rx + vs[0], ys - 0.6, xb + 0.3, ys + 0.6), "VGND")
    F.via("via3", xb, ys - 0.25, "VGND", pads=("hi",))
    F.via("via3", xb, ys + 0.3, "VGND", pads=("hi",))
    # ---- ua[0]: Metal4 from the tile pin up onto B1's Metal3 pad, via3 row
    ua0 = fp.PINS_BOT["ua[0]"]
    pad = g["ua0"][0]["rects"][0]
    py = by + (pad[1] + pad[3]) / 2
    F.p("metal4", (ua0 - 3.0, 0.0, ua0 + 3.0, py + 0.3), "ua[0]")
    F.p("metal3", (ua0 - 2.9, py - 0.3, ua0 + 2.9, py + 0.3), "ua[0]")
    x = ua0 - 2.6
    while x <= ua0 + 2.61:
        F.p("via3", (x - 0.14, py - 0.14, x + 0.14, py + 0.14), "ua[0]")
        x += 0.6
    # ---- D1 / AdEx / tau cells: Metal1 stubs off their west edges + via stacks into the nearest stripes
    def m1stub(inst, y_local, net, half=0.3):
        cell, x0, y0 = I[inst]
        y = y0 + y_local
        xs = stripe_at(net, {"VDPWR": 2.0, "VGND": 5.0}[net] if x0 < 40 else
                       {"VDPWR": 50.8, "VGND": 53.4}[net] if x0 < 100 else {"VDPWR": 121.8, "VGND": 124.4}[net])
        F.p("metal1", (xs - 0.3, y - half, x0 + 0.3, y + half), net)
        F.stack(xs, y, net)
    gd = geo("dend_d1")["pins"]
    for p in gd["vdd"]:
        if p["layer"] == "metal1":
            m1stub("d1", p["pt"][1], "VDPWR")
    m1stub("d1", 0.3, "VGND")
    cell, x0, y0 = I["tau0"]                                   # tau0: off its EAST edge to the x 53.4 stack
    F.p("metal1", (x0 + 36.7, y0 + 0.0, stripe_at("VGND", 53.4) + 0.3, y0 + 0.6), "VGND")
    m1stub("tau2", 0.3, "VGND")
    ga = geo("adex_a1")["pins"]
    m1stub("ax", 0.3, "VGND")


def fixed():
    F = Fix()
    stripes(F)
    VDDB, VSSB = array(F)
    stdcells(F, VDDB, VSSB)
    blocks_power(F)
    return F


if __name__ == "__main__":
    F = fixed()
    print(len(F.shapes), "shapes;", len(F.cells), "cells;", sum(len(v) for v in F.terms.values()), "terminals on",
          len(F.terms), "nets")
