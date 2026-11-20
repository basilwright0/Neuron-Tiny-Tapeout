"""Trial-route one region alone (earlier regions' wires absent), first schedule only; no cache written.
python3 route_try.py region   -- early routability signal while the real build runs."""
import sys
sys.path.insert(0, ".")
import dendgen as G
from router import Router
ri = int(sys.argv[1])
L, insts, obst, mom, lib, devs, ports = G.build()
xs, ys_all = G.make_grid(L)
y0, y1 = G.REGIONS[ri]
ys = [y for y in ys_all if y0 - 1e-6 <= y <= y1 + 1e-6]
R = Router(xs, ys)
for lay, r, n in obst:
    R.add_shape(lay, r, n)
G.add_forbids(R, mom)
def nodes(shapes):
    out = set()
    for lay, r in shapes:
        for i, x in enumerate(xs):
            if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                for j, y in enumerate(ys):
                    if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                        out.add((lay, i, j))
    return out
nets = {}
for net, terms in L.nets.items():
    tn = [t for t in (nodes(t) for t in terms) if t]
    if len(tn) >= 2:
        nets[net] = tn
order = [n for n in G.ROUTE_FIRST if n in nets]
order += sorted((n for n in nets if n not in G.ROUTE_FIRST + G.ROUTE_LAST), key=lambda n: (n.count(".") == 0, n))
order += [n for n in G.ROUTE_LAST if n in nets]
u, b = R.route_all(nets, order, iters=40, log=lambda s: print(s[:160], flush=True))
print("RESULT region", ri, "unrouted", sorted(u), "conflicts", sorted(b))
