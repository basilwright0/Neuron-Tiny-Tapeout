"""Diagnostic: route every net of one region alone (only static obstacles). Nets that fail here are
blocked by placement, not by congestion.   python3 diag_alone.py [region]"""
import sys
sys.path.insert(0, ".")
import dendgen as G
from router import Router
ri = int(sys.argv[1]) if len(sys.argv) > 1 else 0
L, insts, obst, mom, lib, devs, ports = G.build()
xs, ys_all = G.make_grid(L)
y0, y1 = G.REGIONS[ri]
ys = [y for y in ys_all if y0 - 1e-6 <= y <= y1 + 1e-6]


def nodes(shapes):
    out = set()
    for lay, r in shapes:
        for i, x in enumerate(xs):
            if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                for j, y in enumerate(ys):
                    if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                        out.add((lay, i, j))
    return out


for net, terms in sorted(L.nets.items()):
    tn = [t for t in (nodes(t) for t in terms) if t]
    if len(tn) < 2:
        continue
    R = Router(xs, ys)
    for lay, r, n in obst:
        R.add_shape(lay, r, n)
    G.add_forbids(R, mom)
    R.margin = None
    ok = R.route_net(net, tn, max_expand=2000000)
    if not ok:
        # which terminal is isolated?
        for k, t in enumerate(terms):
            if nodes(t):
                R2 = Router(xs, ys)
                for lay, r, n in obst:
                    R2.add_shape(lay, r, n)
                G.add_forbids(R2, mom)
                R2.margin = None
                others = set().union(*[nodes(u) for j, u in enumerate(terms) if j != k and nodes(u)])
                if not R2.route_net(net, [nodes(t), others], max_expand=2000000):
                    print("BLOCKED", net, "terminal", k, t)
        print("FAIL", net, flush=True)
print("done")
