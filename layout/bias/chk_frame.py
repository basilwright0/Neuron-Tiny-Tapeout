"""Check the bias_b1 GDS against the integrator's frame: notches empty (all layers), corridor free of Metal3,
pin positions."""
import klayout.db as kdb
ly = kdb.Layout(); ly.read("out/bias_b1.gds"); top = ly.cell("bias_b1")
d = ly.dbu
import os
WT = float(os.environ.get("B1_WT", "23.0"))   # west trim (topgen.py WT); 0 = rev C frame
N1 = (182.0 - WT, 0.0, 222.0 - WT, 42.0); CORR = (196.0 - WT, 42.0, 222.0 - WT, 115.0)
N2 = (0.0, 104.0, 23.0 - WT, 115.0)
box = lambda r: kdb.Region(kdb.Box(*[round(v / d) for v in r]))
bb = top.bbox()
print("bbox", bb.left * d, bb.bottom * d, bb.right * d, bb.top * d)
for li in ly.layer_indexes():
    info = ly.get_info(li)
    reg = kdb.Region(top.begin_shapes_rec(li))
    if reg.is_empty():
        continue
    for nm, r in (("N1", N1), ("N2", N2)) if N2[2] > 0 else (("N1", N1),):
        hit = reg & box(r)
        if not hit.is_empty():
            print("NOTCH", nm, "layer", info, "area", round(hit.area() * d * d, 3), hit.bbox())
    if (info.layer, info.datatype) == (42, 0):   # Metal3
        hit = reg & box(CORR)
        print("Metal3 in corridor:", "none" if hit.is_empty() else hit.bbox())
it = top.begin_shapes_rec(ly.find_layer(42, 10) if ly.find_layer(42, 10) is not None else 0)
for li in ly.layer_indexes():
    for sh in top.shapes(li).each():
        if sh.is_text() and sh.text_string in ("ua0", "vth_ref", "vreset_src", "ib_r1", "el", "vdd", "vss", "vbn_leak", "vth_cmp"):
            print("label", sh.text_string, ly.get_info(li), round(sh.text_dpos.x, 2), round(sh.text_dpos.y, 2))
