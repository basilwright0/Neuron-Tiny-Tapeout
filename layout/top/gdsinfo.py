"""Dump bbox + text labels of a GDS top cell (klayout python). Usage: python3 gdsinfo.py <gds> [cell]"""
import sys, klayout.db as db
ly = db.Layout(); ly.read(sys.argv[1])
top = ly.cell(sys.argv[2]) if len(sys.argv) > 2 else ly.top_cell()
print("CELL", top.name, "bbox", top.bbox().to_dtype(ly.dbu))
layers = {}
for li in ly.layer_indexes():
    info = ly.get_info(li)
    it = top.begin_shapes_rec(li)
    n = 0
    while not it.at_end():
        s = it.shape()
        if s.is_text():
            t = s.text.transformed(it.trans())
            print(f"LBL {info.layer}/{info.datatype} {t.string} {t.x*ly.dbu:.3f} {t.y*ly.dbu:.3f}" + ("" if it.cell_index() == top.cell_index() else " (sub)"))
        else:
            n += 1
        it.next()
    layers[f"{info.layer}/{info.datatype}"] = n
print("LAYERS", layers)
