"""Find same-layer overlaps/touches between different nets (obstacles + routed wires + notch fills)."""
import json, sys
sys.path.insert(0, ".")
import dendgen as G
L, insts, obst, mom, lib, devs, ports = G.build()
c = json.load(open("out/route_cache_dend_d1.json"))
wires = [(l, tuple(r), n) for l, r, n in c["wires"]]
fills = G.fill_notches(obst, wires)
sh = [s for s in list(obst) + wires + fills if s[2] is not None]
vias = [s for s in sh if s[0] == "v1"]
for lay in ("m1", "m2"):
    S = [s for s in sh if s[0] == lay]
    S.sort(key=lambda s: s[1][0])
    for i, (l, a, na) in enumerate(S):
        for l2, b, nb in S[i + 1:]:
            if b[0] > a[2]:
                break
            if na != nb and a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                if True:
                    print("TOUCH", lay, na, a, nb, b)
