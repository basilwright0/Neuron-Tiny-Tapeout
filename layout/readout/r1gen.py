"""Generate the R1 corner layout r1_corner (gf180mcuD): pad driver pad_psf + its bias receiver +
Vreset buffer, in the 40 x 40 um corner box (tile 262,14 - 302,54).

    scripts/eda.sh "cd layout/readout && python3 r1gen.py"     (build.sh runs it, then magic/netgen/klayout)

Schematic: cells/readout/r1_corner.spice (+ readout.spice pad_psf, vreset/vreset_buf.spice).
Inputs : PDK device cells in devices/ (gen_devices.tcl, gf180mcu::{n,p}fet_03v3_draw, guard 0, no gate
         contacts).  Everything else (gate bars, rings, straps, routing) is drawn here with explicit
         coordinates: the block has 10 devices, so it is hand-placed and hand-routed in code.
Outputs: r1_corner_base.mag (device placements), r1_corner_paint.tcl (all drawn geometry, labels,
         ports), preview.png.

Units um, origin = box lower-left (tile x 262, y 14).  Layers: Metal1-3 only (no Metal4/5).
Routing convention: device S/D stripes -> horizontal Metal2 bars (via1 on the stripes); stripes tied
to a ring net (vdd, t, vss) drop to the ring in Metal1; long runs and pins are vertical Metal3.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CELL = "r1_corner"
U = 200                      # magic internal units per um in device files (magscale 1 10)
W, H = 40.0, 40.0
RING = 0.60                  # p-tap (VSS) ring on the box edge
MARGIN = 0.80                # device extents -> inner edge of their tap ring
NWE = 0.12                   # nwell enclosure of the n-tap ring

# pin x positions (top edge, Metal3 verticals) and rails
PIN_X = {"vrin": 4.60, "ibias": 12.30, "vreset": 15.20, "abus": 18.00, "en_b": 29.02}
VTH_X, VSRC_X = 2.00, 34.00  # vsrc buffer pins (Metal3, top edge)
PAD_X = (18.64, 24.64)       # ua[1] entry on the bottom edge (tile x 280.64-286.64)
VDD_RAIL = (35.00, 36.50)    # Metal3, full height
VSS_RAIL = (37.30, 38.80)

# ---------------------------------------------------------------------------- devices
# name: (cell, cx, cy, stripe nets left->right, gate net)
DEVS = {
    # band 1: pad follower in its own n-well (body = source = pad)
    "XPF": ("p_w5_l0p5_nf8", 21.64, 6.20, ["pad", "vss"] * 4 + ["pad"], "abus"),
    # band 2: vdd well -- bias pmos row
    "XPT": ("p_w1_l1_nf3", 5.06, 17.00, ["vdd", "t", "vdd", "t"], "ibias"),
    "XPR": ("p_w0p4_l1_nf1", 9.46, 17.30, ["vdd", "ibias"], "ibias"),
    "XPB": ("p_w4_l1_nf10", 19.22, 17.00, ["s", "pad"] * 5 + ["s"], "ibias"),
    "XPE": ("p_w5_l0p28_nf2", 29.02, 17.00, ["vdd", "s", "vdd"], "en_b"),
    # band 3: Vreset input pair in its own n-well (body = tail t), nmos mirror in a p-tap ring
    "XM1": ("p_w5_l0p5_nf4", 4.60, 29.00, ["t", "a"] * 2 + ["t"], "vrin"),
    "XM2": ("p_w5_l0p5_nf4", 10.60, 29.00, ["t", "vreset"] * 2 + ["t"], "vreset"),
    "XN1": ("n_w2_l2_nf2", 20.40, 28.50, ["vss", "a", "vss"], "a"),
    "XN2": ("n_w2_l2_nf2", 27.00, 28.50, ["vss", "vreset", "vss"], "a"),
    # top: abus weak pull-down (gate = vdd)
    "XPD": ("n_w0p22_l20_nf1", 18.00, 37.00, ["vss", "abus"], "vdd"),
    # vsrc buffer (cells/vsrc/vsrc_buf.spice)
    # region A (bottom-left, n-well merged into the band-2 vdd well): input pair, tail, pull-up
    "XVB": ("p_w5_l2_nf2", 4.30, 4.50, ["t2", "o", "t2"], "vth_ref"),
    "XVA": ("p_w5_l2_nf2", 10.70, 4.50, ["t2", "a2", "t2"], "vsrc"),
    "XVT": ("p_w0p22_l2_nf1", 5.50, 10.22, ["vdd", "t2"], "ibias"),     # cx re-aligned below
    "XVU": ("p_w1p6_l1_nf1", 9.00, 9.60, ["vdd", "vsrc"], "ibias"),
    # upper row inside the (extended) Vreset-mirror p-tap ring: mirror + shunt
    "XVNA": ("n_w1_l4_nf1", 20.00, 32.60, ["vss", "a2"], "a2"),
    "XVNB": ("n_w1_l4_nf1", 25.60, 32.60, ["vss", "o"], "a2"),
    "XVS": ("n_w2p5_l0p5_nf4", 31.20, 32.60, ["vss", "vsrc", "vss", "vsrc", "vss"], "o"),
    # region B (bottom-right): Miller cap, pfet in its own n-well on vsrc (accumulation, gate = o)
    "XVC": ("p_w8_l7_nf1", 33.55, 6.50, ["vsrc", "vsrc"], "o"),
}


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
    gates = sorted(R.get("nmos", []) + R.get("pmos", []))
    conts = sorted(R.get("ndiffc", []) + R.get("pdiffc", []))
    allr = [r for v in R.values() for r in v]
    return dict(name=name, ts=ts, R=R, diff=bb(diff), gates=gates, conts=conts, bbox=bb(allr))


def snap(v, g=0.005):
    return round(round(v / g) * g, 4)


class Layout:
    def __init__(self):
        self.paint = []
        self.labels = []

    def p(self, layer, r):
        x0, y0, x1, y1 = r
        self.paint.append((layer, (snap(min(x0, x1)), snap(min(y0, y1)), snap(max(x0, x1)), snap(max(y0, y1)))))

    def label(self, text, layer, r, use):
        self.labels.append((text, layer, r, use))


L = Layout()


def box(cx, cy, hw, hh):
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def wire(layer, x0, y0, x1, y1, w):
    """Manhattan segment of width w (ends extended by w/2)."""
    h = w / 2
    if abs(y1 - y0) < 1e-9:
        L.p(layer, (min(x0, x1) - h, y0 - h, max(x0, x1) + h, y0 + h))
    elif abs(x1 - x0) < 1e-9:
        L.p(layer, (x0 - h, min(y0, y1) - h, x0 + h, max(y0, y1) + h))
    else:
        raise ValueError("non-Manhattan wire")


def path(layer, pts, w):
    for a, b in zip(pts, pts[1:]):
        wire(layer, a[0], a[1], b[0], b[1], w)


def via1(x, y, pad=0.40):
    L.p("metal1", box(x, y, pad / 2, pad / 2))
    L.p("metal2", box(x, y, pad / 2, pad / 2))
    L.p("via1", box(x, y, 0.13, 0.13))


def via2(x, y, pad=0.44):
    L.p("metal2", box(x, y, pad / 2, pad / 2))
    L.p("metal3", box(x, y, pad / 2, pad / 2))
    L.p("via2", box(x, y, 0.14, 0.14))


def stack(x, y):
    via1(x, y)
    via2(x, y)


def stack2(xc, y):
    """Two via1+via2 stacks at xc -/+ 0.35 with merged Metal1/2/3 pads."""
    for x in (xc - 0.35, xc + 0.35):
        stack(x, y)
    for lay in ("metal1", "metal2", "metal3"):
        L.p(lay, (xc - 0.57, y - 0.22, xc + 0.57, y + 0.22))


# ---------------------------------------------------------------------------- device helpers
lib = {}
inst = {}
for name, (cell, cx, cy, nets, g) in DEVS.items():
    if cell not in lib:
        lib[cell] = load_dev(cell)
    lc = lib[cell]
    if len(lc["conts"]) != len(nets):
        raise SystemExit(f"{name}: {len(lc['conts'])} stripes, {len(nets)} nets")
    inst[name] = dict(lc=lc, cx=cx, cy=cy, nets=nets, g=g,
                      sx=[snap(cx + (c[0] + c[2]) / 2) for c in lc["conts"]],
                      dbot=snap(cy + lc["diff"][1]), dtop=snap(cy + lc["diff"][3]),
                      x0=snap(cx + lc["diff"][0]), x1=snap(cx + lc["diff"][2]))


def move(name, dx=0.0, dy=0.0):
    d = inst[name]
    d["cx"], d["cy"] = snap(d["cx"] + dx), snap(d["cy"] + dy)
    for k in ("dbot", "dtop"):
        d[k] = snap(d[k] + dy)
    for k in ("x0", "x1"):
        d[k] = snap(d[k] + dx)
    d["sx"] = [snap(x + dx) for x in d["sx"]]


# vsrc buffer: the tail's t2 stripe sits right above XVB's right t2 stripe (one Metal1 drop joins them)
move("XVT", dx=inst["XVB"]["sx"][2] - inst["XVT"]["sx"][1])


def gate_bar(name, contacts=(), xext=()):
    """Poly bar 0.45 above the diffusion joining all gates; polycontacts (with 0.38 Metal1 pads) at the
    given absolute x.  Returns the bar centre y."""
    d = inst[name]
    lc, cx, cy = d["lc"], d["cx"], d["cy"]
    hcy = snap(d["dtop"] + 0.45)
    gx = [(cx + gt[0], cx + gt[2]) for gt in lc["gates"]]
    for a, b in gx:
        L.p("polysilicon", (a, d["dtop"], b, hcy + 0.18))
    xs = [a for a, b in gx] + [b for a, b in gx] + [x - 0.18 for x in contacts] + [x + 0.18 for x in contacts] + list(xext)
    L.p("polysilicon", (min(xs), hcy - 0.18, max(xs), hcy + 0.18))
    for x in contacts:
        L.p("metal1", box(x, hcy, 0.19, 0.19))
        L.p("polycontact", box(x, hcy, 0.115, 0.115))
    d["hcy"] = hcy
    return hcy


def stripe_vias(name, net, ys):
    d = inst[name]
    for x, n in zip(d["sx"], d["nets"]):
        if n == net:
            for y in ys:
                via1(x, y)
            if len(ys) > 1:      # one merged pad (no same-net notches between the cut pads)
                for lay in ("metal1", "metal2"):
                    L.p(lay, (x - 0.2, min(ys) - 0.2, x + 0.2, max(ys) + 0.2))


def stripe_m1(name, net, y_to):
    """Extend the Metal1 of every stripe of `net` from the diffusion edge to y_to (0.23 wide)."""
    d = inst[name]
    for x, n in zip(d["sx"], d["nets"]):
        if n == net:
            ya = d["dbot"] + 0.07 if y_to < d["dbot"] else d["dtop"] - 0.07
            L.p("metal1", (x - 0.115, ya, x + 0.115, y_to))


def ext_box(names, bars=True):
    """Union of diffusion (+ poly end caps) and gate-bar pads of the named devices."""
    x0 = min(inst[n]["x0"] for n in names)
    x1 = max(inst[n]["x1"] for n in names)
    y0 = min(inst[n]["dbot"] - 0.22 for n in names)
    y1 = max((inst[n]["dtop"] + 0.45 + 0.19) if bars else inst[n]["dtop"] for n in names)
    return (x0, y0, x1, y1)


def tap_ring(names, kind, net, m=MARGIN):
    """Tap ring (0.6 wide, inner edge m from the devices).  kind 'n' adds the n-well around it.
    Returns the ring outer box."""
    e = ext_box(names)
    ri = (e[0] - m, e[1] - m, e[2] + m, e[3] + m)
    ro = (ri[0] - 0.6, ri[1] - 0.6, ri[2] + 0.6, ri[3] + 0.6)
    sides = [(ro[0], ro[1], ro[2], ri[1]), (ro[0], ri[3], ro[2], ro[3]),
             (ro[0], ro[1], ri[0], ro[3]), (ri[2], ro[1], ro[2], ro[3])]
    diff = "nsubdiff" if kind == "n" else "psubdiff"
    cont = diff + "cont"
    c = (0.6 - 0.23) / 2
    for k, r in enumerate(sides):
        L.p(diff, r)
        L.p("metal1", r)
        if k < 2:
            L.p(cont, (r[0] + c + 0.1, r[1] + c, r[2] - c - 0.1, r[3] - c))
        else:
            L.p(cont, (r[0] + c, r[1] + c + 0.6, r[2] - c, r[3] - c - 0.6))
    if kind == "n":
        L.p("nwell", (ro[0] - NWE, ro[1] - NWE, ro[2] + NWE, ro[3] + NWE))
    return ro


# ============================================================================ build
# ---------------------------------------------------------------- box-edge p-tap ring (VSS)
c = (RING - 0.23) / 2
for r in [(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]:
    L.p("psubdiff", r)
    L.p("metal1", r)
    if r[2] - r[0] > r[3] - r[1]:
        L.p("psubdiffcont", (r[0] + c + 0.7, r[1] + c, r[2] - c - 0.7, r[3] - c))
    else:
        L.p("psubdiffcont", (r[0] + c, r[1] + c + 0.7, r[2] - c, r[3] - c - 0.7))

# ---------------------------------------------------------------- power rails (Metal3, full height)
L.p("metal3", (VDD_RAIL[0], 0, VDD_RAIL[1], H))
L.p("metal3", (VSS_RAIL[0], 0, VSS_RAIL[1], H))
vssx = (VSS_RAIL[0] + VSS_RAIL[1]) / 2
vddx = (VDD_RAIL[0] + VDD_RAIL[1]) / 2
# vss rail <-> box ring (right side) at bottom and top
for y in (1.6, H - 1.6):
    L.p("metal1", (VSS_RAIL[0], y - 0.3, W, y + 0.3))
    stack2(vssx, y)
    L.p("metal1", (W - RING, y - 0.3, W, y + 0.3))

# ---------------------------------------------------------------- band 1: pad follower XPF
d = inst["XPF"]
hcy = gate_bar("XPF", contacts=[PIN_X["abus"] + 0.10])
ro_pad = tap_ring(["XPF"], "n", "pad")
y_pad, y_vss = d["cy"] - 1.25, d["cy"] + 1.25
stripe_vias("XPF", "pad", (y_pad - 0.26, y_pad + 0.26))
stripe_vias("XPF", "vss", (y_vss - 0.26, y_vss + 0.26))
# pad bar (Metal2, 1.0 wide) across the device and onto both ring sides (well/body = pad)
L.p("metal2", (ro_pad[0], y_pad - 0.5, ro_pad[2], y_pad + 0.5))
for x in (ro_pad[0] + 0.3, ro_pad[2] - 0.3):
    for y in (y_pad - 0.26, y_pad + 0.26):
        via1(x, y)
# vss bar (Metal2, 1.0 wide) east to the vss rail
L.p("metal2", (d["x0"] - 0.2, y_vss - 0.5, VSS_RAIL[1], y_vss + 0.5))
for x in (vssx - 0.35, vssx + 0.35):
    for y in (y_vss - 0.26, y_vss + 0.26):
        via2(x, y)
# ua[1] strap: Metal3 6 um wide from the bottom edge onto the pad bar (via2 array)
L.p("metal3", (PAD_X[0], 0, PAD_X[1], y_pad + 0.5))
x = PAD_X[0] + 0.40
while x < PAD_X[1] - 0.35:
    for y in (y_pad - 0.26, y_pad + 0.26):
        via2(x, y)
    x = snap(x + 0.60)
L.label("pad", "metal3", (PAD_X[0], 0.0, PAD_X[1], 0.6), "signal")
# XPF gate = abus: stack to the abus Metal3 line
stack(PIN_X["abus"] + 0.10, hcy)
L.p("metal3", (PIN_X["abus"] + 0.10 - 0.22, hcy - 0.22, PIN_X["abus"] + 0.10 + 0.22, hcy + 0.22))

# ---------------------------------------------------------------- band 2: vdd well
for n in ("XPT", "XPR"):
    gate_bar(n, contacts=[inst["XPR"]["sx"][1]] if n == "XPR" else [])
# XPT bar -> XPR bar (same y) in poly
hb = inst["XPT"]["hcy"]
assert inst["XPT"]["hcy"] == inst["XPR"]["hcy"], "XPT/XPR gate bars must line up (poly bridge)"
L.p("polysilicon", (inst["XPT"]["cx"], hb - 0.18, inst["XPR"]["cx"], hb + 0.18))
hb_b = gate_bar("XPB", contacts=[PIN_X["ibias"]])
hb_e = gate_bar("XPE", contacts=[PIN_X["en_b"]])
ro_vdd = tap_ring(["XPT", "XPR", "XPB", "XPE"], "n", "vdd")
for n in ("XPT", "XPR", "XPE"):
    stripe_m1(n, "vdd", ro_vdd[1] + 0.6)
# XPR diode: drain stripe up to its gate pad
xr = inst["XPR"]["sx"][1]
L.p("metal1", (xr - 0.115, inst["XPR"]["dtop"] - 0.07, xr + 0.115, inst["XPR"]["hcy"]))
# ibias: XPB gate pad -> XPR gate pad (Metal1), and up to the pin (Metal3)
path("metal1", [(PIN_X["ibias"], hb_b), (xr, hb_b), (xr, inst["XPR"]["hcy"])], 0.38)
stack(PIN_X["ibias"], hb_b)
# s: XPB sources + XPE drain on one Metal2 bar; pad: XPB drains -> Metal3 down to the pad strap
cy2 = inst["XPB"]["cy"]
y_s, y_p = cy2 - 1.0, cy2 + 1.0
stripe_vias("XPB", "s", (y_s - 0.26, y_s + 0.26))
stripe_vias("XPB", "pad", (y_p - 0.26, y_p + 0.26))
stripe_vias("XPE", "s", (y_s - 0.26, y_s + 0.26))
L.p("metal2", (inst["XPB"]["sx"][0] - 0.2, y_s - 0.5, inst["XPE"]["sx"][1] + 0.2, y_s + 0.5))
L.p("metal2", (inst["XPB"]["sx"][1] - 0.2, y_p - 0.5, inst["XPB"]["sx"][-2] + 0.2, y_p + 0.5))
PADV = (22.50, 24.50)
L.p("metal3", (PADV[0], y_pad - 0.5, PADV[1], y_p + 0.5))
for x in (22.80, 23.50, 24.20):
    for y in (y_p - 0.26, y_p + 0.26):
        via2(x, y)
# en_b: XPE gate -> Metal3 up
stack(PIN_X["en_b"], hb_e)
# t: XPT drains -> Metal2 bar -> Metal2 up to the t-well ring
xt = inst["XPT"]["sx"]
stripe_vias("XPT", "t", (cy2,))
L.p("metal2", (xt[1] - 0.2, cy2 - 0.2, xt[3] + 0.2, cy2 + 0.2))
# vdd ring -> vdd rail (Metal1 bridge + stacks)
L.p("metal1", (ro_vdd[2] - 0.6, cy2 - 0.3, VDD_RAIL[1], cy2 + 0.3))
stack2(vddx, cy2)

# ---------------------------------------------------------------- band 3: Vreset buffer
h1 = gate_bar("XM1", contacts=[PIN_X["vrin"]])
h2 = gate_bar("XM2", contacts=[inst["XM2"]["cx"]])
ro_t = tap_ring(["XM1", "XM2"], "n", "t")
for n in ("XM1", "XM2"):
    stripe_m1(n, "t", ro_t[1] + 0.6)
# t from XPT (Metal2 vertical) onto the t ring bottom
L.p("metal2", (xt[3] - 0.2, cy2, xt[3] + 0.2, ro_t[1] + 0.3))
via1(xt[3], ro_t[1] + 0.3)
y_a, y_r = 28.00, 30.25
stripe_vias("XM1", "a", (y_a,))
stripe_vias("XM2", "vreset", (y_r,))
# nmos mirror: N1 diode (drain up to the gate pad), gates of N1/N2 joined in poly
hn = gate_bar("XN1", contacts=[inst["XN1"]["sx"][1]])
gate_bar("XN2")
L.p("polysilicon", (inst["XN1"]["cx"], hn - 0.18, inst["XN2"]["cx"], hn + 0.18))
xn1 = inst["XN1"]["sx"][1]
L.p("metal1", (xn1 - 0.115, inst["XN1"]["dtop"] - 0.07, xn1 + 0.115, hn))
ro_n = tap_ring(["XN1", "XN2", "XVNA", "XVNB", "XVS"], "p", "vss")
for n in ("XN1", "XN2"):
    stripe_m1(n, "vss", ro_n[1] + 0.6)
stripe_vias("XN1", "a", (y_a,))
xn2 = inst["XN2"]["sx"][1]
L.p("metal1", (xn2 - 0.115, inst["XN2"]["dtop"] - 0.07, xn2 + 0.115, y_r))
via1(xn2, y_r)
# a bar, vreset bar (Metal2)
L.p("metal2", (inst["XM1"]["sx"][1] - 0.2, y_a - 0.2, xn1 + 0.2, y_a + 0.2))
L.p("metal2", (inst["XM2"]["sx"][1] - 0.2, y_r - 0.2, xn2 + 0.2, y_r + 0.2))
# XM2 gate = vreset: pad -> via1 -> Metal2 down to the vreset bar
via1(inst["XM2"]["cx"], h2)
L.p("metal2", (inst["XM2"]["cx"] - 0.2, y_r, inst["XM2"]["cx"] + 0.2, h2))
# vrin pin, vreset pin
stack(PIN_X["vrin"], h1)
via2(PIN_X["vreset"], y_r)
# nmos ring -> vss rail (Metal1 bridge on its bottom side, east to the box ring)
yb = (ro_n[1] + ro_n[1] + 0.6) / 2
L.p("metal1", (ro_n[2] - 0.6, yb - 0.3, W, yb + 0.3))
stack2(vssx, yb)

# ---------------------------------------------------------------- top: abus pull-down XPD
d = inst["XPD"]
xg = d["cx"] + 9.0
hd = gate_bar("XPD", contacts=[xg])
stripe_m1("XPD", "vss", H - RING + 0.1)    # source straight up into the box ring
xd = d["sx"][1]
via1(xd, d["cy"])
L.p("metal2", (PIN_X["abus"] - 0.2, d["cy"] - 0.2, xd + 0.2, d["cy"] + 0.2))
via2(PIN_X["abus"], d["cy"])
# gate = vdd: Metal1 up and east to the vdd rail
ytop = 38.60
path("metal1", [(xg, hd), (xg, ytop), (vddx + 0.35, ytop)], 0.40)
stack2(vddx, ytop)

# ---------------------------------------------------------------- vsrc buffer (cells/vsrc/vsrc_buf.spice)
# Region A (x 1-14, y 1-13): XVB/XVA input pair (bodies on vdd), XVT tail, XVU pull-up, in an n-well merged
# into the band-2 vdd well (whose ring is their n-tap).  Mirror XVNA/XVNB + shunt XVS: in the Vreset-mirror
# p-tap ring (row above XN1/XN2).  Region B (x 29-38, y 1-9): Miller cap XVC in its own n-well on vsrc.
# Long nets: a2 (Metal3 A_X), o (Metal3 O_X), vsrc (Metal3 VSRC_X -> pin), vth_ref (Metal3 VTH_X -> pin).
A_X = 13.70
OA_X = 14.60
O_X = inst["XVS"]["sx"][3]
VS_GX = 11.30
Y_T2, Y_A2, Y_O = 2.60, 4.20, 5.80          # region-A Metal2 bars
Y_OH, Y_VH = 11.20, 12.00                   # region-A -> east Metal2 runs (o, vsrc)
Y_AR = 34.70                                # a2 Metal2 run in the mirror ring
# -- region A n-well (merges with the band-2 well)
ea = ext_box(["XVB", "XVA", "XVT", "XVU"])
nwa = (snap(ea[0] - 0.43), snap(ea[1] - 0.43), snap(ea[2] + 0.43), snap(ro_vdd[1] + 0.30))
L.p("nwell", nwa)
pad_nw_x0 = ro_pad[0] - NWE
assert pad_nw_x0 - nwa[2] >= 1.7, f"region-A well too close to the pad well ({pad_nw_x0 - nwa[2]:.2f})"
hp = gate_bar("XVB", contacts=[VTH_X])
assert gate_bar("XVA", contacts=[VS_GX]) == hp
ht = gate_bar("XVT")
hu = gate_bar("XVU", contacts=[PIN_X["ibias"]])
assert ht == hu, "XVT/XVU gate bars must line up (poly bridge)"
L.p("polysilicon", (inst["XVT"]["cx"], ht - 0.18, inst["XVU"]["cx"], ht + 0.18))
for n in ("XVT", "XVU"):
    stripe_m1(n, "vdd", ro_vdd[1] + 0.6)
# t2: XVT drain stripe drops straight onto XVB's right t2 stripe; pair sources on a Metal2 bar
xt2 = inst["XVT"]["sx"][1]
L.p("metal1", (xt2 - 0.115, inst["XVB"]["dtop"] - 0.07, xt2 + 0.115, inst["XVT"]["dbot"] + 0.07))
for n in ("XVB", "XVA"):
    stripe_vias(n, "t2", (Y_T2,))
L.p("metal2", (inst["XVB"]["sx"][0] - 0.2, Y_T2 - 0.2, inst["XVA"]["sx"][2] + 0.2, Y_T2 + 0.2))
# a2: XVA drain -> Metal3 A_X up to the mirror ring -> Metal2 east -> XVNA diode stripe
stripe_vias("XVA", "a2", (Y_A2,))
L.p("metal2", (inst["XVA"]["sx"][1] - 0.2, Y_A2 - 0.2, A_X + 0.2, Y_A2 + 0.2))
via2(A_X, Y_A2)
L.p("metal3", (A_X - 0.15, Y_A2 - 0.22, A_X + 0.15, Y_AR + 0.22))
via2(A_X, Y_AR)
xna = inst["XVNA"]["sx"][1]
L.p("metal2", (A_X - 0.2, Y_AR - 0.2, xna + 0.2, Y_AR + 0.2))
# o: XVB drain -> Metal2 east/north/east -> Metal3 O_X (Miller cap below, mirror/shunt above)
stripe_vias("XVB", "o", (Y_O,))
path("metal2", [(inst["XVB"]["sx"][1], Y_O), (OA_X, Y_O), (OA_X, Y_OH), (O_X, Y_OH)], 0.40)
via2(O_X, Y_OH)
# vsrc: XVA gate + XVU drain -> Metal2 north/east -> Metal3 VSRC_X
via1(VS_GX, hp)
L.p("metal2", (VS_GX - 0.2, hp, VS_GX + 0.2, Y_VH + 0.2))
stripe_vias("XVU", "vsrc", (inst["XVU"]["cy"],))
L.p("metal2", (inst["XVU"]["sx"][1] - 0.2, inst["XVU"]["cy"] - 0.2, VS_GX + 0.2, inst["XVU"]["cy"] + 0.2))
L.p("metal2", (VS_GX - 0.2, Y_VH - 0.2, VSRC_X + 0.2, Y_VH + 0.2))
via2(VSRC_X, Y_VH)
# vbp (ibias): XVU gate pad -> the ibias Metal3 line, extended down from band 2
stack(PIN_X["ibias"], hu)
L.p("metal3", (PIN_X["ibias"] - 0.15, hu - 0.22, PIN_X["ibias"] + 0.15, hb_b))
# vth_ref: XVB gate pad -> Metal3 pin line
stack(VTH_X, hp)
# -- mirror + shunt row (inside ro_n)
hm = gate_bar("XVNA", contacts=[xna])
assert gate_bar("XVNB") == hm
L.p("polysilicon", (inst["XVNA"]["cx"], hm - 0.18, inst["XVNB"]["cx"], hm + 0.18))
hs = gate_bar("XVS", contacts=[O_X])
for n in ("XVNA", "XVNB", "XVS"):
    stripe_m1(n, "vss", ro_n[3] - 0.3)
L.p("metal1", (xna - 0.115, inst["XVNA"]["dtop"] - 0.07, xna + 0.115, Y_AR))
via1(xna, Y_AR)
cyr = inst["XVNB"]["cy"]
stripe_vias("XVNB", "o", (cyr,))
L.p("metal2", (inst["XVNB"]["sx"][1] - 0.2, cyr - 0.2, O_X + 0.2, cyr + 0.2))
via2(O_X, cyr)
stack(O_X, hs)
Y_VS = cyr - 0.80
stripe_vias("XVS", "vsrc", (Y_VS,))
L.p("metal2", (inst["XVS"]["sx"][1] - 0.2, Y_VS - 0.2, VSRC_X + 0.2, Y_VS + 0.2))
via2(VSRC_X, Y_VS)
# -- region B: Miller cap XVC (pfet, gate o, S/D + n-well = vsrc), n-tap strip below it
d = inst["XVC"]
hc = gate_bar("XVC", contacts=[O_X])
Y_NT = 1.55
nt = (d["x0"], Y_NT - 0.30, VSS_RAIL[0] - 0.70, Y_NT + 0.30)
L.p("nsubdiff", nt)
L.p("metal1", nt)
L.p("nsubdiffcont", (nt[0] + 0.285, nt[1] + 0.185, nt[2] - 0.285, nt[3] - 0.185))
nwb = (snap(d["x0"] - 0.43), snap(nt[1] - NWE - 0.05), snap(d["x1"] + 0.43), snap(d["dtop"] + 0.43))
L.p("nwell", nwb)
assert nwb[0] - (ro_pad[2] + NWE) >= 1.7, f"region-B well too close to the pad well ({nwb[0] - ro_pad[2] - NWE:.2f})"
xc0, xc1 = d["sx"]
L.p("metal1", (xc0 - 0.115, Y_NT, xc0 + 0.115, d["dbot"] + 0.07))     # left stripe -> n-tap strip
stripe_vias("XVC", "vsrc", (4.00,))                                     # right stripe joins on Metal2
L.p("metal2", (xc0 - 0.2, 3.80, xc1 + 0.2, 4.20))
stack(O_X, hc)
stack(VSRC_X, Y_NT)
# -- long Metal3 lines
L.p("metal3", (O_X - 0.15, hc - 0.22, O_X + 0.15, hs + 0.22))
L.p("metal3", (VSRC_X - 0.15, Y_NT - 0.22, VSRC_X + 0.15, H))
L.p("metal3", (VTH_X - 0.15, hp - 0.22, VTH_X + 0.15, H))
L.label("vth_ref", "metal3", (VTH_X - 0.15, H - 0.5, VTH_X + 0.15, H), "signal")
L.label("vsrc", "metal3", (VSRC_X - 0.15, H - 0.5, VSRC_X + 0.15, H), "signal")

# ---------------------------------------------------------------- Metal3 pin lines to the top edge
starts = {"vrin": h1, "ibias": hb_b, "vreset": y_r, "abus": hcy, "en_b": hb_e}
for net, x in PIN_X.items():
    xx = x + 0.10 if net == "abus" else x
    L.p("metal3", (xx - 0.15, starts[net] - 0.22, xx + 0.15, H))
    L.label(net, "metal3", (xx - 0.15, H - 0.5, xx + 0.15, H), "signal")
L.label("vdd", "metal3", (VDD_RAIL[0], H - 0.5, VDD_RAIL[1], H), "power")
L.label("vss", "metal3", (VSS_RAIL[0], H - 0.5, VSS_RAIL[1], H), "ground")


# ============================================================================ output
def write_outputs():
    base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
    for name, d in inst.items():
        lc = d["lc"]
        b = lc["bbox"]
        base += [f"use {lc['name']}  {name}", f"timestamp {lc['ts']}",
                 f"transform 1 0 {round(d['cx'] * U)} 0 1 {round(d['cy'] * U)}",
                 f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
    base.append("<< end >>")
    (HERE / f"{CELL}_base.mag").write_text("\n".join(base) + "\n", newline="\n")
    tcl = [f"# generated by r1gen.py -- do not edit", f"load {CELL}_base", f"cellname rename {CELL}_base {CELL}",
           "tech unlock *"]
    order = ["nwell", "psubdiff", "nsubdiff", "polysilicon", "metal1", "metal2", "metal3",
             "psubdiffcont", "nsubdiffcont", "polycontact", "via1", "via2", "comment"]
    for layer in order:
        for l, r in L.paint:
            if l == layer:
                tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
    for k, (text, layer, r, use) in enumerate(L.labels, 1):
        tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
        tcl.append(f"label {text} FreeSans 0.25um 0 0 0 c {layer}")
        tcl.append(f"port make {k}; port use {use}; port class bidirectional")
    tcl.append(f"box values 0um 0um {W}um {H}um")
    tcl.append(f"save {CELL}")
    (HERE / f"{CELL}_paint.tcl").write_text("\n".join(tcl) + "\n", newline="\n")


def preview(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(12, 12))
    col = {"nwell": ("#cfe8cf", 0.6), "psubdiff": ("#e8c070", 0.7), "nsubdiff": ("#70c0e8", 0.7),
           "polysilicon": ("#d04040", 0.5), "metal1": ("#3050d0", 0.35), "metal2": ("#d020d0", 0.35),
           "metal3": ("#20a020", 0.30), "via1": ("#000000", 0.6), "via2": ("#806000", 0.6)}
    for name, d in inst.items():
        for k, rs in d["lc"]["R"].items():
            c = {"ndiff": "#40a040", "pdiff": "#a08040", "nmos": "#c03030", "pmos": "#c03030",
                 "polysilicon": "#d04040", "ndiffc": "#3050d0", "pdiffc": "#3050d0", "metal1": "#3050d0"}.get(k)
            if c:
                for r in rs:
                    ax.add_patch(Rectangle((r[0] + d["cx"], r[1] + d["cy"]), r[2] - r[0], r[3] - r[1], fc=c, alpha=0.5, lw=0))
        ax.text(d["cx"], d["cy"], name, fontsize=7, ha="center", va="center")
    for layer in col:
        for l, r in L.paint:
            if l == layer:
                ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
    for text, layer, r, use in L.labels:
        ax.text((r[0] + r[2]) / 2, r[3] + 0.2, text, fontsize=7, ha="center")
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, ec="k"))
    ax.set_xlim(-0.5, W + 0.5)
    ax.set_ylim(-0.5, H + 1.0)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    write_outputs()
    preview(HERE / "preview.png")
    print(f"{CELL}: {len(L.paint)} shapes, {len(inst)} devices")


# ============================================================================ ua[1] wrapper
# r1_ua1: r1_corner placed at (0, 14) (tile y 14) + the ua[1] connection through CH_BOT: Metal3 strap
# 6 um wide (tile x 280.64-286.64) from the tile edge up into the box, dropped from the Metal4 pin
# footprint (y 0-1, outside the 40 x 40 box) with a via3 array.  Origin = tile (262, 0).
def write_wrapper():
    y0 = 14.0
    t = ["# generated by r1gen.py -- do not edit", "load r1_ua1", "tech unlock *",
         f"box values 0um {y0:.3f}um 0um {y0:.3f}um", "getcell r1_corner"]
    t.append(f"box values {PAD_X[0]:.3f}um 0um {PAD_X[1]:.3f}um {y0 + 0.6:.3f}um; paint metal3")
    t.append(f"box values {PAD_X[0]:.3f}um 0um {PAD_X[1]:.3f}um 1.000um; paint metal4")
    x = PAD_X[0] + 0.40
    while x + 0.14 < PAD_X[1] - 0.25:
        t.append(f"box values {x - 0.14:.3f}um 0.360um {x + 0.14:.3f}um 0.640um; paint via3")
        x = snap(x + 0.60)
    t.append(f"box values {PAD_X[0]:.3f}um 0um {PAD_X[1]:.3f}um 1.000um")
    t.append("label ua1 FreeSans 0.25um 0 0 0 c metal4")
    t.append("port make 1; port use signal; port class bidirectional")
    t.append(f"box values 0um 0um {W}um {y0 + H}um")
    t.append("save r1_ua1")
    (HERE / "r1_ua1_paint.tcl").write_text("\n".join(t) + "\n", newline="\n")


if __name__ == "__main__":
    write_wrapper()
