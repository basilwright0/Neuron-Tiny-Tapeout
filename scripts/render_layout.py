"""Render the top-level GDS to PNG images with KLayout (batch mode, no GUI).

Usage (repo root, Git Bash):
    scripts/eda.sh "klayout -b -r scripts/render_layout.py"

Writes, under docs/images/:
    layout.png          full tile, device + routing layers (datasheet image, < 512 kB)
    layout_hd.png       same view at high resolution
    layout_blocks.png   same view with the floorplan blocks outlined and labelled
"""
import importlib.util
import os

import pya

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOP = "tt_um_basilwright0_analog_neurons"
GDS = os.path.join(ROOT, "gds", TOP + ".gds")
OUT = os.path.join(ROOT, "docs", "images")

# (name, layer, datatype, colour, dither pattern); listed top-most first (KLayout paints the first entry on top)
STYLE = [
    ("Metal4", 46, 0, 0xE8C547, 5),
    ("Via3",   40, 0, 0xFFFFFF, 0),
    ("Metal3", 42, 0, 0x4FB3E8, 6),
    ("Via2",   38, 0, 0xFFFFFF, 0),
    ("Metal2", 36, 0, 0xD9658B, 7),
    ("Via1",   35, 0, 0xFFFFFF, 0),
    ("Metal1", 34, 0, 0x6E8BF5, 9),
    ("Contact", 33, 0, 0xCCCCCC, 0),
    ("Poly2",  30, 0, 0xE0453A, 1),
    ("COMP",   22, 0, 0x3FC46A, 1),
    ("Nwell",  21, 0, 0x6B5A3A, 2),
]


def make_view():
    v = pya.LayoutView()
    v.set_config("background-color", "#0e1116")
    v.set_config("grid-visible", "false")
    v.set_config("text-visible", "false")
    v.set_config("bitmap-oversampling", "3")
    v.set_config("default-text-size", "0")
    cv = v.load_layout(GDS, False)
    v.clear_layers()
    for name, ln, dt, col, dither in STYLE:
        lp = pya.LayerPropertiesNode()
        lp.source = f"{ln}/{dt}@{cv + 1}"
        lp.name = name
        lp.fill_color = col
        lp.frame_color = col
        lp.dither_pattern = dither
        lp.width = 0
        v.insert_layer(v.end_layers(), lp)
    v.max_hier()
    v.zoom_fit()
    return v


def floorplan():
    spec = importlib.util.spec_from_file_location("floorplan", os.path.join(ROOT, "floorplan", "floorplan.py"))
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    return fp.BLOCKS


LABELS = {
    "C1 control macro": "Control block + digital LIF",
    "NA neuron array 4x4": "Neuron array (4 x 4)",
    "D1 dendrite": "D1 dendrite",
    "B1 bias generator": "B1 bias generator",
    "R1 readout corner": "R1",
    "A1 AdEx": "AdEx",
}

os.makedirs(OUT, exist_ok=True)
v = make_view()
v.save_image(os.path.join(OUT, "layout.png"), 560, 526)
v.save_image(os.path.join(OUT, "layout_hd.png"), 2600, 2440)

# block outlines and labels as annotations
for key, (x0, y0, x1, y1) in floorplan().items():
    if key not in LABELS:
        continue
    a = pya.Annotation()
    a.p1, a.p2 = pya.DPoint(x0, y0), pya.DPoint(x1, y1)
    a.style = pya.Annotation.StyleLine
    a.outline = pya.Annotation.OutlineBox
    a.fmt = a.fmt_x = a.fmt_y = ""
    a.color = 0xFFFFFF
    v.insert_annotation(a)
    t = pya.Annotation()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    t.p1 = t.p2 = pya.DPoint(cx, cy)
    t.fmt = t.fmt_x = t.fmt_y = LABELS[key]
    t.style = pya.Annotation.StyleLine
    t.outline = pya.Annotation.OutlineDiag
    t.color = 0xFFFFFF
    v.insert_annotation(t)
v.set_config("ruler-color", "#ffffff")
v.save_image(os.path.join(OUT, "layout_blocks.png"), 1300, 1220)

for f in ("layout.png", "layout_hd.png", "layout_blocks.png"):
    print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "kB")
