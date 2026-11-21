"""B1 bias generator leaf cells, part 2: bias_rails, bias_master, vref_string64, vdac6, bias_rangegen.

    python3 leafs2.py <cell>      (inside the EDA container, from layout/bias; build.sh calls it)

Same conventions as leafs.py (origin lower-left, p-tap ring, Metal1/Metal2 only, Metal2 pin pads).
Devices are placed in rows by place_row(); the router (router.py) makes every connection that is not
drawn explicitly (resistor serpentines, vdac gate rails).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cellgen import Cell, snap, load_dev, need_mos, need_res   # noqa: E402
from leafs import RING, pin, frame, finish                       # noqa: E402

RUNIT_L, RSEG_L = 14.555, 1.31


def place_row(c, y, devs, x0, x1, gap_x=1.0, align="center"):
    """devs: (inst, model, w, l, nf, strips, gates, head[, kw]).  Returns (top y, [centre x])."""
    exts = [c.mos_extent(d[1], d[2], d[3], d[4], d[7]) for d in devs]
    widths = [e[2] - e[0] for e in exts]
    total = sum(widths) + gap_x * (len(devs) - 1)
    x = (x0 + x1) / 2 - total / 2 if align == "center" else x0
    bot = min(e[1] for e in exts)
    top = max(e[3] for e in exts)
    cy = snap(y - bot)
    xs = []
    for d, e, wd in zip(devs, exts, widths):
        cx = snap(x - e[0])
        kw = d[8] if len(d) > 8 else {}
        c.mos(d[0], d[1], d[2], d[3], cx, cy, d[5], d[6], nf=d[4], head=d[7], **kw)
        xs.append(cx)
        x += wd + gap_x
    return cy + top, xs, cy


def res_extent(w, l):
    lc = load_dev(need_res(w, l))
    return lc["bbox"]


# ============================================================================ bias_rails
def rails(compact=False):
    c = Cell("bias_rails_c" if compact else "bias_rails")
    nodes = ["top", "vsp", "a1", "a2", "a3", "vgln", "b1", "vglp", "c1", "c2", "vsn", "vss"]
    named = {"top", "vsp", "vgln", "vglp", "vsn", "vss"}
    bb = res_extent(1.0, RUNIT_L)
    hh = bb[3]
    W = 31.0
    pitch = 2.2
    x0 = RING + 1.6
    yres = RING + 1.6 + hh
    heads = {}
    for i in range(11):
        x = x0 + i * pitch
        a, b = nodes[i], nodes[i + 1]
        bot, topn = (a, b) if i % 2 == 0 else (b, a)
        r = c.res(f"R{i}", 1.0, RUNIT_L, x, yres, topn, bot, term=False)
        heads[(i, "b")] = (r["heads"][0], bot)
        heads[(i, "t")] = (r["heads"][1], topn)
    # serpentine jumpers (Metal1) and terminals for the named nodes
    for i in range(10):
        side = "t" if i % 2 == 0 else "b"
        h1, n1 = heads[(i, side)]
        h2, n2 = heads[(i + 1, side)]
        assert n1 == n2
        j = c.p("metal1", (h1[0], h1[1], h2[2], h1[3]), n1)
        if n1 in named:
            c.term(n1, [("m1", j)])
    c.term("top", [("m1", heads[(0, "b")][0])])
    c.term("vss", [("m1", heads[(10, "t")][0])])
    ytop_res = yres + hh
    # keep everything else 0.8 um away from the resistor bodies/heads (HRES spacing)
    rx1 = x0 + 10 * pitch + 0.5
    c.forbid_box(("m1",), (x0 - 1.3, RING + 0.8, rx1 + 0.8, ytop_res + 0.8), allowed=named)
    if compact:
        # M3 re-pack (b1a): header pfet in the free column east of the string, decaps above, pins on top
        e = c.mos_extent("pfet", 4.0, 0.5, 1, "top")
        xh = snap(rx1 + 0.8 + 1.6 - e[0])
        yh0 = RING + 2.4
        cyh = yh0 + 1.2 - e[1]
        c.mos("HDR", "pfet", 4.0, 0.5, xh, cyh, ["vdd", "top"], "en_b", head="top")
        yt = cyh + e[3]
        nw = (xh + e[0] - 1.0, yh0, xh + e[2] + 1.0, yt + 2.0)
        c.p("nwell", nw)
        c.tap("n", (nw[0] + 1.0, yt + 0.8, nw[2] - 1.0, yt + 1.4), "vdd")
    y = ytop_res + 2.0
    e1 = c.mos_extent("pfet", 10.0, 10.0, 1, "top")
    cyc = y + 1.4 - e1[1]
    xc1 = RING + 1.6 + 1.0 - e1[0]
    xc2 = xc1 + (e1[2] - e1[0]) + 4.2
    c.mos("C1", "pfet", 10.0, 10.0, xc1, cyc, ["vss", "vss"], "vsn", head="top")
    c.mos("C2", "pfet", 10.0, 10.0, xc2, cyc, ["vsp", "vsp"], "vdd", head="top")
    ytop = cyc + e1[3]
    for xc, net in ((xc1, "vss"), (xc2, "vsp")):
        nw = (xc + e1[0] - 1.0, y, xc + e1[2] + 1.0, ytop + 2.0)
        c.p("nwell", nw)
        c.tap("n", (nw[0] + 1.0, ytop + 0.8, nw[2] - 1.0, ytop + 1.4), net)
    if compact:
        y = ytop + 2.0 + 1.0
    else:
        y = ytop + 2.0 + 1.6
        # header pfet in its own vdd n-well
        e = c.mos_extent("pfet", 4.0, 0.5, 1, "top")
        cyh = y + 1.2 - e[1]
        c.mos("HDR", "pfet", 4.0, 0.5, W / 2 - 4, cyh, ["vdd", "top"], "en_b", head="top")
        yt = cyh + e[3]
        nw = (W / 2 - 4 + e[0] - 1.0, y, W / 2 - 4 + e[2] + 1.0, yt + 2.0)
        c.p("nwell", nw)
        c.tap("n", (nw[0] + 1.0, yt + 0.8, nw[2] - 1.0, yt + 1.4), "vdd")
        y = yt + 2.0 + 0.8
    pins = ["vsn", "vsp", "vgln", "vglp", "en_b", "vdd"]
    for k, net in enumerate(pins):
        pin(c, net, 2.5 + k * 3.8, y + 0.4, "power" if net == "vdd" else "signal")
    H = snap(y + 0.8 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6)


# ============================================================================ bias_master
def master():
    c = Cell("bias_master")
    W = 32.0
    XL, XR = RING + 0.9, W - RING - 0.9 - 5.0      # right 5 um: resistor column
    y = RING + 0.9
    # bottom pins: pad + digital mode lines
    for k, net in enumerate(["pad", "s0", "s1", "stim", "intref", "en"]):
        pin(c, net, 2.6 + k * 2.4, y + 0.3)
    y += 0.6 + 1.4
    # secondary ESD clamps on 'pin' (10 x 1 um each): n+/psub to vss, p+/n-well to vdd
    nd = (XL + 0.6, y, XL + 10.6, y + 1.0)
    c.p("ndiode", nd)
    c.p("ndiodec", (nd[0] + 0.185, nd[1] + 0.185, nd[2] - 0.185, nd[3] - 0.185))
    m = c.p("metal1", (nd[0] + 0.12, nd[1] + 0.12, nd[2] - 0.12, nd[3] - 0.12), "pin", term=True)
    x0n = XL + 11.8
    nw = (x0n, y - 1.0, x0n + 12.2, y + 3.0)
    c.p("nwell", nw)
    pdr = (x0n + 1.1, y, x0n + 11.1, y + 1.0)
    c.p("pdiode", pdr)
    c.p("pdiodec", (pdr[0] + 0.185, pdr[1] + 0.185, pdr[2] - 0.185, pdr[3] - 0.185))
    c.p("metal1", (pdr[0] + 0.12, pdr[1] + 0.12, pdr[2] - 0.12, pdr[3] - 0.12), "pin", term=True)
    c.tap("n", (x0n + 1.1, y + 1.6, x0n + 11.1, y + 2.2), "vdd")
    y = nw[3] + 1.4
    # n rows
    sw = [("S0", "nfet", 4.0, 0.5, 1, ["pin", "nd"], "s0", "top"),
          ("S1", "nfet", 8.0, 0.5, 1, ["pin", "nx"], "s1", "top"),
          ("STN", "nfet", 2.0, 0.5, 1, ["pin", "ua0_stim"], "stim", "top"),
          ("PDN", "nfet", 4.0, 0.5, 1, ["nd", "vss"], "en_b", "top")]
    y, _, _ = place_row(c, y, sw, XL, XR, 1.4)
    y += 1.3
    inv = [(f"I{n}n", "nfet", 0.5, 0.28, 1, ["vss", o], i, "top") for n, i, o in
           (("EN", "en", "en_b"), ("ST", "stim", "stim_b"), ("IR", "intref", "intref_b"))]
    y, _, _ = place_row(c, y, inv, XL, XR, 2.4)
    y += 1.3
    diode = lambda nm, g: (nm, "nfet", 2.0, 2.0, 8, ["vss", g] * 4 + ["vss"], g, "bar")
    y, _, _ = place_row(c, y, [diode("DXa", "nx")], XL, XR)
    y += 1.3
    y, _, _ = place_row(c, y, [diode("DXb", "nx")], XL, XR)
    y += 1.3
    y, _, _ = place_row(c, y, [diode("Da", "nd")], XL, XR)
    y += 1.3
    y, _, _ = place_row(c, y, [diode("Db", "nd")], XL, XR)
    y += 1.3
    outs = [("ON", "nfet", 2.0, 2.0, 1, ["vss", "in_n"], "nd", "top"),
            ("OP", "nfet", 2.0, 2.0, 1, ["vss", "pd"], "nd", "top"),
            ("OS", "nfet", 2.0, 2.0, 1, ["vss", "vbp_st"], "nd", "top"),
            ("OX", "nfet", 2.0, 2.0, 1, ["vss", "px"], "nx", "top")]
    y, _, _ = place_row(c, y, outs, XL, XR, 1.2)
    # p rows in one vdd n-well
    y += 1.6
    nwb = y - 0.6
    y += 0.6
    y, _, _ = place_row(c, y, [("QX", "pfet", 2.0, 2.0, 4, ["nd", "vdd", "px", "vdd", "nd"], "px", "bar")], XL, XR)
    y += 1.3
    y, _, _ = place_row(c, y, [("PD", "pfet", 2.0, 2.0, 4, ["vdd", "in_p", "vdd", "pd", "vdd"], "pd", "bar")], XL, XR)
    y += 1.3
    prow = [("STP", "pfet", 4.0, 0.5, 1, ["pin", "ua0_stim"], "stim_b", "top"),
            ("SWI", "pfet", 2.0, 0.5, 1, ["iint", "nd"], "intref_b", "top")]
    prow += [(f"I{n}p", "pfet", 1.0, 0.28, 1, ["vdd", o], i, "top") for n, i, o in
             (("EN", "en", "en_b"), ("ST", "stim", "stim_b"), ("IR", "intref", "intref_b"))]
    y, _, _ = place_row(c, y, prow, XL, XR, 1.0)
    c.tap("n", (XL + 0.5, y + 0.6, XR - 0.5, y + 1.2), "vdd")
    c.p("nwell", (XL - 0.5, nwb, XR + 0.5, y + 1.8))
    ytop_dev = y + 1.8
    # resistor on the right: RS (pad -> pin, W=4, 1 kOhm), next to the pad pin at the bottom
    xr = W - RING - 2.8
    brs = res_extent(4.0, 3.97)
    rs = c.res("RS", 4.0, 3.97, xr - 0.6, RING + 2.2 - brs[1], "pin", "pad")
    c.forbid_box(("m1",), (xr - 3.0, RING + 0.9, W - RING - 0.3, rs["bbox"][3] + 0.8), allowed={"pad", "pin"})
    y = ytop_dev + 1.0
    for k, net in enumerate(["in_n", "in_p", "vbp_st", "iint", "ua0_stim", "en_b", "vdd"]):
        pin(c, net, 2.4 + k * 3.2, y + 0.3, "power" if net == "vdd" else "signal")
    H = snap(y + 0.6 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6, first=("nd", "nx"))


# ============================================================================ vref_string64
def vref():
    """Tap segments stacked in 4 columns (merged heads), 5 x 15 kOhm strips, pfet header."""
    c = Cell("vref_string64")
    bs = res_extent(1.0, RSEG_L)
    seg_pitch = 2 * (bs[3] - 0.0) - 2 * 0.61 + 0.86 - (bs[3] * 2 - 0.61 * 2 - RSEG_L) if False else RSEG_L + 0.86
    hl = RSEG_L / 2 + 0.43            # head contact centre offset from the resistor centre
    colp = 3.2
    x0 = RING + 2.2
    y0 = RING + 2.4
    W = None
    taps = {}
    tap_xy = {}
    heads_of = {}
    # columns 0..3: col k holds segments t(16k) .. t(16k+16) (col 3: 15 segments)
    for col in range(4):
        x = x0 + col * colp
        nseg = 16 if col < 3 else 15
        for s in range(nseg):
            k = 16 * col + s                      # segment RS_k : t(k) -> t(k+1)
            pos = s if col % 2 == 0 else (nseg - 1 - s)
            if col == 3:
                pos = 15 - s                      # col 3 runs downwards from the top like col 1
            yc = y0 + hl + pos * seg_pitch
            if (col % 2 == 0):
                bot, top = f"t{k}", f"t{k + 1}"
            else:
                bot, top = f"t{k + 1}", f"t{k}"
            r = c.res(f"RS{k}", 1.0, RSEG_L, x, yc, top, bot, term=False)
            for h, net in zip(r["heads"], (bot, top)):
                tap_xy.setdefault(net, h)
                if h not in heads_of.setdefault(net, []):
                    heads_of[net].append(h)
    colh = y0 + 2 * hl + 15 * seg_pitch
    # column jumpers: t16 (top of col0/1), t32 (bottom col1/2), t48 (top col2/3)
    for net in ("t16", "t32", "t48"):        # column ends: second head joined by the router
        for h in heads_of[net][1:]:
            if abs(h[1] - tap_xy[net][1]) > 0.5 or abs(h[0] - tap_xy[net][0]) > 0.5:
                c.term(net, [("m1", h)])
    for k in range(64):
        h = tap_xy[f"t{k}"]
        cx, cy = (h[0] + h[2]) / 2, (h[1] + h[3]) / 2
        c.via1(cx + 0.0, cy, f"t{k}")
        pr = (cx - 0.2, cy - 0.2, cx + 0.2, cy + 0.2)
        c.label(f"t{k}", "metal2", pr, "signal")
        c.term(f"t{k}", [("m2", pr)])
    # 15 kOhm strips: RB0 (vss -> t0) and RT0..3 (t63 -> u1 -> u2 -> u3 -> top)
    bu = res_extent(1.0, RUNIT_L)
    xs = x0 + 4 * colp + 0.6
    yb = y0 + (bu[3] - bu[1]) / 2
    names = [("RB0", "t0", "vss"), ("RT0", "u1", "t63"), ("RT1", "u2", "u1"), ("RT2", "u3", "u2"), ("RT3", "top", "u3")]
    for i, (nm, tn, bn) in enumerate(names):
        x = xs + (i % 3) * 2.4
        yc = yb if i < 3 else yb + (bu[3] - bu[1]) + 1.6
        r = c.res(nm, 1.0, RUNIT_L, x, yc, tn, bn, term=True)
    xmax = xs + 2 * 2.4 + 1.0
    W = snap(xmax + 2.2 + RING + 6.0)
    ytop = max(colh, yb + 2 * (bu[3] - bu[1]) + 1.6) + 1.2
    c.forbid_box(("m1",), (x0 - 1.0, y0 - 1.0, xmax + 0.8, ytop), allowed=None,
                 only={"vdd", "en_b"})
    # header in a vdd n-well at the right
    e = c.mos_extent("pfet", 4.0, 0.5, 1, "top")
    xh = W - RING - 2.2 - e[2]
    cyh = y0 + 2.0 - e[1]
    c.mos("HDR", "pfet", 4.0, 0.5, xh, cyh, ["vdd", "top"], "en_b", head="top")
    yt = cyh + e[3]
    nw = (xh + e[0] - 1.0, y0, xh + e[2] + 1.0, yt + 2.0)
    c.p("nwell", nw)
    c.tap("n", (nw[0] + 1.0, yt + 0.8, nw[2] - 1.0, yt + 1.4), "vdd")
    pin(c, "en_b", xh, yt + 3.0)
    pin(c, "vdd", xh + 1.2, yt + 4.4, "power")
    H = snap(max(ytop, yt + 5.0) + 0.8 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6)


# ============================================================================ vdac6
def vdac6():
    """Binary nfet tree: rows L0a (even pairs), L0b (odd pairs), L1, L2, L3-5, inverters.
    Gate rails (c_l / cb_l) are drawn Metal1 lines over the heads ('alt': finger 0 = cb on top,
    finger 1 = c below); the router makes the tap and tree connections."""
    c = Cell("vdac6")
    TP = 2.0                     # pair pitch in L0
    x0 = RING + 2.0
    W = snap(x0 + 32 * TP + 1.0 + RING + 0.6)
    dev = lambda nm, a, o, b, l: (nm, "nfet", 0.5, 0.28, 2, [a, o, b], [f"cb{l}", f"c{l}"], "alt")
    e = c.mos_extent("nfet", 0.5, 0.28, 2, "alt")
    rails = {}

    def row(y, items, lev_of):
        """items: list of (x, dev tuple); returns top y; draws gate rails per level segment."""
        cy = snap(y - e[1])
        segs = {}
        for x, d in items:
            r = c.mos(d[0], d[1], d[2], d[3], x, cy, d[5], d[6], nf=2, head="alt")
            l = lev_of(d)
            g = r["gates"]
            s = segs.setdefault(l, [1e9, -1e9, g[0][1], g[1][1]])
            s[0] = min(s[0], g[0][0], g[1][0])
            s[1] = max(s[1], g[0][2], g[1][2])
        lmin = min(segs, key=lambda k: segs[k][0])
        segs[lmin][0] = RING + 1.0           # leftmost segment runs to the left edge: free via landing
        for l, (a, b, yt, yb) in segs.items():
            for yy, net in ((yt, f"cb{l}"), (yb, f"c{l}")):
                r = c.p("metal1", (a, yy, b, yy + 0.38), net)
                c.term(net, [("m1", r)])
        return cy + e[3]
    y = RING + 1.0
    # inverters at the bottom: nfet row, pfet row (vdd well)
    invn = [(f"IC{b}n", "nfet", 0.5, 0.28, 1, ["vss", f"cb{b}"], f"c{b}", "top") for b in range(6)]
    invp = [(f"IC{b}p", "pfet", 1.0, 0.28, 1, ["vdd", f"cb{b}"], f"c{b}", "top") for b in range(6)]
    # pins c0..c5, out, vdd at the bottom
    for b in range(6):
        pin(c, f"c{b}", x0 + 2.0 + b * 6.0, y + 0.3)
    pin(c, "out", x0 + 2.0 + 6 * 6.0, y + 0.3)
    pin(c, "vdd", x0 + 2.0 + 7 * 6.0, y + 0.3, "power")
    y += 0.5 + 1.3
    y, _, _ = place_row(c, y, invn, x0, W - RING - 1.0, 5.0)
    y += 2.0
    nwb = y - 0.7
    y, _, _ = place_row(c, y, invp, x0, W - RING - 1.0, 4.6)
    c.tap("n", (x0 + 0.5, y + 0.5, W - RING - 2.1, y + 1.1), "vdd")
    c.p("nwell", (x0 - 0.6, nwb, W - RING - 1.0, y + 1.8))
    y += 1.8 + 1.8
    # tree rows, top-down order of levels: L5..L3 row, L2, L1, L0b, L0a (taps at the top)
    px = lambda j: x0 + 0.8 + j * TP                 # L0 pair j centre
    xs = {0: [px(j) for j in range(32)]}
    for l in range(1, 6):
        xs[l] = [(xs[l - 1][2 * i] + xs[l - 1][2 * i + 1]) / 2 for i in range(len(xs[l - 1]) // 2)]
    node = lambda l, i: "out" if l == 5 else f"n{l}_{i}"
    inp = lambda l, i: (f"t{2*i}", f"t{2*i+1}") if l == 0 else (node(l - 1, 2 * i), node(l - 1, 2 * i + 1))
    D = lambda l, i: dev(f"T{l}_{i}", inp(l, i)[0], node(l, i), inp(l, i)[1], l)
    levof = lambda d: int(d[6][0][2])
    # L3..L5 in one row (non-overlapping x: L5 shifted)
    # L3 row with L5 at the far right (separate rail segments), then L4 alone
    items = [(xs[3][i], D(3, i)) for i in range(4)] + [(xs[3][3] + 5.5, D(5, 0))]
    y = row(y, items, levof) + 1.6
    y = row(y, [(xs[4][0], D(4, 0)), (xs[4][1], D(4, 1))], levof) + 1.6
    y = row(y, [(xs[2][i], D(2, i)) for i in range(8)], levof) + 2.0
    y = row(y, [(xs[1][i], D(1, i)) for i in range(16)], levof) + 2.0
    y = row(y, [(xs[0][j], D(0, j)) for j in range(1, 32, 2)], levof) + 2.2
    y = row(y, [(xs[0][j], D(0, j)) for j in range(0, 32, 2)], levof) + 1.8
    # tap pins along the top, t_k above its strip
    for k in range(64):
        j = k // 2
        pin(c, f"t{k}", xs[0][j] + (-0.4 if k % 2 == 0 else 0.4), y + 0.3)
    H = snap(y + 0.5 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.5)


# ============================================================================ bias_rangegen
def rangegen():
    c = Cell("bias_rangegen")
    W = 68.0
    XL, XR = RING + 0.9, W - RING - 0.9
    G = 1.1
    y = RING + 0.9
    bot_pins = ["in_n", "vgln", "vsn"] + [f"vgn{r}" for r in range(6)]
    for k, net in enumerate(bot_pins):
        pin(c, net, 3.0 + k * 6.5, y + 0.3)
    y += 0.6 + G

    def shunts(pol, pre, inp, dump, tap):
        nd = lambda k: inp if k == 0 else f"{pre}{k}"
        m = pol + "fet"
        g = "vgln" if pol == "n" else "vglp"
        grp = [(f"{pre}SH01", ["%s" % nd(0), dump, nd(1)]), (f"{pre}SH2", [nd(2), dump])]
        for r in range(5):
            k = 3 * r + 3
            grp.append((f"{pre}SH{k}", [nd(k), f"{tap}{r}"]))
            grp.append((f"{pre}SH{k+1}{k+2}", [nd(k + 1), dump, nd(k + 2)]))
        grp.append((f"{pre}SH18T", [f"{tap}5", nd(18), dump]))
        return [(nm, m, 2.0, 2.0, len(st) - 1, st, g, "top") for nm, st in grp]

    def ladder(pol, pre, inp):
        g = "vgln" if pol == "n" else "vglp"
        return [(f"{pre}SE", pol + "fet", 4.0, 2.0, 18, [inp] + [f"{pre}{k}" for k in range(1, 19)], g, "bar")]

    # ---------------- n side (substrate) ----------------
    y, _, _ = place_row(c, y, ladder("n", "nn", "in_n"), XL, XR) ; y += G
    sh = shunts("n", "nn", "in_n", "vdd", "xp")
    y, _, _ = place_row(c, y, sh, XL, XR, 0.45); y += G
    c.tap("p", (XL + 1.0, y - 0.5, XR - 1.0, y + 0.1), "vss"); y += 0.6 + 0.4
    dn = lambda r: (f"DN{r}", "nfet", 2.0, 2.0, 8, ["vsn", f"xn{r}"] * 4 + ["vsn"], f"vgn{r}", "bar")
    for r in (0, 3):
        y, _, _ = place_row(c, y, [dn(r), dn(r + 1), dn(r + 2)], XL, XR, 1.4); y += G
        if r == 0:      # substrate tap in the middle of the n side (DF.14: <= 20 um to a p-tap)
            c.tap("p", (XL + 1.0, y - 0.5, XR - 1.0, y + 0.1), "vss"); y += 0.6 + 0.4
    fb = []
    for r in range(6):
        fb.append((f"FN{r}", "nfet", 2.0, 1.0, 1, ["vdd", f"vgn{r}"], f"xn{r}", "top"))
        fb.append((f"BN{r}", "nfet", 2.0, 2.0, 1, [f"vgn{r}", "vss"], "vgn4", "top"))
    y, _, _ = place_row(c, y, fb, XL, XR, 2.4); y += G + 0.6
    # FP followers: pfet with body = source = vgp<r>, each in its own n-well
    e = c.mos_extent("pfet", 2.0, 1.0, 1, "top")
    pitch = (XR - XL) / 6
    cy = y + 0.8 - e[1]
    for r in range(6):
        x = XL + pitch * (r + 0.5) - 0.6
        c.mos(f"FP{r}", "pfet", 2.0, 1.0, x, cy, ["vss", f"vgp{r}"], f"xp{r}", head="top")
        nw = (x + e[0] - 0.9, y, x + e[2] + 0.9 + 2.0, cy + e[3] + 1.2)
        c.p("nwell", nw)
        c.tap("n", (nw[2] - 1.6, nw[1] + 1.0, nw[2] - 1.0, nw[3] - 1.0), f"vgp{r}")
    y = cy + e[3] + 1.2 + 2.0
    # ---------------- p side (one vdd n-well) ----------------
    nwb = y
    y += 0.6
    c.tap("n", (XL + 1.0, y, XR - 1.0, y + 0.6), "vdd")
    y += 0.6 + 1.0
    bp = [(f"BP{r}", "pfet", 2.0, 2.0, 1, ["vdd", f"vgp{r}"], "vgp4", "top") for r in range(6)]
    y, _, _ = place_row(c, y, bp, XL, XR, 3.0); y += G
    dp = lambda r: (f"DP{r}", "pfet", 2.0, 2.0, 8, ["vsp", f"xp{r}"] * 4 + ["vsp"], f"vgp{r}", "bar")
    for r in (0, 3):
        y, _, _ = place_row(c, y, [dp(r), dp(r + 1), dp(r + 2)], XL, XR, 1.4); y += G
    sh = shunts("p", "np", "in_p", "vss", "xn")
    y, _, _ = place_row(c, y, sh, XL, XR, 0.45); y += G
    y, _, _ = place_row(c, y, ladder("p", "np", "in_p"), XL, XR)
    c.tap("n", (XL + 1.0, y + 0.8, XR - 1.0, y + 1.4), "vdd")
    c.p("nwell", (XL - 0.3, nwb, XR + 0.3, y + 2.0))
    y += 2.0 + 1.0
    top_pins = ["in_p", "vglp", "vsp", "vdd"] + [f"vgp{r}" for r in range(6)]
    for k, net in enumerate(top_pins):
        pin(c, net, 3.0 + k * 6.2, y + 0.3, "power" if net == "vdd" else "signal")
    H = snap(y + 0.6 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6)


# ============================================================================ bias_ladder (rev C)
def ladder():
    """Two short R-2R ladders with fixed taps: n side (nodes 0..6, taps 3,5,6 -> pfet diodes -> vgp3/5/6)
    and p side (nodes 0..5, taps 3,5 -> nfet diodes -> vgn3/5).  Same row style as the rev B rangegen."""
    c = Cell("bias_ladder")
    W = 48.0
    XL, XR = RING + 0.9, W - RING - 0.9
    G = 1.1
    y = RING + 0.9
    for k, net in enumerate(["in_n", "vgln", "vsn", "vgn3", "vgn5"]):
        pin(c, net, 3.0 + k * 8.5, y + 0.3)
    y += 0.6 + G
    # ---------------- n side (substrate): n-ladder, shunts, DN diodes, followers ----------------
    nn = lambda k: "in_n" if k == 0 else f"nn{k}"
    y, _, _ = place_row(c, y, [("nnSE", "nfet", 4.0, 2.0, 6, [nn(k) for k in range(7)], "vgln", "bar")], XL, XR)
    y += G
    sh = [("nnSH01", [nn(0), "vdd", nn(1)]), ("nnSH24", [nn(2), "vdd", nn(4)]), ("nnSH3", [nn(3), "xp3"]),
          ("nnSH5", [nn(5), "xp5"]), ("nnSH6T", ["xp6", nn(6), "vdd"])]
    y, _, _ = place_row(c, y, [(nm, "nfet", 2.0, 2.0, len(st) - 1, st, "vgln", "top") for nm, st in sh],
                        XL, XR, 0.8)
    y += G
    c.tap("p", (XL + 1.0, y - 0.5, XR - 1.0, y + 0.1), "vss"); y += 0.6 + 0.4
    dn = lambda r: (f"DN{r}", "nfet", 2.0, 2.0, 8, ["vsn", f"xn{r}"] * 4 + ["vsn"], f"vgn{r}", "bar")
    y, _, _ = place_row(c, y, [dn(3), dn(5)], XL, XR, 1.4); y += G
    fb = []
    for r in (3, 5):
        fb.append((f"FN{r}", "nfet", 2.0, 1.0, 1, ["vdd", f"vgn{r}"], f"xn{r}", "top"))
        fb.append((f"BN{r}", "nfet", 2.0, 2.0, 1, [f"vgn{r}", "vsn"], "vgn5", "top"))
    y, _, _ = place_row(c, y, fb, XL, XR, 3.0); y += G + 0.6
    # FP followers: pfet with body = source = vgp<r>, each in its own n-well
    e = c.mos_extent("pfet", 2.0, 1.0, 1, "top")
    pitch = (XR - XL) / 3
    cy = y + 0.8 - e[1]
    for i, r in enumerate((3, 5, 6)):
        x = XL + pitch * (i + 0.5) - 0.6
        c.mos(f"FP{r}", "pfet", 2.0, 1.0, x, cy, ["vss", f"vgp{r}"], f"xp{r}", head="top")
        nw = (x + e[0] - 0.9, y, x + e[2] + 0.9 + 2.0, cy + e[3] + 1.2)
        c.p("nwell", nw)
        c.tap("n", (nw[2] - 1.6, nw[1] + 1.0, nw[2] - 1.0, nw[3] - 1.0), f"vgp{r}")
    y = cy + e[3] + 1.2 + 2.0
    # ---------------- p side (one vdd n-well) ----------------
    nwb = y
    y += 0.6
    c.tap("n", (XL + 1.0, y, XR - 1.0, y + 0.6), "vdd")
    y += 0.6 + 1.0
    bp = [(f"BP{r}", "pfet", 2.0, 2.0, 1, ["vsp", f"vgp{r}"], "vgp6", "top") for r in (3, 5, 6)]
    y, _, _ = place_row(c, y, bp, XL, XR, 5.0); y += G
    dp = lambda r: (f"DP{r}", "pfet", 2.0, 2.0, 8, ["vsp", f"xp{r}"] * 4 + ["vsp"], f"vgp{r}", "bar")
    y, _, _ = place_row(c, y, [dp(3), dp(5)], XL, XR, 1.4); y += G
    y, _, _ = place_row(c, y, [dp(6)], XL, XR, 1.4); y += G
    np_ = lambda k: "in_p" if k == 0 else f"np{k}"
    sh = [("npSH01", [np_(0), "vss", np_(1)]), ("npSH24", [np_(2), "vss", np_(4)]), ("npSH3", [np_(3), "xn3"]),
          ("npSH5T", ["xn5", np_(5), "vss"])]
    y, _, _ = place_row(c, y, [(nm, "pfet", 2.0, 2.0, len(st) - 1, st, "vglp", "top") for nm, st in sh],
                        XL, XR, 0.8)
    y += G
    y, _, _ = place_row(c, y, [("npSE", "pfet", 4.0, 2.0, 5, [np_(k) for k in range(6)], "vglp", "bar")], XL, XR)
    c.tap("n", (XL + 1.0, y + 0.8, XR - 1.0, y + 1.4), "vdd")
    c.p("nwell", (XL - 0.3, nwb, XR + 0.3, y + 2.0))
    y += 2.0 + 1.0
    for k, net in enumerate(["in_p", "vglp", "vsp", "vdd", "vgp3", "vgp5", "vgp6"]):
        pin(c, net, 3.0 + k * 6.4, y + 0.3, "power" if net == "vdd" else "signal")
    H = snap(y + 0.6 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6)

if __name__ == "__main__":
    name = sys.argv[1]
    f = {"bias_rails": rails, "bias_master": master, "vref_string64": vref, "vdac6": vdac6, "bias_rangegen": rangegen,
         "bias_ladder": ladder, "bias_rails_c": lambda: rails(True)}[name]()
    sys.exit(1 if f else 0)
