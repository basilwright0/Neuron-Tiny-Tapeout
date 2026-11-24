"""B1 bias generator leaf cells (gf180mcuD): generation scripts.

    python3 leafs.py <cell>      (inside the EDA container, from layout/bias; build.sh calls it)

Cells: rx_n4 rx_n2 rx_p05 rx_p1 idac_n idac_p (more in leafs2.py).
Every cell: origin at its lower-left corner, p-tap (vss) guard ring on the perimeter, Metal1/Metal2
only (Metal3 is left free for the B1 top level), pins = labelled Metal2 pads.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cellgen import Cell, snap, load_dev, need_mos   # noqa: E402

RING = 0.60          # perimeter p-tap ring width
NWTOP = 0.75        # idac_p: n-well top edge above the inverter pfet row (b1c re-pack)
OUT = HERE / "out"


def ext(model, w, l, nf=1):
    lc = load_dev(need_mos(model, w, l, nf))
    return lc["diff"]


def pin(c, net, x, y, use="signal"):
    """Metal2 pin pad 0.4 x 0.4 at (x, y) (terminal for the leaf router, label for LVS)."""
    r = c.p("metal2", (x - 0.2, y - 0.2, x + 0.2, y + 0.2), net, term=True)
    c.label(net, "metal2", r, use)
    c.req_x.add(snap(x))
    c.req_y.add(snap(y))
    return r


def frame(c, W, H):
    """p-tap ring (vss) on the perimeter + routing forbids along it."""
    c.ring("p", (0, 0, W, H), RING, "vss")
    for r in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        c.forbid_box(("m1",), r, allowed={"vss"})
    for r in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        c.forbid_box(("m2",), r)


def finish(c, W, H, ports, layers=("m1", "m2"), base=0.6, first=(), last=("vdd", "vss"), skip=()):
    failed = c.route((0, 0, W, H), layers=layers, order_first=first, order_last=last, base=base,
                     cache=OUT / f"route_cache_{c.name}.json", skip=skip)
    c.fill_notches()
    c.write((0, 0, W, H))
    c.preview(OUT / f"preview_{c.name}.png", (0, 0, W, H))
    # geometry for the top level (Metal2 obstacles, pins)
    geo = dict(W=W, H=H,
               m2=[r for l, r, n in list(c.obst) + c.wires + c.fills if l == "m2"],
               m1=[r for l, r, n in list(c.obst) + c.wires + c.fills if l == "m1"],
               pins={t: r for t, lay, r, u in c.labels if u})
    (OUT / f"geo_{c.name}.json").write_text(json.dumps(geo))
    print(f"AREA {c.name} {W:.2f} x {H:.2f} = {W * H:.0f} um^2")
    print("FAILED:", failed if failed else "none")
    return failed


# ============================================================================ receivers
RX = {"n4": ("n", 2.0, 4.0, 4), "n1": ("n", 2.0, 4.0, 1), "p24": ("p", 2.0, 4.0, 1), "n2": ("n", 2.0, 4.0, 2), "p05": ("p", 1.0, 4.0, 1), "p1": ("p", 1.0, 2.0, 1)}


def rx(name):
    pol, w, l, k = RX[name]
    c = Cell(f"rx_{name}")
    d = ext(pol + "fet", w, l, k)
    dw, dh = d[2] - d[0], d[3] - d[1]
    sup = "vss" if pol == "n" else "vdd"
    W = snap(max(dw + 2 * RING + 3.0, 7.0))
    inner = 2.6 if pol == "p" else 1.4
    H = snap(dh + 2 * RING + 2 * inner + 1.6)
    x0, y0 = W / 2, RING + inner + 0.6 + dh / 2
    frame(c, W, H)
    if pol == "p":
        nw = (RING + 0.5, RING + 0.4, W - RING - 0.5, H - RING - 0.4)
        c.p("nwell", nw)
        c.tap("n", (nw[0] + 0.3, nw[1] + 0.3, nw[2] - 0.3, nw[1] + 0.9), "vdd")
    strips = [("line" if i % 2 else sup) for i in range(k + 1)]
    c.mos("D", pol + "fet", w, l, x0, y0, strips, "line", nf=k, head="bar")
    pin(c, "line", W / 2, H - RING - 0.6)
    pin(c, "vdd", RING + 0.9, H - RING - 0.6, "power")
    if pol == "n":
        c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    else:
        c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, ["line", "vdd", "vss"])


# ============================================================================ idac
def idac(pol):
    """idac_n / idac_p (rev C).  Bottom to top: g / rail pins, unit rows (2 x 2 rows of 8 fingers
    around two source rails), per-bit slices (SO/SD pair, inverter pairs), fine-code / out pins."""
    n = pol == "n"
    Pm = pol + "fet"
    rail = "vsn" if n else "vsp"
    c = Cell(f"idac_{pol}")
    W = 25.4
    GAP = 0.70 if n else 0.85
    XL, XR = RING + 0.8, W - RING - 0.8
    # ---- bottom pins (rev C: gate line + rail only; the range mux is gone) -------------------
    ypa = RING + 0.75
    for k, net in enumerate(["g", rail]):
        pin(c, net, W / 2 - 3.0 + k * 6.0, ypa)
    y = ypa + 0.2 + 0.7
    # M3 re-pack (b1c): no bottom well-tie row.  idac_n: the perimeter p-tap ring ties the substrate
    # (every nfet is < 13 um from it).  idac_p: one n-tap row between the two unit row pairs keeps
    # every pfet of the cell within 20 um of an n-tap (DF.13), replacing the bottom and top n-tap rows.
    nw0 = y - 0.5
    y += 0.0 if n else 0.0
    # ---- unit rows -------------------------------------------------------------------------
    rows = [("U4a", ["d4"] * 4), ("U4b", ["d4"] * 4), ("U3", ["d3"] * 4), ("U210", None)]
    d = ext(Pm, 2.0, 2.0, 8)
    hdiff = (d[3] - d[1]) / 2
    for pr in range(2):
        rb_name, rb_d = rows[2 * pr]
        ra_name, ra_d = rows[2 * pr + 1]
        ybus_b = y + 0.15
        ybar_b = ybus_b + 0.15 + 0.45 + 0.19
        cyb = ybar_b + 0.45 + hdiff
        yrail = cyb + hdiff + 0.35 + 0.3
        cya = yrail + 0.3 + 0.35 + hdiff
        ybus_a = cya + hdiff + 0.45 + 0.19 + 0.45 + 0.15
        for name, ds, cyy, head, ybus in ((rb_name, rb_d, cyb, "barbot", ybus_b), (ra_name, ra_d, cya, "bar", ybus_a)):
            if ds is None:
                strips = [rail, "d2", rail, "d2", rail, "d1", rail, "d0"]
                nf = 7
            else:
                strips = []
                for dd in ds:
                    strips += [rail, dd]
                strips.append(rail)
                nf = 8
            busses = {dd: ybus for dd in set(strips) if dd != rail}
            c.mos(name, Pm, 2.0, 2.0, W / 2 - (0.0 if nf == 8 else 1.26), cyy, strips, "g", nf=nf, head=head,
                  rails={rail: yrail}, busses=busses)
        c.p("metal1", (XL + 0.6, yrail - 0.3, XR - 0.6, yrail + 0.3), rail, term=True)
        if pr == 0 and not n:
            yt = ybus_a + 0.15 + 0.1
            c.tap("n", (XL + 0.6, yt, XR - 0.6, yt + 0.6), "vdd")
            y = yt + 0.6 + 0.8
        else:
            y = ybus_a + 0.15 + (GAP if pr == 0 else 0.9)
    # ---- per-bit slices: SO/SD pair, inverter pairs ------------------------------------------
    if n:
        x1, x2 = [f"bd{b}" for b in range(5)], [f"bc{b}" for b in range(5)]
    else:
        x1, x2 = [f"bc{b}" for b in range(5)], [f"bd{b}" for b in range(5)]
    xs_ = [XL + 2.0 + b * 4.25 for b in range(5)]
    e = c.mos_extent(Pm, 0.5, 0.5, 2, "top")
    cy = y - e[1]
    for b in range(5):
        c.mos(f"SW{b}", Pm, 0.5, 0.5, xs_[b], cy, ["out", f"d{b}", "dump"], [f"bc{b}", f"bd{b}"], nf=2, head="top")
    y = cy + e[3] + GAP
    inv_rows = [("nfet", 0.5, "vss" if n else "vcas"), ("pfet", 1.0, "vcas" if n else "vdd")]
    if not n:
        inv_rows.reverse()
    for k, (model, w, src) in enumerate(inv_rows):
        if model == "pfet" and n:
            y += 0.7
            nwb = y - 0.75
        if model == "nfet" and not n:
            y += 0.7
        e = c.mos_extent(model, w, 0.28, 2, "alt")
        cy = y - e[1]
        for b in range(5):
            c.mos(f"I{model[0].upper()}{b}", model, w, 0.28, xs_[b] + 0.6, cy, [x1[b], src, x2[b]],
                  [f"b{b}", x1[b]], nf=2, head="alt")
        y = cy + e[3]
        if model == "pfet":
            if n:
                c.tap("n", (XL + 0.6, y + 0.85, XR - 0.6, y + 1.45), "vcas")
                c.p("nwell", (XL - 0.4, nwb, XR + 0.4, y + 2.05))
                y += 2.05 + GAP
            else:
                c.p("nwell", (XL - 0.4, nw0, XR + 0.4, y + NWTOP))
                y += NWTOP + GAP
        else:
            y += GAP
    # ---- top pins ---------------------------------------------------------------------------
    ypt = y + 0.2
    top = [f"b{b}" for b in range(5)]
    for b in range(5):
        pin(c, top[b], xs_[b] - 0.6, ypt)
    for k, net in enumerate(["out", "dump", "vcas", "vdd"]):
        pin(c, net, xs_[k] + 1.8, ypt, "power" if net == "vdd" else "signal")
    H = snap(ypt + 0.2 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.65 if n else 0.6, first=("g", "vdd"), last=("vss",))


if __name__ == "__main__":
    name = sys.argv[1]
    if name.startswith("rx_"):
        f = rx(name[3:])
    elif name.startswith("idac_"):
        f = idac(name[5:])
    else:
        raise SystemExit(f"unknown cell {name}")
    sys.exit(1 if f else 0)
