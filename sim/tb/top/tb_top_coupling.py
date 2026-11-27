"""Check 3 (static part): coupling capacitance from every top-level digital line to the sensitive analog nodes,
from the full-chip R+C extraction (layout/top/work/pexr/top_rc_flat.spice), and the charge-sharing kick
dV = 3.3 V * Cc / C_node (C_node = membrane cap + all extracted C of the node).

  python3 sim/tb/top/tb_top_coupling.py           # needs layout/top/work/pexr/top_rc_flat.spice (ext_rc.tcl)
  python3 sim/tb/top/tb_top_coupling.py --list    # only print the victim list (name, slot, cell, C_mem); no PEX
Victims: vm of every array neuron, D1 vs / d1 / d2, AdEx vm / vw; shared analog lines (bias / reference lines).
Aggressors: every net driven by the macro or the glue row (rt_out, spk_in, probe lines, trims, B1 codes, en_b,
D1 selects, ...) and the TT digital pins. Writes sim/results/top/coupling.txt.
"""
import re
import sys
from collections import defaultdict

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topnet as T            # noqa: E402
import config as C            # noqa: E402  (layout/top, on sys.path via topnet)

fp = C.fp
# ---- victims: vm of every array neuron (floorplan MAP; instance s<row><col>, CMP s13), D1, AdEx.
# C_mem = the cell's membrane MOS caps (topnet.membrane_cap: 200 fF, AH50 50 fF, AH400 ~470 fF).
VICT = {}                        # name -> (net, C_mem, inst, cell, pin)
for name, inst, cell in T.neurons() + T.bay():          # R2: + the bay column (by0..by2), listed after the array
    VICT[f"{name} vm ({inst})"] = (f"{inst}.vm", T.membrane_cap(cell), inst, cell, "vm")
for nm, n, cm in (("D1 vs", "d1.vs", 200e-15), ("D1 d1", "d1.d1", 100e-15), ("D1 d2", "d1.d2", 100e-15),
                  ("AdEx vm", "ax.vm", 200e-15), ("AdEx vw", "ax.vw", 200e-15)):
    inst, pin = n.split(".")
    VICT[nm] = (n, cm, inst, C.instances()[inst][0], pin)
if "--list" in sys.argv:
    for nm, (n, cm, inst, cell, pin) in VICT.items():
        print(f"{nm:22s} {n:8s} {cell:14s} C_mem {cm * 1e15:6.1f} fF")
    sys.exit(0)
d = T.load()
# ---- group R-network nodes into nets (union-find over R elements)
par = {}


def f(x):
    while par.get(x, x) != x:
        par[x] = par.get(par[x], par[x])
        x = par[x]
    return x


for l in d["lines"]:
    if l[0] == "R":
        t = l.split()
        a, b = f(t[1]), f(t[2])
        if a != b:
            par[a] = b
caps = defaultdict(float)
for l in d["lines"]:
    if l[0] == "C":
        t = l.split()
        v = T._unit(t[3])
        if v <= 0:
            continue
        a, b = f(t[1]), f(t[2])
        if T.is_macro_node(t[1]):
            a = "MACRO"
        if T.is_macro_node(t[2]):
            b = "MACRO"
        if a == b:
            continue
        caps[(a, b)] += v
        caps[(b, a)] += v
tot = defaultdict(float)
for (a, b), v in caps.items():
    tot[a] += v


def grp(name):
    return f(T.net(name))


# ---- aggressors: macro outputs + glue outputs + TT digital pins
agg = {}
for p, n in T.macro_outputs().items():
    if not T.is_macro_node(n):
        agg[f(n)] = p
for p in ("en_b", "d1_sel0", "d1_sel1", "d1_sel2", "g_any", "g_nsel", "g_ns0", "g_ns1", "g_bay"):
    try:
        agg[grp(p)] = p
    except KeyError:
        pass
for k in range(getattr(fp, "N_SPK", 16)):                 # R2: 24 channels, the unused ones are tied to VGND
    if k not in getattr(fp, "SPK_TIED", ()):
        agg[grp(f"spk_in[{k}]")] = f"spk_in[{k}]"
for p in [f"ui_in[{i}]" for i in range(8)] + [f"uo_out[{i}]" for i in range(8)] + \
        [f"uio_out[{i}]" for i in range(8)] + ["clk", "rst_n"]:
    agg[f(p)] = p
agg["MACRO"] = "macro-internal (all)"
victims = {nm: (grp(n), cm, inst, cell, pin) for nm, (n, cm, inst, cell, pin) in VICT.items()}

# block-level PEX coupling between a block's own pins (what the block checks already saw)
_bp = {}


