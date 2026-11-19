"""List nets whose terminals fall in more than one routing region without a shared terminal
(spine, feed, Metal3 line) spanning those regions: such nets would be left open by region routing."""
import sys
sys.path.insert(0, ".")
import dendgen as G
L, insts, obst, mom, lib, devs, ports = G.build()
bad = 0
for net, terms in sorted(L.nets.items()):
    regs = []
    for t in terms:
        ys = [y for lay, r in t for y in (r[1], r[3])]
        rs = {i for i, (a, b) in enumerate(G.REGIONS) if min(ys) <= b and max(ys) >= a}
        regs.append(rs)
    span = set().union(*regs) if regs else set()
    if len(span) > 1:
        # connected across regions if one terminal touches every region the net needs
        needed = {min(r) for r in regs if len(r) == 1} | {i for r in regs for i in r if len(r) == 1}
        if not any(needed <= r for r in regs):
            print("CROSS", net, [sorted(r) for r in regs])
            bad += 1
print("cross-region nets without a spanning terminal:", bad)
