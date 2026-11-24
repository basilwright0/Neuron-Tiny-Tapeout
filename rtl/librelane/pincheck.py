"""R2 C1 pin freeze check.
  python3 pincheck.py cfg [pin_order.cfg]       slot map implied by a pin_order.cfg (N/S/W; E has no spacers)
  python3 pincheck.py lef OLD.lef [NEW.lef]     LEF pin rects; with NEW: diff, fails unless only additions
  python3 pincheck.py cfglef pin_order.cfg OLD.lef   every N/S/W cfg slot must equal the OLD LEF pin position
  python3 pincheck.py cfgdiff OLD.cfg NEW.cfg   fails unless NEW only adds pins (old pins keep their slots)
Slot k center = 0.28 + 1.12 k um from the S (W/E edges) or W (N/S edges) corner."""
import re
import sys

P0, PITCH, SIZE = 0.28, 1.12, 166.0


def cfg_slots(path):
    out, edge, k = {}, None, 0
    for line in open(path):
        t = line.strip()
        if not t:
            continue
        if t.startswith("#"):
            edge, k = t[1:], 0
            continue
        if t.startswith("$"):
            k += int(t[1:])
            continue
        out[t.replace("\\", "")] = (edge, k if edge != "E" else None)
        k += 1
    return out


def lef_pins(path):
    pins, name, layer = {}, None, None
    for line in open(path):
        t = line.split()
        if not t:
            continue
        if t[0] == "PIN":
            name = t[1]
        elif t[0] == "END" and len(t) > 1 and t[1] == name:
            name = None
        elif name and t[0] == "LAYER":
            layer = t[1]
        elif name and t[0] == "RECT" and name not in ("VDD", "VSS") and name not in pins:
            pins[name] = (layer, tuple(float(v) for v in t[1:5]))
    return pins


def lef_slot(rect, layer="Metal3"):
    """Edge from the layer (Metal2 pins sit on N/S, Metal3 on W/E; corners are ambiguous by rect)."""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if layer == "Metal2":
        e, c = ("S", cx) if y0 <= 0.01 else ("N", cx)
    else:
        e, c = ("W", cy) if x0 <= 0.01 else ("E", cy)
    return e, round((c - P0) / PITCH, 3)


def main(a):
    bad = 0
    if a[0] == "cfg":
        for p, v in sorted(cfg_slots(a[1] if len(a) > 1 else "pin_order.cfg").items(), key=lambda x: (x[1][0], x[1][1] or 0)):
            print(p, *v)
    elif a[0] == "lef":
        old = lef_pins(a[1])
        if len(a) == 2:
            for p, (l, r) in sorted(old.items()):
                print(p, l, *r, *lef_slot(r, l))
            return 0
        new = lef_pins(a[2])
        for p in sorted(set(old) | set(new)):
            if p not in new:
                print("REMOVED", p, *old[p]); bad += 1
            elif p not in old:
                print("ADDED", p, new[p][0], *new[p][1], *lef_slot(new[p][1], new[p][0]))
            elif old[p] != new[p]:
                print("MOVED", p, old[p], "->", new[p]); bad += 1
        print(f"old {len(old)} new {len(new)} pins; {'FAIL' if bad else 'OK: only additions'}")
    elif a[0] == "cfglef":
        cs, lp = cfg_slots(a[1]), lef_pins(a[2])
        n = 0
        for p, (e, k) in cs.items():
            if p not in lp:
                continue
            le, lk = lef_slot(lp[p][1], lp[p][0])
            n += 1
            if e != le or (k is not None and abs(k - lk) > 1e-6):
                print("MISMATCH", p, "cfg", e, k, "lef", le, lk, lp[p]); bad += 1
        print(f"{n} cfg pins checked against LEF; {'FAIL' if bad else 'OK'}")
    elif a[0] == "cfgdiff":
        old, new = cfg_slots(a[1]), cfg_slots(a[2])
        for p in sorted(set(old) | set(new)):
            if p not in new:
                print("REMOVED", p, old[p]); bad += 1
            elif p not in old:
                print("ADDED", p, *new[p])
            elif old[p] != new[p]:
                print("MOVED", p, old[p], "->", new[p]); bad += 1
        print(f"old {len(old)} new {len(new)}; {'FAIL' if bad else 'OK: only additions'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
