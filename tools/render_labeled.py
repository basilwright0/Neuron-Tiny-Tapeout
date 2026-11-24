"""Labeled renders of the final tile GDS: full chip, sections / sub-sections / every neuron slot, zooms.

Every box is taken from the GDS itself: the bounding box of a top-level cell instance (or of a B1 leaf
instance inside bias_b1). Neuron names come from the repo slot map (floorplan/floorplan.py slot_map()); each
slot instance is matched to its map position by its origin and checked against the slot map's cell type, so a
label can only land on the instance it names. Routing channels are the floorplan reservations (fp.CHANNELS),
which are not cells; they are drawn dashed. Pin groups come from the Metal4 pin labels in the GDS.

Usage (repo root). Either the KLayout Python module (`pip install klayout`, or the unpacked wheel on PYTHONPATH):
    python3 tools/render_labeled.py [--out docs/images/renders] [--rev <git rev>] [--px 6000]
or inside the EDA image:
    scripts/eda.sh "python3 tools/render_labeled.py"

Writes (default --out docs/images/renders):
    chip_full.png        full tile, all drawing layers, scale bar
    chip_labeled.png     same tile with every section, sub-section and neuron slot outlined and labeled + legend
    chip_labeled.svg     same, labels as vector text over the layout bitmap (stays sharp when zoomed)
    array_labeled.png/.svg   neuron array zoom, every slot labeled
    b1_labeled.png/.svg      B1 bias generator zoom, every leaf labeled
"""
import argparse
import base64
import hashlib
import html
import importlib.util
import os
import subprocess

try:
    import klayout.db as db
    import klayout.lay as lay
except ImportError:                       # inside `klayout -b -r`
    import pya as db
    lay = db

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOP = "tt_um_basilwright0_analog_neurons"
BG = 0x0E1116

# (name, layer, datatype, colour, dither); top-most first (KLayout paints the first entry on top).
# Same scheme as scripts/render_layout.py, plus the implant / marker layers so every drawing layer is shown.
STYLE = [
    ("Metal4", 46, 0, 0xE8C547, 5),
    ("Via3", 40, 0, 0xFFFFFF, 0),
    ("Metal3", 42, 0, 0x4FB3E8, 6),
    ("Via2", 38, 0, 0xFFFFFF, 0),
    ("Metal2", 36, 0, 0xD9658B, 7),
    ("Via1", 35, 0, 0xFFFFFF, 0),
    ("Metal1", 34, 0, 0x6E8BF5, 9),
    ("Contact", 33, 0, 0xCCCCCC, 0),
    ("Poly2", 30, 0, 0xE0453A, 1),
    ("COMP", 22, 0, 0x3FC46A, 1),
    ("Pplus", 31, 0, 0xB07AD9, 1),
    ("Nplus", 32, 0, 0x5FC7B8, 1),
    ("Dualgate", 55, 0, 0x8A7F5A, 1),
    ("SAB", 49, 0, 0xC08850, 1),
    ("Resistor marker", 62, 0, 0xD0A070, 1),
    ("Nwell", 21, 0, 0x6B5A3A, 2),
]
# layers that are not geometry worth painting at chip scale (labels, LVS / boundary markers): outline only
FAINT = 0x3A4150

# overlay layers (label geometry is added to the in-memory layout only; the GDS file is never written)
OV = {"txt_sec": 9001, "txt_sub": 9002, "txt_neu": 9003, "txt_aux": 9004, "plate": 9010,
      "box_sec": 9020, "box_sub": 9021, "box_neu": 9022, "box_chan": 9023, "box_pin": 9024, "scale": 9030}
C_SEC, C_SUB, C_NEU, C_CHAN, C_PIN, C_TXT = 0xFFFFFF, 0x5FD7FF, 0xFFC34D, 0x9AA3B5, 0xC79BFF, 0xE6E6E6

