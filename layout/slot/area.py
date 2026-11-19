"""Area accounting for a slot cell (SLOT_CELL=<any slot variant>; run after slotgen.py): footprints from the placed device cells.

Device footprint = diffusion+poly bbox of the PDK cell plus its drawn gate head, i.e. the box no other
device may enter. Everything not in a device, keep-out, MOM, ring or the column band is local routing
and spacing.
"""
import sys
sys.path.insert(0, ".")
import slotgen as S   # noqa: E402

L, insts, obst, mom, lib, devs, ports = S.build()
group = {"XC.": "membrane cap (XC)", "XC2.": "membrane cap 2 (AH800)", "XR.XCR": "Cr 50 fF", "XL.": "leak OTA",
         "XD.": "detector (AH or comparator)", "XR.": "refractory", "XPM.": "probe tap vm", "XPR.": "probe tap vr",
         "XS.": "input synapse + hold/reset", "XT.": "gap trim (4-bit)"}
area = {}
for lc, name, cx, cy in insts:
    b = lc["bbox"]
    top = lc["diff"][3] + 0.45 + 0.19          # gate head pad top
    a = (b[2] - b[0]) * (max(b[3], top) - b[1])
    g = next(v for k, v in group.items() if name.startswith(k))
    area[g] = area.get(g, 0) + a
if mom:
    mb = mom["box"]
    area["Cfb MOM (M1-M3)"] = (mb[2] - mb[0]) * (mb[3] - mb[1])
for k, r in S.KEEPOUT.items():
    area[f"reserved {k}"] = (r[2] - r[0]) * (r[3] - r[1])
ring = S.W * S.H - (S.W - 2 * S.RING) * (S.H - 2 * S.RING)
area["p-tap guard ring (perimeter)"] = ring
nw = S.NWELL
nt = (nw[2] - nw[0] - 0.24) * (nw[3] - nw[1] - 0.24) - (nw[2] - nw[0] - 0.24 - 2 * S.NTAP) * (nw[3] - nw[1] - 0.24 - 2 * S.NTAP)
area["n-tap guard ring (n-well)"] = nt
total = S.W * S.H
used = sum(area.values())
print(f"{S.CELL}: cell {S.W} x {S.H} um = {total:.0f} um^2 (target box 28.0 x 43.5 = 1218 um^2)")
for k, v in area.items():
    print(f"  {k:34s} {v:7.1f} um^2  {100 * v / total:5.1f} %")
print(f"  {'routing, column band, spacing':34s} {total - used:7.1f} um^2  {100 * (total - used) / total:5.1f} %")
