"""Generate the EL trim cell trim_el4 (cells/trim/trim_el.spice) for the TE strip below the neuron array.

    scripts/eda.sh "cd layout/slot && SLOT_CELL=trim_el4 python3 elgen.py"   (build.sh runs it for CELLS=trim_el4)

Same machinery as slotgen.py (PDK device cells from devices/, gridded M1/M2/M3 router, notch fill, magic
paint script). Frame 28.0 x 10.6 um, one per P column, placed directly under that column:
  * vdd / el / aux / vbn_leak are full-height Metal2 lines at the array's column x positions
    (19.85 / 20.65 / 21.35 / 22.05), so the top-level route through CH_MID is a straight vertical run;
  * trim bits b3..b0: Metal2 straps from the top edge (x = 9.70 / 11.50 / 13.30 / 15.10);
  * VSS p-tap ring on the cell edge (abuts like the slots); pfets in an n-well with an n-tap strip.
Outputs: trim_el4_base.mag, trim_el4_paint.tcl, trim_el4_lvs.spice, out/preview_trim_el4.png.
"""
import hashlib
import json
import sys

import slotgen as SG
from slotgen import HERE, U, Layout, devcell, load_dev, shift, snap, fill_notches, flatten
from router import Router

import os
CELL = os.environ.get("SLOT_CELL", "trim_tau4")
if CELL not in ("trim_el4", "trim_tau4"):
    CELL = "trim_tau4"
RING = 0.60
PORT_MAP = {}                            # subckt port -> pin name (identical)
if CELL == "trim_el4":                   # UNUSED since 2026-11-18 (P second knob = leak tau); kept for reference
    W, H = 28.0, 10.6
    COLS = [("vdd", 19.85, 0.60), ("el", 20.65, 0.30), ("aux", 21.35, 0.30), ("vbn_leak", 22.05, 0.30)]
    STRAPS = [("b3", 9.70), ("b2", 11.50), ("b1", 13.30), ("b0", 15.10)]
    STRAP_Y = (3.00, H)
    NWELL = (0.90, 5.70, 17.00, 9.70)
    NTAP = (1.10, 8.98, 16.80, 9.58)          # n-tap strip (VDD) inside the n-well, along its top
    PLACE = {
        "XRS": (2.90, 1.45), "XL3": (7.34, 1.45), "XL2": (11.78, 1.45), "XL1": (16.22, 1.45),
        "XL0": (20.66, 1.45), "XLT": (25.10, 1.45),
        "XR1": (2.15, 3.75), "XR2": (4.95, 3.75), "XR3": (7.75, 3.75),
        "XN3": (10.00, 3.75), "XN2": (11.80, 3.75), "XN1": (13.60, 3.75), "XN0": (15.40, 3.75),
        "XMT": (18.60, 3.75), "XM1": (22.00, 3.75), "XM2": (24.60, 3.75),
        "XP1": (3.00, 7.10), "XP2": (6.40, 7.10),
        "XS3": (9.40, 7.10), "XS2": (11.20, 7.10), "XS1": (13.00, 7.10), "XS0": (14.80, 7.10),
    }
else:
    # trim_tau4 rev B (2026-11-20, vbn_leak / vss reference): 3 cells side by side fill the 112 um TE strip
    # (37.0 + 0.3 gaps); aux goes up through CH_MID, vbn_leak comes down from the bias channel.
    W, H = 37.0, 11.8
    COLS = []
    # all pins are Metal2 straps from the top edge; c0..c3 land on their source-switch gate heads
    STRAPS = [("aux", 6.20), ("vbn_leak", 12.20), ("c2", 15.20), ("c3", 21.60), ("c1", 27.60), ("c0", 31.00),
              ("vdd", 35.20)]
    STRAP_Y = (6.20, H)
    NWELL = (13.40, 8.30, 34.10, 10.85)
    NTAP = (33.25, 8.55, 33.85, 10.60)        # n-tap strip at the right end of the n-well
    # row A: the L = 4 mirror units on vbn_leak (4/4 x 5, then 2/4 under 1/4 in the last column)
    PLACE = {"XB0": (3.40, 3.10), "XB1": (9.10, 3.10), "XU2": (14.90, 3.10), "XU3a": (20.70, 3.10),
             "XU3b": (26.50, 3.10), "XU1": (32.30, 2.10), "XU0": (32.30, 4.94),
             # source switches under the pfet row, aux diodes (2 x 2/4) at the left, pfets in the n-well
             "XS2": (15.20, 6.95), "XS3": (21.60, 6.95), "XS1": (27.60, 6.95), "XS0": (31.00, 6.95),
             "XNDa": (3.40, 8.60), "XNDb": (9.10, 8.60),
             "XPM": (15.40, 9.55), "XPD0": (19.20, 9.55), "XPD1": (23.00, 9.55), "XPD2": (26.80, 9.55),
             "XPD3": (30.60, 9.55)}
