"""Top-level router (Python + numpy, runs in the EDA container; ~minutes).

Gridded A* maze router on Metal2 / Metal3 / Metal4, grid 0.14 um (geom.G/OX/OY), wires 0.28, via pads 0.40.
Legality is checked against real geometry on every layer:
  real_w[l]: node can carry a wire of net k if value is 0 or k (-1 = foreign metal within spacing)
  real_v[l]: same for a via pad
  ko[l]    : keep-out (inside a block frame + 0.42 um); a net may enter it only through its own terminals.
Preferred directions: Metal2 vertical, Metal3 horizontal, Metal4 vertical (Metal4 horizontal is expensive).
Metal4 may cross analog blocks (they use Metal1-3) but not the macro; it costs more over the neuron array.

Inputs : config.py (nets), geom.py (fixed geometry + terminals), work/geo/*.json (block pins / metal).
Outputs: work/routes.json  {net: {"wires": [[layer, rect]], "vias": [[kind, x, y]]}, "_stubs": [...],
         "_failed": [...]}
"""
import heapq, json, math, sys, time
import numpy as np
import config as C
import geom as GM

fp = C.fp
G, OX, OY = GM.G, GM.OX, GM.OY
NX = int((fp.TILE_W - OX) / G) + 1
NY = int((fp.TILE_H - OY) / G) + 1
LAYERS = ["metal2", "metal3", "metal4"]
LI = {n: i for i, n in enumerate(LAYERS)}
VP = 0.19                                  # half size of a router via pad (0.38 x 0.38)
EW, EV = 0.14 + 0.28, VP + 0.28            # node influence for wire / via legality
EF = 0.03                                  # extra margin against foreign (block) metal
STUB = 0.70                                # pin stub length out of a block edge
KO_M = 0.42                                # keep-out margin around block frames

# per-layer step costs (dx, dy) and via costs
COST = {0: (2.5, 1.0), 1: (1.0, 2.5), 2: (6.0, 1.3)}
VIA_COST = {0: 4.0, 1: 6.0}                # via2 (M2-M3), via3 (M3-M4)
M4_ARRAY = 3.0                             # extra multiplier for Metal4 over the neuron array


def idx_range(a0, a1, o, n):
    i0 = max(0, math.ceil((a0 - o) / G - 1e-6))
    i1 = min(n - 1, math.floor((a1 - o) / G + 1e-6))
    return i0, i1


def ispan(a0, a1, o, n):
    """node indices whose centre lies strictly inside (a0, a1)"""
    i0 = max(0, math.floor((a0 - o) / G + 1e-6) + 1)
    i1 = min(n - 1, math.ceil((a1 - o) / G - 1e-6) - 1)
    return i0, i1


class Grid:
    def __init__(self):
        self.rw = np.zeros((3, NY, NX), np.int32)
        self.rv = np.zeros((3, NY, NX), np.int32)
        self.ko = np.zeros((3, NY, NX), np.bool_)
        self.acc = np.zeros((3, NY, NX), np.int32)
        self.m4pen = np.zeros((NY, NX), np.bool_)

    def mark(self, l, r, k, foreign=False):
        e = EF if foreign else 0.0
        for arr, ex in ((self.rw, EW + e), (self.rv, EV + e)):
            i0, i1 = ispan(r[0] - ex, r[2] + ex, OX, NX)
            j0, j1 = ispan(r[1] - ex, r[3] + ex, OY, NY)
            if i0 > i1 or j0 > j1:
                continue
            sub = arr[l, j0:j1 + 1, i0:i1 + 1]
            if k < 0:
                sub[...] = -1
            else:
                sub[(sub != 0) & (sub != k)] = -1
                sub[sub == 0] = k

    def keepout(self, l, r, m=KO_M):
        i0, i1 = ispan(r[0] - m, r[2] + m, OX, NX)
        j0, j1 = ispan(r[1] - m, r[3] + m, OY, NY)
        if i0 <= i1 and j0 <= j1:
            self.ko[l, j0:j1 + 1, i0:i1 + 1] = True

    def access(self, l, r, k):
        i0, i1 = idx_range(r[0], r[2], OX, NX)
        j0, j1 = idx_range(r[1], r[3], OY, NY)
        if i0 <= i1 and j0 <= j1:
            for ll in range(3):              # all layers: a terminal may be left by a via stack
                sub = self.acc[ll, j0:j1 + 1, i0:i1 + 1]
                sub[sub == 0] = k
        return [(l, j, i) for j in range(j0, j1 + 1) for i in range(i0, i1 + 1)]


