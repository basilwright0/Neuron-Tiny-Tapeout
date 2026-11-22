"""Compact-layout geometry core (gf180mcuD, 3.3 V devices): shared-diffusion transistor chains, drawn flat.

A *chain* is one continuous diffusion strip with vertical gates. Neighbouring gates share their source/drain
region; a shared node that nothing else touches stays uncontacted (poly-to-poly spacing only), every other
region gets a contact column. Wide devices are folded into parallel fingers of the same L before chaining
(netgen adds parallel widths, as slotgen.split_devs already relies on).

Local chain frame: x from the left diffusion edge, y = 0 at the diffusion edge on the *rail side* (the tap
strip the row hangs from); gates grow towards +y, gate heads sit above the diffusion (channel side). Rows on
the other side of their rail are drawn mirrored in y by the placer.

Dimensions follow the PDK device generator (gf180mcu::nfet_03v3_draw, see layout/slot/devices/*.mag): contact
0.23, contact to gate 0.145 (0.165 next to a diffusion bend), diffusion past contact 0.065, bend 0.10 from the
gate, poly end cap 0.22, contacted diffusion at least 0.36 tall (dog-bone), gate head as slotgen.py.
"""
from dataclasses import dataclass, field

# ---------------------------------------------------------------- rules (um)
CONT = 0.23          # diffusion contact square
CG = 0.145           # contact to gate edge
CG_BEND = 0.165      # contact to gate edge when the diffusion bends between them
BEND = 0.10          # gate edge to a diffusion bend
DENC = 0.065         # diffusion enclosure of a contact
CMIN_H = 0.36        # diffusion height under a contact (CONT + 2 DENC = 0.36)
POLY_SP = 0.28       # gate-to-gate space over an uncontacted shared node
ENDCAP = 0.22        # poly past diffusion
HEAD_DY = 0.45       # gate-head centre above the top of the chain's diffusion
HEAD_POLY = 0.18     # head poly half-size (at least; L/2 for long gates)
HEAD_PAD = 0.19      # head metal1 pad half-size
PC = 0.115           # poly contact half-size
HEAD_STEP = 0.61     # second head level (staggered heads): pad 0.38 + metal1 space 0.23
POLY_SPACE = 0.24
M1_SPACE = 0.23
M1_MIN_LEN = 0.63    # 0.23-wide metal1 stub length for the 0.1444 um2 minimum area
DIFF_SP = 0.34       # diffusion to diffusion (separate chains in a row), with margin
SNAP = 0.005


def snap(v, g=SNAP):
    return round(round(v / g) * g, 4)


@dataclass
class Finger:
    name: str            # device name; folded fingers get a suffix (_f0, _f1, ...)
    dev: str             # original device name (LVS reference)
    typ: str             # "n" or "p"
    W: float
    L: float
    d: str
    g: str
    s: str
    slot: float = 0.0    # kept-slot footprint L (> L): drawn in that gate pitch, channel narrowed about its centre


@dataclass
class Chain:
    typ: str
    items: list = field(default_factory=list)      # [(Finger, flipped)]  flipped: drain on the left

    def nets(self):
        """Left-to-right list of diffusion nets: n0, n1, ..., nk (k = number of gates)."""
        out = []
        for f, fl in self.items:
            l, r = (f.d, f.s) if fl else (f.s, f.d)
            if not out:
                out.append(l)
            out.append(r)
        return out


def fold(dev, wmax):
    """Split a device wider than wmax into k equal parallel fingers whose width is on the 0.005 grid."""
    W = dev["W"]
    k = 1
    while W / k > wmax + 1e-9 or abs(snap(W / k) * k - W) > 1e-6:
        k += 1
        if k > 64:
            raise ValueError(f"cannot fold {dev['name']} W={W}")
    typ = dev["model"][0]
    sl = dev.get("slot", 0.0)
    if k == 1:
        return [Finger(dev["name"], dev["name"], typ, W, dev["L"], dev["d"], dev["g"], dev["s"], sl)]
    return [Finger(f"{dev['name']}_f{i}", dev["name"], typ, snap(W / k), dev["L"], dev["d"], dev["g"], dev["s"], sl)
            for i in range(k)]


def pitch(f):
    """Gate pitch of a finger in its chain: L, or the kept-slot footprint L (level 4: leak OTA 0.5 um in 1 um)."""
    return max(f.L, f.slot)