FLIP = set()
SCHEDULES = [(1.3, 0.5), (1.6, 0.3), (1.2, 0.7), (1.45, 0.4)]


def build():
    ports, devs, caps = flatten.write_lvs(HERE / f"{CELL}_lvs.spice", CELL)
    lib = {}
    for d in devs:
        lib.setdefault(devcell(d), load_dev(devcell(d)))
    nm = lambda n: PORT_MAP.get(n, n)
    L, insts, obst = Layout(), [], []
    for d in devs:
        lc = lib[devcell(d)]
        cx, cy = PLACE[d["name"]]
        insts.append((lc, d["name"], cx, cy))
        nL, nR = (d["d"], d["s"]) if d["name"] in FLIP else (d["s"], d["d"])
        for side, net in (("L", nm(nL)), ("R", nm(nR))):
            for r in lc["m1"][side]:
                obst.append(("m1", shift(r, cx, cy), net))
            L.term(net, [("m1", shift(lc["stripe"][side], cx, cy))])
        g, dtop = lc["gate"], lc["diff"][3]
        hcy = snap(dtop + 0.45)
        hx = max((g[2] - g[0]) / 2, 0.18)
        L.p("polysilicon", shift((g[0], g[3], g[2], hcy + 0.18), cx, cy))
        L.p("polysilicon", shift((-hx, hcy - 0.18, hx, hcy + 0.18), cx, cy))
        pad = shift((-0.19, hcy - 0.19, 0.19, hcy + 0.19), cx, cy)
        L.p("metal1", pad)
        L.p("polycontact", shift((-0.115, hcy - 0.115, 0.115, hcy + 0.115), cx, cy))
        obst.append(("m1", pad, nm(d["g"])))
        L.term(nm(d["g"]), [("m1", pad)])
    # VSS p-tap ring (full Metal1 ring: no rail crosses it)
    c = (RING - 0.23) / 2
    for r in [(0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)]:
        L.p("psubdiff", r)
        L.p("metal1", r)
        obst.append(("m1", r, "vss"))
        L.term("vss", [("m1", r)])
        if r[2] - r[0] > r[3] - r[1]:
            L.p("psubdiffcont", (r[0] + c, r[1] + c, r[2] - c, r[3] - c))
        else:
            L.p("psubdiffcont", (r[0] + c, r[1] + c + 0.1, r[2] - c, r[3] - c - 0.1))
    L.labels.append(("vss", "metal1", (2.0, 0.1, 3.0, 0.5), "ground"))
    # n-well + n-tap strip
    L.p("nwell", NWELL)
    L.p("nsubdiff", NTAP)
    L.p("metal1", NTAP)
    L.p("nsubdiffcont", (NTAP[0] + c, NTAP[1] + c, NTAP[2] - c, NTAP[3] - c))
    obst.append(("m1", NTAP, "vdd"))
    L.term("vdd", [("m1", NTAP)])
    # full-height Metal2 lines (array column positions) and bit straps
    for net, x, w in COLS:
        r = (x - w / 2, 0, x + w / 2, H)
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", (r[0], H - 0.5, r[2], H - 0.1), "power" if net == "vdd" else "signal"))
    for net, x in STRAPS:
        r = (x - 0.15, STRAP_Y[0], x + 0.15, STRAP_Y[1])
        L.p("metal2", r)
        obst.append(("m2", r, net))
        L.term(net, [("m2", r)])
        L.labels.append((net, "metal2", (r[0], H - 0.5, r[2], H - 0.1), "signal"))
    return L, insts, obst, lib


def make_grid(L, base=0.70):
    req_x, req_y = set(), set()
    for net, terms in L.nets.items():
        for t in terms:
            for lay, r in t:
                if r[2] - r[0] < 1.0:
                    req_x.add(snap((r[0] + r[2]) / 2, 0.005))
                if r[3] - r[1] < 1.0:
                    req_y.add(snap((r[1] + r[3]) / 2, 0.005))

    def merge(req, lo, hi):
        req = sorted(v for v in req if lo <= v <= hi)
        out, v = list(req), base
        while v <= hi + 1e-9:
            if all(abs(v - q) >= base * 0.55 for q in req):
                out.append(snap(v, 0.005))
            v += base
        return sorted(set(out))
    return merge(req_x, 0.30, W - 0.30), merge(req_y, 0.30, H - 0.30)


