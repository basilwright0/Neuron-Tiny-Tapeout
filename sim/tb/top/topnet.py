"""Full-chip post-layout netlist for the top-level PEX spot checks (runs inside the EDA container).

Source: layout/top/work/pexr/top_rc_flat.spice, written by sim/tb/top/ext_rc.tcl (magic, final GDS flattened,
`extract do resistance` + `extresist all`, all coupling C). R networks exist for VDPWR / VGND (every device
terminal) and for the nets extresist keeps (vsrc, abus, el, vreset, stb, ...); every other net is a
single node with all its C. The analog blocks are therefore their own layout (same extraction as the block-level
PEX), wired by the real top-level routing.

What this module does to that netlist:
  - drops the control macro (every *_05v0 device outside the glue row; the uio_oe tie cells too) and drives
    the macro's output nets with ideal sources behind R_DRV (std-cell output resistance), edges TR;
    macro-internal nodes are AC-grounded (their coupling C to top-level wires is kept, to ground);
  - keeps the glue row (en_b NOR, D1 tap decode) as extracted transistors;
  - sanitises node names for ngspice ('#' -> 'h', '[' / ']' -> '_');
  - power: VDPWR / VGND entry points = the Metal4 stripe ends (TT PDN; `entry`), or one ideal node.

build(state, ...) returns the deck body (no analysis); `node(name)` gives the sanitised node of a flat net.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]     # /work in the EDA container
FLAT = ROOT / "layout/top/work/pexr/top_rc_flat.spice"
RESEXT = ROOT / "layout/top/work/pexr/top_flat.res.ext"
sys.path.insert(0, str(ROOT / "layout/top"))
import config as _C                # noqa: E402  (layout/top/config.py; floorplan/floorplan.py as _C.fp)
fp = _C.fp
UNIT = 0.005                       # um per .ext / a_x_y unit (scale 1000 1 0.5 at 10 internal units / lambda)
MACRO = (fp.MACRO_X, fp.MACRO_Y, fp.MACRO_X + fp.MACRO_S, fp.MACRO_Y + fp.MACRO_S)
GLUE = (169.5, 4.5, 204.5, 10.5)   # pre-M3 glue row box (keep its std cells); the M3 / R2 rows: glue_boxes()
R_DRV = 1.5e3                      # macro output driver (buf_1-ish, 3.3 V)
# Glue std cells kept as transistors. 'm3' (default, the rule of every bench up to M3): a device is glue if one of its
# nodes is an a_x_y node inside GLUE or is named g_*. Since M3 moved the glue rows to x 282.6, that keeps only 20 of
# the 50 glue transistors (no nfet pull-down of en_b / d1_sel*: their nodes are all named nets + VGND.t*), and none of
# the R2 bay or3 (g_bor -> g_bay). 'full' (TOP_GLUE=full, needed for the bay probe): every device with an internal
# node or a power terminal inside a glue-row box of config.std_cells() (50 / 50 on the R2 netlist).
import os as _os                   # noqa: E402
GLUE_MODE = _os.environ.get("TOP_GLUE", "m3")
TR = 0.5e-9

_cache = {}


# ------------------------------------------------------------------ array map (floorplan/floorplan.py MAP)
CAP_DENS = 4.0e-15                 # F / um^2 of the nfet_03v3 membrane caps (7.07 x 7.07 = 200 fF; slotbench.CFAC)


def slot_pos(name):
    """Map position (row, col) of an array neuron by name (the instance is s<row><col>; CMP: s13)."""
    return next(rc for rc, n in fp.slot_map().items() if n == name)


def slot_inst(name):
    r, c = slot_pos(name)
    return f"s{r}{c}"


def neurons():
    """[(name, instance, cell)] of every array neuron (REF excluded), bottom row first."""
    return [(n, f"s{r}{c}", fp.slot_cell(n)) for (r, c), n in sorted(fp.slot_map().items()) if n != "REF"]


def bay():
    """[(name, instance, cell)] of the R2 bay column (by0 = S4, by1 = F4, by2 = E1 slot), bottom first; [] before R2."""
    bc = getattr(fp, "bay_cells", None)
    return [(n, f"by{k}", c) for k, n, c, x, y, h in bc()] if bc else []


def membrane_cap(cell):
    """Membrane C of a slot cell: the nfet_03v3 MOS caps with gate on vm and d = s = b = vss in the cell's LVS
    netlist (layout/top/config.LIB[cell]['lvs']), x CAP_DENS. They are devices, so not in the extracted C."""
    key = "cm_" + cell
    if key not in _cache:
        txt = re.sub(r"\n\+", " ", (ROOT / _C.LIB[cell]["lvs"]).read_text())
        txt = txt[txt.index(f".subckt {cell} "):]
        txt = txt[:txt.index(".ends")]
        a = 0.0
        for l in txt.splitlines():
            t = l.split()
            if len(t) > 5 and t[0][0] in "Xx" and t[1:6] == ["vss", "vm", "vss", "vss", "nfet_03v3"]:
                kv = dict(x.lower().split("=") for x in t[6:] if "=" in x)
                a += _unit(kv["w"]) * _unit(kv["l"]) * 1e12
        _cache[key] = a * CAP_DENS
    return _cache[key]


def san(n: str) -> str:
    n = n.replace("\\", "")
    if n in ("0", "VSUBS"):
        return "0"
    return n.replace("#", "h").replace("[", "_").replace("]", "_")


def node(name: str) -> str:
    return san(name)


def names():
    """Every node name of the flat netlist (raw)."""
    if "names" not in _cache:
        S = set()
        for l in load()["lines"]:
            for t in l.split()[1:]:
                if "=" in t:
                    break
                S.add(t)
        _cache["names"] = S
    return _cache["names"]


def net(logical: str) -> str:
    """Raw flat name of a logical net of layout/top/config.nets() (or a TT pin / inst.pin), e.g. 'vbn_leak' ->
    'tau2.vbn_leak' (the flattened cell names each net after one of its labels)."""
    import config as C
    S = names()
    if logical in S:
        return logical
    if "nets" not in _cache:
        _cache["nets"] = C.nets()
    for inst, pin in _cache["nets"].get(logical, []):
        for cand in (f"{inst}.{pin}", f"{inst}.r1_corner_0.{pin}"):
            if cand in S:
                return cand
    # any alias of the hierarchical extraction (instance pins of the same net)
    hier = hier_aliases().get(logical)
    for cand in hier or []:
        if cand in S:
            return cand
    raise KeyError(logical)


def hier_aliases():
    """logical net -> every inst.pin on it, from the LVS netlist's instance lines (pins named by their subckt)."""
    if "hal" in _cache:
        return _cache["hal"]
    txt = re.sub(r"\n\+", " ", (ROOT / "layout/top/work/top_ext.spice").read_text())
    sub = {m.group(1): m.group(2).split() for m in re.finditer(r"^\.subckt (\S+) (.*)$", txt, re.M)}
    top = txt[txt.index(".subckt tt_um"):]
    by_net = {}
    for m in re.finditer(r"^X(\S+) (.*)$", top, re.M):
        inst, rest = m.group(1), m.group(2).split()
        cell, conns = rest[-1], rest[:-1]
        for p, n in zip(sub.get(cell, []), conns):
            by_net.setdefault(n.replace("/", "."), []).append(f"{inst}.{p}")
    _cache["hal"] = by_net
    return by_net


