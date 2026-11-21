"""Check 4: static IR drop of VDPWR / VGND on the final GDS (KLayout net trace + raster resistive mesh).

  python3 sim/tb/top/pgrid.py [icur json] [case] [h_um]

Why not magic extresist alone: its VDPWR / VGND networks are electrically right but have no node at the Metal4
stripe ends (where the TT PDN feeds the tile), so the PDN cannot be attached there. Here:
  - the power nets are traced on Metal1..Metal4 + via1..via3 (KLayout LayoutToNetlist, flattened GDS) from a
    point on each stripe;
  - each layer of the net is rasterised on an h x h grid (default 0.2 um); neighbour cells are joined by R_sheet
    (0.09 ohm/sq, Metal1-4, magic gf180mcuD tech), every via cut by 4.5 ohm (tech `contact m2c/m3c`);
  - every analog / glue device's DC supply current (sim/tb/top/tb_top_icur.py: full-chip PEX op, one ammeter
    per power terminal) is injected at that terminal's position (magic .res.ext rnode) into the nearest net cell;
  - PDN models: 'ends'  = ideal supply at both ends of every Metal4 stripe (TT PDN hookup at the tile edge);
                'top'   = top ends only (worst case);
                'dense' = the whole stripe ideal (dense Metal5 PDN strapping every stripe).
Prints, per block, the mean / worst rail drop at its contacts; writes sim/results/top/pgrid_<case>.txt.
"""
import json
import sys
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
import klayout.db as db

sys.path.insert(0, "/work/sim/tb/top")
sys.path.insert(0, "/work/layout/top")
import topnet as T            # noqa: E402
import config as C            # noqa: E402

fp = C.fp
GDS = "/work/gds/tt_um_basilwright0_analog_neurons.gds"
RS = 0.09
RVIA = 4.5
LAY = {"m1": (34, 0), "v1": (35, 0), "m2": (36, 0), "v2": (38, 0), "m3": (42, 0), "v3": (40, 0), "m4": (46, 0),
       "co": (33, 0)}
METALS = ["m1", "m2", "m3", "m4"]
VIAS = {"v1": ("m1", "m2"), "v2": ("m2", "m3"), "v3": ("m3", "m4")}

ICUR = sys.argv[1] if len(sys.argv) > 1 else "/work/sim/results/top/icur_typical_27.json"
CASE = sys.argv[2] if len(sys.argv) > 2 else "S1000_probe_on_ibx2"
H = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
WHATIF = sys.argv[4] if len(sys.argv) > 4 else ""   # 'b1vias': via3 drops from the stripes crossing B1 ('b1vias_w': only the x 121 / 123.6 pair)


def trace():
    ly = db.Layout()
    ly.read(GDS)
    top = ly.top_cell()
    top.flatten(-1, True)
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, []))
    L = {k: l2n.make_layer(ly.layer(*v), k) for k, v in LAY.items()}
    for m in METALS:
        l2n.connect(L[m])
    for v, (a, b) in VIAS.items():
        l2n.connect(L[v])
        l2n.connect(L[a], L[v])
        l2n.connect(L[v], L[b])
    l2n.extract_netlist()
    return ly, l2n, L


def net_regions(l2n, L, net):
    """Union of the nets probed at mid-height of every stripe of `net`."""
    regs = {k: db.Region() for k in LAY}
    seen = set()
    for n, x, w in fp.STRIPES:
        if n != net:
            continue
        nn = l2n.probe_net(L["m4"], db.DPoint(x + w / 2, 160.0))
        if nn is None or nn.cluster_id in seen:
            continue
        seen.add(nn.cluster_id)
        for k in METALS + list(VIAS):
            regs[k] += l2n.shapes_of_net(nn, L[k], True)
    for k in METALS:
        regs[k].merge()
    return regs, len(seen)


def raster(reg, dbu, nx, ny):
    a = np.zeros((nx, ny), dtype=bool)
    for poly in reg.each():
        for tr in poly.decompose_trapezoids():
            b = tr.bbox()
            x0, y0, x1, y1 = b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu
            i0, i1 = int(np.ceil(x0 / H - 0.5)), int(np.floor(x1 / H - 0.5))
            j0, j1 = int(np.ceil(y0 / H - 0.5)), int(np.floor(y1 / H - 0.5))
            if i1 < i0:                          # narrower than a cell: take the nearest column / row
                i0 = i1 = int(round((x0 + x1) / 2 / H - 0.5))
            if j1 < j0:
                j0 = j1 = int(round((y0 + y1) / 2 / H - 0.5))
            a[max(i0, 0):i1 + 1, max(j0, 0):j1 + 1] = True
    return a


