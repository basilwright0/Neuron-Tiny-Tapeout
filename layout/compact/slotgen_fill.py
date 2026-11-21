"""Same-net notch fill (copied from layout/slot/slotgen.py) and metal minimum-area repair for the compact generator."""
from router import SPACE


def snap(v, g=0.005):
    return round(round(v / g) * g, 4)


def fill_notches(obst, wires):
    """Same-net metal closer than min spacing (slots/notches between a wire end and a pad or
    stripe) is a DRC error. Per net and layer, take the union of all its metal and apply a
    morphological closing (grow by s/2, shrink by s/2, square corners): that fills exactly the
    sub-spacing gaps. The added area is returned as filler rectangles."""
    import klayout.db as kdb
    from router import SPACE
    dbu = 0.005
    per = {}
    for lay, r, net in list(obst) + list(wires):
        if lay in ("m1", "m2", "m3") and net is not None:
            per.setdefault((lay, net), []).append(r)
    out = []
    for (lay, net), rs in per.items():
        reg = kdb.Region()
        for r in rs:
            reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
        reg.merge()
        d = int(round(SPACE[lay] / dbu))          # also bridges diagonal (corner-to-corner) same-net gaps
        minw = int(round({"m1": 0.23, "m2": 0.28, "m3": 0.28}[lay] / dbu))
        closed = reg.dup()
        for _ in range(3):
            # close sub-spacing gaps, then widen min-width necks the fill may leave
            closed = closed.sized(d, d, 2).sized(-d, -d, 2)
            # same-net corner-to-corner gaps the closing leaves (2026-11-19): bridge each remaining same-net
            # spacing violation with a box over the gap, at least min-width in both directions
            for ep in closed.space_check(d).each():
                bb = ep.bbox()
                cx, cy = bb.center().x, bb.center().y
                w2 = max(bb.width(), minw) // 2 + 1
                h2 = max(bb.height(), minw) // 2 + 1
                closed.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
            closed.merge()
            eps = list(closed.width_check(minw).each())
            for ep in eps:
                bb = ep.bbox()
                cx, cy = bb.center().x, bb.center().y
                w2 = max(bb.width(), minw) // 2 + 1
                h2 = max(bb.height(), minw) // 2 + 1
                closed.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
            closed.merge()
            if not eps:
                break
        add = (closed - reg)
        # never let a filler come closer than min spacing to another net's metal on this layer
        others = kdb.Region()
        for (l2, n2), rs2 in per.items():
            if l2 == lay and n2 != net:
                for r in rs2:
                    others.insert(kdb.Box(*(round(v / dbu) for v in r)))
        sp = int(round(SPACE[lay] / dbu))
        add = add - others.sized(sp, sp, 2)
        # clipping can leave a min-width neck in net + fill: widen it where that stays clear of other nets
        fin = (reg + add).merged()
        for ep in fin.width_check(minw).each():
            bb = ep.bbox()
            cx, cy = bb.center().x, bb.center().y
            w2 = max(bb.width(), minw) // 2 + 1
            h2 = max(bb.height(), minw) // 2 + 1
            add.insert(kdb.Box(cx - w2, cy - h2, cx + w2, cy + h2))
        add = (add - others.sized(sp, sp, 2)).merged()
        for bx in add.each_merged():
            for t in kdb.Region(bx).decompose_trapezoids(1):
                pts = [p for p in t.each_point_hull()]
                xs = [p.x * dbu for p in pts]
                ys = [p.y * dbu for p in pts]
                out.append((lay, (snap(min(xs)), snap(min(ys)), snap(max(xs)), snap(max(ys))), net))
    return out


MIN_AREA = {"m1": 0.1444, "m2": 0.1444, "m3": 0.1444}


def fix_min_area(shapes):
    """Grow every same-net metal polygon below the minimum area into a box of at least that area (square-ish,
    around its centre), clipped by the spacing to other nets. Returns [(layer, rect)]."""
    import klayout.db as kdb
    dbu = 0.005
    per = {}
    for lay, r, net in shapes:
        if lay in MIN_AREA and net is not None:
            per.setdefault((lay, net), []).append(r)
    out = []
    for (lay, net), rs in per.items():
        reg = kdb.Region()
        for r in rs:
            reg.insert(kdb.Box(*(round(v / dbu) for v in r)))
        reg.merge()
        others = kdb.Region()
        for (l2, n2), rs2 in per.items():
            if l2 == lay and n2 != net:
                for r in rs2:
                    others.insert(kdb.Box(*(round(v / dbu) for v in r)))
        sp = int(round(SPACE[lay] / dbu))
        keep = others.sized(sp, sp, 2)
        amin = MIN_AREA[lay] / dbu / dbu
        for poly in reg.each():
            if poly.area() >= amin:
                continue
            bb = poly.bbox()
            w, h = bb.width(), bb.height()
            done = False
            for mode in ((0, 1), (1, 0), (1, 1)):       # grow along y, along x, then both (only into free space)
                for grow in range(2, 80, 2):
                    box = kdb.Box(bb.left - grow * mode[0], bb.bottom - grow * mode[1],
                                  bb.right + grow * mode[0], bb.top + grow * mode[1])
                    if not (kdb.Region(box) & keep).is_empty():
                        break
                    if (kdb.Region(poly) + kdb.Region(box)).merged().area() >= amin:
                        out.append((lay, (snap(box.left * dbu), snap(box.bottom * dbu), snap(box.right * dbu),
                                          snap(box.top * dbu))))
                        done = True
                        break
                if done:
                    break
            if not done:
                print(f"  min-area: no room to grow {lay} {net} at {bb.left * dbu:.3f},{bb.bottom * dbu:.3f}")
    return out