def vnode(logical: str) -> str:
    return san(net(logical))


def _xy(n):
    m = re.match(r"a_(n?\d+)_(n?\d+)#", n)
    if not m:
        return None
    f = lambda s: -int(s[1:]) if s.startswith("n") else int(s)
    return f(m.group(1)) * UNIT, f(m.group(2)) * UNIT


def _inbox(p, b):
    return p is not None and b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def is_macro_node(n):
    return n.startswith("ctrl.") or _inbox(_xy(n), MACRO)


def glue_boxes():
    """Boxes of the top-level std cells kept as transistors: the old GLUE box plus every glue-row cell (g_*, gtap*)
    and the R2 probe_sub antenna diodes (gant*) of layout/top/config.std_cells() (M3: rows at x 282.6; R2: + the
    bay or3 row at (119.5, 58)). The uio_oe tie cells (tie*, tap*) stay dropped."""
    if "gboxes" not in _cache:
        import config as C
        B = [GLUE]
        for inst, (cell, x, y) in C.std_cells().items():
            if inst.startswith("g"):
                B.append((x - 0.01, y - 0.01, x + C.SC_W[cell] + 0.01, y + C.SC_H + 0.01))
        _cache["gboxes"] = B
    return _cache["gboxes"]


def in_glue(p):
    return p is not None and any(_inbox(p, b) for b in glue_boxes())


