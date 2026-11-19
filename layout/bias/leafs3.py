"""B1 bias generator leaf cells, part 3 (rev C): bias_vi (V-to-I + copies) and the resistor DACs vdacr_*.

    python3 leafs3.py <cell>      (inside the EDA container, from layout/bias; build.sh calls it)

Same conventions as leafs.py.  Resistor pieces (nodes, length) are read from the schematic
(cells/bias/bias_vi.spice), so the layout always matches the generated netlist; the router makes
every connection that is not drawn explicitly.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cellgen import Cell, snap, load_dev, need_res   # noqa: E402
from leafs import RING, pin, frame, finish             # noqa: E402
from leafs2 import place_row, res_extent               # noqa: E402

ROOT = HERE.parents[1]


def sch_res(cell):
    """[(name, a, b, W, L)] of the ppolyf_u_1k instances of a subckt in bias_vi.spice."""
    out, cur = [], None
    for ln in (ROOT / "cells" / "bias" / "bias_vi.spice").read_text().splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == ".subckt":
            cur = t[1]
        elif t[0] == ".ends":
            cur = None
        elif cur == cell and t[0].startswith("X") and "ppolyf_u_1k" in t:
            w = float(re.search(r"r_width=([\d.]+)u", ln).group(1))
            l = float(re.search(r"r_length=([\d.]+)u", ln).group(1))
            out.append((t[0], t[1], t[2], w, l))
    return out


def res_row(c, items, x0, y0, pitch=2.2, term=True):
    """Vertical resistors side by side, bottoms aligned at y0.  items: (name, top, bot, W, L)."""
    x = x0
    ytop = y0
    for nm, a, b, w, l in items:
        bb = res_extent(w, l)
        r = c.res(nm, w, l, x - bb[0], y0 - bb[1], a, b, term=term)
        ytop = max(ytop, r["bbox"][3])
        x += (bb[2] - bb[0]) + (pitch - 1.0)
    return x, ytop


# ============================================================================ bias_vi
def vi():
    c = Cell("bias_vi")
    W = 56.0
    XL, XR = RING + 0.9, W - RING - 0.9
    G = 1.2
    y = RING + 0.9
    bot = ["en", "ib_x2", "vbn_prb", "ib_r1", "iint", "vglp", "vgln"]
    for k, net in enumerate(bot):
        pin(c, net, 3.0 + k * 7.6, y + 0.3)
    y += 0.6 + G
    # ---- R0: 4 strips (x -> vss) at the left of the n rows ----
    rs = sch_res("bias_vi")
    xend, ytop_r = res_row(c, [(nm, a, b, w, l) for nm, a, b, w, l in rs], XL + 1.0, y + 0.4)
    c.forbid_box(("m1",), (XL + 0.2, y - 0.4, xend + 0.6, ytop_r + 0.8), allowed={a for _, a, _, _, _ in rs} |
                 {b for _, _, b, _, _ in rs})
    XN = xend + 1.2
    # ---- n rows (substrate) ----
    ota = [("N1", "nfet", 4.0, 2.0, 1, ["tl", "vgvi"], "vglp", "top"),
           ("N2", "nfet", 4.0, 2.0, 1, ["tl", "oa"], "x", "top"),
           ("NT", "nfet", 2.0, 2.0, 1, ["vss", "tl"], "vbt", "top"),
           ("NB", "nfet", 2.0, 2.0, 1, ["vss", "vbt"], "vbt", "top"),
           ("NS", "nfet", 4.0, 2.0, 2, ["ns", "vss", "ns"], "vbt", "top"),
           ("MS1", "nfet", 0.5, 1.0, 1, ["vgvi", "su"], "ns", "top"),
           ("MS2", "nfet", 0.5, 1.0, 1, ["su", "vss"], "en", "top")]
    y, _, _ = place_row(c, y, ota, XN, XR, 0.8); y += G
    outs = [("DB", "nfet", 2.0, 2.0, 1, ["vss", "vbn_prb"], "vbn_prb", "top"),
            ("OR", "nfet", 2.0, 2.0, 4, ["vss", "ib_r1", "vss", "ib_r1", "vss"], "vbn_prb", "bar"),
            ("OX", "nfet", 2.0, 2.0, 4, ["vss", "ibx", "vss", "ibx", "vss"], "vbn_prb", "bar"),
            ("SX2", "nfet", 4.0, 0.5, 1, ["ibx", "ib_r1"], "ib_x2", "top")]
    y, _, _ = place_row(c, y, outs, XN, XR, 0.8); y += G
    y = max(y, ytop_r + 1.4)
    c.tap("p", (XL + 1.0, y - 0.6, XR - 1.0, y), "vss"); y += 0.4
    # ---- p rows (one vdd n-well) ----
    y += 1.6
    nwb = y - 0.6
    y += 0.6
    small = [("P1", "pfet", 2.0, 2.0, 1, ["vdd", "oa"], "oa", "top"),
             ("P2", "pfet", 2.0, 2.0, 1, ["vdd", "vgvi"], "oa", "top"),
             ("PB", "pfet", 0.5, 4.0, 1, ["vdd", "vbt"], "vgvi", "top"),
             ("PS", "pfet", 0.5, 10.0, 1, ["vdd", "ns"], "vgln", "top"),
             ("POFF", "pfet", 1.0, 0.5, 1, ["vdd", "vgvi"], "en", "top"),
             ("PP", "pfet", 0.8, 2.0, 1, ["vdd", "vbn_prb"], "vgvi", "top"),
             ("PI", "pfet", 0.8, 2.0, 1, ["vdd", "iint"], "vgvi", "top")]
    y, _, _ = place_row(c, y, small, XL, XR, 1.2); y += G
    mir = [(f"M{n}", "pfet", 4.0, 2.0, 4, ["vdd", f"m{n.lower()}", "vdd", f"m{n.lower()}", "vdd"], "vgvi", "bar")
           for n in "OERC"] + [("MT", "pfet", 4.0, 2.0, 1, ["vdd", "mt"], "vgvi", "bar")]
    y, _, _ = place_row(c, y, mir, XL, XR, 0.9); y += G
    cas = [(f"K{n}", "pfet", 4.0, 1.0, 4, [f"m{n.lower()}", o, f"m{n.lower()}", o, f"m{n.lower()}"], "vglp", "bar")
           for n, o in (("O", "x"), ("E", "el"), ("R", "vreset_src"), ("C", "vth_cmp"))]
    cas.append(("KT", "pfet", 4.0, 1.0, 1, ["mt", "vth_ref"], "vglp", "bar"))
    y, _, _ = place_row(c, y, cas, XL, XR, 0.9)
    c.tap("n", (XL + 0.5, y + 0.7, XR - 0.5, y + 1.3), "vdd")
    c.p("nwell", (XL - 0.5, nwb, XR + 0.5, y + 1.9))
    y += 1.9 + 0.8
    top = ["vdd", "el", "vreset_src", "vth_cmp", "vth_ref"]
    for k, net in enumerate(top):
        pin(c, net, W - 3.0 - k * 6.0, y + 0.3, "power" if net == "vdd" else "signal")
    H = snap(y + 0.6 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6, first=("vgvi",))


# ============================================================================ vdacr_*
def vdacr(k):
    """Inverters, shorting switches, p-tap, then the resistor row on top."""
    name = f"vdacr_{k}"
    rs = sch_res(name)
    nb = 6 if k == "vt" else 5
    sw = (12.0, 0.28) if nb == 6 else (8.0, 0.28)
    c = Cell(name)
    W = snap(max(len(rs) * 2.2 + 4.0, nb * 5.4 + 4.0))
    XL, XR = RING + 0.9, W - RING - 0.9
    G = 1.2
    y = RING + 0.9
    for b in range(nb):
        pin(c, f"b{b}", 2.6 + b * 4.6, y + 0.3)
    pin(c, "vdd", 2.6 + nb * 4.6, y + 0.3, "power")
    y += 0.6 + G
    nwb = y
    y += 1.0
    invp = [(f"IB{b}p", "pfet", 1.0, 1.0, 1, ["vdd", f"bb{b}"], f"b{b}", "top") for b in range(nb)]
    y, _, _ = place_row(c, y, invp, XL, XR, 3.0)
    c.tap("n", (XL + 0.5, y + 0.6, XR - 0.5, y + 1.2), "vdd")
    c.p("nwell", (XL - 0.5, nwb, XR + 0.5, y + 1.8))
    y += 1.8 + 1.4
    invn = [(f"IB{b}n", "nfet", 0.5, 1.0, 1, ["vss", f"bb{b}"], f"b{b}", "top") for b in range(nb)]
    y, _, _ = place_row(c, y, invn, XL, XR, 3.4); y += G
    sws = []
    for b in range(nb):
        top_, bot_ = f"n{b}", ("vss" if b == nb - 1 else f"n{b + 1}")
        sws.append((f"SW{b}", "nfet", sw[0] / 2, sw[1], 2, [top_, bot_, top_], f"bb{b}", "top"))
    y, _, _ = place_row(c, y, sws, XL, XR, 1.0); y += G
    c.tap("p", (XL + 1.0, y - 0.6, XR - 1.0, y), "vss"); y += 0.4 + 1.2
    xend, ytop = res_row(c, rs, XL + 1.0, y)
    nets = {a for _, a, _, _, _ in rs} | {b for _, _, b, _, _ in rs}
    c.forbid_box(("m1",), (XL + 0.2, y - 0.8, xend + 0.6, ytop + 0.8), allowed=nets)
    y = ytop + 1.4
    pin(c, "out", W / 2, y + 0.3)
    H = snap(y + 0.6 + 0.6 + RING)
    frame(c, W, H)
    c.label("vss", "metal1", (0.1, 0.1, 0.5, 0.5), "ground")
    return finish(c, W, H, None, base=0.6)


if __name__ == "__main__":
    name = sys.argv[1]
    f = vi() if name == "bias_vi" else vdacr(name.split("_", 1)[1])
    sys.exit(1 if f else 0)