def centers(reg, dbu):
    return [((p.bbox().left + p.bbox().right) / 2 * dbu, (p.bbox().bottom + p.bbox().top) / 2 * dbu)
            for p in reg.each()]


def solve(net, ly, l2n, L, currents, pdn):
    dbu = ly.dbu
    regs, nisl = net_regions(l2n, L, net)
    nx, ny = int(fp.TILE_W / H) + 2, int(fp.TILE_H / H) + 2
    R = {m: raster(regs[m], dbu, nx, ny) for m in METALS}
    idx = {}
    off = 0
    for m in METALS:
        k = np.full((nx, ny), -1, dtype=np.int64)
        n = int(R[m].sum())
        k[R[m]] = np.arange(off, off + n)
        idx[m] = k
        off += n
    N = off
    A, Bn, Gv = [], [], []
    for m in METALS:
        k = idx[m]
        for di, dj in ((1, 0), (0, 1)):
            a = k[:nx - di, :ny - dj]
            b = k[di:, dj:]
            ok = (a >= 0) & (b >= 0)
            A.append(a[ok]); Bn.append(b[ok]); Gv.append(np.full(int(ok.sum()), 1.0 / RS))
    va, vb, extra_g = [], [], []
    for v, (lo, hi) in VIAS.items():
        for (x, y) in centers(regs[v], dbu):
            i, j = int(x / H), int(y / H)
            a, b = _near(idx[lo], i, j), _near(idx[hi], i, j)
            if a >= 0 and b >= 0:
                va.append(a); vb.append(b)
    nvia = len(va)
    if WHATIF.startswith("b1vias"):   # what-if: via3 drops from every stripe of the net onto the net's Metal3 under it in B1
        for n_, x_, w_ in fp.STRIPES:
            if n_ != net:
                continue
            k3 = idx["m3"][int(x_ / H):int((x_ + w_) / H) + 1, int(12.0 / H):int(126.5 / H)]
            k4 = idx["m4"][int(x_ / H):int((x_ + w_) / H) + 1, int(12.0 / H):int(126.5 / H)]
            ok = (k3 >= 0) & (k4 >= 0)
            if x_ < 80 or not ok.any() or (WHATIF == "b1vias_w" and x_ > 130):
                continue
            va += list(k3[ok]); vb += list(k4[ok])
            extra_g.extend([(H * H / 0.36) / RVIA] * int(ok.sum()))
    A.append(np.array(va, dtype=np.int64)); Bn.append(np.array(vb, dtype=np.int64))
    Gv.append(np.concatenate([np.full(nvia, 1.0 / RVIA), np.array(extra_g)]))
    a, b, gg = np.concatenate(A), np.concatenate(Bn), np.concatenate(Gv)
    G = sp.csr_matrix((np.concatenate([gg, gg, -gg, -gg]), (np.concatenate([a, b, a, b]), np.concatenate([a, b, b, a]))),
                      shape=(N, N))
    # ---- injections: every device power terminal (position from magic's .res.ext, current from the
    #      full-chip op of tb_top_icur.py) into the nearest net cell (Metal1 first)
    I = np.zeros(N)
    rn = T.rnodes(net)
    own = currents["owner"]
    where = {}
    miss = 0.0
    for term, cur in currents["terms"].items():
        if not term.startswith(net) or term not in rn:
            continue
        x, y = rn[term]
        i, j = int(x / H), int(y / H)
        n = -1
        for m in METALS:
            n = _near(idx[m], i, j, r=8)
            if n >= 0:
                break
        if n < 0:
            miss += abs(cur)
            continue
        I[n] += cur
        where.setdefault(own.get(term, "other"), []).append(n)
    for box, cur in currents.get("box_inject", []):   # e.g. the macro: spread over its net Metal1 cells
        k1 = idx["m1"][int(box[0] / H):int(box[2] / H), int(box[1] / H):int(box[3] / H)]
        k1 = k1[k1 >= 0]
        I[k1] += cur / len(k1)
    # observation points: every block's net Metal1 cells too (for blocks without terminal currents)
    for blk, b in T.block_boxes().items():
        if blk not in where:
            k1 = idx["m1"][int(b[0] / H):int(b[2] / H), int(b[1] / H):int(b[3] / H)]
            k1 = k1[k1 >= 0]
            if len(k1):
                where[blk] = list(k1[:: max(1, len(k1) // 200)])
    where = {k: np.array(v) for k, v in where.items()}
    # ---- PDN (Dirichlet: drop 0)
    fix = np.zeros(N, dtype=bool)
    k4 = idx["m4"]
    for n, x, w in fp.STRIPES:
        if n != net:
            continue
        i0, i1 = int(x / H), int((x + w) / H)
        j0, j1 = int(fp.STRIPE_Y[0] / H), int(fp.STRIPE_Y[1] / H)
        for (ja, jb) in ({"ends": [(j0, j0 + 2), (j1 - 2, j1 + 1)], "top": [(j1 - 2, j1 + 1)],
                          "dense": [(j0, j1 + 1)]}[pdn]):
            sub = k4[i0:i1 + 1, ja:jb]
            fix[sub[sub >= 0]] = True
    # raster islands without a PDN node (cut thin features) carry no current here: leave them out
    from scipy.sparse.csgraph import connected_components
    ncomp, lab = connected_components(G, directed=False)
    good = np.isin(lab, np.unique(lab[fix]))
    lost = float(np.abs(I[~good]).sum())
    I[~good] = 0.0
    free = ~fix & good
    # drop u (V): G u = I on free nodes, u = 0 on fixed ones (drop below VDD for VDPWR, rise above 0 for VGND)
    Gf = G[free][:, free].tocsc()
    t0 = time.time()
    uf = spl.spsolve(Gf, I[free])
    u = np.zeros(N)
    u[free] = uf
    floating = lost
    u[~good] = np.nan
    # voltage at every placed terminal (for the bias-mirror source offsets)
    tv = {}
    for term in currents.get("all_terms", []):
        if term.startswith(net) and term in rn:
            x, y = rn[term]
            for m in METALS:
                n = _near(idx[m], int(x / H), int(y / H), r=8)
                if n >= 0:
                    tv[term] = u[n]
                    break
    return dict(N=N, nvia=nvia, nisl=nisl, t=time.time() - t0, miss=miss, tv=tv, where={b: u[n] for b, n in where.items()},
                floating=floating, umax=0.0)


def _near(k, i, j, r=2):
    nx, ny = k.shape
    for d in range(r + 1):
        sub = k[max(i - d, 0):min(i + d + 1, nx), max(j - d, 0):min(j + d + 1, ny)]
        v = sub[sub >= 0]
        if len(v):
            return int(v[0])
    return -1


if __name__ == "__main__":
    if CASE == "macro":                               # 1 mA out of VDD / into VSS spread over the macro
        cur = {"terms": {}, "blocks": {}, "box_inject": [((C.fp.MACRO_X, C.fp.MACRO_Y, C.fp.MACRO_X + 166,
                                                            C.fp.MACRO_Y + 166), 1e-3)]}
    else:
        cur = json.loads(open(ICUR).read())[CASE]
    # owner of each terminal (block of its device)
    own = {}
    for l in T.load()["lines"]:
        if l[0] in "XD":
            t = l.split()
            nn = [q for q in t[1:] if "=" not in q][:-1]
            o = None
            for q in nn:
                if q in cur["terms"]:
                    o = o or T.owner(nn) or "other"
                    own[q] = o
    cur["owner"] = own
    # bias mirrors: receiver diodes in B1 (gate = drain = line) and the mirror devices (gate = line) of the far
    # blocks; their source terminal on VGND (n lines) / VDPWR (p lines)
    BL = ["vbn_leak", "vbn_ref", "vbn_ax", "vbn_prb", "vbp_syn", "vbp_st", "vbp_w"]
    mir = {}
    allt = set()
    for l in T.load()["lines"]:
        if l[0] != "X":
            continue
        t = l.split()
        nn = [q for q in t[1:] if "=" not in q]
        if len(nn) < 5 or not nn[-1].endswith("_03v3") or "fet" not in nn[-1]:
            continue
        d, g, sr = nn[0], nn[1], nn[2]
        for ln in BL:
            if T.net(ln) != g and not g.startswith(T.net(ln) + "."):
                continue
            for a, b in ((d, sr), (sr, d)):
                if b.startswith(("VGND", "VDPWR")):
                    o = T.owner(nn[:-1]) or "other"
                    kind = "rx" if (a == g and o == "b1") else o
                    mir.setdefault((ln, kind), []).append(b)
                    allt.add(b)
    cur["all_terms"] = sorted(allt)
    t0 = time.time()
    ly, l2n, L = trace()
    out = [f"IR drop, case {CASE} ({ICUR.split('/')[-1]}), grid {H} um, Rsheet {RS} ohm/sq, via {RVIA} ohm",
           f"(device terminal currents at their extracted positions; drop = mV below VDD at the block's VDD "
           f"device terminals, rise above 0 V at its VSS terminals; mean / max over the block's terminals)"]
    print(f"traced in {time.time() - t0:.0f} s", flush=True)
    res = {}
    for pdn in ("ends", "top", "dense"):
        for net in ("VDPWR", "VGND"):
            r = solve(net, ly, l2n, L, cur, pdn)
            res[(pdn, net)] = r
            print(f"{pdn} {net}: {r['N']} nodes, {r['nvia']} vias, {r['nisl']} stripe nets, solve {r['t']:.0f} s, "
                  f"max {np.nanmax(list(np.nanmax(v) for v in r['where'].values())) * 1e3:.2f} mV, current on islands {r['floating'] * 1e6:.3f} uA", flush=True)
    blks = sorted(set(b for r in res.values() for b in r["where"]))
    out.append("")
    hdr = "block    I_vdd(uA) I_vss(uA) | " + " | ".join(f"{p:5s} VDD mean/max   VSS mean/max" for p in ("ends", "top", "dense"))
    out.append(hdr)
    for b in blks:
        bc = cur["blocks"].get(b, [0, 0])
        s = f"{b:8s} {bc[0] * 1e6:9.2f} {bc[1] * 1e6:9.2f} | "
        for pdn in ("ends", "top", "dense"):
            vd = res[(pdn, "VDPWR")]["where"].get(b, np.array([np.nan]))
            vs = res[(pdn, "VGND")]["where"].get(b, np.array([np.nan]))
            s += (f"      {np.nanmean(vd) * 1e3:6.3f}/{np.nanmax(vd) * 1e3:6.3f}  "
                  f"{np.nanmean(vs) * 1e3:6.3f}/{np.nanmax(vs) * 1e3:6.3f} | ")
        out.append(s)
    out += ["", "bias mirrors: source-rail offset of the far mirror devices vs B1's receiver diode, mV (far - receiver;",
            "n lines: VGND rise, p lines: VDPWR drop). An n-line mirror current scales by exp(-dV / nUT) with nUT ~ 35 mV",
            "(-1 mV ~ +2.9 %); for p lines a larger VDD drop at the far device lowers its current the same way."]
    for pdn in ("ends", "top"):
        out.append(f"PDN '{pdn}':")
        for ln in BL:
            net = "VDPWR" if ln.startswith("vbp") else "VGND"
            tv = res[(pdn, net)]["tv"]
            rx = [tv[q] for q in mir.get((ln, "rx"), []) if q in tv]
            if not rx:
                out.append(f"  {ln:9s} (no receiver terminal found)")
                continue
            row = f"  {ln:9s} receiver {np.mean(rx) * 1e3:7.3f} mV | "
            for b in ("s30", "s33", "s01", "ax", "d1", "tau0", "tau2"):
                v = [tv[q] for q in mir.get((ln, b), []) if q in tv]
                if v:
                    row += f"{b} {(np.mean(v) - np.mean(rx)) * 1e3:+7.2f}  "
            out.append(row)
    txt = "\n".join(out)
    print(txt)
    (T.ROOT / f"sim/results/top/pgrid_{CASE}_{ICUR.split('/')[-1].replace('icur_', '').replace('.json', '')}{'_' + WHATIF if WHATIF else ''}.txt").write_text(txt + "\n")