def load():
    if "lines" in _cache:
        return _cache
    txt = re.sub(r"\n\+", " ", FLAT.read_text())
    lines = txt.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith(".subckt"))
    ports = lines[i].split()[2:]
    body = [l for l in lines[i + 1:] if l and l[0] in "XRCD"]
    _cache.update(lines=body, ports=ports)
    return _cache


def macro_ports():
    """Macro pin -> flat net, from the hierarchical LVS extraction (same GDS)."""
    if "mports" in _cache:
        return _cache["mports"]
    txt = re.sub(r"\n\+", " ", (ROOT / "layout/top/work/top_ext.spice").read_text())
    ports = re.search(r"^\.subckt neuron_ctrl (.*)$", txt, re.M).group(1).split()
    top = txt[txt.index(".subckt tt_um"):]
    x = re.search(r"^Xctrl (.*)$", top, re.M).group(1).split()[:-1]
    # hierarchical names use '/', the flattened cell uses '.'
    _cache["mports"] = {p: n.replace("/", ".") for p, n in zip(ports, x)}
    return _cache["mports"]


MACRO_IN = re.compile(r"^(clk|rst_n|ui_in\[\d\]|uio_in\[\d\]|spk_in\[\d+\]|VDD|VSS)$")


def resolve(n):
    """Flat name of a net known by its hierarchical-extraction name (the flattened cell may name it after
    another label of the same net)."""
    S = names()
    if n in S:
        return n
    for a in hier_aliases().get(n, []):
        if a in S:
            return a
    return n


def macro_outputs():
    return {p: resolve(n) for p, n in macro_ports().items() if not MACRO_IN.match(p)}


def _unit(v):
    m = re.match(r"^([-\d.e+]+)([a-zA-Z]*)$", v)
    x = float(m.group(1))
    s = m.group(2).lower()
    return x * {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "a": 1e-18, "k": 1e3,
                "meg": 1e6}[s]


def rnodes(net):
    """{rnode name: (x, y) um} of a resistively extracted net (from the .res.ext)."""
    key = "rn_" + net
    if key in _cache:
        return _cache[key]
    out = {}
    pat = re.compile(r'^rnode "(' + re.escape(net) + r'(?:\.[nt]\d+)?)" \S+ \S+ (-?\d+) (-?\d+)')
    for l in RESEXT.read_text().splitlines():
        m = pat.match(l)
        if m:
            out[m.group(1)] = (int(m.group(2)) * UNIT, int(m.group(3)) * UNIT)
    _cache[key] = out
    return out


def stripe_entries(net, tol=6.0):
    """Nodes of `net` at the two ends of each Metal4 stripe (x inside the stripe, y within tol of the end)."""
    import config as C
    fp = C.fp
    rn = rnodes(net)
    out = []
    for n, x0, w in fp.STRIPES:
        if n != net:
            continue
        on = {k: p for k, p in rn.items() if x0 - 0.05 <= p[0] <= x0 + w + 0.05}
        if not on:
            continue
        lo = min(on, key=lambda k: on[k][1])
        hi = max(on, key=lambda k: on[k][1])
        for k, yend in ((lo, fp.STRIPE_Y[0]), (hi, fp.STRIPE_Y[1])):
            out.append((k, x0 + w / 2, on[k][1], abs(on[k][1] - yend)))
    return out


def block_boxes():
    """instance -> box (tile um) of every analog block, R1 first (it sits in B1's notch), glue row last."""
    import config as C
    fp = C.fp
    I = C.instances()
    B = {"r1": (262.0, 0.0, 302.0, 54.0)}
    for inst, (cell, x, y) in I.items():
        if inst in ("ctrl", "r1"):
            continue
        if inst == "b1":
            B[inst] = fp.B1_BOX
        elif inst.startswith("tau"):
            B[inst] = (x, y, x + 37.0, y + 11.8)
        else:
            sz = C.LIB[cell].get("size")
            if sz is None:                # R2 E2 (e2_leak): no LIB size; its floorplan block box
                bx = next((v for k, v in fp.BLOCKS.items() if k.startswith("E2")), (x, y, x + 31.0, y + 11.8))
                sz = (bx[2] - bx[0], bx[3] - bx[1])
            w, h = sz
            B[inst] = (x, y, x + w, y + h)
    B["glue"] = GLUE
    return B


