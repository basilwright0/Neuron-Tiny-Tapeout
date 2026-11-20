"""List m1/m2/m3 shapes (obstacles, routed, fills) near a point: python3 near_check.py layer x y [r]"""
import json, sys
sys.path.insert(0, ".")
import dendgen as G
lay, x, y = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rad = float(sys.argv[4]) if len(sys.argv) > 4 else 0.6
L, insts, obst, mom, lib, devs, ports = G.build()
c = json.load(open("out/route_cache_dend_d1.json"))
wires = [(l, tuple(r), n) for l, r, n in c["wires"]]
fills = G.fill_notches(obst, wires)
for src, sh in (("obst", obst), ("wire", wires), ("fill", fills)):
    for l, r, n in sh:
        if l == lay and r[0] < x + rad and r[2] > x - rad and r[1] < y + rad and r[3] > y - rad:
            print(src, n, [round(v, 3) for v in r])