# B1 leaves (bias_b1 instances): role, from layout/bias/README.md and docs/info.md
B1_ROLE = {
    "b1_idac_n": "5-bit current DAC (n)",
    "b1_idac_p": "5-bit current DAC (p)",
    "b1_vdacr_el": "5-bit R-DAC: EL",
    "b1_vdacr_vr": "5-bit R-DAC: V_reset",
    "b1_vdacr_vc": "5-bit R-DAC: vth_cmp (CMP threshold)",
    "b1_vdacr_vt": "6-bit R-DAC: vth_ref (threshold)",
    "b1_bias_vi": "V-to-I converter + copies",
    "b1_bias_master": "master reference (ua[0] / internal)",
    "b1_bias_ladder": "bias ladder",
    "b1_bias_rails": "bias rails (compact M3 re-pack)",
    "b1_rx_n4": "n mirror master (L = 4)",
    "b1_rx_n2": "n mirror master (L = 2)",
    "b1_rx_n1": "n mirror master (L = 1)",
    "b1_rx_p24": "p mirror master",
    "b1_rx_p05": "p mirror master",
}
# neuron types (docs/info.md, "Neuron array" and spike-channel table)
NEURON_TYPE = {
    "S": "shared biases", "F": "leak by geometry, tau_F = 2 tau_S", "H": "4-bit Vth trim",
    "P": "Vth trim + 4-bit leak-tau trim", "CMP": "comparator LIF, Vth trim, double slot",
    "AH50": "50 fF membrane", "AH400": "~470 fF membrane", "REF": "EL probe (calibration, no spike ch.)",
}


def load_floorplan():
    spec = importlib.util.spec_from_file_location("floorplan", os.path.join(ROOT, "floorplan", "floorplan.py"))
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    return fp


def ntype(name):
    return name if name in NEURON_TYPE else name.rstrip("0123456789")


def union(boxes):
    b = db.DBox()
    for x in boxes:
        b += x
    return b


