"""Pin extraction from block GDS (klayout python, runs in the EDA container).

block_pins(gds, cell) -> {name: [(layer, (x0, y0, x1, y1)), ...]}  (cell-local um)
A pin is a text label on <metal>/10 of the block's top cell; its shape is the merged polygon of the
drawing layer under the label (bbox).  Labels of subcells are ignored.
"""
import sys, json
import klayout.db as db

MET = {34: "metal1", 36: "metal2", 42: "metal3", 46: "metal4"}


def block_pins(gds, cell=None):
    ly = db.Layout(); ly.read(gds)
    top = ly.cell(cell) if cell else ly.top_cell()
    dbu = ly.dbu
    out = {}
    regs = {}
    for li in ly.layer_indexes():
        inf = ly.get_info(li)
        if inf.datatype != 10 or inf.layer not in MET:
            continue
        dl = ly.find_layer(inf.layer, 0)
        if dl is None:
            continue
        if inf.layer not in regs:
            regs[inf.layer] = db.Region(top.begin_shapes_rec(dl)).merged()
        reg = regs[inf.layer]
        for s in top.shapes(li).each():
            if not s.is_text():
                continue
            t = s.text
            pt = db.Box(t.x - 1, t.y - 1, t.x + 1, t.y + 1)
            hit = reg.interacting(db.Region(pt))
            if hit.is_empty():
                r = (t.x * dbu, t.y * dbu, t.x * dbu, t.y * dbu)
            else:
                b = hit.bbox()
                r = (b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)
            out.setdefault(t.string, []).append((MET[inf.layer], tuple(round(v, 3) for v in r)))
    bb = top.bbox()
    return out, (bb.left * dbu, bb.bottom * dbu, bb.right * dbu, bb.top * dbu)


if __name__ == "__main__":
    p, bb = block_pins(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("BBOX", bb)
    for n, v in sorted(p.items()):
        print(n, v)
