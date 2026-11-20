"""Time one PathFinder iteration of one region, per net (diagnostic). python3 prof_route.py region"""
import sys, time
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
R.pres = 0.5
tt = []
for net in sorted(nets, key=lambda n: (n.count(".") == 0, n)):
    t0 = time.time(); ok = R.route_net(net, nets[net]); dt = time.time() - t0
    tt.append((dt, net, ok, len(nets[net])))
tt.sort(reverse=True)
print("total", round(sum(t[0] for t in tt), 1), "s; grid", len(xs), "x", len(ys))
for t in tt[:15]:
    print(f"  {t[0]:7.1f}s {t[1]:14s} ok={t[2]} terms={t[3]}")