def owner(nodes):
    """Block instance a device belongs to, from its position: internal a_x_y nodes, else the .res.ext position
    of its VDPWR / VGND terminal, else inst.* names that are block-local (not shared nets named after a block's
    label, e.g. 'd1.vbn_ref'); None if unknown."""
    bb = block_boxes()
    if "pw_rn" not in _cache:
        _cache["pw_rn"] = {**rnodes("VDPWR"), **rnodes("VGND")}
    pts = [_xy(n) for n in nodes] + [_cache["pw_rn"].get(n) for n in nodes]
    for p in pts:
        if p is None:
            continue
        for k, b in bb.items():
            if _inbox(p, b):
                return k
    shared = set(hier_aliases())
    for n in nodes:
        pre = n.split(".")[0]
        if pre.startswith("g_"):
            return "glue"
        if pre in bb and "." in n and n.replace(".", "/", 1) not in shared and n not in shared:
            return pre
    return None


def build(state: dict, sources: dict | None = None, cmin=1e-18, power="entry", r_entry=0.05,
          vdd=3.3, keep_macro_caps=True, extra_loads=True, glue=True, drop_inst=()):
    """state: macro pin -> value (V, or a SPICE source spec string). sources: extra 'name': 'line' entries.
    power: 'entry' (stripe ends, R networks kept) | 'ideal' (all VDPWR.* / VGND.* nodes shorted).
    drop_inst: block instances whose devices are removed (owner() by position), e.g. the R2 bay ('by0'..'by2') for
    the with / without bay-load comparison; their wiring C stays."""
    d = load()
    out = []
    drop = 0
    _cache["dropped_inst"] = 0
    if power == "gndnet":          # VDPWR ideal, VGND keeps its extracted R network, grounded at the 'VGND' port
        power = "ideal"            # node (bottom end of the B1 / R1 stripe x 342.6, magic's port location)
        _cache["keep_gnd"] = True
    for l in d["lines"]:
        t = l.split()
        kind = l[0]
        if kind in "XD":
            nn = [x for x in t[1:] if "=" not in x]
            model = nn[-1]
            nodes = nn[:-1]
            if model.endswith("_05v0"):
                pts = [_xy(x) for x in nodes]
                if GLUE_MODE == "full":       # device in a glue-row box by an internal node or its power terminal
                    if "pw_rn" not in _cache:
                        _cache["pw_rn"] = {**rnodes("VDPWR"), **rnodes("VGND")}
                    pts += [_cache["pw_rn"].get(x) for x in nodes]
                    glue_dev = glue and (any(in_glue(p) for p in pts) or any(x.startswith("g_") for x in nodes))
                else:                         # M3 rule (benches up to M3): old GLUE box or a g_* node name
                    glue_dev = glue and (any(_inbox(p, GLUE) for p in pts) or any(x.startswith("g_") for x in nodes))
                _cache["glue_kept"] = _cache.get("glue_kept", 0) + bool(glue_dev)
                if not glue_dev:
                    drop += 1
                    continue
            if any(is_macro_node(x) for x in nodes):
                drop += 1
                continue
            if drop_inst and owner(nodes) in drop_inst:
                _cache["dropped_inst"] += 1
                continue
            if power == "perdev":                     # one ammeter per device power terminal
                for x in nodes:
                    if x.startswith(("VDPWR", "VGND")):
                        _cache.setdefault("pterms", set()).add(x)
                nodes = [f"PT_{x}" if x.startswith(("VDPWR", "VGND")) else x for x in nodes]
            if power == "perblock":
                blk = owner(nodes) or "other"
                _cache.setdefault("blocks", set()).add(blk)
                nodes = [f"VDD_{blk}" if x.startswith("VDPWR") else f"VSS_{blk}" if x.startswith("VGND") else x
                         for x in nodes]
            nodes = [san(x) for x in nodes]
            if power in ("ideal", "perblock"):
                nodes = [_pw(x) for x in nodes]
            params = [x for x in t[1:] if "=" in x]
            if kind == "D":
                params = [re.sub(r"^pj=([\d.]+)p$", r"pj=\1u", x) for x in params]
            out.append(" ".join([t[0]] + nodes + [model] + params))
        elif kind == "R":
            a, b = san(t[1]), san(t[2])
            if is_macro_node(t[1]) or is_macro_node(t[2]):
                continue
            if power in ("ideal", "perblock", "perdev"):
                a, b = _pw(a), _pw(b)
                if a == b:
                    continue
            out.append(f"{t[0]} {a} {b} {t[3]}")
        elif kind == "C":
            v = _unit(t[3])
            if v < cmin:
                continue
            a = "0" if is_macro_node(t[1]) else san(t[1])
            b = "0" if is_macro_node(t[2]) else san(t[2])
            if not keep_macro_caps and "0" in (a, b):
                continue
            if power in ("ideal", "perblock", "perdev"):
                a, b = _pw(a), _pw(b)
            if a == b:
                continue
            out.append(f"{t[0]} {a} {b} {v:.6g}")
    # ---- R2 diagnostic (TOP_VSRC_FIX=1): the R+C extraction of the R2 chip has every vsrc coupling C as a ground C
    # ('**FLOATING' to VGND, 195 fF); the C-only extraction (layout/top/work/pex/top_c_flat.spice) has 241 fF with
    # 37 fF to vbn_leak, 36 fF to vbp_st, 10 fF to abus, digital lines ... Replace the vsrc-VGND caps by the C-only
    # vsrc caps, lumped at the vsrc root node (the line's R is ~0.1 mV at DC).
    if _os.environ.get("TOP_VSRC_FIX") == "1":
        out = vsrc_fix(out, power)
    # ---- power
    P = []
    if power in ("ideal", "perblock", "perdev"):
        P += [f"Vvdd VDPWR 0 {vdd}", "Vvss VGND 0 0"]
    if power == "perdev":
        for x in sorted(_cache.get("pterms", ())):
            P.append(f"Vpt_{san(x)} PT_{san(x)} 0 {vdd if x.startswith('VDPWR') else 0}")
    if power == "perblock":                       # one ammeter per block and rail
        for blk in sorted(_cache.get("blocks", ())):
            P += [f"Vdd_{blk} VDD_{blk} 0 {vdd}", f"Vss_{blk} VSS_{blk} 0 0"]
    else:
        P.append(f"Vsup vsup 0 {vdd}")
        for net, top in (("VDPWR", "vsup"), ("VGND", "0")):
            for k, (n, x, y, dy) in enumerate(stripe_entries(net)):
                P.append(f"Rpdn_{net}_{k} {san(n)} {top} {r_entry}")
    # ---- macro outputs
    mo = macro_outputs()
    for p, net in mo.items():
        val = state.get(p, 0.0)
        src = val if isinstance(val, str) else f"{float(val):g}"
        n = san(net)
        if n == "0" or is_macro_node(net) and not net.startswith("ctrl.cfg_out") and not net.startswith("ctrl.uio"):
            pass
        if is_macro_node(net):          # macro-internal (unconnected pins): already grounded
            continue
        P.append(f"Vm_{san(p)} md_{san(p)} 0 {src}")
        P.append(f"Rm_{san(p)} md_{san(p)} {n} {R_DRV}")
    if extra_loads:                      # macro input pins: ~ 5 fF gate + pin each
        for p, net in macro_ports().items():
            m = re.match(r"spk_in\[(\d+)\]", p)
            if m and int(m.group(1)) not in getattr(fp, "SPK_TIED", ()):       # R2: tied inputs sit on VGND
                P.append(f"Cmi_{san(p)} {san(resolve(net))} 0 5f")
    for k, v in (sources or {}).items():
        P.append(v)
    _cache["dropped"] = drop
    _cache["keep_gnd"] = False
    return "\n".join(out + P) + "\n"