def block_pin_caps(cell):
    if cell in _bp:
        return _bp[cell]
    path = (T.ROOT / C.LIB[cell]["gds"]).with_name(f"{cell}_pex.spice")   # layout/slot/out, layout/compact/final, ...
    txt = re.sub(r"\n\+", " ", path.read_text())
    top = txt[txt.index(f".subckt {cell} "):]
    top = top[:top.index(".ends")]
    cc = defaultdict(float)
    for l in top.splitlines():
        if l.startswith("C"):
            t = l.split()
            v = T._unit(t[3])
            cc[(t[1], t[2])] += v
            cc[(t[2], t[1])] += v
    _bp[cell] = cc
    return cc


pin_of = defaultdict(dict)       # inst -> {top net group: pin}
for n, al in T.hier_aliases().items():
    for ip in al:
        inst, pin = ip.split(".", 1)
        try:
            g = grp(n)             # extracted names (g_i0/I, s33/en) aren't flat-netlist nodes; resolve like the victims
        except KeyError:
            g = f(n)
        pin_of[inst][g] = pin
lines = ["Coupling from digital lines to analog nodes (full-chip R+C PEX, coupling C summed over R-network nodes).",
         "kick = 3.3 V x Cc / (C_mem + C_extracted). C_mem: from the slot cell's MOS caps (" +
         ", ".join(sorted({f"{c} {T.membrane_cap(c) * 1e15:.0f} fF" for _, _, c in T.neurons()})) +
         "; D1 dendrites / AdEx w ~ nominal). 'chip' = full-chip Cc, 'blk' = the same pin pair in the block-level PEX (already in the",
         "block checks), 'top' = chip - blk = what the top-level wiring adds. A neuron's own spike line (Cfb, by",
         "design) is excluded.", "",
         "victim                 C_extr(fF)  top-3 aggressors by top-level-added Cc: chip / blk / top (aF) -> top kick (mV)"]
worst = []
for nm, (g, cm, inst, cell, vpin) in victims.items():
    ct = cm + tot[g]
    bpc = block_pin_caps(cell)
    rows = []
    for a, an in agg.items():
        v = caps.get((g, a), 0.0)
        if v <= 0:
            continue
        pin = pin_of[inst].get(a)
        if pin == "spk" and an.startswith("spk_in"):
            continue                                  # own Cfb
        vb = bpc.get((vpin, pin), 0.0) if pin else 0.0
        rows.append((v - vb, v, vb, an))
    rows.sort(reverse=True)
    s = "; ".join(f"{an}: {v * 1e18:.0f}/{vb * 1e18:.0f}/{d * 1e18:.0f} -> {3.3 * d / ct * 1e3:.2f} mV"
                  for d, v, vb, an in rows[:3])
    lines.append(f"{nm:22s} {tot[g] * 1e15:8.2f}    {s}")
    if rows:
        worst.append((3.3 * rows[0][0] / ct * 1e3, nm, rows[0][3]))
    tot_top = sum(d for d, v, vb, an in rows if an != "macro-internal (all)" and d > 0)
    tot_dig = sum(v for d, v, vb, an in rows if an != "macro-internal (all)")
    lines.append(f"{'':20s} {'':8s}    all digital lines: chip {tot_dig * 1e18:.0f} aF, top-added {tot_top * 1e18:.0f} aF "
                 f"-> {3.3 * tot_top / ct * 1e3:.2f} mV if all toggled together")
worst.sort(reverse=True)
lines += ["", "worst single-line top-level-added kicks: " + "; ".join(f"{w[1]} <- {w[2]} {w[0]:.2f} mV" for w in worst[:6])]
# ---- shared analog lines: total C and the digital C on them
lines += ["", "shared analog line   C_total(fF)  digital-coupled C (aF), top-4"]
for ln in ("vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_prb", "el", "vreset", "vsrc", "vth_ref", "vreset_src",
           "aux0", "aux2", "aux3", "vbn_ax", "vbp_w", "abus", "ib_r1"):
    g = grp(ln)
    al = sorted(((caps[(g, a)], an) for a, an in agg.items() if caps.get((g, a), 0) > 0), reverse=True)
    dsum = sum(v for v, an in al if an != "macro-internal (all)")
    lines.append(f"{ln:20s} {tot[g] * 1e15:9.1f}   sum {dsum * 1e18:6.0f}: " +
                 "; ".join(f"{an} {v * 1e18:.0f}" for v, an in al[:4]))
txt = "\n".join(lines)
print(txt)
(T.ROOT / "sim/results/top/coupling.txt").write_text(txt + "\n")
