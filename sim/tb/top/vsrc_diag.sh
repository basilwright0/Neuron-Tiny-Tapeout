#!/bin/bash
# R2 PEX diagnostic (MIL-362): the R+C flat netlist has no coupling C on vsrc (195 fF, all to VGND, '**FLOATING');
# M3 had 387 fF incl. 29.6 fF to digital lines. Compare with the C-only extraction and the flat .ext.
cd /work
O=sim/results/top/vsrc_diag.txt
{
echo "== top_c_flat.spice (C-only): C lines touching a vsrc node, total and to-ground"
python3 - <<'P'
import re
tot = gnd = 0.0; n = 0; other = {}
u = {"f": 1e-15, "a": 1e-18, "p": 1e-12}
for l in open("layout/top/work/pex/top_c_flat.spice"):
    if not l.startswith("C"):
        continue
    t = l.split()
    if not any("vsrc" in x and "vsrcp" not in x for x in t[1:3]):
        continue
    m = re.match(r"([\d.eE+-]+)([fap]?)", t[3]); v = float(m.group(1)) * u.get(m.group(2), 1)
    tot += v; n += 1
    o = t[2] if "vsrc" in t[1] else t[1]
    if o in ("0", "VSUBS", "VGND"):
        gnd += v
    else:
        other[o] = other.get(o, 0) + v
print(f"{n} caps, total {tot * 1e15:.1f} fF, to ground {gnd * 1e15:.1f} fF")
for k, v in sorted(other.items(), key=lambda kv: -kv[1])[:15]:
    print(f"  {k} {v * 1e18:.0f} aF")
P
echo "== top_flat.ext: lines naming vsrc (cap / node / merge)"
grep -c vsrc layout/top/work/pexr/top_flat.ext
grep -E '^(node|cap|merge|equiv)' layout/top/work/pexr/top_flat.ext | grep vsrc | head -20
grep '^cap' layout/top/work/pexr/top_flat.ext | grep -c vsrc
} > $O 2>&1