# ======================================================================== pins, stubs
def xf(r, x, y):
    return (round(r[0] + x, 3), round(r[1] + y, 3), round(r[2] + x, 3), round(r[3] + y, 3))


def edge_stub(pin, bbox, ox, oy, extra=0.0):
    """Stub + terminal for a block pin: pick the pin rectangle touching the frame edge nearest the label,
    extend it STUB um outward. Returns (layer, stub_rect, term_rect) in tile coords, or None."""
    x0, y0, x1, y1 = bbox
    px, py = pin["pt"]
    best = None
    for r in pin["rects"]:
        for e, d in (("b", r[1] - y0), ("t", y1 - r[3]), ("l", r[0] - x0), ("r", x1 - r[2])):
            if d <= 0.06:
                cx = min(max(px, r[0]), r[2]); cy = min(max(py, r[1]), r[3])
                dist = abs(cx - px) + abs(cy - py)
                if best is None or dist < best[0]:
                    best = (dist, e, r)
    if best is None:
        return None
    _, e, r = best
    STUB = globals()["STUB"] + extra
    KO_M = globals()["KO_M"] + extra
    if e in "bt":
        cx = min(max(px, r[0]), r[2])
        w0, w1 = max(r[0], cx - 1.0), min(r[2], cx + 1.0)
        if w1 - w0 < 0.28:
            w0, w1 = cx - 0.14, cx + 0.14
        if e == "b":
            s = (w0, y0 - STUB, w1, r[1] + 0.01); t = (w0, y0 - STUB, w1, y0 - KO_M)
        else:
            s = (w0, r[3] - 0.01, w1, y1 + STUB); t = (w0, y1 + KO_M, w1, y1 + STUB)
    else:
        cy = min(max(py, r[1]), r[3])
        w0, w1 = max(r[1], cy - 1.0), min(r[3], cy + 1.0)
        if w1 - w0 < 0.28:
            w0, w1 = cy - 0.14, cy + 0.14
        if e == "l":
            s = (x0 - STUB, w0, r[0] + 0.01, w1); t = (x0 - STUB, w0, x0 - KO_M, w1)
        else:
            s = (r[2] - 0.01, w0, x1 + STUB, w1); t = (x1 + KO_M, w0, x1 + STUB, w1)
    return pin["layer"], xf(s, ox, oy), xf(t, ox, oy)


def frame_rects(inst, cell, x, y, bbox):
    if cell == "bias_b1":
        return fp.b1_rects()
    if cell == "r1_ua1":
        return [xf((0, 14, 40, 54), x, y)]
    return [xf((0, 0, bbox[2], bbox[3]), x, y) if bbox[0] > -0.1 else xf(bbox, x, y)]


# ======================================================================== build
SKIP = {"vth_ref", "vreset_src", "ib_r1", "ua[0]", "ua[1]"}     # abutting / drawn by geom.py


