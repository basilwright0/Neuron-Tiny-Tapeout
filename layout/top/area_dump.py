"""Dump the assembled tile for the top-level area audit (klayout python, runs in the EDA image).

Usage: python3 layout/top/area_dump.py [gds] [out.json]
Writes: every child instance of the top cell (cell, bbox) and the top cell's OWN shapes (top-level routing, geom.py
shapes, stubs) per layer as boxes (polygons decomposed into rectangles). area_audit.py (host Python) does the rest.
"""
import sys, json
import klayout.db as db

gds = sys.argv[1] if len(sys.argv) > 1 else "gds/tt_um_basilwright0_analog_neurons.gds"
out = sys.argv[2] if len(sys.argv) > 2 else "layout/top/work/area_dump.json"
ly = db.Layout(); ly.read(gds)
top = ly.top_cell()
d = ly.dbu
LAY = {(34, 0): "metal1", (35, 0): "via1", (36, 0): "metal2", (38, 0): "via2", (42, 0): "metal3", (40, 0): "via3",
       (46, 0): "metal4"}
res = {"cell": top.name, "bbox": [v * d for v in (top.bbox().left, top.bbox().bottom, top.bbox().right, top.bbox().top)],
       "inst": [], "own": {}}
for inst in top.each_inst():
    b = inst.bbox()
    res["inst"].append([ly.cell(inst.cell_index).name, round(b.left * d, 3), round(b.bottom * d, 3),
                        round(b.right * d, 3), round(b.top * d, 3)])
for li in ly.layer_indexes():
    info = ly.get_info(li)
    name = LAY.get((info.layer, info.datatype))
    if not name:
        continue
    reg = db.Region(top.shapes(li))     # own shapes only (not recursive)
    reg.merge()
    boxes = []
    for poly in reg.each():
        for p in db.Region(poly).decompose_trapezoids_to_region().each():   # rectangles for Manhattan shapes
            b = p.bbox()
            boxes.append([round(b.left * d, 3), round(b.bottom * d, 3), round(b.right * d, 3), round(b.top * d, 3)])
    res["own"][name] = boxes
json.dump(res, open(out, "w"))
print("wrote", out, {k: len(v) for k, v in res["own"].items()}, len(res["inst"]), "instances")
