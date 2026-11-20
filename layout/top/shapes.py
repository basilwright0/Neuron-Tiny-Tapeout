"""List merged shapes of a GDS cell in a window: python3 shapes.py gds cell layer x0 y0 x1 y1"""
import sys, klayout.db as db
ly = db.Layout(); ly.read(sys.argv[1]); top = ly.cell(sys.argv[2])
L, D = map(int, sys.argv[3].split("/"))
x0, y0, x1, y1 = map(float, sys.argv[4:8])
li = ly.find_layer(L, D)
reg = db.Region(top.begin_shapes_rec(li)).merged()
win = db.Region(db.DBox(x0, y0, x1, y1).to_itype(ly.dbu))
for p in (reg & win).each():
    b = p.bbox().to_dtype(ly.dbu)
    print(f"{b.left:.3f} {b.bottom:.3f} {b.right:.3f} {b.top:.3f}  {p.num_points()}pts")