def vsrc_fix(out, power):
    par = {}

    def f(x):
        while par.get(x, x) != x:
            par[x] = par.get(par[x], par[x])
            x = par[x]
        return x
    for l in load()["lines"]:
        if l[0] == "R":
            t = l.split()
            a, b = f(san(t[1])), f(san(t[2]))
            if a != b:
                par[a] = b
    root = san(net("vsrc"))
    g = f(root)
    keep, removed = [], 0.0
    for l in out:
        if l[0] == "C":
            t = l.split()
            a, b = t[1], t[2]
            if (f(a) == g and b.startswith("VGND")) or (f(b) == g and a.startswith("VGND")):
                removed += float(t[3])
                continue
        keep.append(l)
    S = {san(x) for x in names()}
    added, mapped, gnd = 0.0, 0.0, 0.0
    cf = ROOT / "layout/top/work/pex/top_c_flat.spice"
    for k, l in enumerate(re.sub(r"\n\+", " ", cf.read_text()).splitlines()):
        if not l.startswith("C"):
            continue
        t = l.split()
        ends = [x for x in t[1:3] if "vsrc" in x and "vsrcp" not in x]
        if len(ends) != 1:
            continue
        o = t[2] if t[1] in ends else t[1]
        v = _unit(t[3])
        cand = san(resolve(o.replace("/", ".")))
        if o in ("0", "VSUBS", "VGND") or o.startswith(("VGND", "VDPWR")) or cand not in S:
            other = "VGND" if not o.startswith("VDPWR") else "VDPWR"
            if power not in ("ideal", "perblock", "perdev"):
                other = "0" if other == "VGND" else other
            gnd += v
        else:
            other = "0" if is_macro_node(o.replace("/", ".")) else cand
            mapped += v
        added += v
        keep.append(f"Cvfix{k} {root} {other} {v:.6g}")
    _cache["vsrc_fix"] = (removed, added, mapped, gnd)
    return keep


