"""Small gridded Metal1/Metal2 router with exact geometric spacing checks (PathFinder-style).

Grid: non-uniform (a base pitch plus every pin's centre line, so device pins are on grid).
Legality is never assumed from the pitch: every wire segment / via pad is checked geometrically
against existing shapes using the Chebyshev (square-corner) gap that magic's DRC uses.

  * static shapes (device metal, rails, column lines, MOM, pins) are hard obstacles for other nets;
  * routed shapes of other nets are *soft*: a move that would violate spacing to them is allowed
    at a cost (present-congestion factor x number of nets hit, plus history).  Nets that end up
    in conflict are ripped up and rerouted with growing penalties until no conflicts remain
    (negotiated congestion, McMurchie & Ebeling's PathFinder).
"""
import heapq
import math
from collections import defaultdict

SPACE = {"m1": 0.23, "m2": 0.28, "m3": 0.28, "v1": 0.26, "v2": 0.26}     # gf180mcuD min spacing (um)
VIA = {("m1", "m2"): "v1", ("m2", "m3"): "v2"}    # cut layer between two adjacent metals
HW = 0.15            # wire half-width (0.30 wide on M1 and M2)
PAD = 0.20           # via1 landing pad half-size (0.40 x 0.40 on M1 and M2)
CUT = 0.13           # via1 cut half-size (0.26)


def rgap(a, b):
    """Chebyshev gap between rectangles (0 if they touch or overlap)."""
    dx = max(0.0, b[0] - a[2], a[0] - b[2])
    dy = max(0.0, b[1] - a[3], a[1] - b[3])
    return max(dx, dy)


