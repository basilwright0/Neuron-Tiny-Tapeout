"""Route only the given nets of one region (others absent) and print remaining conflicts with geometry.
python3 diag_pair.py region net1 net2 ..."""
import sys, json
sys.path.insert(0, ".")
import dendgen as G
from router import Router
ri = int(sys.argv[1]); want = sys.argv[2:]
L, insts, obst, mom, lib, devs, ports = G.build()
xs, ys_all = G.make_grid(L)
y0, y1 = G.REGIONS[ri]
ys = [y for y in ys_all if y0 - 1e-6 <= y <= y1 + 1e-6]
done = []
for k in range(ri):
    done += [(l, tuple(r), n) for l, r, n in json.load(open(f"out/route_region{k}.json"))["wires"]]
R = Router(xs, ys)
for lay, r, n in list(obst) + done:
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
nets = {n: [t for t in (nodes(t) for t in L.nets[n]) if t] for n in want}
for n in want:
    print(n, "terminals:", [sorted({(xs[a[1]], ys[a[2]]) for a in t})[:3] for t in nets[n]])
u, b = R.route_all(nets, want, iters=30, log=lambda s: None)
print("unrouted", u, "bad", b)
for c in R.conflict_list():
    print("CONFLICT", c)