def _pw(n):
    if _cache.get("keep_gnd") and n.startswith("VGND"):
        return n
    if n.startswith("VDPWR"):
        return "VDPWR"
    if n.startswith("VGND"):
        return "VGND"
    return n


# ------------------------------------------------------------------ chip configuration -> macro pin values
CODES_S100 = dict(i0=10, i1=14, i2=7, i3=9, i4=8)      # B1 report C.3 nominal codes (S = 100; S scales with ua[0])


def vcodes(el=1.30, vreset=1.30, vth_cmp=1.38, vth_ref=0.505):
    r0 = round((el - 0.994) / 0.0201)
    r1 = round((vreset - 0.891) / 0.0201)
    # M3 vth_cmp DAC (vdacr_vc R_base 60 sq): 1.231 .. 1.655 V; full-chip PEX gives 1.5261 V at code 22 (MIL-298).
    # The pre-M3 mapping (1.094 + 13.3 mV / code) clipped 1.58 V at code 31, which the M3 DAC turns into 1.655 V.
    r2 = min(31, round((vth_cmp - 1.2251) / 0.01368))
    v0 = round((vth_ref - 0.350) / 0.00635)
    return dict(r0=max(0, min(31, r0)), r1=max(0, min(31, r1)), r2=max(0, r2), v0=max(0, min(63, v0)))


def config(codes=None, probe=None, rt=(0, 0, 0, 0), bias_en=1, ib_x2=0, trims=8, vdd=3.3, plateau=0, chain=0,
           bsel=0, ua0_mode=0, grp_en=0):
    """Macro output pin values for a chip configuration.
    codes: dict i0..i4, r0..r2 (5 bit), v0 (6 bit).  probe: None or dict(sel=k, sub=s, en=1) in physical terms:
    dict(row=r, col=c, sub=s) for an array slot, 'd1' / 'adex' with sub, dict(blk='bay', k=0..2) for an R2 bay
    neuron (SEL 16 + k: probe_sel_bay[k] = EN, rsel / en_c all 0 as in the RTL), or None (probe off; rsel row 0)."""
    import config as C
    st = {}
    codes = dict(codes or {})
    for d in ("i0", "i1", "i2", "i3", "i4", "r0", "r1", "r2"):
        c = codes.get(d, 0)
        for j in range(5):
            st[f"{d}_b{j}"] = vdd * ((c >> j) & 1)
    for j in range(6):
        st[f"v0_c{j}"] = vdd * ((codes.get("v0", 0) >> j) & 1)
    st["ua0_s0"] = vdd if ua0_mode in (0, 3) else 0
    st["ua0_s1"] = vdd if ua0_mode == 1 else 0
    st["ua0_stim"] = vdd if ua0_mode == 2 else 0
    st["ua0_int"] = vdd if (ua0_mode >= 2 and bias_en) else 0
    st["bias_en"] = vdd * bias_en
    st["ib_x2"] = vdd * ib_x2
    for k in range(4):
        st[f"rt_out[{k}]"] = rt[k] if isinstance(rt[k], str) else vdd * rt[k]
    # probe
    rsel = [0, 0, 0, 0]
    en = [0, 0, 0, 0]
    sub, d1, ax, raw = 0, 0, 0, 0
    bay_sel = [0, 0, 0]
    if probe:
        if probe.get("blk") == "bay":
            bay_sel[probe["k"]], raw = probe.get("en", 1), probe.get("sub", 0)
        elif probe.get("blk") == "d1":         # rsel all 0 for D1 / AdEx
            d1, raw = probe.get("en", 1), probe.get("sub", 0)
        elif probe.get("blk") == "adex":
            ax, raw = probe.get("en", 1), probe.get("sub", 0)
        else:
            rsel[probe["row"]] = 1
            en[probe["col"]] = probe.get("en", 1)
            sub = probe.get("sub", 0)
            raw = sub
    else:
        rsel[0] = 1                       # reset state: rsel row of channel 0
    for k in range(4):
        st[f"probe_rsel[{k}]"] = vdd * rsel[k]
        st[f"probe_en_c[{k}]"] = vdd * en[k]
    st["probe_sub"] = vdd * (raw & 1)
    st["probe_sub_b"] = vdd * (1 - (raw & 1))
    st["probe_sel_d1"] = vdd * d1
    st["probe_sel_adex"] = vdd * ax
    for k in range(3):                    # R2 bay lines (macro outputs; a pre-R2 netlist has no such pins)
        st[f"probe_sel_bay[{k}]"] = vdd * bay_sel[k]
    st["probe_sub_raw[0]"] = vdd * (raw & 1)
    st["probe_sub_raw[1]"] = vdd * ((raw >> 1) & 1)
    # cfg_out: GRP_EN (cfg_out[0..3], reset 0; R2: [0] E2 charge, [1] E1 run, [2] E2 clamp), plateau / chain / bsel,
    # trims = code `trims` everywhere
    for j in range(4):
        st[f"cfg_out[{j}]"] = vdd * ((grp_en >> j) & 1)
    st["cfg_out[4]"] = vdd * plateau
    st["cfg_out[5]"] = vdd * chain
    st["cfg_out[6]"] = vdd * bsel
    for n in range(16):
        for j in range(4):
            st[f"cfg_out[{7 + 4 * n + j}]"] = vdd * ((trims >> j) & 1)
    for i in range(8):
        st[f"uo_out[{i}]"] = 0
        st[f"uio_out[{i}]"] = 0
    return st