def draw_chain(ch, contacted):
    """Geometry of one chain in its local frame.

    contacted(net, i) -> bool: whether diffusion region i (0..k, between gates i-1 and i) needs a contact.
    End regions are always contacted. Returns dict:
      shapes: [(layer, rect)], width, height (top of the gate heads), terms: [(net, 'm1', rect)] for the
      router (contact stripes and gate pads), gates: [(Finger, x0, x1)], regions: [(net, x0, x1, contacted)].
    """
    nets = ch.nets()
    k = len(ch.items)
    diff = "ndiff" if ch.typ == "n" else "pdiff"
    dc = "ndiffc" if ch.typ == "n" else "pdiffc"
    mos = "nmos" if ch.typ == "n" else "pmos"
    Ws = [f.W for f, _ in ch.items]
    shapes, terms, gates, regions = [], [], [], []
    x = 0.0
    for i in range(k + 1):
        wl = Ws[i - 1] if i > 0 else None       # gate on the left of region i
        wr = Ws[i] if i < k else None           # gate on the right
        con = i in (0, k) or contacted(nets[i], i)
        if not con and wl != wr:
            con = True                          # no bend in an uncontacted gap
        if con:
            hc = max(w for w in (wl, wr, CMIN_H) if w is not None)
            bend_l = wl is not None and hc > wl + 1e-9
            bend_r = wr is not None and hc > wr + 1e-9
            gl = (CG_BEND if bend_l else CG) if wl is not None else DENC
            gr = (CG_BEND if bend_r else CG) if wr is not None else DENC
            w = gl + CONT + gr
            # diffusion: full contact height in the middle, the gate's own height for BEND next to a gate
            xa, xb = x, x + w
            if bend_l:
                shapes.append((diff, (xa, 0, xa + BEND, wl)))
                xa += BEND
            if bend_r:
                shapes.append((diff, (xb - BEND, 0, xb, wr)))
                xb -= BEND
            shapes.append((diff, (xa, 0, xb, hc)))
            cx0 = x + gl
            cy0, cy1 = DENC, hc - DENC
            shapes.append((dc, (cx0, cy0, cx0 + CONT, cy1)))
            # metal1 stripe over the contact (as the PDK generator draws it); routed wires add the area
            m1 = (cx0, cy0 - 0.055, cx0 + CONT, cy1 + 0.055)
            shapes.append(("metal1", m1))
            terms.append((nets[i], "m1", m1))
        else:
            w = POLY_SP
            shapes.append((diff, (x, 0, x + w, wl)))
        regions.append((nets[i], x, x + w, con))
        x += w
        if i < k:
            f, fl = ch.items[i]
            pad = (pitch(f) - f.L) / 2          # kept slot: plain diffusion either side of the narrowed channel
            if pad > 1e-9:
                shapes.append((diff, (x, 0, x + pad, f.W)))
                shapes.append((diff, (x + pad + f.L, 0, x + pitch(f), f.W)))
            gates.append((f, x + pad, x + pad + f.L))
            shapes.append((mos, (x + pad, 0, x + pad + f.L, f.W)))
            x += pitch(f)
    width = x
    top = max(Ws + [CMIN_H])
    # gate heads: level 0 at top + HEAD_DY; staggered to level 1 where the previous head is too close
    hc0 = top + HEAD_DY
    lvl_prev, xprev = None, None
    for gi, (f, x0, x1) in enumerate(gates):
        cx = (x0 + x1) / 2
        hx = max(pitch(f) / 2, HEAD_POLY)       # kept slot: head (and the stagger decision) as for the footprint
        lvl = 0
        if xprev is not None and lvl_prev == 0:
            pcx, phx = xprev
            if (cx - max(hx, HEAD_PAD)) - (pcx + max(phx, HEAD_PAD)) < max(POLY_SPACE, M1_SPACE) - 1e-9:
                lvl = 1
        hc = hc0 + lvl * HEAD_STEP
        shapes.append(("polysilicon", (x0, -ENDCAP, x1, 0)))                  # rail-side end cap
        shapes.append(("polysilicon", (x0, f.W, x1, hc + HEAD_POLY)))          # stem to the head
        shapes.append(("polysilicon", (cx - hx, hc - HEAD_POLY, cx + hx, hc + HEAD_POLY)))
        shapes.append(("polycontact", (cx - PC, hc - PC, cx + PC, hc + PC)))
        pad = (cx - HEAD_PAD, hc - HEAD_PAD, cx + HEAD_PAD, hc + HEAD_PAD)
        shapes.append(("metal1", pad))
        terms.append((f.g, "m1", pad))
        lvl_prev, xprev = lvl, (cx, hx)
    height = hc0 + HEAD_STEP + HEAD_PAD if any(
        s[0] == "metal1" and s[1][3] > hc0 + HEAD_PAD + 0.01 for s in shapes) else hc0 + HEAD_PAD
    shapes = [(l, tuple(snap(v) for v in r)) for l, r in shapes]
    terms = [(n, l, tuple(snap(v) for v in r)) for n, l, r in terms]
    return dict(shapes=shapes, width=snap(width), height=snap(height), terms=terms, gates=gates,
                regions=regions, top=top)