def overlap_area(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


class Index:
    def __init__(self, bin_=2.0):
        self.b = bin_
        self.d = defaultdict(set)
        self.items = {}
        self.k = 0

    def _bins(self, r):
        b = self.b
        for i in range(int(math.floor(r[0] / b)), int(math.floor(r[2] / b)) + 1):
            for j in range(int(math.floor(r[1] / b)), int(math.floor(r[3] / b)) + 1):
                yield (i, j)

    def add(self, rect, net):
        k = self.k
        self.k += 1
        self.items[k] = (rect, net)
        for bn in self._bins(rect):
            self.d[bn].add(k)
        return k

    def remove(self, k):
        rect, net = self.items.pop(k)
        for bn in self._bins(rect):
            self.d[bn].discard(k)

    def near(self, rect, margin):
        r = (rect[0] - margin, rect[1] - margin, rect[2] + margin, rect[3] + margin)
        seen = set()
        for bn in self._bins(r):
            for k in self.d.get(bn, ()):
                if k not in seen:
                    seen.add(k)
                    yield self.items[k]


class Router:
    def __init__(self, xs, ys, layers=("m1", "m2"), hw=HW):
        self.xs, self.ys = list(xs), list(ys)
        self.hw = hw                                      # wire half-width
        self.layers = tuple(layers)                       # routing metals, bottom to top
        allk = self.layers + tuple(VIA[(a, b)] for a, b in zip(self.layers, self.layers[1:]))
        self.static = {l: Index() for l in set(allk) | {"m1", "m2", "v1"}}
        self.dyn = {l: Index() for l in set(allk) | {"m1", "m2", "v1"}}
        self.forbid = []          # (layer, rect, allowed, only): overlap forbidden
        self.hist = defaultdict(float)
        self.netshapes = defaultdict(list)    # net -> [(layer, key)]
        self.netpaths = defaultdict(list)     # net -> [path]
        self.cost = {("m1", "h"): 1.5, ("m1", "v"): 2.5, ("m2", "v"): 1.0, ("m2", "h"): 1.2,
                     ("m3", "h"): 1.1, ("m3", "v"): 1.6, "via": 0.6}
        self.pres = 1.0

    # ------------------------------------------------------------------ shapes
    def add_shape(self, layer, rect, net):
        self.static[layer].add(rect, net)

    def add_forbid(self, layers, rect, allowed=None, only=None):
        for l in layers:
            self.forbid.append((l, rect, allowed, only))

    def hard_ok(self, layer, rect, net):
        sp = SPACE[layer]
        for l, r, allowed, only in self.forbid:
            if l != layer or (only is not None and net not in only) or (allowed is not None and net in allowed):
                continue
            if overlap_area(r, rect) > 0:
                return False
        for r, n in self.static[layer].near(rect, sp):
            if layer in ("v1", "v2") and n == net and r != rect and rgap(r, rect) < sp - 1e-9:
                return False
            if n != net and rgap(r, rect) < sp - 1e-9:
                return False
        return True

    def soft_hits(self, layer, rect, net):
        sp = SPACE[layer]
        hit = set()
        for r, n in self.dyn[layer].near(rect, sp):
            if layer in ("v1", "v2") and n == net and r != rect and rgap(r, rect) < sp - 1e-9:
                hit.add(n + "#self")
            elif n != net and rgap(r, rect) < sp - 1e-9:
                hit.add(n)
        return hit

    # ------------------------------------------------------------------ geometry of moves
    def seg_rect(self, a, b):
        x1, x2 = sorted((self.xs[a[1]], self.xs[b[1]]))
        y1, y2 = sorted((self.ys[a[2]], self.ys[b[2]]))
        return (x1 - self.hw, y1 - self.hw, x2 + self.hw, y2 + self.hw)

    def via_shapes(self, i, j, lo="m1", hi="m2"):
        x, y = self.xs[i], self.ys[j]
        pad = (x - PAD, y - PAD, x + PAD, y + PAD)
        c = CUT if lo == "m1" else 0.14          # magic draws via2 as >= 0.28 um squares
        return [(lo, pad), (hi, pad), (VIA[(lo, hi)], (x - c, y - c, x + c, y + c))]

    def move_shapes(self, a, b):
        if a[0] != b[0]:
            lo, hi = sorted((a[0], b[0]), key=self.layers.index)
            return self.via_shapes(a[1], a[2], lo, hi)
        return [(a[0], self.seg_rect(a, b))]

    # ------------------------------------------------------------------ one net
    def route_net(self, net, terminals, max_expand=300000):
        terms = [set(t) for t in terminals if t]
        if len(terms) < 2:
            return True
        cache = {}

        def move_cost(a, b):
            key = (a, b) if a < b else (b, a)
            if key in cache:
                return cache[key]
            v = 0.0
            for l, r in self.move_shapes(a, b):
                if not self.hard_ok(l, r, net):
                    v = None
                    break
                v += self.pres * len(self.soft_hits(l, r, net))
            cache[key] = v
            return v

        terms.sort(key=lambda t: -len(t))
        tree = set(terms[0])
        remaining = terms[1:]
        while remaining:
            tgt = set().union(*remaining)
            boxes = []
            for t in remaining:
                xs = [self.xs[n[1]] for n in t]
                ys = [self.ys[n[2]] for n in t]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))

            def h(n):
                x, y = self.xs[n[1]], self.ys[n[2]]
                return min(max(0, b[0] - x, x - b[2]) + max(0, b[1] - y, y - b[3]) for b in boxes)

            dist, prev, pq = {}, {}, []
            for n in tree:
                dist[n] = 0.0
                heapq.heappush(pq, (h(n), 0.0, n))
            found, nexp = None, 0
            while pq:
                f, g, n = heapq.heappop(pq)
                if g > dist.get(n, 1e18) + 1e-12:
                    continue
                if n in tgt and n not in tree:
                    found = n
                    break
                nexp += 1
                if nexp > max_expand:
                    break
                l, i, j = n
                k = self.layers.index(l)
                nbrs = [((self.layers[q], i, j), self.cost["via"]) for q in (k - 1, k + 1) if 0 <= q < len(self.layers)]
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    i2, j2 = i + di, j + dj
                    if 0 <= i2 < len(self.xs) and 0 <= j2 < len(self.ys):
                        d = abs(self.xs[i2] - self.xs[i]) + abs(self.ys[j2] - self.ys[j])
                        nbrs.append(((l, i2, j2), d * self.cost[(l, "h" if di else "v")]))
                for m, c in nbrs:
                    mc = move_cost(n, m)
                    if mc is None:
                        continue
                    ng = g + c + mc + self.hist.get(m, 0.0)
                    if ng >= dist.get(m, 1e18) - 1e-12:
                        continue
                    dist[m] = ng
                    prev[m] = n
                    heapq.heappush(pq, (ng + h(m), ng, m))
            if found is None:
                return False
            path = [found]
            while path[-1] not in tree:
                path.append(prev[path[-1]])
            path.reverse()
            self.commit(net, path)
            ps = set(path)
            tree |= ps
            hit = [t for t in remaining if t & ps]
            for t in hit:
                tree |= t
            remaining = [t for t in remaining if not (t & ps)]
            cache.clear()
        return True

    def commit(self, net, path):
        self.netpaths[net].append(path)
        shapes = []
        for a, b in zip(path, path[1:]):
            shapes += self.move_shapes(a, b)
        if len(path) == 1:
            n = path[0]
            x, y = self.xs[n[1]], self.ys[n[2]]
            shapes.append((n[0], (x - self.hw, y - self.hw, x + self.hw, y + self.hw)))
        for l, r in shapes:
            self.netshapes[net].append((l, self.dyn[l].add(r, net)))

    def ripup(self, net):
        for l, k in self.netshapes.pop(net, []):
            self.dyn[l].remove(k)
        self.netpaths.pop(net, None)

    def conflict_list(self):
        out = []
        for l in self.dyn:
            sp = SPACE[l]
            for k, (r, n) in list(self.dyn[l].items.items()):
                for r2, n2 in self.dyn[l].near(r, sp):
                    if n2 != n and n < n2 and rgap(r, r2) < sp - 1e-9:
                        out.append((l, n, n2, r, r2))
        return out

    def conflicts(self):
        bad = set()
        for l in self.dyn:
            sp = SPACE[l]
            for k, (r, n) in list(self.dyn[l].items.items()):
                for r2, n2 in self.dyn[l].near(r, sp):
                    if (n2 != n or (l in ("v1", "v2") and r2 != r)) and rgap(r, r2) < sp - 1e-9:
                        bad.add(n)
                        bad.add(n2)
        return bad

    # ------------------------------------------------------------------ all nets
    def route_all(self, nets, order, iters=40, pres0=0.5, pres_mult=1.3, hist_step=0.5, log=print):
        """nets: {net: [terminal node sets]}.  Returns (unrouted nets, conflicting nets)."""
        self.pres = pres0
        todo = list(order)
        unrouted, bad = set(), set()
        for it in range(iters):
            for net in todo:
                self.ripup(net)
                if not self.route_net(net, nets[net]):
                    unrouted.add(net)
                else:
                    unrouted.discard(net)
            bad = self.conflicts()
            log(f"  iter {it:2d}: pres={self.pres:7.2f} conflicts={len(bad):2d} unrouted={len(unrouted)} "
                f"{sorted(bad | unrouted)}")
            if not bad and not unrouted:
                break
            for net in bad:
                for p in self.netpaths.get(net, []):
                    for n in p:
                        self.hist[n] += hist_step
            self.pres = min(self.pres * pres_mult, 1000.0)
            todo = [n for n in order if n in bad or n in unrouted]
        # final repair: reroute each remaining offender alone with all other nets effectively hard
        if bad:
            self.pres = 1e6
            for net in sorted(bad):
                self.ripup(net)
                if not self.route_net(net, nets[net]):
                    unrouted.add(net)
                bad = self.conflicts()
                log(f"  repair {net}: conflicts now {sorted(bad)} unrouted {sorted(unrouted)}")
        return unrouted, bad

    def wires(self):
        out = []
        for net, lst in self.netshapes.items():
            for l, k in lst:
                out.append((l, self.dyn[l].items[k][0], net))
        return out