# --------------------------------------------------------------------------- label model from the GDS
def build_model(ly, fp):
    top = ly.top_cell()
    dbu = ly.dbu
    inst = [(i.cell.name, i.dbbox(), i) for i in top.each_inst()]
    by_cell = {}
    for n, b, i in inst:
        by_cell.setdefault(n, []).append((b, i))

    def one(cell):
        (b, _), = by_cell[cell]
        return b

    m = dict(sections=[], subs=[], neurons=[], chans=[], pins=[])

    # ---- neuron array: slot instances -> slot map position -> name (checked against the map's cell)
    slot_cells = set(fp.SLOT_CELL.values())
    slots = [(n, b) for n, b, _ in inst if n in slot_cells]
    na = union(b for _, b in slots)
    row_y = [na.bottom]
    for h in fp.ROW_H:
        row_y.append(row_y[-1] + h)
    found = {}
    for cell, b in slots:
        col = round((b.left - na.left) / fp.SLOT_W)
        row = min(range(4), key=lambda r: abs(row_y[r] - b.bottom))
        dbl = [n for n, rc in fp.DOUBLE.items() if rc == (row, col)]      # double slot: origin at its lower row
        name = dbl[0] if dbl else fp.slot_map()[(row, col)]
        assert fp.slot_cell(name) == cell, f"slot {name} at r{row}c{col}: GDS cell {cell} != map {fp.slot_cell(name)}"
        assert name not in found, f"slot {name} placed twice"
        found[name] = (row, col, cell, b)
    assert set(found) == set(fp.slot_map().values()), f"slots missing from GDS: {set(fp.slot_map().values()) - set(found)}"
    for name, (row, col, cell, b) in sorted(found.items(), key=lambda kv: (kv[1][0], kv[1][1])):
        rows = "r0-1" if name in fp.DOUBLE else f"r{row}"
        ch = fp.SPIKE_CH.get(name)
        m["neurons"].append(dict(name=name, box=b, cell=cell, pos=f"{rows} c{col}",
                                 ch="-" if ch is None else str(ch), kind=NEURON_TYPE[ntype(name)]))
    m["sections"].append(dict(key="NA", title="NA  neuron array (4 x 4 grid: 14 neurons + REF probe)", box=na, at="above"))
    kinds = {0: "trimmed rows (45.74 um)", 1: "trimmed rows (45.74 um)", 2: "compact row (29.42 um)", 3: "compact-X row (34.29 um)"}
    for r in range(4):
        members = [n for n, v in found.items() if v[0] == r and n not in fp.DOUBLE]
        members.sort(key=lambda n: found[n][1])
        rb = db.DBox(na.left, row_y[r], na.right, row_y[r + 1])
        m["subs"].append(dict(key=f"row{r}", title=f"row {r}", note=f"{kinds[r]}: {' '.join(members)}"
                              + (" + CMP" if r < 2 else ""), box=rb, at="left"))

    # ---- other neurons (own sections)
    ax, d1 = one("adex_a1"), one("dend_d1")
    m["neurons"].append(dict(name="ADEX", box=ax, cell="adex_a1", pos="A1", ch=str(fp.SPIKE_CH["ADEX"]),
                             kind="adaptive exponential LIF"))
    m["neurons"].append(dict(name="D1", box=d1, cell="dend_d1", pos="D1", ch=str(fp.SPIKE_CH["D1"]),
                             kind="dendrite neuron (plateau trims)"))
    m["sections"].append(dict(key="A1", title="A1  AdEx", box=ax, at="above"))
    m["sections"].append(dict(key="D1", title="D1  dendrite", box=d1, at="above_in"))

    # ---- B1 and its leaves (instance boxes inside bias_b1, transformed to the tile)
    (b1, b1i), = by_cell["bias_b1"]
    m["sections"].append(dict(key="B1", title="B1  bias generator", box=b1, at="below"))
    cnt = {}
    for ci in b1i.cell.each_inst():
        n = ci.cell.name
        cnt[n] = cnt.get(n, 0) + 1
    seen = {}
    for ci in b1i.cell.each_inst():
        n = ci.cell.name
        seen[n] = seen.get(n, 0) + 1
        b = ci.dbbox().transformed(b1i.dcplx_trans)
        short = n[3:] + (f" #{seen[n]}" if cnt[n] > 1 else "")
        m["subs"].append(dict(key=n, title=short, note=B1_ROLE.get(n, ""), box=b, at="center", b1=True))

    # ---- tau trims, readout, control macro, glue / tie std cells
    for k, (b, _) in enumerate(sorted(by_cell["trim_tau4"], key=lambda t: t[0].left)):
        col = round((b.left - na.left) / fp.SLOT_W)
        pn = [n for n, c in fp.el_columns().items() if c == col][0]
        m["sections"].append(dict(key=f"TE{col}", title=f"TE{col}  tau trim ({pn}.TAU)", box=b, at="center"))
    m["sections"].append(dict(key="R1", title="R1  readout (ua[1])", box=one("r1_ua1"), at="center"))
    m["sections"].append(dict(key="C1", title="C1  control block (digital macro)", box=one("neuron_ctrl"), at="center"))
    m["subs"].append(dict(key="C1n", title="config port, 23 B latches, probe decoder, digital LIF (synthesized, flat)",
                          note="", box=None, at="none"))
    std = [b for n, b, _ in inst if n.startswith("gf180mcu_fd_sc")]
    glue = union(b for b in std if b.bottom < 200)
    tie = union(b for b in std if b.bottom > 300)
    m["sections"].append(dict(key="GL", title="glue logic", box=glue, at="right"))
    m["sections"].append(dict(key="TIE", title="uio_oe tie row", box=tie, at="below"))

    # ---- routing channels (floorplan reservations, not cells)
    for k, b in fp.CHANNELS.items():
        m["chans"].append(dict(key=k.split()[0], title=k, box=db.DBox(*b)))
    # ---- free areas kept empty (fp.RESERVED; R2: RW = the bay freed by the B1 re-pack), drawn like the channels
    for k, b in getattr(fp, "RESERVED", {}).items():
        m["chans"].append(dict(key="FREE " + k.split()[0], title="free: " + k, box=db.DBox(*b)))

    # ---- pins: Metal4 pin labels (46/10) in the top cell, grouped by port name
    li = ly.find_layer(46, 10)
    groups = {}
    for s in top.shapes(li).each():
        if s.is_text():
            t = s.text_string
            g = t.split("[")[0] if "[" in t else ("ctrl" if t in ("clk", "ena", "rst_n") else t)
            groups.setdefault(g, []).append(s.text_dpos)
    m4 = ly.find_layer(46, 0)
    for g, pts in sorted(groups.items()):
        bb = db.DBox()
        for p in pts:
            hit = [s.dbbox() for s in top.shapes(m4).each_touching(db.DBox(p, p)) if not s.is_text()]
            bb += hit[0] if hit else db.DBox(p, p).enlarged(0.5, 0.5)
        name = {"ctrl": "clk ena rst_n"}.get(g, g)
        m["pins"].append(dict(key=g, title=name, box=bb, n=len(pts)))
    return m


