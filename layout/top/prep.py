"""Prepare block layouts for the top level (KLayout Python, runs in the EDA container).

For every cell in config.LIB:
  final       -> work/gds/<cell>.gds  (subcells renamed with the block prefix so blocks never clash)
  placeholder -> work/gds/<cell>.gds  (pins only: the block's current pin shapes, shifted per PH_SHIFT)
and work/geo/<cell>.json with bbox, pins (exact rectangles of the labelled shapes) and obstacles
(merged Metal1-4 rectangles, cell-local um).  Also work/gds/stdcells.gds with the PDK std cells used by
the top level that the macro GDS does not already contain.
Run: scripts/eda.sh "cd layout/top && python3 prep.py"
"""
import json, os, sys
import klayout.db as db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

MET = {34: "metal1", 36: "metal2", 42: "metal3", 46: "metal4"}
LNUM = {v: k for k, v in MET.items()}
GDIR, JDIR = C.WORK / "gds", C.WORK / "geo"
GDIR.mkdir(parents=True, exist_ok=True); JDIR.mkdir(parents=True, exist_ok=True)


def rects(region, dbu):
    out = []
    for p in region.each():
        for t in p.decompose_trapezoids():
            b = t.bbox()
            out.append([round(b.left * dbu, 3), round(b.bottom * dbu, 3), round(b.right * dbu, 3), round(b.top * dbu, 3)])
    return out


def analyse(ly, top, sub=None):
    dbu = ly.dbu
    regs, obs = {}, {}
    for L, name in MET.items():
        li = ly.find_layer(L, 0)
        regs[L] = db.Region(top.begin_shapes_rec(li)).merged() if li is not None else db.Region()
        obs[name] = rects(regs[L], dbu)
    pins = {}
    srcs = [(top, db.Trans())]
    if sub:
        srcs += [(ly.cell(i.cell_index), i.trans) for i in top.each_inst() if ly.cell(i.cell_index).name == sub]
    for li in ly.layer_indexes():
        inf = ly.get_info(li)
        if inf.datatype != 10 or inf.layer not in MET:
            continue
        for cc, tr in srcs:
          for s in cc.shapes(li).each():
            if not s.is_text():
                continue
            t = s.text.transformed(tr)
            hit = regs[inf.layer].interacting(db.Region(db.Box(t.x - 1, t.y - 1, t.x + 1, t.y + 1)))
            pins.setdefault(t.string, []).append(dict(layer=MET[inf.layer], pt=[t.x * dbu, t.y * dbu],
                                                     rects=rects(hit, dbu)))
    # foreign metal = everything that is not a labelled pin polygon (the router treats pins as their net's)
    pinreg = {L: db.Region() for L in MET}
    for lst in pins.values():
        for p in lst:
            L = LNUM[p["layer"]]
            for r in p["rects"]:
                pinreg[L].insert(db.DBox(*r).to_itype(dbu))
    for L, name in MET.items():
        obs[name] = rects(regs[L] - pinreg[L].merged(), dbu)
    bb = top.bbox()
    return dict(bbox=[bb.left * dbu, bb.bottom * dbu, bb.right * dbu, bb.top * dbu], pins=pins, obs=obs)


def placeholder(cell, geo, size):
    """Pins-only stand-in: through-lines keep their full shape, edge pins become stubs to the nearest edge,
    band pads / straps become small pads (so the shapes never short each other)."""
    W, H = size
    shifts = C.PH_SHIFT.get(cell, [])
    def sh(x):
        for a, b, d in shifts:
            if a <= x < b:
                return d
        return 0.0
    out = {}
    for name, lst in geo["pins"].items():
        for p in lst:
            x, y = p["pt"]
            dx = sh(x)
            x += dx
            lay = p["layer"]
            bb = [min(r[0] for r in p["rects"]), min(r[1] for r in p["rects"]),
                  max(r[2] for r in p["rects"]), max(r[3] for r in p["rects"])] if p["rects"] else [x, y, x, y]
            bb = [bb[0] + dx, bb[1], bb[2] + dx, bb[3]]
            if lay == "metal1" and name == "vss" and bb[2] - bb[0] > 5:
                r = [0.0, 0.0, W, 0.6]                                  # p-tap ring bottom edge only
            elif bb[3] - bb[1] >= H - 0.05:
                r = [x - 0.2, 0.0, x + 0.2, H]                           # through-line (column line)
            elif bb[2] - bb[0] >= W - 0.05:
                r = [0.0, y - 0.2, W, y + 0.2]
            elif cell.startswith("slot") and (name in ("spk", "t0", "t1", "t2", "t3")):
                r = [x - 0.2, 31.95, x + 0.2, 42.66]                     # strap over the row band
            else:
                d = {"l": x, "r": W - x, "b": y, "t": H - y}
                e = min(d, key=d.get)
                if d[e] <= 1.5:
                    hw = 0.2 if lay != "metal1" else 0.3
                    r = {"l": [0.0, y - hw, x + hw, y + hw], "r": [x - hw, y - hw, W, y + hw],
                         "b": [x - hw, 0.0, x + hw, y + hw], "t": [x - hw, y - hw, x + hw, H]}[e]
                else:
                    r = [x - 0.2, y - 0.2, x + 0.2, y + 0.2]
            mv = C.PH_MOVE.get(cell, {}).get(name)
            if mv:
                lay, x, y = mv
                r = [x, y - 0.2, x + 0.6, y + 0.2]
            out.setdefault(name, []).append(dict(layer=lay, pt=[round(x, 3), round(y, 3)],
                                                 rects=[[round(v, 3) for v in r]]))
    ly = db.Layout(); ly.dbu = 0.001
    top = ly.create_cell(cell)
    for name, lst in out.items():
        for p in lst:
            L = LNUM[p["layer"]]
            li, lt = ly.layer(L, 0), ly.layer(L, 10)
            for r in p["rects"]:
                top.shapes(li).insert(db.DBox(*r))
            top.shapes(lt).insert(db.DText(name, db.DTrans(db.DVector(*p["pt"]))))
    obs = {k: [] for k in MET.values()}          # placeholders: no foreign metal (keep-out covers the box)
    ly.write(str(GDIR / f"{cell}.gds"))
    return dict(bbox=[0.0, 0.0, W, H], pins=out, obs=obs, placeholder=True)


