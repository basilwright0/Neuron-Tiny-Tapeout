"""Check that every leaf's Metal2 in its GDS is covered by the obstacles in out/geo_<cell>.json."""
import json, sys
import klayout.db as kdb
cells = sys.argv[1:]
for c in cells:
    ly = kdb.Layout(); ly.read(f"out/{c}.gds")
    top = ly.cell(c)
    li = ly.find_layer(36, 0)
    g = json.load(open(f"out/geo_{c}.json"))
    reg = kdb.Region(top.begin_shapes_rec(li)); reg.merge()
    cov = kdb.Region()
    for r in g["m2"] + list(g["pins"].values()):
        cov.insert(kdb.Box(*[round(v / ly.dbu) for v in r]))
    miss = reg - cov
    print(c, "M2 area", round(reg.area() * ly.dbu ** 2, 1), "uncovered", round(miss.area() * ly.dbu ** 2, 2),
          [str(b) for b in list(miss.each())[:4]])