# --------------------------------------------------------------------------- drawing helpers
class Overlay:
    """Label geometry for KLayout (polygons on overlay layers) and the same items as SVG elements."""

    def __init__(self, ly, cell):
        self.ly, self.cell = ly, cell
        self.gen = db.TextGenerator.default_generator()
        self.li = {k: ly.layer(v, 0) for k, v in OV.items()}
        self.svg = []

    def box(self, b, kind, w_um, dash=False):
        r = db.Region(b.to_itype(self.ly.dbu))
        w = max(1, int(round(w_um / self.ly.dbu)))
        frame = r - r.sized(-w)
        if dash:                                  # dashed frame: remove every other 2w-long piece
            cut = db.Region()
            x = b.left
            while x < b.right:
                cut.insert(db.DBox(x + 2 * w_um, b.bottom - 1, min(x + 4 * w_um, b.right), b.top + 1).to_itype(self.ly.dbu))
                x += 4 * w_um
            y = b.bottom
            while y < b.top:
                cut.insert(db.DBox(b.left - 1, y + 2 * w_um, b.right + 1, min(y + 4 * w_um, b.top)).to_itype(self.ly.dbu))
                y += 4 * w_um
            frame = frame - cut
        self.cell.shapes(self.li[kind]).insert(frame)
        col = {"box_sec": C_SEC, "box_sub": C_SUB, "box_neu": C_NEU, "box_chan": C_CHAN, "box_pin": C_PIN}[kind]
        self.svg.append(("rect", b, col, w_um, dash))

    def text(self, s, x, y, h, kind, anchor="ll", plate=True):
        """Text of cap height ~h um; anchor ll / lc / cc / ul / ur / lr (lower/center/upper x left/center/right)."""
        mag = h / 0.7
        r = self.gen.text(s, self.ly.dbu, mag)
        bb = r.bbox().to_dtype(self.ly.dbu)
        w, hh = bb.width(), bb.height() or h
        dx = {"l": 0, "c": -w / 2, "r": -w}[anchor[1]]
        dy = {"l": 0, "c": -h / 2, "u": -h}[anchor[0]]
        t = db.DCplxTrans(1, 0, False, x + dx - bb.left, y + dy)
        r.transform(t.to_itrans(self.ly.dbu) if hasattr(t, "to_itrans") else db.ICplxTrans(t, self.ly.dbu))
        self.cell.shapes(self.li[kind]).insert(r)
        pb = db.DBox(x + dx, y + dy - 0.28 * h, x + dx + w, y + dy + h).enlarged(0.25 * h, 0.22 * h)
        if plate:
            self.cell.shapes(self.li["plate"]).insert(pb.to_itype(self.ly.dbu))
        col = {"txt_sec": C_SEC, "txt_sub": C_SUB, "txt_neu": C_NEU, "txt_aux": C_TXT}[kind]
        self.svg.append(("text", s, x + dx, y + dy, h, col, pb if plate else None))
        return pb

    def fit(self, s, maxw, maxh):
        """Cap height so that s fits in maxw x maxh."""
        r = self.gen.text(s, self.ly.dbu, 1.0 / 0.7)        # cap height 1 um
        w = r.bbox().to_dtype(self.ly.dbu).width() or 1
        return max(0.05, min(maxh, maxw / w))


