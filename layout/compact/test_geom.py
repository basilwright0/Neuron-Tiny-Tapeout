"""DRC/extraction test cell for geom.py chains (writes out/test_geom_paint.tcl; run_test.sh runs magic).

Rows: a p-tap rail, an nmos row hanging from it (chains with uncontacted series nodes, mixed widths, a dog-bone
0.22 device, a long gate), and a pmos row in an n-well hanging (mirrored) from an n-tap rail above.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from geom import Finger, Chain, draw_chain, snap, DIFF_SP, ENDCAP  # noqa: E402

TAP_GAP = 0.32       # diffusion edge (rail side) to tap strip
TAP_H = 0.60


def F(name, t, W, L, d, g, s):
    return Finger(name, name, t, W, L, d, g, s)


nchains = [
    Chain("n", [(F("A1", "n", 1, 0.28, "x1", "a", "vss"), False), (F("A2", "n", 1, 0.28, "x2", "b", "x1"), False),
                (F("A3", "n", 1, 0.28, "out", "c", "x2"), False)]),
    Chain("n", [(F("B1", "n", 1, 0.5, "o1", "a", "vss"), False), (F("B2", "n", 0.5, 0.28, "o1", "b", "vss"), True),
                (F("B3", "n", 0.22, 2, "o2", "c", "vss"), False)]),
    Chain("n", [(F("C1", "n", 2, 4, "o3", "a", "vss"), False), (F("C2", "n", 2, 4, "o3", "a", "vss"), True)]),
]
pchains = [
    Chain("p", [(F("P1", "p", 1, 0.28, "y1", "a", "vdd"), False), (F("P2", "p", 1, 0.28, "o4", "b", "y1"), False)]),
    Chain("p", [(F("P3", "p", 2, 1, "o5", "c", "vdd"), False), (F("P4", "p", 0.22, 1, "o5", "a", "vdd"), True)]),
]
deg = {"x1": 2, "x2": 2, "y1": 2}
contacted = lambda net, i: deg.get(net, 9) != 2

paint, labels = [], []


def put(sh, x0, y0, mirror):
    for l, r in sh:
        if mirror:
            r = (r[0], -r[3], r[2], -r[1])
        paint.append((l, (snap(r[0] + x0), snap(r[1] + y0), snap(r[2] + x0), snap(r[3] + y0))))


# nmos row: p-tap rail at y 0..0.6, diffusion bottom at 0.6 + TAP_GAP
y_n = TAP_H + TAP_GAP
x = 1.0
W = 0
for ch in nchains:
    g = draw_chain(ch, contacted)
    put(g["shapes"], x, y_n, False)
    x += g["width"] + DIFF_SP
W = x + 1.0
paint.append(("psubdiff", (0, 0, W, TAP_H)))
paint.append(("psubdiffcont", (0.3, 0.185, W - 0.3, 0.415)))
paint.append(("metal1", (0, 0.13, W, 0.47)))
# pmos row mirrored under an n-tap rail at y_t
y_t = 6.5
paint.append(("nsubdiff", (0, y_t, W, y_t + TAP_H)))
paint.append(("nsubdiffcont", (0.3, y_t + 0.185, W - 0.3, y_t + 0.415)))
paint.append(("metal1", (0, y_t + 0.13, W, y_t + 0.47)))
x = 1.0
ymin = y_t
for ch in pchains:
    g = draw_chain(ch, contacted)
    put(g["shapes"], x, y_t - TAP_GAP, True)
    ymin = min(ymin, y_t - TAP_GAP - g["height"])
    x += g["width"] + DIFF_SP
paint.append(("nwell", (-0.5, ymin - 0.1, W + 0.5, y_t + TAP_H + 0.5)))

order = ["nwell", "psubdiff", "nsubdiff", "ndiff", "pdiff", "nmos", "pmos", "polysilicon", "ndiffc", "pdiffc",
         "psubdiffcont", "nsubdiffcont", "polycontact", "metal1"]
tcl = ["tech unlock *", "load test_geom"]
for lay in order:
    for l, r in paint:
        if l == lay:
            tcl.append(f"box values {r[0]:.3f}um {r[1]:.3f}um {r[2]:.3f}um {r[3]:.3f}um; paint {l}")
tcl += ["save test_geom", "select top cell", "drc style drc(full)", "drc on", "drc check", "drc catchup",
        "set n [drc list count total]", 'puts "MAGIC_DRC_COUNT $n"',
        "foreach {why boxes} [drc listall why] { puts \"DRC [llength $boxes] $why\"; foreach b $boxes { puts \"   [lmap v $b {expr {$v / 200.0}}]\" } }",
        "gds write test_geom.gds",
        "extract all", "ext2spice lvs", "ext2spice -o test_geom.spice", "quit -noprompt"]
out = HERE / "out"
out.mkdir(exist_ok=True)
(out / "test_geom.tcl").write_text("\n".join(tcl) + "\n")
print("cells:", W, "x", y_t + TAP_H)