def build():
    nets = C.nets()
    F = GM.fixed()
    I = C.instances()
    geos = {c: GM.geo(c) for c in set(c for c, _, _ in I.values())}
    ids = {"VDPWR": 1, "VGND": 2}
    for n in sorted(nets):
        ids.setdefault(n, len(ids) + 1)
    for n in F.terms:
        ids.setdefault(n, len(ids) + 1)
    ids.setdefault("ua[0]", len(ids) + 1)
    g = Grid()
    stubs = []                                                    # (layer, rect, net)
    terms = {}                                                    # net -> list of groups [(l, rect)]
    used = {}                                                     # (inst, pin) -> net
    for n, lst in nets.items():
        for inst, pin in lst:
            used.setdefault((inst, pin), n)
    # ---- blocks: foreign metal, keep-outs, pins
    for inst, (cell, x, y) in I.items():
        gg = geos[cell]
        for lay, rs in gg["obs"].items():
            if lay not in LI:
                continue
            for r in rs:
                g.mark(LI[lay], xf(r, x, y), -1, foreign=True)
        kol = (0, 1, 2) if cell == "neuron_ctrl" else (0, 1)
        m = KO_M + (0.5 if gg.get("placeholder") else 0.0)
        for fr in frame_rects(inst, cell, x, y, gg["bbox"]):
            for l in kol:
                g.keepout(l, fr, m)
        is_slot = cell.startswith("slot") or cell in fp.COMPACT_CELLS   # array cells: no edge stubs (cslot_*, czslot_*)
        for pn, plist in gg["pins"].items():
            net = used.get((inst, pn))
            if inst == "d1" and pn == "vsrcp":
                net = "vsrc"
            if pn in ("vdd", "vss", "VDD", "VSS"):
                net = {"vdd": "VDPWR", "vss": "VGND", "VDD": "VDPWR", "VSS": "VGND"}[pn]
            for p in plist:
                if p["layer"] not in LI:
                    continue
                k = ids.get(net, -1) if net else -1
                for r in p["rects"]:
                    g.mark(LI[p["layer"]], xf(r, x, y), k, foreign=(k < 0))
                if k < 0 or is_slot or net in SKIP:
                    continue
                if pn in ("vdd", "vss", "VDD", "VSS") and not (inst in ("d1", "ax", "tau0", "tau2") and pn == "vdd"):
                    continue
                st = edge_stub(p, gg["bbox"] if gg["bbox"][0] > -0.1 else [0, 0, gg["bbox"][2], gg["bbox"][3]], x, y,
                               extra=0.5 if gg.get("placeholder") else 0.0)
                if st is None:
                    continue
                lay, s, t = st
                if inst == "r1" and s[1] < 50:                   # R1: top-edge pins only
                    continue
                stubs.append((lay, s, net))
                terms.setdefault(net, []).append([(lay, t)])
    # B1 corridor: Metal3 allowed (R1 feed-throughs)
    cx0, cy0, cx1, cy1 = fp.B1_CORRIDOR
    i0, i1 = ispan(cx0 + 0.3, cx1 - 0.3, OX, NX)
    j0, j1 = ispan(cy0 - 1.0, cy1 + KO_M + 0.3, OY, NY)
    g.ko[1, j0:j1 + 1, i0:i1 + 1] = False
    # no through-routing on Metal2/3 in the 2 um gap between D1's top edge and the tau cells (pins escape on Metal4)
    j0, j1 = ispan(fp.BLOCKS["D1 dendrite"][3], fp.BLOCKS["TE0 tau trim col 0"][1], OY, NY)
    for tb in (fp.BLOCKS["TE0 tau trim col 0"], fp.BLOCKS["TE2 tau trim col 2"]):
        i0, i1 = ispan(tb[0] - 1, tb[2] + 1, OX, NX)
        g.ko[0:2, j0:j1 + 1, i0:i1 + 1] = True
    # bias channel (between B1 / tau cells and the array): Metal2/3 reserved for the analog column lines
    g.bz = np.zeros((3, NY, NX), np.bool_)
    i0, i1 = ispan(0.0, fp.BLOCKS["A1 AdEx"][0], OX, NX)
    j0, j1 = ispan(fp.B1_BOX[3] - 1.0, fp.BLOCKS["NA neuron array 4x4"][1] - 0.2, OY, NY)
    g.bz[0:2, j0:j1 + 1, i0:i1 + 1] = True
    # Metal4 horizontal is cheap where no stripe crosses: CH_MID between the strap pairs, and CH_BOT below y 4.8
    g.m4h = np.zeros((NY, NX), np.bool_)
    i0, i1 = ispan(fp.MACRO_X + fp.MACRO_STRAPS[1][0] + 2.0, fp.MACRO_X + fp.MACRO_STRAPS[4][0] - 0.5, OX, NX)
    j0, j1 = ispan(fp.B1_BOX[3], fp.MACRO_Y, OY, NY)
    g.m4h[j0:j1 + 1, i0:i1 + 1] = True
    i0, i1 = ispan(0.0, fp.TILE_W, OX, NX); j0, j1 = ispan(0.0, fp.STRIPE_Y[0] - 0.2, OY, NY)
    g.m4h[j0:j1 + 1, i0:i1 + 1] = True
    # Metal4 penalty over the neuron array
    ax0, ay0, ax1, ay1 = fp.BLOCKS["NA neuron array 4x4"]
    i0, i1 = ispan(ax0, ax1, OX, NX); j0, j1 = ispan(ay0, ay1, OY, NY)
    g.m4pen[j0:j1 + 1, i0:i1 + 1] = True
    # tile edge
    for arr in (g.rw, g.rv):
        b = int(0.35 / G)
        arr[:, :b, :] = -1; arr[:, -b:, :] = -1; arr[:, :, :b] = -1; arr[:, :, -b:] = -1
    # ---- TT pins (Metal4)
    for n, x in fp.PINS_TOP.items():
        r = (x - 0.3, 324.36, x + 0.3, 325.36)
        k = ids.get(n, -1) if n in nets else -1
        g.mark(2, r, k, foreign=k < 0)
        if k > 0:
            terms.setdefault(n, []).append([(2, (x - 0.3, 324.36, x + 0.3, 325.2))])
    for n, x in fp.PINS_BOT.items():
        if n not in fp.ANALOG_USED:
            g.mark(2, (x - 3, 0, x + 3, 1), -1, foreign=True)
    # the TT analog-pin check flags any Metal4 within 0.5 um of its (fixed) pin rectangles: keep Metal4
    # routing above y 1.7 everywhere
    j1 = int((1.7 - OY) / G) + 1
    g.rw[2, :j1, :] = -1; g.rv[2, :j1, :] = -1; g.rv[1, :j1, :] = -1
    # ---- fixed geometry
    for lay, r, net in F.shapes:
        if lay in LI:
            g.mark(LI[lay], r, ids[net])
    for lay, r, net in stubs:
        g.mark(LI[lay], r, ids[net])
    for net, groups in F.terms.items():
        for grp in groups:
            terms.setdefault(net, []).append([(LI[l], r) for l, r in grp])
    # power tasks: block vdd pin -> the VDPWR stripes
    stripe_groups = {net: [(2, (x, fp.STRIPE_Y[0], x + w, fp.STRIPE_Y[1])) for nn, x, w in fp.STRIPES if nn == net]
                     for net in ("VDPWR", "VGND")}
    tasks = []
    for net in sorted(terms):
        if net in SKIP:
            continue
        grps = [[(LI[l] if isinstance(l, str) else l, r) for l, r in grp] for grp in terms[net]]
        if net in ("VDPWR", "VGND"):
            for grp in grps:
                tasks.append((net, [grp, stripe_groups[net]]))
        elif len(grps) >= 2:
            tasks.append((net, grps))
    # access maps for terminals
    for net, grps in tasks:
        for grp in grps:
            if grp is stripe_groups.get(net):
                continue
            for l, r in grp:
                g.access(l, r, ids[net])
    return g, ids, tasks, stubs, F