def draw_labels(ov, m, view, scope):
    """scope: 'chip' | 'array' | 'b1' -- what to label and at which text size."""
    chip = scope == "chip"
    lw = {"chip": 0.55, "array": 0.28, "b1": 0.30}[scope]
    # sections
    if scope in ("chip", "b1"):
        for s in m["sections"]:
            if scope == "b1" and s["key"] not in ("B1", "R1"):
                continue
            b = s["box"]
            ov.box(b, "box_sec", lw * 1.6)
            h = 3.4 if chip else 3.0
            t = s["title"]
            if s["at"] == "above":
                ov.text(t, b.left, b.top + 0.9, h, "txt_sec")
            elif s["at"] == "above_in":
                ov.text(t, b.left + 1.0, b.top - h - 1.0, h, "txt_sec")
            elif s["at"] == "below":
                ov.text(t, b.left, b.bottom - h - 1.2, h, "txt_sec")
            elif s["at"] == "right":
                ov.text(t, b.right + 1.5, b.center().y, min(h, 2.4), "txt_sec", anchor="cl")
            else:
                hh = ov.fit(t, 0.92 * b.width(), min(h, 0.4 * b.height()))
                ov.text(t, b.center().x, b.center().y, hh, "txt_sec", anchor="cc")
    if scope == "array":
        na = [s for s in m["sections"] if s["key"] == "NA"][0]
        ov.box(na["box"], "box_sec", lw * 1.6)
        ov.text(na["title"], na["box"].left, na["box"].top + 0.8, 2.6, "txt_sec")
    # sub-sections
    for s in m["subs"]:
        b = s["box"]
        if b is None:
            continue
        if s.get("b1"):
            if scope == "array":
                continue
            ov.box(b, "box_sub", lw)
            if chip:
                hh = ov.fit(s["title"], 0.9 * b.width(), min(2.2, 0.3 * b.height()))
                ov.text(s["title"], b.center().x, b.center().y, hh, "txt_sub", anchor="cc")
            else:
                hh = ov.fit(s["title"], 0.9 * b.width(), min(2.6, 0.28 * b.height()))
                ov.text(s["title"], b.center().x, b.center().y + 0.35 * hh, hh, "txt_sub", anchor="lc")
                note = s["note"]
                h2 = ov.fit(note, 0.92 * b.width(), min(1.3, 0.16 * b.height()))
                ov.text(note, b.center().x, b.center().y - 0.5 * hh, h2, "txt_aux", anchor="uc")
        elif scope in ("chip", "array"):
            ov.box(b, "box_sub", lw)
            h = 2.2 if chip else 1.8
            ov.text(s["title"], b.left - 1.0, b.center().y + 0.4 * h, h, "txt_sub", anchor="cr")
            if not chip:
                ov.text(s["note"], b.left - 1.0, b.center().y - 0.8 * h, 0.55 * h, "txt_aux", anchor="cr")
    # neuron slots
    if scope in ("chip", "array"):
        for n in m["neurons"]:
            b = n["box"]
            if scope == "array" and n["cell"] in ("adex_a1", "dend_d1"):
                continue
            ov.box(b.enlarged(-lw * 1.2, -lw * 1.2), "box_neu", lw)
            big = {"chip": 5.0, "array": 6.0}[scope]
            cx, cy = b.center().x, b.center().y
            if n["cell"] in ("adex_a1", "dend_d1"):
                cy = b.top - 13 if n["cell"] == "dend_d1" else b.center().y
            hh = ov.fit(n["name"], 0.8 * b.width(), big)
            ov.text(n["name"], cx, cy + 0.15 * hh, hh, "txt_neu", anchor="lc")
            sub = f"{n['pos']}  ch {n['ch']}"
            h2 = ov.fit(sub, 0.85 * b.width(), 0.36 * big)
            ov.text(sub, cx, cy - 0.25 * hh, h2, "txt_aux", anchor="uc")
            if not chip:
                h3 = ov.fit(n["cell"], 0.85 * b.width(), 0.3 * big)
                ov.text(n["cell"], cx, cy - 0.25 * hh - 1.7 * h2, h3, "txt_aux", anchor="uc")
                h4 = ov.fit(n["kind"], 0.9 * b.width(), 0.25 * big)
                ov.text(n["kind"], cx, cy - 0.25 * hh - 1.7 * h2 - 1.7 * h3, h4, "txt_aux", anchor="uc")
    # routing channels and pins (chip only)
    if chip:
        for c in m["chans"]:
            b = c["box"]
            ov.box(b, "box_chan", lw * 0.7, dash=True)
            hh = ov.fit(c["key"], 0.9 * b.width(), min(1.6, 0.55 * b.height()))
            ov.text(c["key"], b.left + 0.4, b.top - 0.4, hh, "txt_aux", anchor="ul", plate=True)
        for p in m["pins"]:
            b = p["box"]
            if p["key"] in ("VDPWR", "VGND"):       # full-height power stripes: not outlined
                continue
            ov.box(b.enlarged(0.3, 0.3), "box_pin", lw * 0.6)
            above = b.center().y > 200
            y = b.top + 0.9 if above else b.bottom - 0.9 - 1.6
            ov.text(f"{p['title']} ({p['n']})" if p["n"] > 1 else p["title"], b.center().x, y, 1.6, "txt_aux",
                    anchor="lc")


