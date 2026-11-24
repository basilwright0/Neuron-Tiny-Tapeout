"""Check the bias_b1 GDS against the integrator's frame: notches empty (all layers), corridor free of Metal3,
pin positions.  M3 (b1int, B1_M3=1, default): also the bottom pocket NB west of N1, and every pin label
compared with the b1d reference positions (b1_pins_242.json)."""
import json
import os
import klayout.db as kdb
ly = kdb.Layout(); ly.read("out/bias_b1.gds"); top = ly.cell("bias_b1")
d = ly.dbu
WT = float(os.environ.get("B1_WT", "23.0"))   # west trim (topgen.py WT); 0 = rev C frame
M3 = os.environ.get("B1_M3", "1") == "1" and WT == 23.0
N1 = (182.0 - WT, 0.0, 222.0 - WT, 42.0); CORR = (196.0 - WT, 42.0, 222.0 - WT, 115.0)
N2 = (0.0, 104.0, 23.0 - WT, 115.0)
NB = (131.0, 0.0, N1[0], 40.0)
notches = [("N1", N1)] + ([("N2", N2)] if N2[2] > 0 else []) + ([("NB", NB)] if M3 else [])
box = lambda r: kdb.Region(kdb.Box(*[round(v / d) for v in r]))
bb = top.bbox()
print("bbox", bb.left * d, bb.bottom * d, bb.right * d, bb.top * d)
bad = 0
for li in ly.layer_indexes():
    info = ly.get_info(li)
    reg = kdb.Region(top.begin_shapes_rec(li))
    if reg.is_empty():
        continue
    for nm, r in notches:
        hit = reg & box(r)
        if not hit.is_empty():
            bad += 1
            print("NOTCH", nm, "layer", info, "area", round(hit.area() * d * d, 3), hit.bbox())
    if (info.layer, info.datatype) == (42, 0):   # Metal3
        hit = reg & box(CORR)
        bad += 0 if hit.is_empty() else 1
        print("Metal3 in corridor:", "none" if hit.is_empty() else hit.bbox())
labels = {}
for li in ly.layer_indexes():
    for sh in top.shapes(li).each():
        if sh.is_text():
            labels.setdefault(sh.text_string, (ly.get_info(li), round(sh.text_dpos.x, 3), round(sh.text_dpos.y, 3)))
for n in ("ua0", "vth_ref", "vreset_src", "ib_r1", "el", "vdd", "vss", "vbn_leak", "vth_cmp"):
    if n in labels:
        print("label", n, *labels[n])
if M3:
    ref = json.loads(open("b1_pins_242.json").read())
    miss = []
    for n, r in ref.items():
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        if n not in labels or abs(labels[n][1] - cx) > 0.006 or abs(labels[n][2] - cy) > 0.006:
            miss.append((n, labels.get(n), (cx, cy)))
    print(f"pins vs b1d reference: {len(ref) - len(miss)}/{len(ref)} at the same position", miss or "")
    bad += len(miss)
print("FRAME_CHECK", "PASS" if bad == 0 else f"FAIL ({bad})")
