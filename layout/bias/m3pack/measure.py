"""Area breakdown of vdacr_* leaves from the .mag (rasterised, 0.05 um)."""
import sys, numpy as np, re
from pathlib import Path
D = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir() else Path(__file__).resolve().parents[1]
G = 5  # internal units per raster px (mag units 0.01um ->0.05um)
def parse(path):
    uses, rects, layer = [], {}, None
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        t = lines[i].split()
        if lines[i].startswith("<<"):
            layer = t[1]
        elif t and t[0] == "rect":
            rects.setdefault(layer, []).append(tuple(map(int, t[1:5])))
        elif t and t[0] == "use":
            cell, inst = t[1], t[2]
            tr = box = None
            j = i + 1
            while j < len(lines) and not lines[j].startswith(("use", "<<")):
                u = lines[j].split()
                if u[0] == "transform": tr = list(map(int, u[1:7]))
                if u[0] == "box": box = list(map(int, u[1:5]))
                j += 1
            a, b, c, d, e, f = tr
            xs = [a*x + b*y + c for x in box[0::2] for y in box[1::2]]
            ys = [d*x + e*y + f for x in box[0::2] for y in box[1::2]]
            uses.append((cell, inst, (min(xs), min(ys), max(xs), max(ys))))
            i = j - 1
        i += 1
    return uses, rects
def cls(cell, inst):
    if cell.startswith("r_"): return "R_base" if inst.startswith("XRB") else "R_seg"
    if inst.startswith("SW"): return "switch"
    return "inverter"
for name in sys.argv[1:]:
    uses, rects = parse(D / f"{name}.mag")
    W, H = rects["psubdiff"][-1][2] if False else None, None
    xs = [r[2] for r in rects["psubdiff"]]; ys = [r[3] for r in rects["psubdiff"]]
    W, H = max(xs), max(ys)
    nx, ny = W // G, H // G
    lab = np.zeros((ny, nx), np.int8)  # 0 empty
    order = {"ring": 1, "tap/nwell-band": 2, "routing": 3, "R_base": 4, "R_seg": 5, "switch": 6, "inverter": 7}
    def paint(r, k):
        x1, y1, x2, y2 = [v // G for v in r]
        sub = lab[max(y1,0):y2, max(x1,0):x2]
        sub[sub < k] = k
    for L in ("metal1", "metal2", "via1"):
        for r in rects.get(L, []): paint(r, 3)
    for L in ("nsubdiff", "psubdiff"):
        for r in rects.get(L, []): paint(r, 2)
    # ring = outer 0.6 um
    R = 120 // G
    lab[:R, :] = 1; lab[-R:, :] = 1; lab[:, :R] = 1; lab[:, -R:] = 1
    for cell, inst, bb in uses: paint(bb, order[cls(cell, inst)])
    px = (G / 200) ** 2
    tot = W * H / 4e4
    print(f"{name}: {W/200:.2f} x {H/200:.2f} = {tot:.0f} um2")
    inv = {v: k for k, v in order.items()}; inv[0] = "empty"
    for k in range(8):
        a = (lab == k).sum() * px
        print(f"  {inv[k]:16s} {a:7.1f}  {100*a/tot:5.1f} %")
    # device bbox sums (not overlapped)
    s = {}
    for cell, inst, bb in uses:
        s[cls(cell, inst)] = s.get(cls(cell, inst), 0) + (bb[2]-bb[0])*(bb[3]-bb[1])/4e4
    print("  device bbox sums:", {k: round(v, 1) for k, v in s.items()}, "total", round(sum(s.values()), 1))