def legend(ov, m, x, ytop, info):
    y = ytop
    def line(s, h, kind="txt_aux", dx=0, gap=1.55):
        nonlocal y
        y -= h * gap
        ov.text(s, x + dx, y, h, kind, plate=False)
    line("tt_um_basilwright0_analog_neurons", 4.2, "txt_sec")
    for s in info:
        line(s, 2.0)
    y -= 3
    line("Outlines (all from GDS instance bounding boxes)", 2.4, "txt_sec")
    for kind, col_kind, s in (("box_sec", "txt_sec", "section (top-level block)"),
                              ("box_sub", "txt_sub", "sub-section (array row / B1 leaf)"),
                              ("box_neu", "txt_neu", "neuron slot: name, row/col, spike channel"),
                              ("box_chan", "txt_aux", "routing channel (floorplan reservation)"),
                              ("box_pin", "txt_aux", "TT pin group (Metal4 pin labels)")):
        y -= 2.4 * 1.6
        ov.box(db.DBox(x, y - 0.3, x + 7, y + 2.3), kind, 0.5, dash=(kind == "box_chan"))
        ov.text(s, x + 9, y, 2.0, col_kind, plate=False)
    y -= 3
    line("Neurons (16 analog + digital LIF in C1)", 2.4, "txt_sec")
    line("name    pos     ch  cell             type", 1.8, "txt_aux")
    for n in m["neurons"]:
        line(f"{n['name']:<7} {n['pos']:<7} {n['ch']:>2}  {n['cell']:<16} {n['kind']}", 1.8, "txt_neu")
    y -= 3
    line("Sections", 2.4, "txt_sec")
    for s in m["sections"]:
        line(s["title"], 1.8, "txt_aux")
    y -= 3
    line("B1 leaves (cell: role)", 2.4, "txt_sec")
    roles = {}
    for s in m["subs"]:
        if s.get("b1"):
            roles.setdefault(s["key"][3:], s["note"])
    for k, v in roles.items():
        line(f"{k}: {v}", 1.8, "txt_sub")


def scale_bar(ov, x, y, length, h):
    ov.cell.shapes(ov.li["scale"]).insert(db.DBox(x, y, x + length, y + h * 0.35).to_itype(ov.ly.dbu))
    for t in (0, length / 2, length):
        ov.cell.shapes(ov.li["scale"]).insert(db.DBox(x + t - h * 0.08, y, x + t + h * 0.08, y + h * 0.8).to_itype(ov.ly.dbu))
    ov.svg.append(("bar", x, y, length, h))
    ov.text(f"{length:g} um", x + length / 2, y + h * 1.0, h, "txt_aux", anchor="lc", plate=False)


# --------------------------------------------------------------------------- view / render
def blend(c, k):
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    br, bg_, bb = (BG >> 16) & 255, (BG >> 8) & 255, BG & 255
    return (int(r * k + br * (1 - k)) << 16) | (int(g * k + bg_ * (1 - k)) << 8) | int(b * k + bb * (1 - k))


