"""Locate a vdd-vss short in out/dend_d1.gds: shape connectivity graph, BFS from a vdd-labelled
shape to a vss-labelled shape, print the path (layer, bbox)."""
import collections
import klayout.db as kdb
ly = kdb.Layout(); ly.read("out/dend_d1.gds")
top = ly.top_cell()
dbu = ly.dbu
def R(l, d=0):
    li = ly.find_layer(l, d)
    return kdb.Region(top.begin_shapes_rec(li)) if li is not None else kdb.Region()
comp, poly, cont, m1, v1, m2, v2, m3, nplus, nwell = (R(22), R(30), R(33), R(34), R(35), R(36), R(38), R(42), R(32), R(21))
pplus = R(31)
sdn = (comp & nplus) - poly
sdp = (comp & pplus) - poly
gate_poly = poly
ntap = comp & nplus & nwell
layers = {"sdn": sdn.merged(), "sdp": sdp.merged(), "poly": poly.merged(), "m1": m1.merged(), "m2": m2.merged(), "m3": m3.merged(),
          "nwell": nwell.merged()}
nodes = []
for name, reg in layers.items():
    for p in reg.each():
        nodes.append((name, p))
idx = {name: [i for i, n in enumerate(nodes) if n[0] == name] for name in layers}
adj = collections.defaultdict(set)
def link(cut, la, lb):
    for c in cut.each():
        cr = kdb.Region(c)
        A = [i for i in idx[la] if not (kdb.Region(nodes[i][1]) & cr).is_empty()]
        B = [i for i in idx[lb] if not (kdb.Region(nodes[i][1]) & cr).is_empty()]
        for a in A:
            for b in B:
                adj[a].add(b); adj[b].add(a)
# speed: use bbox prefilter
def link_fast(cut, la, lb):
    import bisect
    for c in cut.each():
        bb = c.bbox()
        cr = kdb.Region(c)
        A = [i for i in idx[la] if nodes[i][1].bbox().overlaps(bb) and not (kdb.Region(nodes[i][1]) & cr).is_empty()]
        B = [i for i in idx[lb] if nodes[i][1].bbox().overlaps(bb) and not (kdb.Region(nodes[i][1]) & cr).is_empty()]
        for a in A:
            for b in B:
                adj[a].add(b); adj[b].add(a)
link_fast(cont & comp, "sdn", "m1")
link_fast(cont & comp, "sdp", "m1")
link_fast(cont & poly, "poly", "m1")
link_fast(v1, "m1", "m2")
link_fast(v2, "m2", "m3")
link_fast(ntap, "sdn", "nwell")
def find_label(text):
    out = set()
    for li in ly.layer_indexes():
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            s = it.shape()
            if s.is_text() and s.text.string == text:
                pt = it.trans() * s.text.trans.disp if hasattr(s.text.trans, 'disp') else None
                pt = (it.trans() * s.text).trans.disp
                info = ly.get_info(li)
                lname = {34: "m1", 36: "m2", 42: "m3"}.get(info.layer)
                if lname:
                    for i in idx[lname]:
                        if nodes[i][1].bbox().contains(pt):
                            out.add(i)
            it.next()
    return out
src, dst = find_label("vdd"), find_label("vss")
print("vdd shapes", len(src), "vss shapes", len(dst))
prev = {s: None for s in src}
q = collections.deque(src)
hit = None
while q:
    u = q.popleft()
    if u in dst:
        hit = u; break
    for v in adj[u]:
        if v not in prev:
            prev[v] = u; q.append(v)
if hit is None:
    print("no path")
else:
    path = []
    while hit is not None:
        path.append(hit); hit = prev[hit]
    for i in reversed(path):
        b = nodes[i][1].bbox()
        print(nodes[i][0], round(b.left*dbu,3), round(b.bottom*dbu,3), round(b.right*dbu,3), round(b.top*dbu,3))
# contacts linking the first two path shapes
if hit is None or True:
    a = [i for i in idx["m1"] if nodes[i][1].bbox().bottom*dbu > 57 and nodes[i][1].bbox().bottom*dbu < 58]
    for i in a:
        x = (cont & comp & pplus) & kdb.Region(nodes[i][1])
        for c in x.each():
            b = c.bbox(); print("CUT", b.left*dbu, b.bottom*dbu, b.right*dbu, b.top*dbu)