if __name__ == "__main__":
    if "--nodes" in sys.argv:          # check that every victim / probe node resolves in the flat R+C netlist
        miss = 0
        for nm, n in [(f"{a} ({i}, {c}, Cm {membrane_cap(c) * 1e15:.0f} fF)", f"{i}.vm") for a, i, c in neurons()] + \
                [(x, x) for x in ("d1.vs", "d1.d1", "d1.d2", "ax.vm", "ax.vw", "abus", "en_b", "ua[1]")] + \
                [(f"bay {a} ({i}, {c})", f"{i}.{p}") for a, i, c in bay() for p in ("vm", "spk")] + \
                [(x, x) for x in ["g_bay"] + [f"probe_sel_bay[{k}]" for k in range(len(bay()))]]:
            try:
                print(f"{nm:36s} {n:8s} -> {net(n)}")
            except KeyError:
                print(f"{nm:36s} {n:8s} -> MISSING")
                miss += 1
        # glue devices kept: old rule (GLUE box / g_* node) vs glue_boxes(); bay devices by owner(); bay macro pins
        n05 = dict(old=0, new=0)
        for l in load()["lines"]:
            if l[0] not in "XD":
                continue
            nn = [x for x in l.split()[1:] if "=" not in x]
            if not nn[-1].endswith("_05v0") or any(is_macro_node(x) for x in nn[:-1]):
                continue
            pts = [_xy(x) for x in nn[:-1]]
            n05["old"] += any(_inbox(p, GLUE) for p in pts) or any(x.startswith("g_") for x in nn[:-1])
            n05["new"] += any(in_glue(p) for p in pts) or any(x.startswith("g_") for x in nn[:-1])
        print(f"_05v0 devices outside the macro kept as glue: old rule {n05['old']}, with glue_boxes() {n05['new']}")
        build(config(), drop_inst={i for _, i, _ in bay()})
        print(f"bay devices (owner by0..by2): {_cache['dropped_inst']}; macro outputs: " +
              ", ".join(f"{p}->{n}" for p, n in macro_outputs().items() if "bay" in p or "probe_sel" in p))
        sys.exit(1 if miss else 0)
    b = build(config(codes=dict(CODES_S100, **vcodes())))
    print(len(b.splitlines()), "lines; dropped", _cache["dropped"], "macro devices")
    print("\n".join(l for l in b.splitlines() if l.startswith(("Rpdn", "Vsup"))))