def make_view(gds, dim, overlay):
    v = lay.LayoutView()
    v.set_config("background-color", "#%06x" % BG)
    v.set_config("grid-visible", "false")
    v.set_config("text-visible", "false")
    v.set_config("bitmap-oversampling", "2")
    v.set_config("default-text-size", "0")
    cv = v.load_layout(gds, False)
    ly = v.cellview(cv).layout()
    v.clear_layers()
    entries = []                          # top-most first; inserted reversed (KLayout paints later entries on top)

    def add(src, name, col, dither, width=0, frame=None, line_style=None):
        lp = lay.LayerPropertiesNode()
        lp.source = f"{src}@{cv + 1}"
        lp.name = name
        lp.fill_color = col
        lp.frame_color = col if frame is None else frame
        lp.dither_pattern = dither
        lp.width = width
        if line_style is not None:
            lp.line_style = line_style
        entries.append(lp)

    if overlay:
        for k in ("txt_sec", "txt_sub", "txt_neu", "txt_aux"):
            add(f"{OV[k]}/0", k, {"txt_sec": C_SEC, "txt_sub": C_SUB, "txt_neu": C_NEU, "txt_aux": C_TXT}[k], 0)
        add(f"{OV['plate']}/0", "plate", 0x0A0D12, 0, frame=0x0A0D12)
        for k in ("box_neu", "box_sub", "box_sec", "box_chan", "box_pin"):
            add(f"{OV[k]}/0", k, {"box_sec": C_SEC, "box_sub": C_SUB, "box_neu": C_NEU, "box_chan": C_CHAN,
                                  "box_pin": C_PIN}[k], 0)
        add(f"{OV['scale']}/0", "scale", C_TXT, 0)
    known = set()
    for name, ln, dt, col, dither in STYLE:
        add(f"{ln}/{dt}", name, blend(col, dim), dither)
        known.add((ln, dt))
    for li in ly.layer_indexes():
        i = ly.get_info(li)
        if (i.layer, i.datatype) not in known and i.layer < 9000:
            add(f"{i.layer}/{i.datatype}", f"{i.layer}/{i.datatype}", blend(FAINT, dim), 1)
    for lp in reversed(entries):
        v.insert_layer(v.end_layers(), lp)
    v.max_hier()
    return v, ly


def save(v, fn, box, px):
    h = int(round(px * box.height() / box.width()))
    v.save_image_with_options(fn, px, h, 0, 2, 0, box, False)
    return px, h


