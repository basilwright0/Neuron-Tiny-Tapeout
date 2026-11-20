"""Preview of the top level: blocks, fixed geometry, routes (work/routes.json) -> work/top_preview.png
   python3 plot.py [x0 y0 x1 y1]  (optional zoom window in tile um)"""
import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import config as C, geom as GM
fp = C.fp
win = [float(v) for v in sys.argv[1:5]] if len(sys.argv) >= 5 else [0, 0, fp.TILE_W, fp.TILE_H]
out = sys.argv[5] if len(sys.argv) > 5 else str(C.WORK / "top_preview.png")
W, H = win[2] - win[0], win[3] - win[1]
sc = 14.0 / max(W, H) * (60 if max(W, H) < 80 else 1)
fig, ax = plt.subplots(figsize=(max(6, W / max(W, H) * 28), max(6, H / max(W, H) * 28)))
col = {"metal1": "#4060ff", "metal2": "#d020d0", "metal3": "#20a020", "metal4": "#e08000"}
for n, rs in fp.frames().items():
    for b in rs:
        ax.add_patch(Rectangle(b[:2], b[2] - b[0], b[3] - b[1], fill=True, fc="#eeeeee", ec="k", lw=0.5))
    b = fp.BLOCKS[n]; ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, n.split()[0], ha="center", fontsize=8)
F = GM.fixed()
for lay, r, net in F.shapes:
    if lay in col:
        ax.add_patch(Rectangle(r[:2], r[2] - r[0], r[3] - r[1], fc=col[lay], alpha=0.35 if lay != "metal4" else 0.15, lw=0))
R = json.loads((C.WORK / "routes.json").read_text())
for l, r, n in R["_stubs"]:
    ax.add_patch(Rectangle(r[:2], r[2] - r[0], r[3] - r[1], fc="k", alpha=0.8, lw=0))
for net, rec in R.items():
    if net.startswith("_"):
        continue
    for lay, r in rec["wires"]:
        ax.add_patch(Rectangle(r[:2], r[2] - r[0], r[3] - r[1], fc=col[lay], alpha=0.6, lw=0))
    for kind, x, y in rec["vias"]:
        ax.plot([x], [y], "k.", ms=1.5)
ax.set_xlim(win[0], win[2]); ax.set_ylim(win[1], win[3]); ax.set_aspect("equal")
for n, cnt, (x, y, l) in R.get("_conflicts", []):
    ax.plot([x], [y], "rx", ms=6)
ax.set_title(f"failed: {[f[0] for f in R['_failed']]}  conflicts: {len(R.get('_conflicts', []))}", fontsize=8)
fig.savefig(out, dpi=150, bbox_inches="tight")
print("wrote", out)
