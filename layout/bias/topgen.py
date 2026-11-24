"""B1 assembly: bias_vblk (string + 3 vdac6) and the B1 top level in two shapes.

    python3 topgen.py bias_vblk          (needs the leaf cells' out/geo_<cell>.json)
    python3 topgen.py bias_b1_w           shape (a): ~104 um tall, as wide as needed
    python3 topgen.py bias_b1_n           shape (b): ~131 um wide, as tall as needed

Leaf cells are placed as subcell uses (magic hierarchy); the connections come from the reference
netlist (cells/bias/bias_b1.spice).  Routing uses Metal2 + Metal3 only (leaves use Metal1/Metal2,
Metal3 over them is free).  Leaf Metal2 is an obstacle; a leaf pin pad (and the leaf Metal2
touching it) carries the pin's net.  vss: a via1 + Metal2 pad on each leaf's p-tap ring corner.
The 64 VDAC taps in bias_vblk are straight Metal3 lines through the stacked vdac6 cells.
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cellgen import Cell, snap, U       # noqa: E402

ROOT = HERE.parents[1]
OUT = HERE / "out"


# ---------------------------------------------------------------- reference connectivity
def ref_subckts():
    sub = {}
    for f in sorted((ROOT / "cells" / "bias").glob("bias_*.spice")):
        if f.name == "bias_all.spice":
            continue
        cur = None
        for ln in f.read_text().splitlines():
            t = ln.split()
            if not t:
                continue
            if t[0].lower() == ".subckt":
                cur = t[1]
                sub[cur] = dict(ports=[x for x in t[2:] if "=" not in x], inst=[])
            elif t[0].lower() == ".ends":
                cur = None
            elif cur and t[0][0] in "Xx":
                args = [x for x in t[1:] if "=" not in x]
                sub[cur]["inst"].append((t[0], args[-1], args[:-1]))
    return sub


SUB = ref_subckts()


def conn(parent):
    """inst -> (cellname, {pin: net})"""
    out = {}
    for name, model, nets in SUB[parent]["inst"]:
        out[name] = (model, dict(zip(SUB[model]["ports"], nets)))
    return out


# ---------------------------------------------------------------- geometry of a placed subcell
def load_geo(cell):
    return json.loads((OUT / f"geo_{cell}.json").read_text())


def xform(r, x, y, rot):
    if rot == 0:
        return (snap(r[0] + x), snap(r[1] + y), snap(r[2] + x), snap(r[3] + y))
    # 90 deg counter-clockwise: (u, v) -> (-v, u), then translate
    return (snap(-r[3] + x), snap(r[0] + y), snap(-r[1] + x), snap(r[2] + y))


def touching(a, b):
    return a[0] <= b[2] + 1e-9 and b[0] <= a[2] + 1e-9 and a[1] <= b[3] + 1e-9 and b[1] <= a[3] + 1e-9


class Top(Cell):
    def __init__(self, name):
        super().__init__(name)
        self.placed = {}

    def place(self, inst, cell, x, y, nets, rot=0):
        g = load_geo(cell)
        W, H = g["W"], g["H"]
        if rot == 0:
            bbox_abs = (x, y, x + W, y + H)
        else:
            bbox_abs = (x - H, y, x, y + W)
        self.uses.append((cell, inst, snap(x), snap(y), (0, 0, W, H), rot))
        pins = {k: v for k, v in g["pins"].items() if k != "vss"}
        # leaf Metal2 / Metal3: pin pads and the shapes touching them carry the pin's net
        for lay in ("m2", "m3"):
            rects = [tuple(r) for r in g.get(lay, [])]
            owner = [None] * len(rects)
            if lay == "m2":
                for pn, pr in pins.items():
                    stack = [i for i, r in enumerate(rects) if owner[i] is None and touching(r, pr)]
                    while stack:
                        i = stack.pop()
                        if owner[i] is not None:
                            continue
                        owner[i] = pn
                        stack += [j for j, r in enumerate(rects) if owner[j] is None and touching(r, rects[i])]
            for r, o in zip(rects, owner):
                net = nets.get(o, f"_o_{inst}_{o}") if o else f"_o_{inst}"
                self.obst.append((lay, xform(r, x, y, rot), net))
        abs_pins = {}
        for pn, pr in pins.items():
            r = xform(pr, x, y, rot)
            abs_pins[pn] = r
            net = nets.get(pn)
            if net is None:
                continue
            self.obst.append(("m2", r, net))
            self.term(net, [("m2", r)])
        # vss: via1 + Metal2 pad on the ring's lower-left corner (assembled cells export a Metal2 vss pin)
        if "vss" in g["pins"] and cell.startswith("bias_vblk"):
            vr = xform(g["pins"]["vss"], x, y, rot)
            self.obst.append(("m2", vr, "vss"))
            self.term("vss", [("m2", vr)])
        else:
            vr = xform((0.15, 0.15, 0.55, 0.55), x, y, rot)
            cx, cy = (vr[0] + vr[2]) / 2, (vr[1] + vr[3]) / 2
            self.p("metal1", vr, "vss")
            self.p("metal2", vr, "vss", term=True)
            self.p("via1", (cx - 0.13, cy - 0.13, cx + 0.13, cy + 0.13), "vss")
        self.placed[inst] = dict(cell=cell, bbox=bbox_abs, pins=abs_pins, nets=nets)
        return bbox_abs

    def write_top(self, box):
        """Like Cell.write, with rotated uses."""
        self.uses_rot = self.uses
        self.uses = []
        try:
            self.write(box)
        finally:
            self.uses = self.uses_rot
        base = (HERE / f"{self.name}_base.mag").read_text().splitlines()
        assert base[-1] == "<< end >>"
        base = base[:-1]
        for cname, inst, x, y, b, rot in self.uses_rot:
            tr = f"1 0 {round(x * U)} 0 1 {round(y * U)}" if rot == 0 else f"0 -1 {round(x * U)} 1 0 {round(y * U)}"
            base += [f"use {cname}  {inst}", "timestamp 0", f"transform {tr}",
                     f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
        base.append("<< end >>")
        (HERE / f"{self.name}_base.mag").write_text("\n".join(base) + "\n")


def export_geo(c, W, H, pins):
    """geo json of an assembled cell: all Metal2/Metal3 (own + subcells) and its pins."""
    m2 = [r for l, r, n in list(c.obst) + c.wires + c.fills if l == "m2"]
    m3 = [r for l, r, n in list(c.obst) + c.wires + c.fills if l == "m3"]
    (OUT / f"geo_{c.name}.json").write_text(json.dumps(dict(W=W, H=H, m2=m2, m3=m3, pins=pins)))


def route_and_write(c, box, base=0.8, first=(), last=("vdd", "vss")):
    failed = c.route(box, layers=("m2", "m3"), order_first=first, order_last=last, base=base,
                     cache=OUT / f"route_cache_{c.name}.json")
    c.fill_notches()
    c.write_top(box)
    c.preview(OUT / f"preview_{c.name}.png", box, show_labels=False)
    return failed


# ============================================================================ bias_vblk
def vblk():
    c = Top("bias_vblk")
    conns = conn("bias_vblk")
    gv = load_geo("vdac6")
    gs = load_geo("vref_string64")
    G = 3.0                                   # gap between stacked cells
    W = max(gv["W"], gs["W"]) + 2.0
    # three vdac6 stacked at x = 1, string on top-left, tap lines straight Metal3 through the stack
    y = 1.0
    order = ["Xv2", "Xv1", "Xv0"]
    for inst in order:
        c.place(inst, "vdac6", 1.0, y, conns[inst][1])
        y += gv["H"] + G
    ys = y + 3.0                               # string right above the top vdac6 between the top vdac6 and the string
    c.place("Xs", "vref_string64", 1.0, ys, conns["Xs"][1])
    H = snap(ys + gs["H"] + 1.0)
    # taps: Metal3 from each vdac6 tap pin of the bottom cell up to the top cell, via2 at every pin
    for k in range(64):
        net = f"t{k}"
        rs = [c.placed[i]["pins"][net] for i in order]
        xs = (rs[0][0] + rs[0][2]) / 2
        ytop = ys + gs["H"] - 1.0          # lines continue over the string: short local hops to its taps
        line = c.p("metal3", (xs - 0.15, rs[0][1], xs + 0.15, ytop), net)
        c.term(net, [("m3", line)])
        for r in rs:
            c.via2((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, net)
        # these vdac6 pins are now connected structurally: drop their separate terminals
        c.nets[net] = [t for t in c.nets[net] if not any(sh[0] == "m2" and sh[1] in rs for sh in t)]
    box = (0, 0, W, H)
    failed = route_and_write(c, box, base=0.6)
    # pins of bias_vblk = subcell pins of one occurrence per port net
    pins = {}
    for inst, pl in c.placed.items():
        for pn, r in pl["pins"].items():
            net = pl["nets"].get(pn)
            if net in SUB["bias_vblk"]["ports"] and net not in pins:
                pins[net] = r
    for net, r in pins.items():
        c.p("metal2", r)
        c.label(net, "metal2", r, "power" if net == "vdd" else "signal")
    vr = c.placed["Xv2"]["bbox"]
    vss = (vr[0] + 0.15, vr[1] + 0.15, vr[0] + 0.55, vr[1] + 0.55)
    c.label("vss", "metal2", vss, "ground")
    pins["vss"] = vss
    c.write_top(box)
    export_geo(c, W, H, pins)
    print(f"AREA {c.name} {W:.2f} x {H:.2f} = {W * H:.0f} um^2")
    print("FAILED:", failed if failed else "none")
    return failed


# ============================================================================ bias_b1 (two shapes)
def edge_pins(c, nets_targets, edge, box, pitch=0.9):
    """M3 pin pads along one edge, ordered by their target position; returns {net: rect}."""
    x0, y0, x1, y1 = box
    along = sorted(nets_targets.items(), key=lambda kv: kv[1])
    n = len(along)
    out = {}
    lo, hi = (x0 + 2.0, x1 - 2.0) if edge in "tb" else (y0 + 2.0, y1 - 2.0)
    span = hi - lo
    step = max(pitch, span / max(n, 1))
    start = lo + (span - step * (n - 1)) / 2 if step * (n - 1) < span else lo
    for k, (net, _) in enumerate(along):
        t = snap(start + k * step)
        if edge == "t":
            r = (t - 0.2, y1 - 0.9, t + 0.2, y1 - 0.5)
        elif edge == "b":
            r = (t - 0.2, y0 + 0.5, t + 0.2, y0 + 0.9)
        elif edge == "l":
            r = (x0 + 0.5, t - 0.2, x0 + 0.9, t + 0.2)
        else:
            r = (x1 - 0.9, t - 0.2, x1 - 0.5, t + 0.2)
        c.p("metal3", r, net, term=True)
        c.label(net, "metal3", r, "power" if net == "vdd" else ("ground" if net == "vss" else "signal"))
        out[net] = r
    return out


def vblk_dims():
    gv, gs_ = load_geo("vdac6"), load_geo("vref_string64")
    W = max(gv["W"], gs_["W"]) + 2.0
    H = 1.0 + 3 * (gv["H"] + 3.0) + 3.0 + gs_["H"] + 1.0
    return dict(W=snap(W), H=snap(H), m2=[], m3=[], pins={})


def b1(shape, route=True):
    name = f"bias_b1_{shape}"
    c = Top(name)
    conns = conn("bias_b1")
    gs = {k: load_geo(k) for k in ("idac_p", "idac_n", "bias_master", "bias_rails", "bias_rangegen")}
    gs["bias_vblk"] = load_geo("bias_vblk") if (OUT / "geo_bias_vblk.json").exists() and route else vblk_dims()
    gx = {k: load_geo(k) for k in ("rx_n4", "rx_n2", "rx_n1", "rx_p24", "rx_p05", "rx_p1")}
    pos = {}
    W_ = lambda k: gs[k]["W"]
    H_ = lambda k: gs[k]["H"]
    idacs = ["Xi0", "Xi1", "Xi2", "Xi3", "Xi4", "Xi5"]
    icell = {i: conns[i][0] for i in idacs}
    rxs = ["Xx0", "Xx1", "Xx2", "Xx3", "Xx4", "Xx5"]
    rot = {}
    E, G = 3.0, 3.0
    gxw = lambda r: gx[conns[r][0]]["W"]
    gxh = lambda r: gx[conns[r][0]]["H"]
    if shape == "n":            # ~131 um wide
        # bottom row: rangegen, master (ESD / ua[0] at the bottom edge), receivers stacked;
        # above: vblk at the left, rails then 2 x 3 idacs at the right (idacs nearest the top edge)
        pos["Xg"] = (E, E)
        pos["Xm"] = (E + W_("bias_rangegen") + G, E)
        xx = E + W_("bias_rangegen") + G + W_("bias_master") + G
        yy = E
        for r in rxs:
            pos[r] = (xx, yy)
            yy += gxh(r) + 1.5
        yb = max(E + H_("bias_rangegen"), E + H_("bias_master"), yy) + G
        pos["Xvb"] = (E, yb)
        xr = E + W_("bias_vblk") + G
        pos["Xr"] = (xr, yb)
        yi = yb + H_("bias_rails") + G
        for k, i in enumerate(idacs):
            col, row = k % 2, k // 2
            pos[i] = (xr + col * (W_("idac_p") + G), yi + row * (H_("idac_p") + G))
        W = max(xr + 2 * W_("idac_p") + G + E, xx + max(gxw(r) for r in rxs) + E)
        H = max(yb + H_("bias_vblk"), yi + 3 * H_("idac_p") + 2 * G) + E
    else:                       # shape w: ~104 um tall
        # vblk rotated 90 deg at the left with the receivers above it; idacs 3 x 2; rangegen with the
        # rails (rotated) on top; master
        hv = W_("bias_vblk")
        pos["Xvb"] = (E + H_("bias_vblk"), E)
        rot["Xvb"] = 90
        xx = E
        for r in rxs:
            pos[r] = (xx, E + hv + G)
            xx += gxw(r) + 1.5
        x = E + H_("bias_vblk") + G
        for k, i in enumerate(idacs):
            col, row = k % 3, k // 3
            pos[i] = (x + col * (W_("idac_p") + G), E + row * (H_("idac_p") + G))
        x += 3 * W_("idac_p") + 3 * G
        pos["Xg"] = (x, E)
        pos["Xr"] = (x + H_("bias_rails"), E + H_("bias_rangegen") + G)
        rot["Xr"] = 90
        x += max(W_("bias_rangegen"), H_("bias_rails")) + G
        pos["Xm"] = (x, E)
        W = x + W_("bias_master") + E
        H = max(E + hv + G + max(gxh(r) for r in rxs), E + 2 * H_("idac_p") + G,
                E + H_("bias_rangegen") + G + W_("bias_rails"), E + H_("bias_master")) + E
    W, H = snap(W), snap(H)
    if not route:
        leaf = 0.0
        for inst in pos:
            cell = "bias_vblk" if inst == "Xvb" else conns[inst][0]
            g = gs.get(cell) or gx.get(cell)
            leaf += g["W"] * g["H"]
        print(f"PLACE {name} {W:.1f} x {H:.1f} = {W * H:.0f} um^2  (leaf cells {leaf:.0f} um^2, {100 * leaf / (W * H):.0f} %)")
        for inst, (x, y) in sorted(pos.items()):
            print(f"  {inst:5s} {conns[inst][0]:15s} at ({x:6.1f}, {y:6.1f})")
        return []
    for inst, (x, y) in pos.items():
        cell, nets = conns[inst]
        if inst == "Xvb":
            cell = "bias_vblk"
        c.place(inst, cell, x, y, nets, rot=rot.get(inst, 0))
    box = (0, 0, W, H)
    # block pins: digital on top, analog outputs on the left, pad / R1 lines at the bottom, power on the right
    dig, ana = SUB["bias_b1"]["ports"][:96], [p for p in SUB["bias_b1"]["ports"][96:] if p not in ("vdd", "vss")]
    target = {}
    for inst, pl in c.placed.items():
        for pn, r in pl["pins"].items():
            net = pl["nets"].get(pn)
            if net is not None and net not in target:
                target[net] = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
    edge_pins(c, {n: target[n][0] for n in dig}, "t", box, 0.9)
    bot = ["ua0", "ib_r1", "vreset_src"]
    edge_pins(c, {n: target[n][0] for n in bot}, "b", box, 3.0)
    edge_pins(c, {n: target[n][1] for n in ana if n not in bot}, "l", box, 2.0)
    edge_pins(c, {"vdd": 1, "vss": 2}, "r", box, 4.0)
    failed = route_and_write(c, box, base=0.8)
    print(f"AREA {c.name} {W:.2f} x {H:.2f} = {W * H:.0f} um^2")
    print("FAILED:", failed if failed else "none")
    return failed



# ============================================================================ bias_b1 rev C
# columns left -> right, entries bottom -> top; an entry is an instance, (instance, 90) = rotated 90 deg
# (counter-clockwise), or a list of instances placed side by side.  Instance names: cells/bias/bias_b1.spice
COLS_C = [[("Xd2", 90), ("Xd1", 90), ("Xd0", 90)],
          ["Xvi", ("Xd3", 90), ["Xx2", "Xxst", "Xx4"]],
          ["Xi2", "Xi4", "Xx0", "Xx1"],
          ["Xi0", "Xi1", "Xx3"],
          ["Xg", ("Xr", 90)],
          ["Xm", "Xi3"]]
E_C, G_C, GX_C = 2.0, 2.0, 2.5


def b1c(route=True, cols=None):
    cols = cols or COLS_C
    c = Top("bias_b1")
    conns = conn("bias_b1")
    geo, rot, pos = {}, {}, {}

    def dims(e):
        i, r = (e if isinstance(e, tuple) else (e, 0))
        g = geo.setdefault(i, load_geo(conns[i][0]))
        rot[i] = r
        return (g["H"], g["W"]) if r else (g["W"], g["H"])

    def entry_dims(e):
        if isinstance(e, list):
            ds = [dims(x) for x in e]
            return sum(d[0] for d in ds) + 1.5 * (len(ds) - 1), max(d[1] for d in ds)
        return dims(e)

    x, Hmax = E_C, 0.0
    for col in cols:
        wcol = max(entry_dims(e)[0] for e in col)
        y = E_C
        for e in col:
            we, he = entry_dims(e)
            xe = x + (wcol - we) / 2
            for it in (e if isinstance(e, list) else [e]):
                i = it[0] if isinstance(it, tuple) else it
                w_, h_ = dims(it)
                pos[i] = (snap(xe + (w_ if rot[i] else 0)), snap(y))
                xe += w_ + 1.5
            y += he + G_C
        Hmax = max(Hmax, y - G_C)
        x += wcol + GX_C
    W, H = snap(x - GX_C + E_C), snap(Hmax + E_C)
    leaf = sum(g["W"] * g["H"] for g in geo.values())
    print(f"PLACE bias_b1 {W:.1f} x {H:.1f} = {W * H:.0f} um^2  (leaf cells {leaf:.0f} um^2, "
          f"x{W * H / leaf:.2f})")
    if not route:
        for inst, (px, py) in sorted(pos.items()):
            print(f"  {inst:5s} {conns[inst][0]:12s} at ({px:6.1f}, {py:6.1f})  {geo[inst]['W']:.1f} x "
                  f"{geo[inst]['H']:.1f}{'  rot90' if rot[inst] else ''}")
        return []
    for inst, (px, py) in pos.items():
        c.place(inst, conns[inst][0], px, py, conns[inst][1], rot=rot[inst])
    box = (0, 0, W, H)
    ports = [p_ for p_ in SUB["bias_b1"]["ports"] if p_ not in ("vdd", "vss")]
    dig = ports[:52]
    ana = ports[52:]
    target = {}
    for inst, pl in c.placed.items():
        for pn, r in pl["pins"].items():
            net = pl["nets"].get(pn)
            if net is not None and net not in target:
                target[net] = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
    edge_pins(c, {n: target[n][0] for n in dig}, "t", box, 0.9)
    edge_pins(c, {"ua0": target["ua0"][0]}, "b", box, 3.0)
    edge_pins(c, {n: target[n][1] for n in ana if n != "ua0"}, "l", box, 2.0)
    edge_pins(c, {"vdd": 1, "vss": 2}, "r", box, 4.0)
    failed = route_and_write(c, box, base=0.8)
    print(f"AREA {c.name} {W:.2f} x {H:.2f} = {W * H:.0f} um^2")
    print("FAILED:", failed if failed else "none")
    return failed


# ============================================================================ bias_b1, floorplan frame (G2)
# Frame from the integrator (2026-11-20): block origin = tile (80, 12), 265 x 115 um (D1 grew to tile x 8-78).
#   notch N1 (R1 corner)  local x 182-222, y 0-42     : empty (R1's top-edge pins at y = 42)
#   notch N2 (tau trim)   local x 0-23,       y 104-115 : empty
#   feed-through corridor above N1 (R1's vreset/abus/en_b/vsrc + vdd/vss straps, drawn by the integrator):
#                         local x 196-222, y 42-115 : no Metal3 from this block
#   ua[0]: bottom edge, local x 244.3-250.3 (tile 324.3-330.3); analog outputs top edge west;
#   digital codes top edge east; vth_ref / vreset_src / ib_r1 as pins on the N1 top edge at R1's
#   pin positions (R1 box-local x 2.00 / 4.6 / 12.3).
FR_W, FR_H = 265.0, 115.0
N1 = (182.0, 0.0, 222.0, 42.0)
N2 = (0.0, 104.0, 23.0, 115.0)
CORR = (196.0, 42.0, 222.0, 115.0)
UA0 = (244.3, 250.3)
PLACE_F = {   # inst: (x, y, rot)  (rot 90: x is the right edge of the rotated footprint)
    # C1: resistor DACs el/vr/vc rotated (code pins face east)
    "Xd2": (1.0 + 38.58 - (38.58 - 37.53) / 2, 1.0, 90), "Xd1": (1.0 + 38.58, 34.0, 90),
    "Xd0": (1.0 + 38.58 - (38.58 - 36.32) / 2, 67.0, 90),
    # C2: idac_n (vbp_w), receivers, idac_n (vbp_syn) on top (code pins near the top edge)
    "Xi4": (43.0, 1.0, 0), "Xx0": (44.4, 37.3, 0), "Xx1": (43.0, 46.0, 0), "Xx3": (57.8, 46.0, 0),
    "Xx2": (43.0, 54.7, 0), "Xxst": (53.6, 54.7, 0), "Xx4": (43.0, 65.8, 0),
    "Xi2": (43.0, 76.0, 0),
    # C3: V-to-I, ladder
    "Xvi": (72.0, 1.0, 0), "Xg": (76.0, 47.4, 0),
    # C4: idac_p x 3 (code pins on top)
    "Xi0": (131.0, 1.0, 0), "Xi1": (131.0, 37.9, 0), "Xi3": (131.0, 74.8, 0),
    # over the R1 notch (partly under the Metal3 corridor; its pins leave on Metal2)
    "Xr": (183.0, 44.0, 0),
    # east column: master (ua[0] at the bottom), vth_ref DAC rotated above it
    "Xm": (231.5, 1.0, 0), "Xd3": (263.96, 66.3, 90),
}
# M3 proposal (b1d): west trim.  The west edge moves east by WT (default 23 um = the N2 notch width), so the
# block becomes tile x 103-345 (242 x 115) and N2 disappears; tile x 80-103, y 12-127 is freed as one rectangle.
# The east group (rails, master, vth_ref DAC), N1, the corridor, ua[0] and every pin keep their tile positions;
# the west columns (C1-C4) keep their old local x, i.e. they move east by WT and close the empty column at
# old local x 156-183.  B1_WT=0 rebuilds the rev C frame.
WT = float(os.environ.get("B1_WT", "23.0"))
if WT:
    _EAST = ("Xr", "Xm", "Xd3")
    PLACE_F = {i: ((x - WT if i in _EAST else x), y, r) for i, (x, y, r) in PLACE_F.items()}
    FR_W = FR_W - WT
    N1 = (N1[0] - WT, N1[1], N1[2] - WT, N1[3])
    CORR = (CORR[0] - WT, CORR[1], CORR[2] - WT, CORR[3])
    UA0 = (UA0[0] - WT, UA0[1] - WT)
    N2 = None if WT >= N2[2] else (N2[0], N2[1], N2[2] - WT, N2[3])

# M3 integration (b1int, MIL-133): all re-packed leaves (vdacr_* packed, bias_rails compact, idac_p/_n shorter)
# in the 242 x 115 frame, plus a bottom pocket NB west of N1 (local x 131-159, y 0-40; tile x 234-262, y 12-52).
# Together with N1 it gives the integrator one free rectangle tile x 234-302, y 12-52 (N1 keeps its 42 um height).
#   C1: the 3 rotated resistor DACs (now 63 um tall) + the six receivers on top (under the analog output pins)
#   C2: idac_n (vbp_w), idac_p Xi3 (vbn_ax, moved from C4), idac_n (vbp_syn)
#   C3: V-to-I + ladder (unchanged);  C4: Xi0 / Xi1 only, lifted above the pocket.
# Every pin is drawn at its b1d position (b1_pins_242.json), i.e. the tile positions are unchanged.
# B1_M3=0 rebuilds the b1d placement (needs the M2 leaves: VDACR_PACK=0 RAILS_C=0 and the old idacs).
M3 = os.environ.get("B1_M3", "1") == "1" and WT == 23.0
NB = None
PINS_REF = None
if M3:
    NB = (131.0, 0.0, N1[0], 40.0)
    PINS_REF = json.loads((HERE / "b1_pins_242.json").read_text())
    _rx0 = (1.0 - 43.0, 70.0 - 37.3)          # receiver group: same relative layout as in the old C2
    PLACE_F = {
        "Xd2": (1.0 + 39.23, 1.0, 90),     # M3 vdac: vdacr_vc R_base 60 sq -> 39.23 tall, west edge at x 1.0
        "Xd1": (1.0 + 38.58, 22.8, 90),
        "Xd0": (1.0 + 38.58 - (38.58 - 36.32) / 2, 44.6, 90),
        "Xx0": (44.4 + _rx0[0], 37.3 + _rx0[1], 0), "Xx1": (43.0 + _rx0[0], 46.0 + _rx0[1], 0),
        "Xx3": (57.8 + _rx0[0], 46.0 + _rx0[1], 0), "Xx2": (43.0 + _rx0[0], 54.7 + _rx0[1], 0),
        "Xxst": (53.6 + _rx0[0], 54.7 + _rx0[1], 0), "Xx4": (43.0 + _rx0[0], 65.8 + _rx0[1], 0),
        "Xi4": (43.0, 1.0, 0), "Xi3": (43.0, 36.0, 0), "Xi2": (43.0, 71.3, 0),
        "Xvi": (72.0, 1.0, 0), "Xg": (76.0, 47.4, 0),
        "Xi0": (131.0, 43.18, 0), "Xi1": (131.0, 77.44, 0),
        "Xr": (160.0, 44.0, 0),
        "Xm": (208.5, 1.0, 0), "Xd3": (240.96, 66.3, 90),
    }

# R2 re-pack (MIL-344, branch r2-b1-pack): the C4 column (idac_p Xi0 / Xi1 above pocket NB) is removed, so the
# west columns C1-C3 sit directly west of N1 and the frame is 28 um narrower (214 x 115, tile x 131-345); NB is gone.
#   C1: the 3 rotated resistor DACs (packed tighter), idac_p Xi0 on top, receivers beside / above it
#   C2, C3: unchanged;  rx_n1 on top of C2.   Over N1: rails + idac_p Xi1 rotated (code pins west).
# The east group (R1/N1, corridor, rails, master, vth_ref DAC), ua[0], vdd/vss and every digital pin keep their
# tile positions (local x - 28); the 10 analog outputs keep their local x (they move 28 um east in the tile).
# Freed: tile x 103-131 joins RW (x 80-103) into one 49 x 104 bay (with the 2 um block gap) west of B1.
R2 = M3 and os.environ.get("B1_R2", "1") == "1"
if R2:
    R2_DX = float(os.environ.get("B1_R2DX", "28.0"))   # west trim; 25 = 6 um C3 | N1 channel
    FR_W = FR_W - R2_DX
    N1 = (N1[0] - R2_DX, N1[1], N1[2] - R2_DX, N1[3])
    # The top level runs no Metal3 through the corridor (R1 feed-throughs are Metal4 at tile x 276-296; only Metal3
    # jogs at tile y 54.0-54.8 = local 42.0-42.8 on N1's top edge), so the Metal3 keep-out is a strip local y 42-43.5.
    CORR = (CORR[0] - R2_DX, CORR[1], CORR[2] - R2_DX, float(os.environ.get("B1_CORR_TOP", "43.5")))
    UA0 = (UA0[0] - R2_DX, UA0[1] - R2_DX)
    NB = None
    _OUTS = ("vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_prb", "el", "vth_cmp", "vbn_ax", "vbp_w", "ua0_stim_out")
    PINS_REF = {n: [r[0] - R2_DX, r[1], r[2] - R2_DX, r[3]] for n, r in PINS_REF.items()}
    # The 10 analog outputs leave on the WEST edge, local y 104.5-113.5 (tile y 116.5-125.5): above B1's top edge the
    # Metal3 band y 127-140 is full, while the old top-west corner (tile x 101-131, y 116-126.5) is empty and opens
    # into the bias channel. B1_R2_OUTPINS=top keeps them on the top edge (same local x as M3).
    if os.environ.get("B1_R2_OUTPINS", "west") == "west":
        for k, n in enumerate(_OUTS):
            y = 113.5 - k * 1.0
            PINS_REF[n] = [0.0, y - 0.2, 0.4, y + 0.2]
    else:
        PINS_REF.update({n: json.loads((HERE / "b1_pins_242.json").read_text())[n] for n in _OUTS})
    (OUT / "b1_pins_r2.json").write_text(json.dumps(PINS_REF, indent=0))
    _E = lambda i: (PLACE_F[i][0] - R2_DX, PLACE_F[i][1], PLACE_F[i][2])
    PLACE_F = {
        "Xd2": (1.0 + 39.23, 1.0, 90), "Xd1": (1.0 + 38.58, 21.8, 90),
        "Xd0": (1.0 + 38.58 - (38.58 - 36.32) / 2, 42.6, 90),
        "Xi0": (1.0, 67.0, 0),
        "Xx4": (27.4, 67.0, 0), "Xx2": (27.4, 77.0, 0), "Xxst": (27.4, 88.0, 0),
        "Xx0": (1.0, 100.3, 0), "Xx1": (24.2, 100.3, 0),
        "Xi4": (43.0, 1.0, 0), "Xi3": (43.0, 36.0, 0), "Xi2": (43.0, 71.3, 0), "Xx3": (43.0, 104.3, 0),
        "Xvi": (72.0, 1.0, 0), "Xg": (76.0, 47.4, 0),
        "Xr": _E("Xr"), "Xi1": (N1[0] + 1.0 + 32.26, float(os.environ.get("B1_XI1_Y", "83.7")), 90),
        "Xm": _E("Xm"), "Xd3": _E("Xd3"),
    }


def pin_at(c, net, r):
    c.p("metal3", r, net, term=True)
    c.label(net, "metal3", r, "power" if net == "vdd" else ("ground" if net == "vss" else "signal"))


def b1f(route=True):
    c = Top("bias_b1")
    conns = conn("bias_b1")
    leaf = 0.0
    boxes = {}
    for inst, (x, y, rot) in PLACE_F.items():
        g = load_geo(conns[inst][0])
        leaf += g["W"] * g["H"]
        bb = (x, y, x + g["W"], y + g["H"]) if rot == 0 else (x - g["H"], y, x, y + g["W"])
        boxes[inst] = bb
    # sanity: inside the frame, out of the notches, no overlaps
    def ov(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    bad = [i for i, b in boxes.items() if b[0] < 0.5 or b[1] < 0.5 or b[2] > FR_W - 0.5 or b[3] > FR_H - 0.5
           or ov(b, N1) or (N2 and ov(b, N2)) or (NB and ov(b, (NB[0] - 1.0, NB[1], NB[2], NB[3] + 1.0)))]
    bad += [f"{i}/{j}" for i in boxes for j in boxes if i < j and ov(boxes[i], boxes[j])]
    nb_a = (NB[2] - NB[0]) * (NB[3] - NB[1]) if NB else 0.0
    print(f"PLACE bias_b1 frame {FR_W} x {FR_H} = {FR_W * FR_H:.0f} um^2 (minus notches "
          f"{FR_W * FR_H - 40 * 42 - (N2[2] * 11 if N2 else 0) - nb_a:.0f}); leaf cells {leaf:.0f} um^2; problems: {bad or 'none'}")
    if not route:
        for i, b in sorted(boxes.items(), key=lambda kv: kv[1]):
            print(f"  {i:5s} {conns[i][0]:12s} x {b[0]:6.2f}-{b[2]:6.2f}  y {b[1]:6.2f}-{b[3]:6.2f}")
    if not route or bad:
        return bad
    for inst, (x, y, rot) in PLACE_F.items():
        c.place(inst, conns[inst][0], x, y, conns[inst][1], rot=rot)
    box = (0, 0, FR_W, FR_H)
    # keep-outs
    c.forbid_box(("m2", "m3"), (N1[0] - 0.3, 0, N1[2] + 0.3, N1[3]))
    if N2:
        c.forbid_box(("m2", "m3"), (0, N2[1], N2[2] + 0.3, FR_H))
    c.forbid_box(("m3",), CORR)
    if NB:
        c.forbid_box(("m2", "m3"), (NB[0] - 0.3, 0, NB[2], NB[3] + 0.3))
    if PINS_REF:
        for net, r in PINS_REF.items():
            pin_at(c, net, tuple(r))
        if R2:   # R2: keep B1's own Metal3 out of the top pin row between the pins (top-level stubs land there)
            xs = sorted((r[0], r[2]) for r in PINS_REF.values() if r[3] >= FR_H - 0.6)
            for (a0, a1), (b0, b1) in zip(xs, xs[1:]):
                if b0 - a1 > 1.0:
                    c.forbid_box(("m3",), (a1 + 0.35, FR_H - 1.6, b0 - 0.35, FR_H))
        failed = route_and_write(c, box, base=0.8)
        print(f"AREA {c.name} {FR_W:.2f} x {FR_H:.2f} = {FR_W * FR_H:.0f} um^2 (notches N1 + NB)")
        print("FAILED:", failed if failed else "none")
        return failed
    # pins
    ports = [p_ for p_ in SUB["bias_b1"]["ports"] if p_ not in ("vdd", "vss")]
    dig, ana = ports[:52], ports[52:]
    target = {}
    for inst, pl in c.placed.items():
        for pn, r in pl["pins"].items():
            net = pl["nets"].get(pn)
            if net is not None and net not in target:
                target[net] = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
    yt = (FR_H - 0.9, FR_H - 0.5)
    # R1 interface on the N1 top edge
    for net, xr in (("vth_ref", 2.00), ("vreset_src", 4.6), ("ib_r1", 12.3)):
        x = N1[0] + xr
        pin_at(c, net, (x - 0.2, N1[3] + 0.0, x + 0.2, N1[3] + 0.4))
    # ua[0] on the bottom edge (6 um, under the ua[0] strap)
    pin_at(c, "ua0", (UA0[0], 0.5, UA0[1], 1.1))
    # analog outputs: top edge, west (east of N2)
    outs = ["vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_prb", "el", "vth_cmp", "vbn_ax", "vbp_w", "ua0_stim_out"]
    for k, net in enumerate(outs):
        x = 26.0 - WT + k * 2.6
        pin_at(c, net, (x - 0.2, yt[0], x + 0.2, yt[1]))
    # digital codes: top edge east, ordered by target x; mode lines east of the corridor
    mode = ["ua0_s0", "ua0_s1", "ua0_stim", "ua0_int", "bias_en", "ib_x2"]
    codes = sorted([n for n in dig if n not in mode], key=lambda n: target[n][0])
    lo, hi = 100.0 - WT, 194.0 - WT
    step = (hi - lo) / (len(codes) - 1)
    for k, net in enumerate(codes):
        x = snap(lo + k * step)
        pin_at(c, net, (x - 0.2, yt[0], x + 0.2, yt[1]))
    for k, net in enumerate(sorted(mode, key=lambda n: target[n][0])):
        x = 232.0 - WT + k * 6.0
        pin_at(c, net, (x - 0.2, yt[0], x + 0.2, yt[1]))
    # power on the east edge
    for net, y in (("vdd", 50.0), ("vss", 56.0)):
        pin_at(c, net, (FR_W - 0.9, y - 0.2, FR_W - 0.5, y + 0.2))
    failed = route_and_write(c, box, base=0.8)
    print(f"AREA {c.name} {FR_W:.2f} x {FR_H:.2f} = {FR_W * FR_H:.0f} um^2")
    print("FAILED:", failed if failed else "none")
    return failed

if __name__ == "__main__":
    name = sys.argv[1]
    f = {"bias_vblk": vblk, "bias_b1_w": lambda: b1("w"), "bias_b1_n": lambda: b1("n"),
         "place_w": lambda: b1("w", False), "place_n": lambda: b1("n", False),
         "bias_b1": b1f, "place_c": lambda: b1c(False), "place_f": lambda: b1f(False)}[name]()
    sys.exit(1 if f else 0)