def add_forbids(R):
    for r in ((0, 0, W, RING + 0.15), (0, H - RING - 0.15, W, H), (0, 0, RING + 0.15, H), (W - RING - 0.15, 0, W, H)):
        R.add_forbid(("m1",), r, allowed={"vss"})
    for r in ((0, 0, W, RING), (0, H - RING, W, H), (0, 0, RING, H), (W - RING, 0, W, H)):
        R.add_forbid(("m2",), r)
    for r in ((0, 0, W, 0.3), (0, H - 0.3, W, H), (0, 0, 0.3, H), (W - 0.3, 0, W, H)):
        R.add_forbid(("m3",), r)


def route(L, obst):
    xs, ys = make_grid(L)

    def nodes(shapes):
        out = set()
        for lay, r in shapes:
            for i, x in enumerate(xs):
                if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                    for j, y in enumerate(ys):
                        if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                            out.add((lay, i, j))
        return out
    nets = {n: [t for t in (nodes(t) for t in terms) if t] for n, terms in L.nets.items()}
    order = sorted(n for n in nets if n not in ("vdd", "vss")) + ["vdd", "vss"]
    for k, (pm, hs) in enumerate(SCHEDULES):
        R = Router(xs, ys, layers=("m1", "m2", "m3"))
        for lay, r, net in obst:
            R.add_shape(lay, r, net)
        add_forbids(R)
        print(f"  schedule {k}: pres_mult={pm} hist_step={hs}")
        unrouted, bad = R.route_all(nets, order, iters=60, pres_mult=pm, hist_step=hs)
        failed = sorted(unrouted | bad)
        if not failed:
            break
    return [w for w in R.wires() if w[0] != "fill"], failed


def write_outputs(L, insts, wires):
    base = ["magic", "tech gf180mcuD", "magscale 1 10", "timestamp 0"]
    for lc, name, cx, cy in insts:
        b = lc["bbox"]
        base += [f"use {lc['name']}  {name.replace('.', '_')}", f"timestamp {lc['ts']}",
                 f"transform 1 0 {round(cx * U)} 0 1 {round(cy * U)}",
                 f"box {round(b[0] * U)} {round(b[1] * U)} {round(b[2] * U)} {round(b[3] * U)}"]
    base.append("<< end >>")
    (HERE / f"{CELL}_base.mag").write_text("\n".join(base) + "\n")
    tcl = ["# generated by elgen.py -- do not edit", f"load {CELL}_base", f"cellname rename {CELL}_base {CELL}",
           "tech unlock *"]
    order = ["nwell", "psubdiff", "nsubdiff", "polysilicon", "metal1", "metal2", "metal3",
             "psubdiffcont", "nsubdiffcont", "polycontact", "via1", "via2"]
    lay = {"m1": "metal1", "m2": "metal2", "v1": "via1", "m3": "metal3", "v2": "via2"}
    allp = list(L.paint) + [(lay[l], r) for l, r, n in wires]
    for layer in order:
        for l, r in allp:
            if l == layer:
                tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {layer}")
    k = 1
    for text, layer, r, use in L.labels:
        tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um")
        tcl.append(f"label {text} FreeSans 0.25um 0 0 0 c {layer}")
        if use:
            tcl.append(f"port make {k}; port use {use}; port class bidirectional")
            k += 1
    tcl += [f"box values 0um 0um {W}um {H}um", f"save {CELL}"]
    (HERE / f"{CELL}_paint.tcl").write_text("\n".join(tcl) + "\n")


def preview(L, insts, wires, path):
    SG.W, SG.H, SG.BAND = W, H, (0, 0, 0, 0)

    class R0:
        wire_list = wires
    SG.preview(L, insts, R0, None, path)


def main():
    L, insts, obst, lib = build()
    if "place" in sys.argv:
        preview(L, insts, [], HERE / "out" / f"place_{CELL}.png")
        return 0
    key = hashlib.sha1(repr((PLACE, COLS, STRAPS, NWELL, NTAP, W, H, open(HERE / "router.py").read(),
                             open(HERE / "elgen.py").read())).encode()).hexdigest()
    cache = HERE / "out" / f"route_cache_{CELL}.json"
    if cache.exists() and "reuse" in sys.argv and json.loads(cache.read_text())["key"] == key:
        c = json.loads(cache.read_text())
        wires, failed = [(l, tuple(r), n) for l, r, n in c["wires"]], c["failed"]
        print("  reusing routing from", cache.name)
    else:
        wires, failed = route(L, obst)
        (HERE / "out").mkdir(exist_ok=True)
        cache.write_text(json.dumps(dict(key=key, failed=failed, wires=wires)))
    fills = fill_notches(obst, wires)
    print(f"  notch fillers: {len(fills)}")
    wires = list(wires) + fills
    write_outputs(L, insts, wires)
    preview(L, insts, wires, HERE / "out" / f"preview_{CELL}.png")
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