def build_chains(fingers, degree, wmatch=True, maxlen=None):
    """Greedy shared-diffusion chaining of one device type.

    degree[net] = number of device terminals (S/D and gate) on the net in the whole cell plus external pins;
    a region shared by exactly two S/D terminals of a net with degree 2 needs no contact.
    Joins prefer (1) uncontacted internal nodes, (2) equal widths, (3) any shared net (supplies included).
    """
    left = list(fingers)
    chains = []

    def score(net, f):
        s = 0
        if degree.get(net, 0) == 2:
            s += 4
        return s

    while left:
        # start from the finger with the fewest sharing options so ends get used first
        left.sort(key=lambda f: (f.W, f.name))
        f0 = left.pop(0)
        ch = Chain(f0.typ, [(f0, False)])
        for side in ("R", "L"):
            while True:
                nets = ch.nets()
                end = nets[-1] if side == "R" else nets[0]
                wend = (ch.items[-1] if side == "R" else ch.items[0])[0].W
                best = None
                for f in left:
                    if wmatch and abs(f.W - wend) > 1e-9:
                        continue
                    for fl in (False, True):
                        l, r = (f.d, f.s) if fl else (f.s, f.d)
                        nb = l if side == "R" else r
                        if nb != end:
                            continue
                        sc = score(end, f) + (1 if abs(f.W - wend) < 1e-9 else 0)
                        if best is None or sc > best[0]:
                            best = (sc, f, fl)
                if best is None:
                    break
                _, f, fl = best
                trial = Chain(ch.typ, ch.items + [(f, fl)] if side == "R" else [(f, fl)] + ch.items)
                if maxlen and draw_chain(trial, lambda n, i: degree.get(n, 0) != 2)["width"] > maxlen:
                    break                       # row-width cap: the rest starts a new chain
                left.remove(f)
                ch.items = trial.items
        chains.append(ch)
    return chains


def reverse(ch):
    return Chain(ch.typ, [(f, not fl) for f, fl in reversed(ch.items)])


def chain_width(ch, contacted):
    return draw_chain(ch, contacted)["width"]


def merge_chains(fingers, degree, contacted, wmax_len=12.0, supply=("vdd", "vss")):
    """Chain by merging chain ends: start from single fingers, repeatedly join the best-scoring pair of chains whose
    facing end nets match (either chain may be reversed). Score: uncontacted internal node (degree 2) 8, signal net 3,
    supply net 2, equal widths at the junction 1. Merged chains stay shorter than wmax_len (placement freedom)."""
    return _merge_rest([Chain(f.typ, [(f, False)]) for f in fingers], degree, contacted, wmax_len, supply, set())


def _merge_rest(chains, degree, contacted, wmax_len, supply, banned):
    while True:
        best = None
        for i, a in enumerate(chains):
            for j, b in enumerate(chains):
                if i >= j:
                    continue
                for ra in (False, True):
                    A = reverse(a) if ra else a
                    for rb in (False, True):
                        B = reverse(b) if rb else b
                        net = A.nets()[-1]
                        if net != B.nets()[0] or (id(a), id(b)) in banned:
                            continue
                        sc = (8 if degree.get(net, 0) == 2 else 2 if net in supply else 3)
                        sc += 1 if abs(A.items[-1][0].W - B.items[0][0].W) < 1e-9 else 0
                        if best is None or sc > best[0]:
                            best = (sc, i, j, A, B, a, b)
        if best is None:
            return chains
        sc, i, j, A, B, a, b = best
        m = Chain(A.typ, A.items + B.items)
        if chain_width(m, contacted) > wmax_len:
            banned.add((id(a), id(b)))
            continue
        chains = [c for k, c in enumerate(chains) if k not in (i, j)] + [m]
