"""Largest free rectangles in the tile for an M1-M3 block (host Python + numpy). MIL-133 M3 measurement tool.

Free = not inside a block frame or std cell and at least 0.3 um from any top-level Metal1-3 / via1-3 shape of the
assembled top cell (area_dump.py JSON). Metal4 (stripes, jumpers) may cross a free area, as over B1 / D1 today.
Usage: python layout/top/area_free.py <area_dump.json> <b1 frame: m2 | m3> [n rectangles]
Greedy: the largest empty axis-aligned rectangle, then the largest one not overlapping it, and so on.
"""
import sys, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "floorplan"))
import floorplan as fp

RES, DIL = 0.2, 0.3
D = json.loads(Path(sys.argv[1]).read_text())
B1 = sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 8
NX, NY = int(round(fp.TILE_W / RES)), int(round(fp.TILE_H / RES))
occ = np.zeros((NY, NX), bool)


def paint(b, d=0.0):
    x0, y0 = max(0, int(np.floor((b[0] - d) / RES))), max(0, int(np.floor((b[1] - d) / RES)))
    x1, y1 = min(NX, int(np.ceil((b[2] + d) / RES))), min(NY, int(np.ceil((b[3] + d) / RES)))
    occ[y0:y1, x0:x1] = True


if B1 == "m2":     # rev C at (80, 12): 264.5 x 114.5 minus N1 (R1) and N2 (tau col 2)
    b1 = [(80, 12, 262, 116), (103, 116, 262, 126.5), (262, 54, 302, 126.5), (302, 12, 344.5, 126.5)]
else:
    b1 = fp.b1_rects()
for r in b1:
    paint(r)
for cell, *bb in D["inst"]:
    if cell.endswith("bias_b1") or cell == "bias_b1":
        continue
    if "r1_ua1" in cell:
        paint((262, 14, 302, 54)); paint(fp.STRAP_UA1)
        continue
    paint(bb)
for lay in ("metal1", "metal2", "metal3", "via1", "via2", "via3"):
    for b in D["own"].get(lay, []):
        paint(b, DIL)
occ[:, :1] = occ[:, -1:] = True; occ[:1, :] = occ[-1:, :] = True


def max_rect(free):
    """largest all-True rectangle: (area cells, x0, y0, x1, y1) in cells (histogram method, row by row)"""
    h = np.zeros(NX, int)
    best = (0, 0, 0, 0, 0)
    for j in range(NY):
        h = np.where(free[j], h + 1, 0)
        st = []
        for i in range(NX + 1):
            cur = h[i] if i < NX else 0
            s = i
            while st and st[-1][1] >= cur:
                s, hh = st.pop()
                a = hh * (i - s)
                if a > best[0]:
                    best = (a, s, j - hh + 1, i, j + 1)
            st.append((s, cur))
    return best


free = ~occ
print(f"free (M1-M3 block, 0.3 um off top-level metal): {free.sum() * RES * RES:,.0f} um^2 of {fp.TILE_W * fp.TILE_H:,.0f}")
for k in range(N):
    a, x0, y0, x1, y1 = max_rect(free)
    if a == 0:
        break
    print(f"  #{k + 1}: x {x0 * RES:6.1f}-{x1 * RES:6.1f}  y {y0 * RES:6.1f}-{y1 * RES:6.1f}  "
          f"{(x1 - x0) * RES:5.1f} x {(y1 - y0) * RES:5.1f} = {a * RES * RES:7,.0f} um^2")
    free[y0:y1, x0:x1] = False