def write_svg(fn, png, box, px, ph, items):
    sx = px / box.width()
    X = lambda x: (x - box.left) * sx
    Y = lambda y: (box.top - y) * sx
    hexc = lambda c: "#%06x" % c
    with open(png, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{px}" height="{ph}" viewBox="0 0 {px} {ph}">',
         f'<rect width="{px}" height="{ph}" fill="{hexc(BG)}"/>',
         f'<image x="0" y="0" width="{px}" height="{ph}" xlink:href="data:image/png;base64,{b64}"/>',
         '<g fill="none">']
    texts = []
    for it in items:
        if it[0] == "rect":
            _, b, col, w, dash = it
            sw = w * sx
            d = f' stroke-dasharray="{2 * sw:.1f} {2 * sw:.1f}"' if dash else ""
            o.append(f'<rect x="{X(b.left) + sw / 2:.1f}" y="{Y(b.top) + sw / 2:.1f}" width="{max(0.1, b.width() * sx - sw):.1f}" '
                     f'height="{max(0.1, b.height() * sx - sw):.1f}" stroke="{hexc(col)}" stroke-width="{sw:.1f}"{d}/>')
        elif it[0] == "bar":
            _, x, y, L, h = it
            o.append(f'<rect x="{X(x):.1f}" y="{Y(y + h * 0.35):.1f}" width="{L * sx:.1f}" height="{h * 0.35 * sx:.1f}" fill="{hexc(C_TXT)}"/>')
        else:
            texts.append(it)
    o.append("</g>")
    for _, s, x, y, h, col, pb in texts:
        if pb is not None:
            o.append(f'<rect x="{X(pb.left):.1f}" y="{Y(pb.top):.1f}" width="{pb.width() * sx:.1f}" height="{pb.height() * sx:.1f}" '
                     f'fill="#0a0d12" fill-opacity="0.85"/>')
        o.append(f'<text x="{X(x):.1f}" y="{Y(y):.1f}" font-family="DejaVu Sans Mono, Consolas, monospace" '
                 f'font-size="{h * sx / 0.72:.1f}" fill="{hexc(col)}" xml:space="preserve">{html.escape(s)}</text>')
    o.append("</svg>")
    with open(fn, "w") as f:
        f.write("\n".join(o))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gds", default=os.path.join(ROOT, "gds", TOP + ".gds"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "images", "renders"))
    ap.add_argument("--rev", default=None, help="git revision shown in the legend (default: git rev-parse HEAD)")
    ap.add_argument("--px", type=int, default=6000, help="width of the full-chip images in pixels")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rev = a.rev
    if rev is None:
        try:
            rev = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], text=True).strip()
        except Exception:
            rev = "unknown"
    sha = hashlib.sha256(open(a.gds, "rb").read()).hexdigest()[:12]
    fp = load_floorplan()

    # 1. full chip, all layers, scale bar
    v, ly = make_view(a.gds, 1.0, True)
    top = ly.top_cell()
    tile = top.dbbox()
    ov = Overlay(ly, top)
    scale_bar(ov, tile.left, tile.bottom - 9, 50, 3)
    ov.text(f"{TOP}  |  gf180mcuD  |  {tile.width():.2f} x {tile.height():.2f} um  |  main {rev}  |  gds sha256 {sha}",
            tile.left + 60, tile.bottom - 8.2, 2.6, "txt_aux", plate=False)
    box = db.DBox(tile.left - 4, tile.bottom - 12, tile.right + 4, tile.top + 4)
    save(v, os.path.join(a.out, "chip_full.png"), box, a.px)

    # 2. labeled chip (+ legend panel on the east side)
    v, ly = make_view(a.gds, 0.5, True)
    top = ly.top_cell()
    m = build_model(ly, fp)
    ov = Overlay(ly, top)
    draw_labels(ov, m, v, "chip")
    scale_bar(ov, tile.left, tile.bottom - 9, 50, 3)
    info = [f"git main {rev}  |  gds sha256 {sha}",
            f"tile {tile.width():.2f} x {tile.height():.2f} um, gf180mcuD",
            "generated by tools/render_labeled.py"]
    legend(ov, m, tile.right + 10, tile.top + 1, info)
    box = db.DBox(tile.left - 32, tile.bottom - 13, tile.right + 172, tile.top + 9)
    fn = os.path.join(a.out, "chip_labeled.png")
    save(v, fn, box, int(a.px * box.width() / (tile.width() + 8)))
    # SVG: same overlay as vectors over the layout without label geometry
    vb, _ = make_view(a.gds, 0.5, False)
    base = os.path.join(a.out, "_base.png")
    px, ph = save(vb, base, box, int(a.px * 0.6 * box.width() / (tile.width() + 8)))
    write_svg(os.path.join(a.out, "chip_labeled.svg"), base, box, px, ph, ov.svg)

    # 3. zooms: neuron array, B1
    na = [s["box"] for s in m["sections"] if s["key"] == "NA"][0]
    b1 = [s["box"] for s in m["sections"] if s["key"] == "B1"][0]
    for scope, zb, px in (("array", db.DBox(na.left - 48, na.bottom - 4, na.right + 4, na.top + 6), 5000),
                          ("b1", db.DBox(b1.left - 3, b1.bottom - 14, b1.right + 3, b1.top + 3), 6000)):
        v, ly = make_view(a.gds, 0.55, True)
        top = ly.top_cell()
        m2 = build_model(ly, fp)
        ov = Overlay(ly, top)
        draw_labels(ov, m2, v, scope)
        scale_bar(ov, zb.right - 24, zb.bottom + 1.2, 20, 1.4)
        save(v, os.path.join(a.out, f"{scope}_labeled.png"), zb, px)
        vb, _ = make_view(a.gds, 0.55, False)
        pw, phh = save(vb, base, zb, int(px * 0.7))
        write_svg(os.path.join(a.out, f"{scope}_labeled.svg"), base, zb, pw, phh, ov.svg)
    os.remove(base)
    for f in sorted(os.listdir(a.out)):
        print(f, os.path.getsize(os.path.join(a.out, f)) // 1024, "kB")
    print("neurons:", " ".join(f"{n['name']}({n['pos']})" for n in m["neurons"]))


if __name__ == "__main__":
    main()