# ======================================================================== A*
BIAS_OK = set(C.COLUMN_NETS) | {"aux0", "aux1", "aux2", "aux3", "vbn_ax", "vbp_w", "VDPWR", "VGND"}


def route_net(g, k, groups, margin=25.0, max_exp=3_000_000, full=False, net=None):
    """Connect all groups of net k. Returns (paths, ok)."""
    xs = [r[0] for grp in groups for l, r in grp] + [r[2] for grp in groups for l, r in grp]
    ys = [r[1] for grp in groups for l, r in grp] + [r[3] for grp in groups for l, r in grp]
    # stripe groups are huge: clip the window to the other groups
    small = [grp for grp in groups if not (len(grp) > 1 and all(l == 2 for l, _ in grp))]
    if len(small) < len(groups):
        xs = [r[0] for grp in small for l, r in grp] + [r[2] for grp in small for l, r in grp]
        ys = [r[1] for grp in small for l, r in grp] + [r[3] for grp in small for l, r in grp]
        margin = max(margin, 75.0)
    i0, i1 = idx_range(min(xs) - margin, max(xs) + margin, OX, NX)
    j0, j1 = idx_range(min(ys) - margin, max(ys) + margin, OY, NY)
    if full:
        j0, j1 = 0, NY - 1
    W, H = i1 - i0 + 1, j1 - j0 + 1
    P = W * H
    rw = g.rw[:, j0:j1 + 1, i0:i1 + 1]; rv = g.rv[:, j0:j1 + 1, i0:i1 + 1]
    ko = g.ko[:, j0:j1 + 1, i0:i1 + 1]; acc = g.acc[:, j0:j1 + 1, i0:i1 + 1]
    own = (acc == k)
    lw = (((rw == 0) | (rw == k)) & (~ko | own))
    lv1 = (((rv == 0) | (rv == k)) & (~ko | own))
    if net is not None and net not in BIAS_OK:
        bz = g.bz[:, j0:j1 + 1, i0:i1 + 1] & ~own
        lw &= ~bz; lv1 &= ~bz
    lv = np.zeros((2, H, W), np.bool_)
    lv[0] = lv1[0] & lv1[1]; lv[1] = lv1[1] & lv1[2]
    LW = lw.astype(np.uint8).tobytes()
    LV = lv.astype(np.uint8).tobytes()
    PEN = (g.m4pen[j0:j1 + 1, i0:i1 + 1].astype(np.uint8) + 2 * g.m4h[j0:j1 + 1, i0:i1 + 1].astype(np.uint8)).tobytes()
    soft = getattr(g, "occW", None) is not None
    if soft:
        OW = np.minimum(g.occW[:, j0:j1 + 1, i0:i1 + 1], 255).astype(np.uint8).tobytes()
        OV = np.minimum(g.occV[:, j0:j1 + 1, i0:i1 + 1], 255).astype(np.uint8).tobytes()
        HI = np.minimum(g.hist[:, j0:j1 + 1, i0:i1 + 1], 255).astype(np.uint8).tobytes()
        pf = g.pf

    def nodes_of(grp):
        out = []
        for l, r in grp:
            a0, a1 = idx_range(r[0], r[2], OX, NX); b0, b1 = idx_range(r[1], r[3], OY, NY)
            a0, a1 = max(a0, i0), min(a1, i1); b0, b1 = max(b0, j0), min(b1, j1)
            for jj in range(b0, b1 + 1):
                base = l * P + (jj - j0) * W
                for ii in range(a0, a1 + 1):
                    u = base + ii - i0
                    if LW[u]:
                        out.append(u)
        return out

    gnodes = [nodes_of(grp) for grp in groups]
    for n, gn in enumerate(gnodes):
        if not gn:
            return [], False, f"group {n} has no legal node"
    # start from the smallest non-stripe group
    order = sorted(range(len(groups)), key=lambda n: (len(gnodes[n]) > 5000, len(gnodes[n])))
    tree = set(gnodes[order[0]])
    todo = set(order[1:])
    paths = []
    cdx = [COST[l][0] for l in range(3)]; cdy = [COST[l][1] for l in range(3)]
    while todo:
        tgt = {}
        for n in todo:
            for u in gnodes[n]:
                tgt[u] = n
        boxes = []
        for n in todo:
            ii = [u % P % W for u in gnodes[n]]; jj = [u % P // W for u in gnodes[n]]
            boxes.append((min(ii), max(ii), min(jj), max(jj)))

        def h(u):
            r = u % P; i = r % W; j = r // W
            best = 1e18
            for a0, a1, b0, b1 in boxes:
                d = (a0 - i if i < a0 else i - a1 if i > a1 else 0) + (b0 - j if j < b0 else j - b1 if j > b1 else 0)
                if d < best:
                    best = d
            return best
        dist = {}
        par = {}
        heap = []
        for u in tree:
            dist[u] = 0.0
            heap.append((h(u), 0.0, u))
        heapq.heapify(heap)
        found = None
        nexp = 0
        while heap:
            f, d, u = heapq.heappop(heap)
            if d > dist.get(u, 1e18):
                continue
            if u in tgt:
                found = u
                break
            nexp += 1
            if nexp > max_exp:
                break
            l = u // P; r = u - l * P; j = r // W; i = r - j * W
            pv = PEN[r] if l == 2 else 0
            pen = M4_ARRAY if (pv & 1) else 1.0
            cx = 1.2 if (pv & 2) else cdx[l]
            for v, c in ((u + 1, cx) if i + 1 < W else (None, 0), (u - 1, cx) if i > 0 else (None, 0),
                         (u + W, cdy[l]) if j + 1 < H else (None, 0), (u - W, cdy[l]) if j > 0 else (None, 0)):
                if v is None or not LW[v]:
                    continue
                nd = d + c * pen
                if soft:
                    nd += c * pen * HI[v] + pf * OW[v]
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; par[v] = u
                    heapq.heappush(heap, (nd + h(v), nd, v))
            for dl in (-1, 1):
                l2 = l + dl
                if l2 < 0 or l2 > 2:
                    continue
                lo = min(l, l2)
                if not LV[lo * P + r]:
                    continue
                v = l2 * P + r
                if not LW[v]:
                    continue
                nd = d + VIA_COST[lo]
                if soft:
                    nd += pf * (OV[lo * P + r] + OV[(lo + 1) * P + r]) + HI[v] * 2.0
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; par[v] = u
                    heapq.heappush(heap, (nd + h(v), nd, v))
        if found is None:
            return paths, False, f"no path ({nexp} expansions), {len(todo)} groups left"
        n = tgt[found]
        path = [found]
        while path[-1] in par:
            path.append(par[path[-1]])
        path.reverse()
        paths.append([(u // P, i0 + (u % P) % W, j0 + (u % P) // W) for u in path])
        tree.update(path)
        tree.update(gnodes[n])
        todo.discard(n)
    return paths, True, ""


def path_shapes(paths):
    """Convert node paths to wires (merged straight runs) and vias."""
    wires, vias = [], []
    for path in paths:
        run = [path[0]]
        def flush(run):
            if not run:
                return
            l = run[0][0]
            xs = [OX + G * i for _, i, _ in run]; ys = [OY + G * j for _, _, j in run]
            wires.append((LAYERS[l], (round(min(xs) - 0.14, 3), round(min(ys) - 0.14, 3),
                                      round(max(xs) + 0.14, 3), round(max(ys) + 0.14, 3))))
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                flush(run)
                vias.append(("via2" if min(a[0], b[0]) == 0 else "via3", round(OX + G * a[1], 3), round(OY + G * a[2], 3)))
                run = [b]
            else:
                straight = len(run) < 2 or ((run[-1][1] - run[-2][1], run[-1][2] - run[-2][2]) == (b[1] - a[1], b[2] - a[2]))
                if straight:
                    run.append(b)
                else:
                    flush(run)
                    run = [a, b]
        flush(run)
    return wires, vias


def commit(g, k, wires, vias):
    for lay, r in wires:
        g.mark(LI[lay], r, k)
    for kind, x, y in vias:
        lo = 0 if kind == "via2" else 1
        for l in (lo, lo + 1):
            g.mark(l, (x - VP, y - VP, x + VP, y + VP), k)


def priority(task):
    net, grps = task
    if net in ("VDPWR", "VGND"):
        return (5, 0)
    rs = [r for grp in grps for l, r in grp]
    span = (max(r[2] for r in rs) - min(r[0] for r in rs)) + (max(r[3] for r in rs) - min(r[1] for r in rs))
    if net.startswith(("ui_in", "uo_out", "uio_out", "rst_n", "clk")):
        return (0, span)
    if net.startswith(("i0_", "i1_", "i2_", "i3_", "i4_", "r0_", "r1_", "r2_", "v0_", "ua0_", "bias_en", "ib_x2")):
        return (1, span)
    if net.startswith("uio_oe"):
        return (0, span)
    if net in C.COLUMN_NETS or net.startswith(("aux", "en_c", "vbn_ax", "vbp_w")):
        return (2, span)
    return (3, span)


def footprint(g, wires, vias, sign):
    """add (sign=+1) / remove (-1) a net's spacing footprint to the occupancy maps"""
    shapes = [(LI[l], r) for l, r in wires]
    for kind, x, y in vias:
        lo = 0 if kind == "via2" else 1
        for l in (lo, lo + 1):
            shapes.append((l, (x - VP, y - VP, x + VP, y + VP)))
    if not shapes:
        return
    for arr, ex in ((g.occW, EW), (g.occV, EV)):
        x0 = min(r[0] for _, r in shapes) - ex; x1 = max(r[2] for _, r in shapes) + ex
        y0 = min(r[1] for _, r in shapes) - ex; y1 = max(r[3] for _, r in shapes) + ex
        a0, a1 = idx_range(x0, x1, OX, NX); b0, b1 = idx_range(y0, y1, OY, NY)
        m = np.zeros((3, b1 - b0 + 1, a1 - a0 + 1), np.bool_)
        for l, r in shapes:
            i0, i1 = ispan(r[0] - ex, r[2] + ex, OX, NX); j0, j1 = ispan(r[1] - ex, r[3] + ex, OY, NY)
            if i0 <= i1 and j0 <= j1:
                m[l, j0 - b0:j1 - b0 + 1, i0 - a0:i1 - a0 + 1] = True
        arr[:, b0:b1 + 1, a0:a1 + 1] += m.astype(np.int16) * sign


def conflicts(g, paths):
    """nodes of a routed net that are over-used (another net's footprint)"""
    bad = []
    for path in paths:
        for idx, (l, i, j) in enumerate(path):
            if g.occW[l, j, i] > 1:
                bad.append((l, j, i))
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                for l in (a[0], b[0]):
                    if g.occV[l, a[2], a[1]] > 1:
                        bad.append((l, a[2], a[1]))
    return bad


# power ties between stripe islands (the islands are otherwise joined only by the TT power grid)
TIES = [("VDPWR", 121.8, 186.72), ("VDPWR", 286.72, 345.4), ("VGND", 124.4, 190.02), ("VGND", 290.02, 343.0)]


def tie_tasks():
    out = []
    for net, xa, xb in TIES:
        grps = []
        for xc in (xa, xb):
            (x, w), = [(x, w) for n, x, w in fp.STRIPES if n == net and x <= xc <= x + w]
            grps.append([(2, (x, fp.STRIPE_Y[0], x + w, fp.STRIPE_Y[1]))])
        out.append((net, grps))
    return out


def add_ties():
    """Route only the stripe ties on top of an existing work/routes.json (its wires are fixed)."""
    g, ids, tasks, stubs, F = build()
    R = json.loads((C.WORK / "routes.json").read_text())
    for net, rec in R.items():
        if net.startswith("_"):
            continue
        commit(g, ids[net], [(l, tuple(r)) for l, r in rec["wires"]], [tuple(v) for v in rec["vias"]])
    for net, grps in tie_tasks():
        paths, ok, msg = route_net(g, ids[net], grps, margin=10.0, max_exp=8_000_000, net=net)
        wires, vias = path_shapes(paths) if paths else ([], [])
        commit(g, ids[net], wires, vias)
        rec = R.setdefault(net, {"wires": [], "vias": []})
        rec["wires"] += [[l, r] for l, r in wires]; rec["vias"] += [[k, x, y] for k, x, y in vias]
        print("tie", net, "OK" if ok else "FAIL " + msg, len(wires), "wires", flush=True)
        if not ok:
            R["_failed"].append([net + " tie", msg])
    (C.WORK / "routes.json").write_text(json.dumps(R))


def restub():
    """Regenerate the pin stubs in work/routes.json (terminals are unchanged, routes stay valid)."""
    g, ids, tasks, stubs, F = build()
    R = json.loads((C.WORK / "routes.json").read_text())
    R["_stubs"] = [[l, r, n] for l, r, n in stubs]
    (C.WORK / "routes.json").write_text(json.dumps(R))
    print("stubs:", len(stubs))


def reroute(nets):
    """Rip up the given nets in work/routes.json and route them again on top of the others (fixed)."""
    g, ids, tasks, stubs, F = build()
    R = json.loads((C.WORK / "routes.json").read_text())
    for net, rec in R.items():
        if net.startswith("_") or net in nets:
            continue
        commit(g, ids[net], [(l, tuple(r)) for l, r in rec["wires"]], [tuple(v) for v in rec["vias"]])
    for net in nets:
        R[net] = {"wires": [], "vias": []}
    for net, grps in tasks + tie_tasks():
        if net not in nets:
            continue
        paths, ok, msg = route_net(g, ids[net], grps, net=net)
        if not ok:
            paths, ok, msg = route_net(g, ids[net], grps, margin=60.0, max_exp=8_000_000, full=True, net=net)
        wires, vias = path_shapes(paths) if paths else ([], [])
        commit(g, ids[net], wires, vias)
        R[net]["wires"] += [[l, r] for l, r in wires]; R[net]["vias"] += [[k, x, y] for k, x, y in vias]
        print("reroute", net, "OK" if ok else "FAIL " + msg, flush=True)
        if not ok:
            R["_failed"].append([net, msg])
    (C.WORK / "routes.json").write_text(json.dumps(R))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "reroute":
        return reroute(set(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "ties":
        return add_ties()
    if len(sys.argv) > 1 and sys.argv[1] == "stubs":
        return restub()
    t0 = time.time()
    g, ids, tasks, stubs, F = build()
    tasks += tie_tasks()
    g.occW = np.zeros((3, NY, NX), np.int16)
    g.occV = np.zeros((3, NY, NX), np.int16)
    g.hist = np.zeros((3, NY, NX), np.int16)
    g.pf = 1.0
    print(f"grid {NX} x {NY} x 3, {len(tasks)} tasks, build {time.time() - t0:.1f}s", flush=True)
    tasks.sort(key=priority)
    only = set(sys.argv[2:])
    if only:
        tasks = [t for t in tasks if t[0] in only]
    res = {}                                   # task index -> (paths, wires, vias, ok, msg)
    def do(ti):
        net, grps = tasks[ti]
        k = ids[net]
        if ti in res:
            footprint(g, res[ti][1], res[ti][2], -1)
        paths, ok, msg = route_net(g, k, grps, net=net)
        if not ok:
            p2, ok2, m2 = route_net(g, k, grps, margin=60.0, max_exp=6_000_000, full=True, net=net)
            if ok2:
                paths, ok, msg = p2, ok2, m2
        wires, vias = path_shapes(paths) if paths else ([], [])
        footprint(g, wires, vias, +1)
        res[ti] = (paths, wires, vias, ok, msg)
        return ok
    def dump():
        out = {"_stubs": [[l, r, n] for l, r, n in stubs], "_failed": [], "_conflicts": []}
        for ti, (paths, wires, vias, ok, msg) in sorted(res.items()):
            net = tasks[ti][0]
            rec = out.setdefault(net, {"wires": [], "vias": []})
            rec["wires"] += [[l, r] for l, r in wires]
            rec["vias"] += [[kd, x, y] for kd, x, y in vias]
            if not ok:
                out["_failed"].append([net, msg])
            c = conflicts(g, paths)
            if c:
                out["_conflicts"].append([net, len(c), [OX + G * c[0][2], OY + G * c[0][1], c[0][0]]])
        (C.WORK / "routes.json").write_text(json.dumps(out))
        return out
    for ti in range(len(tasks)):
        do(ti)
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    for it in range(iters):
        bad = {}
        for ti, (paths, wires, vias, ok, msg) in res.items():
            c = conflicts(g, paths)
            if c:
                bad[ti] = c
        nfail = sum(1 for r in res.values() if not r[3])
        print(f"=== iter {it}: {len(bad)} nets in conflict, {nfail} unrouted, pf {g.pf:.1f}, "
              f"{time.time() - t0:.0f}s", flush=True)
        if it % 3 == 2 or it == iters - 1:
            for ti, c in list(bad.items())[:60]:
                l, j, i = c[0]
                print(f"   conflict {tasks[ti][0]:18s} n={len(c):4d} at L{l} ({OX + G * i:.2f}, {OY + G * j:.2f})", flush=True)
        if not bad and nfail == 0:
            break
        for c in bad.values():
            for l, j, i in c:
                g.hist[l, j, i] += 3
        dump()
        g.pf *= 1.8
        redo = sorted(set(bad) | {ti for ti, r in res.items() if not r[3]}, key=lambda t: -len(bad.get(t, [])))
        for ti in redo:
            do(ti)
    out = dump()
    print(f"done in {time.time() - t0:.0f}s, unrouted: {[f[0] for f in out['_failed']]}, "
          f"in conflict: {[c[0] for c in out['_conflicts']]}", flush=True)


if __name__ == "__main__":
    main()
