"""Small layout-generation library for the B1 bias generator cells (gf180mcuD, magic).

Derived from layout/slot/slotgen.py (same conventions: PDK device cells from
gf180mcu::*_draw in devices/, geometry painted by a generated Tcl script, gridded
PathFinder router with exact spacing checks, KLayout morphological notch fill).

A Cell collects
  * device instances (PDK MOS cells, single- or multi-finger, and ppolyf_u_1k resistors),
    each strip / gate / resistor head becoming a router terminal of its net;
  * painted geometry (wells, taps, rails, straps, labels) and router obstacles;
and routes the remaining connections with router.Router.

All units um.  magic internal units: 200 per um (magscale 1 10).
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from router import Router, HW, PAD, SPACE, rgap   # noqa: E402


def _diag(a, b, sp):
    """same-net shapes that neither touch nor sit in line, closer than sp corner to corner"""
    dx = max(0.0, b[0] - a[2], a[0] - b[2])
    dy = max(0.0, b[1] - a[3], a[1] - b[3])
    return dx > 1e-9 and dy > 1e-9 and max(dx, dy) < sp - 1e-9


class RouterX(Router):
    """Router that also forbids same-net corner-to-corner near misses on metal (magic flags them)."""

    def hard_ok(self, layer, rect, net):
        if not super().hard_ok(layer, rect, net):
            return False
        if layer[0] == "m":
            sp = SPACE[layer]
            for r, n in self.static[layer].near(rect, sp):
                if n == net and _diag(r, rect, sp):
                    return False
        return True

    def soft_hits(self, layer, rect, net):
        hit = super().soft_hits(layer, rect, net)
        if layer[0] == "m":
            sp = SPACE[layer]
            for r, n in self.dyn[layer].near(rect, sp):
                if n == net and _diag(r, rect, sp):
                    hit.add(net + "#diag")
        return hit

    def conflicts(self):
        bad = super().conflicts()
        for l in self.layers:
            sp = SPACE[l]
            for k, (r, n) in list(self.dyn[l].items.items()):
                for r2, n2 in self.dyn[l].near(r, sp):
                    if n2 == n and _diag(r, r2, sp):
                        bad.add(n)
        return bad

U = 200
DEVDIR = HERE / "devices"


def snap(v, g=0.005):
    return round(round(v / g) * g, 4)


def shift(r, dx, dy):
    return (snap(r[0] + dx), snap(r[1] + dy), snap(r[2] + dx), snap(r[3] + dy))


def bb(rs):
    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))


# ============================================================================ device library
def fmt(v):
    return ("%g" % v).replace(".", "p")


def mos_name(model, w, l, nf=1):
    return f"{model[0]}_w{fmt(w)}_l{fmt(l)}" + (f"_f{nf}" if nf > 1 else "")


def res_name(w, l):
    return f"r_w{fmt(w)}_l{fmt(l)}"


DEVSPECS = {}      # cell name -> tcl line for gen_devices


def need_mos(model, w, l, nf=1):
    n = mos_name(model, w, l, nf)
    typ = "nfet_03v3" if model[0] == "n" else "pfet_03v3"
    DEVSPECS[n] = f"mk {n} {typ} [dict merge $common {{w {w:g} l {l:g} nf {nf}}}]"
    return n


def need_res(w, l):
    n = res_name(w, l)
    DEVSPECS[n] = f"mk {n} ppolyf_u_1k [dict merge $rcommon {{w {w:g} l {l:g}}}]"
    return n


_LIB = {}

GEN_TCL = r"""
proc mk {name type params} {
    load $name
    box values 0 0 0 0
    set p [dict merge [gf180mcu::${type}_defaults] $params]
    if {[catch {set p [gf180mcu::${type}_check $p]} err]} { puts "CHECK $name: $err" }
    gf180mcu::${type}_draw $p
    property library gf180mcu
    property gencell $type
    property parameters $p
    save $name
    puts "MADE $name"
}
set common {guard 0 topc 0 botc 0 m 1}
set rcommon {guard 0 m 1 nx 1}
"""


def gen_missing(names):
    """Generate PDK device cells into devices/ with magic (inside the EDA container)."""
    import os
    import subprocess
    DEVDIR.mkdir(exist_ok=True)
    todo = [n for n in names if not (DEVDIR / f"{n}.mag").exists()]
    if not todo:
        return
    tcl = GEN_TCL + "\n".join(DEVSPECS[n] for n in todo) + "\nquit -noprompt\n"
    (DEVDIR / "_gen.tcl").write_text(tcl)
    rc = f"{os.environ['PDK_ROOT']}/{os.environ['PDK']}/libs.tech/magic/{os.environ['PDK']}.magicrc"
    subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", rc, "_gen.tcl"], cwd=DEVDIR,
                   capture_output=True, text=True)
    for n in todo:
        if not (DEVDIR / f"{n}.mag").exists():
            raise SystemExit(f"device generation failed for {n}")


def load_dev(name):
    if name in _LIB:
        return _LIB[name]
    if not (DEVDIR / f"{name}.mag").exists():
        gen_missing([name])
    txt = (DEVDIR / f"{name}.mag").read_text()
    layer, R = None, {}
    ts = int(re.search(r"timestamp (\d+)", txt).group(1))
    for ln in txt.splitlines():
        m = re.match(r"<< (\w+) >>", ln)
        if m:
            layer = m.group(1)
            continue
        if ln.startswith("rect") and layer != "checkpaint":
            x1, y1, x2, y2 = (int(v) / U for v in ln.split()[1:5])
            R.setdefault(layer, []).append((x1, y1, x2, y2))
    allr = [r for k, v in R.items() for r in v]
    d = dict(name=name, ts=ts, R=R, bbox=bb(allr))
    if "nhighres" in R or "hires" in R:
        body = bb(R.get("nhighres", []) + R.get("hires", []))
        heads = sorted(R.get("polycontact", []), key=lambda r: r[1])
        d.update(kind="res", body=body, heads=heads)
    else:
        diff = [r for k in ("ndiff", "pdiff", "ndiffc", "pdiffc") for r in R.get(k, [])]
        gates = sorted(R.get("nmos", []) + R.get("pmos", []), key=lambda r: r[0])
        cont = R.get("ndiffc", []) + R.get("pdiffc", [])
        strips = sorted(cont, key=lambda r: r[0])
        d.update(kind="mos", diff=bb(diff), gates=gates, strips=strips, pol="n" if "nmos" in R else "p",
                 well=bb(R.get("pwell", []) + R.get("nwell", [])))
    _LIB[name] = d
    return d


# ============================================================================ cell
class Cell:
    def __init__(self, name):
        self.name = name
        self.paint = []        # (layer, rect)
        self.labels = []       # (text, layer, rect, use or None)
        self.nets = {}         # net -> list of terminals (list of (layer, rect))
        self.obst = []         # (router layer, rect, net)
        self.insts = []        # (devcell dict, inst name, x, y)
        self.forbid = []       # (layers, rect, allowed, only)
        self.uses = []         # subcell uses: (cellname, inst, x, y, bbox)
        self.devs = []         # placed device records
        self.req_x, self.req_y = set(), set()
        self._k = 0

    # ---------------------------------------------------------------- primitives
    def p(self, layer, r, net=None, term=False):
        r = tuple(snap(v) for v in r)
        self.paint.append((layer, r))
        rl = {"metal1": "m1", "metal2": "m2", "metal3": "m3", "via1": "v1", "via2": "v2"}.get(layer)
        if rl and net is not None:
            self.obst.append((rl, r, net))
            if term and rl[0] == "m":
                self.term(net, [(rl, r)])
        return r

    def term(self, net, shapes):
        self.nets.setdefault(net, []).append(shapes)

    def label(self, text, layer, r, use="signal"):
        self.labels.append((text, layer, tuple(snap(v) for v in r), use))

    def via1(self, x, y, net, w=0.40, h=0.40):
        pad = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        self.p("metal1", pad, net)
        self.p("metal2", pad, net)
        self.p("via1", (x - 0.13, y - 0.13, x + 0.13, y + 0.13), net)

    def via2(self, x, y, net, w=0.40, h=0.40):
        pad = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        self.p("metal2", pad, net)
        self.p("metal3", pad, net)
        self.p("via2", (x - 0.14, y - 0.14, x + 0.14, y + 0.14), net)

    def forbid_box(self, layers, r, allowed=None, only=None):
        self.forbid.append((tuple(layers), tuple(r), allowed, only))

    # ---------------------------------------------------------------- MOS
    def mos(self, inst, model, w, l, x, y, strips, gates, nf=1, head="top", hoff=0.45, rails=None,
            busses=None, term_strips=True):
        """Place a (multi-finger) MOS PDK cell centred at (x, y).

        strips: nets of the nf+1 S/D strips, left to right (None = no connection).
        gates : one net (all fingers) or a list of nf nets.
        head  : 'top' / 'bot' per-finger gate heads, 'alt' alternating, 'bar' / 'barbot' one poly bar
                over all fingers (needs a single gate net), 'none'.
        rails : {net: y}  -> those strips get a Metal1 extension to y (rail drawn by the caller).
        busses: {net: y}  -> those strips get via1 + Metal2 stub to y and a Metal2 bus over their x range.
        """
        nm = need_mos(model, w, l, nf)
        lc = load_dev(nm)
        if isinstance(gates, str):
            gates = [gates] * nf
        assert len(strips) == nf + 1 and len(gates) == nf, (inst, len(strips), nf)
        self.insts.append((lc, inst, x, y))
        rec = dict(inst=inst, lc=lc, x=x, y=y, strips=[], gates=[], model=model, w=w, l=l, nf=nf,
                   snets=strips, gnets=gates)
        dl = lc["diff"]
        dtop, dbot = y + dl[3], y + dl[1]
        rails = rails or {}
        busses = busses or {}
        # ---- S/D strips
        for k, (sr, net) in enumerate(zip(lc["strips"], strips)):
            r = shift(sr, x, y)
            # the device's own M1 over the contact column is slightly taller than the contact
            m1 = (r[0], r[1] - 0.055, r[2], r[3] + 0.055)
            rec["strips"].append(m1)
            n = net if net is not None else f"_nc_{inst}_{k}"
            self.obst.append(("m1", m1, n))
            cx = (r[0] + r[2]) / 2
            if net in rails:
                yr = rails[net]
                ext = (cx - 0.115, min(yr, m1[1]), cx + 0.115, max(yr, m1[3]))
                self.p("metal1", ext, net)
            elif net in busses:
                yb = busses[net]
                cy = (r[1] + r[3]) / 2
                self.p("metal1", (cx - 0.2, cy - 0.2, cx + 0.2, cy + 0.2), net)
                self.p("metal2", (cx - 0.2, cy - 0.2, cx + 0.2, cy + 0.2), net)
                self.p("via1", (cx - 0.13, cy - 0.13, cx + 0.13, cy + 0.13), net)
                self.p("metal2", (cx - 0.15, min(cy, yb) - 0.15, cx + 0.15, max(cy, yb) + 0.15), net)
            elif net is not None and term_strips:
                self.term(net, [("m1", m1)])
                self.req_x.add(snap(cx))
        for net, yb in busses.items():
            xs_ = [(r[0] + r[2]) / 2 for r, n in zip(rec["strips"], strips) if n == net]
            if xs_:
                br = (min(xs_) - 0.15, yb - 0.15, max(xs_) + 0.15, yb + 0.15)
                self.p("metal2", br, net)
                self.term(net, [("m2", br)])
        # ---- gates
        gl = [shift(g, x, y) for g in lc["gates"]]
        rec["gate_rects"] = gl
        if head in ("bar", "barbot"):
            assert len(set(gates)) == 1
            net = gates[0]
            up = head == "bar"
            hcy = snap(dtop + hoff) if up else snap(dbot - hoff)
            for g in gl:
                if up:
                    self.p("polysilicon", (g[0], g[3], g[2], hcy + 0.18))
                else:
                    self.p("polysilicon", (g[0], hcy - 0.18, g[2], g[1]))
            x0, x1 = gl[0][0], gl[-1][2]
            self.p("polysilicon", (x0, hcy - 0.18, x1, hcy + 0.18))
            for g in gl:
                gx = (g[0] + g[2]) / 2
                self.p("polycontact", (gx - 0.115, hcy - 0.115, gx + 0.115, hcy + 0.115))
            bar = self.p("metal1", (x0, hcy - 0.19, x1, hcy + 0.19), net)
            self.term(net, [("m1", bar)])
            self.req_y.add(hcy)
            rec["gates"].append(bar)
        elif head != "none":
            for k, (g, net) in enumerate(zip(gl, gates)):
                up = head == "top" or (head == "alt" and k % 2 == 0)
                hcy = snap(dtop + hoff) if up else snap(dbot - hoff)
                gx = snap((g[0] + g[2]) / 2)
                hx = max((g[2] - g[0]) / 2, 0.18)
                if up:
                    self.p("polysilicon", (g[0], g[3], g[2], hcy + 0.18))
                else:
                    self.p("polysilicon", (g[0], hcy - 0.18, g[2], g[1]))
                self.p("polysilicon", (gx - hx, hcy - 0.18, gx + hx, hcy + 0.18))
                self.p("polycontact", (gx - 0.115, hcy - 0.115, gx + 0.115, hcy + 0.115))
                pad = self.p("metal1", (gx - 0.19, hcy - 0.19, gx + 0.19, hcy + 0.19), net)
                self.term(net, [("m1", pad)])
                self.req_x.add(gx)
                self.req_y.add(hcy)
                rec["gates"].append(pad)
        self.devs.append(rec)
        return rec

    def mos_extent(self, model, w, l, nf=1, head="top", hoff=0.45):
        """(x0, y0, x1, y1) of diffusion+heads relative to the device centre (for placement)."""
        lc = load_dev(need_mos(model, w, l, nf))
        d = lc["diff"]
        top = d[3] + hoff + 0.19 if head in ("top", "bar", "alt") else lc["bbox"][3]
        bot = d[1] - hoff - 0.19 if head in ("bot", "barbot", "alt") else lc["bbox"][1]
        return (d[0], bot, d[2], top)

    # ---------------------------------------------------------------- resistor
    def res(self, inst, w, l, x, y, top_net, bot_net, term=True):
        """ppolyf_u_1k strip, vertical (length along y), centred at (x, y)."""
        nm = need_res(w, l)
        lc = load_dev(nm)
        self.insts.append((lc, inst, x, y))
        out = []
        for h, net in zip(lc["heads"], (bot_net, top_net)):
            r = shift(h, x, y)
            # M1 over the head contact, widened to 0.38 x 0.38 minimum landing
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            hw = max((r[2] - r[0]) / 2 + 0.055, 0.19)
            m1 = (cx - hw, cy - 0.19, cx + hw, cy + 0.19)
            self.p("metal1", m1, net)
            if term:
                self.term(net, [("m1", m1)])
            out.append(m1)
            self.req_y.add(snap(cy))
        return dict(inst=inst, lc=lc, x=x, y=y, heads=out, bbox=shift(lc["bbox"], x, y))

    # ---------------------------------------------------------------- wells / taps
    def tap(self, kind, r, net, term=True, metal=True):
        """kind 'p' (psubdiff, substrate) or 'n' (nsubdiff, n-well); contact strip inset 0.185."""
        diff = "psubdiff" if kind == "p" else "nsubdiff"
        cont = "psubdiffcont" if kind == "p" else "nsubdiffcont"
        self.p(diff, r)
        c = 0.185
        if r[2] - r[0] >= 0.6 - 1e-6 and r[3] - r[1] >= 0.6 - 1e-6:
            self.p(cont, (r[0] + c, r[1] + c, r[2] - c, r[3] - c))
            if metal:
                m = self.p("metal1", (r[0] + 0.13, r[1] + 0.13, r[2] - 0.13, r[3] - 0.13), net)
                if term:
                    self.term(net, [("m1", m)])
                return m
        return None

    def ring(self, kind, box, wdt, net, gaps=(), term=True):
        """Tap ring of width wdt along the inside of box. gaps: list of (side, a, b) metal gaps."""
        x0, y0, x1, y1 = box
        sides = {"b": (x0, y0, x1, y0 + wdt), "t": (x0, y1 - wdt, x1, y1),
                 "l": (x0, y0, x0 + wdt, y1), "r": (x1 - wdt, y0, x1, y1)}
        diff = "psubdiff" if kind == "p" else "nsubdiff"
        cont = "psubdiffcont" if kind == "p" else "nsubdiffcont"
        out = []
        for s, r in sides.items():
            self.p(diff, r)
            segs = [r]
            for gs, a, b in gaps:
                if gs != s:
                    continue
                new = []
                for q in segs:
                    if s in "bt":
                        if a < q[2] and b > q[0]:
                            if a - q[0] > 0.8:
                                new.append((q[0], q[1], a, q[3]))
                            if q[2] - b > 0.8:
                                new.append((b, q[1], q[2], q[3]))
                        else:
                            new.append(q)
                    else:
                        if a < q[3] and b > q[1]:
                            if a - q[1] > 0.8:
                                new.append((q[0], q[1], q[2], a))
                            if q[3] - b > 0.8:
                                new.append((q[0], b, q[2], q[3]))
                        else:
                            new.append(q)
                segs = new
            for q in segs:
                c = 0.185
                self.p(cont, (q[0] + c, q[1] + c, q[2] - c, q[3] - c))
                m = self.p("metal1", (q[0] + 0.13 * 0, q[1], q[2], q[3]), net)
                if term:
                    self.term(net, [("m1", m)])
                out.append(m)
        return out

    # ---------------------------------------------------------------- subcells
    def use(self, cellname, inst, x, y, bbox):
        self.uses.append((cellname, inst, snap(x), snap(y), bbox))

    # ---------------------------------------------------------------- routing
    def make_grid(self, box, base=0.70, extra_x=(), extra_y=()):
        req_x, req_y = set(self.req_x), set(self.req_y)
        for net, terms in self.nets.items():
            for t in terms:
                for lay, r in t:
                    if r[2] - r[0] < 1.0:
                        req_x.add(snap((r[0] + r[2]) / 2))
                    if r[3] - r[1] < 1.0:
                        req_y.add(snap((r[1] + r[3]) / 2))
        req_x.update(extra_x)
        req_y.update(extra_y)

        def merge(req, lo, hi):
            req = sorted(v for v in req if lo <= v <= hi)
            # drop required lines closer than 0.1 um to each other (keep the first)
            out = []
            for v in req:
                if not out or v - out[-1] > 0.1:
                    out.append(v)
            v = lo
            while v <= hi + 1e-9:
                if all(abs(v - q) >= base * 0.55 for q in out):
                    out.append(snap(v))
                v += base
            return sorted(set(out))
        return merge(req_x, box[0] + 0.2, box[2] - 0.2), merge(req_y, box[1] + 0.2, box[3] - 0.2)

    def route(self, box, layers=("m1", "m2"), order_first=(), order_last=(), base=0.70, iters=50,
              schedules=((1.3, 0.5), (1.6, 0.3), (1.2, 0.7), (1.45, 0.4)), extra_x=(), extra_y=(),
              skip=(), log=print, cache=None):
        """Route all nets with >= 2 terminals inside box. Returns list of failed nets."""
        key = None
        if cache is not None:
            key = hashlib.sha1(repr((sorted((k, sorted(map(repr, v))) for k, v in self.nets.items()),
                                     sorted(map(repr, self.obst)), sorted(map(repr, self.forbid)), box, layers,
                                     base, (HERE / "router.py").read_text())).encode()).hexdigest()
            if cache.exists():
                c = json.loads(cache.read_text())
                if c["key"] == key:
                    log(f"  reusing routing from {cache.name}")
                    self.wires = [(l, tuple(r), n) for l, r, n in c["wires"]]
                    return c["failed"]
        xs, ys = self.make_grid(box, base, extra_x, extra_y)
        log(f"  grid {len(xs)} x {len(ys)} x {len(layers)}")

        def mk():
            R = RouterX(xs, ys, layers)
            for lay, r, net in self.obst:
                R.add_shape(lay, r, net)
            for lays, r, allowed, only in self.forbid:
                R.add_forbid(lays, r, allowed, only)
            # cell boundary: nothing outside box
            return R

        def nodes(shapes):
            out = set()
            for lay, r in shapes:
                if lay not in layers:
                    continue
                for i, x in enumerate(xs):
                    if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                        for j, y in enumerate(ys):
                            if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                                out.add((lay, i, j))
            return out

        nets = {}
        for net, terms in self.nets.items():
            if net in skip:
                continue
            tn = [nodes(t) for t in terms]
            empty = [i for i, t in enumerate(tn) if not t]
            if empty:
                log(f"  !! {net}: terminal(s) {empty} have no grid node: {[terms[i] for i in empty]}")
            tn = [t for t in tn if t]
            # merge terminals that share grid nodes (e.g. a drawn gate rail over its gate heads)
            merged = []
            for t in tn:
                t = set(t)
                for m in [m for m in merged if m & t]:
                    t |= m
                    merged.remove(m)
                merged.append(t)
            tn = merged
            if len(tn) >= 2:
                nets[net] = tn
        order = [n for n in order_first if n in nets]
        order += sorted((n for n in nets if n not in order_first and n not in order_last),
                        key=lambda n: -max(len(t) for t in nets[n]) * 0 - len(nets[n]))
        order += [n for n in order_last if n in nets]
        failed = sorted(nets)
        R = None
        import os
        if os.environ.get("ROUTE_QUICK"):
            schedules, iters = schedules[:1], int(os.environ["ROUTE_QUICK"])
        if os.environ.get("ROUTE_ITERS"):       # cap: iterations per schedule, number of schedules (R2 experiments)
            iters = int(os.environ["ROUTE_ITERS"])
            schedules = schedules[:int(os.environ.get("ROUTE_NSCHED", len(schedules)))]
        for k, (pm, hs) in enumerate(schedules):
            R = mk()
            log(f"  schedule {k}: pres_mult={pm} hist_step={hs}  nets={len(nets)}")
            unrouted, bad = R.route_all(nets, order, iters=iters, pres_mult=pm, hist_step=hs, log=log)
            failed = sorted(unrouted | bad)
            if not failed:
                break
        for c in R.conflict_list():
            log(f"  CONFLICT {c}")
        self.wires = R.wires()
        if cache is not None:
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(json.dumps(dict(key=key, failed=failed, wires=self.wires)))
        return failed

    # ---------------------------------------------------------------- notch fill
    def fill_notches(self):
        import klayout.db as kdb
        dbu = 0.005
        per = {}
        for lay, r, net in list(self.obst) + list(getattr(self, "wires", [])):
            # "_o_<inst>" = all internal metal of a placed subcell (one placeholder net for many real nets):
            # closing those would bridge different leaf nets at minimum spacing, so they are never filled
            if lay in ("m1", "m2", "m3") and net is not None and not str(net).startswith(("_nc_", "_o_")):
                per.setdefault((lay, net), []).append(r)
        out = []
        minw = {"m1": 0.23, "m2": 0.28, "m3": 0.28}
        for (lay, net), rs in per.items():
            reg = kdb.Region()
            for r in rs:
                reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
            reg.merge()
            d = int(round(SPACE[lay] / 2 / dbu)) + 1
            mw = int(round(minw[lay] / dbu))
            closed = reg.dup()
            spc = int(round(SPACE[lay] / dbu))
            for _ in range(3):
                closed = closed.sized(d, d, 2).sized(-d, -d, 2)
                eps = list(closed.width_check(mw).each())
                for ep in eps:
                    b = ep.bbox()
                    cx, cy = b.center().x, b.center().y
                    w2 = max(b.width(), mw) // 2 + 1
                    h2 = max(b.height(), mw) // 2 + 1
                    closed.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
                closed.merge()
                if not eps:
                    break
            add = closed - reg
            for bx in add.each_merged():
                for t in kdb.Region(bx).decompose_trapezoids(1):
                    pts = list(t.each_point_hull())
                    xs = [p.x * dbu for p in pts]
                    ys = [p.y * dbu for p in pts]
                    out.append((lay, (snap(min(xs)), snap(min(ys)), snap(max(xs)), snap(max(ys))), net))
        self.fills = out
        return out

    # ---------------------------------------------------------------- output
    def write(self, box, outdir=HERE):
        lay = {"m1": "metal1", "m2": "metal2", "m3": "metal3", "v1": "via1", "v2": "via2"}
        base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
        for lc, name, cx, cy in self.insts:
            b = lc["bbox"]
            base += [f"use {lc['name']}  {name}", f"timestamp {lc['ts']}",
                     f"transform 1 0 {round(cx * U)} 0 1 {round(cy * U)}",
                     f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
        for cname, inst, x, y, b in self.uses:
            base += [f"use {cname}  {inst}", "timestamp 0",
                     f"transform 1 0 {round(x * U)} 0 1 {round(y * U)}",
                     f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
        base.append("<< end >>")
        (outdir / f"{self.name}_base.mag").write_text("\n".join(base) + "\n")
        tcl = ["# generated by cellgen.py -- do not edit", f"load {self.name}_base",
               f"cellname rename {self.name}_base {self.name}", "tech unlock *"]
        order = ["nwell", "psubdiff", "nsubdiff", "ndiode", "pdiode", "polysilicon", "metal1", "metal2", "metal3",
                 "psubdiffcont", "nsubdiffcont", "ndiodec", "pdiodec", "polycontact", "via1", "via2", "comment"]
        allp = list(self.paint) + [(lay[l], r) for l, r, n in getattr(self, "wires", [])] + \
            [(lay[l], r) for l, r, n in getattr(self, "fills", [])]
        for layer in order:
            seen = set()
            for l, r in allp:
                if l == layer and r not in seen:
                    seen.add(r)
                    tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
        k = 1
        for text, layer, r, use in self.labels:
            tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
            tcl.append(f"label {text} FreeSans 0.25um 0 0 0 c {layer}")
            if use:
                tcl.append(f"port make {k}; port use {use}; port class bidirectional")
                k += 1
        tcl.append(f"box values {box[0]}um {box[1]}um {box[2]}um {box[3]}um")
        tcl.append(f"save {self.name}")
        (outdir / f"{self.name}_paint.tcl").write_text("\n".join(tcl) + "\n")

    def preview(self, path, box, show_labels=True):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        w, h = box[2] - box[0], box[3] - box[1]
        fig, ax = plt.subplots(figsize=(max(4, w / 4), max(4, h / 4)))
        col = {"nwell": ("#cfe8cf", 0.6), "psubdiff": ("#e8c070", 0.7), "nsubdiff": ("#70c0e8", 0.7),
               "polysilicon": ("#d04040", 0.5), "metal1": ("#3050d0", 0.35), "metal2": ("#d020d0", 0.35),
               "metal3": ("#20a020", 0.35), "comment": ("#999999", 0.25)}
        for lc, name, cx, cy in self.insts:
            for k, rs in lc["R"].items():
                c = {"ndiff": "#40a040", "pdiff": "#a08040", "nmos": "#c03030", "pmos": "#c03030",
                     "polysilicon": "#d04040", "ndiffc": "#3050d0", "pdiffc": "#3050d0", "metal1": "#3050d0",
                     "nhighres": "#ff8000"}.get(k)
                if c:
                    for r in rs:
                        ax.add_patch(Rectangle((r[0] + cx, r[1] + cy), r[2] - r[0], r[3] - r[1], fc=c, alpha=0.5, lw=0))
        for u in self.uses:
            cname, inst, x, y, b = u[:5]
            if len(u) > 5 and u[5] == 90:
                b = (-b[3], b[0], -b[1], b[2])
            ax.add_patch(Rectangle((b[0] + x, b[1] + y), b[2] - b[0], b[3] - b[1], fill=False, ec="k"))
            ax.text(x + (b[0] + b[2]) / 2, y + (b[1] + b[3]) / 2, inst, ha="center", va="center", fontsize=6)
        lay = {"m1": "metal1", "m2": "metal2", "m3": "metal3"}
        allp = list(self.paint) + [(lay.get(l, l), r) for l, r, n in getattr(self, "wires", [])]
        for l, r in allp:
            if l in col:
                ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col[l][0], alpha=col[l][1], lw=0))
        if show_labels:
            for text, layer, r, use in self.labels:
                ax.text((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, text, fontsize=3, color="k")
        ax.set_xlim(box[0] - 0.5, box[2] + 0.5)
        ax.set_ylim(box[1] - 0.5, box[3] + 0.5)
        ax.set_aspect("equal")
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)


def write_devlist():
    (DEVDIR / "devlist.tcl").write_text("\n".join(sorted(DEVSPECS.values())) + "\n")