def main():
    macro_cells = set()
    for cell, d in C.LIB.items():
        ly = db.Layout(); ly.read(str(C.ROOT / d["gds"]))
        top = ly.cell(cell)
        assert top is not None, f"{cell} not in {d['gds']}"
        geo = analyse(ly, top, d.get("sub"))
        if d.get("kind") == "macro":
            macro_cells = {c.name for c in ly.each_cell()}
        if d["final"]:
            if d.get("prefix"):
                for c in ly.each_cell():
                    if c.cell_index() != top.cell_index():
                        c.name = d["prefix"] + c.name
            for c in [c for c in ly.each_cell() if c.is_top() and c.cell_index() != top.cell_index()]:
                ly.delete_cell(c.cell_index())          # stray top cells
            ly.write(str(GDIR / f"{cell}.gds"))
            geo["placeholder"] = False
        else:
            geo = placeholder(cell, geo, d["size"])
        (JDIR / f"{cell}.json").write_text(json.dumps(geo))
        print(f"{cell:12s} {'FINAL' if d['final'] else 'PLACEHOLDER':11s} bbox {geo['bbox']} pins {len(geo['pins'])}"
              f" obs {sum(len(v) for v in geo['obs'].values())}")
    # std cells for the tie row and glue logic
    want = [C.SC + n for n in C.SC_W]
    if "PDK_ROOT" not in os.environ:          # host run without the PDK (route debug only; assembly needs it)
        print("no PDK_ROOT: work/gds/stdcells.gds not written")
    else:
        _stdcells_gds(want, macro_cells)
    # std-cell pin rectangles (Metal1) from the PDK LEF subset
    import re
    t = (C.HERE / "stdcells" / "cells.lef").read_text()
    sc = {}
    for n in want:
        m = re.search(r"MACRO " + n + r"\n(.*?)END " + n + r"\n", t, re.S)
        pins = {}
        for pn, body in re.findall(r"PIN (\S+)\n(.*?)END \1", m.group(1), re.S):
            rs = []
            for lay, rr in re.findall(r"LAYER (\S+) ;((?:\s*RECT [^;]+;)+)", body):
                if lay == "Metal1":
                    rs += [[float(v) for v in r.split()] for r in re.findall(r"RECT ([^;]+);", rr)]
            pins[pn] = rs
        om = re.search(r"OBS(.*?)END", m.group(1), re.S)
        obs = [[float(v) for v in r.split()] for r in re.findall(r"RECT ([^;]+);", om.group(1))] if om else []
        sc[n] = dict(pins=pins, obs=obs)
    (JDIR / "stdcells.json").write_text(json.dumps(sc))
    print("stdcells:", ", ".join(sc))


def _stdcells_gds(want, macro_cells):
    pdk = os.environ["PDK_ROOT"] + "/" + os.environ["PDK"] + "/libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds"
    lib = db.Layout(); lib.read(pdk)
    ly = db.Layout(); ly.dbu = lib.dbu
    for n in want:
        if n in macro_cells:
            print("std cell from macro GDS:", n)
            continue
        src = lib.cell(n)
        dst = ly.create_cell(n)
        dst.copy_tree(src)
    ly.write(str(GDIR / "stdcells.gds"))


if __name__ == "__main__":
    main()
