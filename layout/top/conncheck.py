"""Connectivity of work/routes.json: every routing task (net terminal groups) must be one connected piece.
Run (layout/top, host python with numpy): python conncheck.py"""
import json, sys
sys.path.insert(0, '.')
import route as RT
g, ids, tasks, stubs, F = RT.build()
tasks += RT.tie_tasks()
R = json.loads((RT.C.WORK / "routes.json").read_text())
LN = ["metal2", "metal3", "metal4"]
def ov(a, b): return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]
bad = []
for n, grps in tasks:
    rec = R.get(n, {"wires": [], "vias": []})
    sh = [(LN.index(l), r) for l, r in rec["wires"]]
    for k, x, y in rec["vias"]:
        lo = 0 if k == "via2" else 1
        sh += [(lo, (x-.19, y-.19, x+.19, y+.19)), (lo+1, (x-.19, y-.19, x+.19, y+.19))]
    # union-find over shapes + groups
    items = [("s", l, r) for l, r in sh] + [("g", i) for i in range(len(grps))]
    par = list(range(len(items)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    ns = len(sh)
    vstart = len(rec["wires"])
    for a in range(vstart, ns, 2): par[f(a)] = f(a + 1)
    for a in range(ns):
        for b in range(a + 1, ns):
            if sh[a][0] == sh[b][0] and ov(sh[a][1], sh[b][1]): par[f(a)] = f(b)
    for gi, grp in enumerate(grps):
        for a in range(ns):
            if any(l == sh[a][0] and ov(r, sh[a][1]) for l, r in grp): par[f(a)] = f(ns + gi)
    roots = {f(ns + gi) for gi in range(len(grps))}
    if len(roots) > 1: bad.append((n, len(roots)))
print("tasks", len(tasks), "disconnected", len(bad), bad[:30])
print("failed", R["_failed"])
