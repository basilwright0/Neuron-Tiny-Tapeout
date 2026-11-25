"""Reachability of one net's terminal groups on the router grid (all other routes fixed): which end of a
"no path" net is trapped. Run (layout/top, host python): PYTHONPATH=<klayout> python reach.py <net>"""
import json, sys, numpy as np
from scipy import ndimage
sys.path.insert(0,'.')
import route as RT
net = sys.argv[1]
g, ids, tasks, stubs, F = RT.build()
R = json.loads((RT.C.WORK / "routes.json").read_text())
for n, rec in R.items():
    if n.startswith("_") or n == net: continue
    RT.commit(g, ids[n], [(l, tuple(r)) for l, r in rec["wires"]], [tuple(v) for v in rec["vias"]])
k = ids[net]
own = g.acc == k
lw = ((g.rw == 0) | (g.rw == k)) & (~g.ko | own)
if net not in RT.BIAS_OK: lw &= ~(g.bz & ~own)
lv1 = ((g.rv == 0) | (g.rv == k)) & (~g.ko | own)
if net not in RT.BIAS_OK: lv1 &= ~(g.bz & ~own)
# connectivity: same-layer 4-neighbour (both directions allowed), via between l, l+1 where lv1 on both
lab = np.zeros(lw.shape, np.int32)
L = []
for l in range(3):
    lab_l, n = ndimage.label(lw[l]); L.append(lab_l)
# union across layers via vias
parent = {}
def f(a):
    while parent.get(a, a) != a: a = parent[a]
    return a
for l in range(2):
    m = lv1[l] & lv1[l + 1] & lw[l] & lw[l + 1]
    a = L[l][m]; b = L[l + 1][m]
    for x, y in set(zip(a.tolist(), b.tolist())):
        ra, rb = f((l, x)), f((l + 1, y))
        if ra != rb: parent[ra] = rb
grps = [t for t in tasks if t[0] == net][0][1]
for gi, grp in enumerate(grps):
    comps = set()
    for li, r in grp:
        i0, i1 = RT.idx_range(r[0], r[2], RT.OX, RT.NX); j0, j1 = RT.idx_range(r[1], r[3], RT.OY, RT.NY)
        for c in np.unique(L[li][j0:j1 + 1, i0:i1 + 1]):
            if c: comps.add(f((li, int(c))))
    print("group", gi, grp[0][1], "components", comps)
    for c in list(comps)[:1]:  # bbox per layer
        # bbox of this component on each layer
        for l in range(3):
            ids_l = [x for x in range(1, L[l].max() + 1)] if False else None
        sizes = []
        for l in range(3):
            labs = [lab for lab in np.unique(L[l]) if lab and f((l, int(lab))) == c]
            if labs:
                m = np.isin(L[l], labs); jj, ii = np.nonzero(m)
                print("   layer", l, "nodes", m.sum(), "x", round(RT.OX + RT.G * ii.min(), 2), round(RT.OX + RT.G * ii.max(), 2), "y", round(RT.OY + RT.G * jj.min(), 2), round(RT.OY + RT.G * jj.max(), 2))
