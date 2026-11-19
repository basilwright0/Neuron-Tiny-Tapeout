"""Placement check: can every device/pin terminal escape (alone, no other routing) to >4 um away?"""
import sys
sys.path.insert(0, '.')
import slotgen as S
from router import Router

L, insts, obst, mom, lib, devs, ports = S.build()
xs, ys = S.make_grid(L, S.GRID)


def mk():
    R = Router(xs, ys, layers=S.LAYERS, hw=S.WIRE_HW)
    for lay, r, net in obst:
        R.add_shape(lay, r, net)
    S.add_forbids(R, mom)
    return R


def nodes(shapes):
    out = set()
    for lay, r in shapes:
        for i, x in enumerate(xs):
            if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                for j, y in enumerate(ys):
                    if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                        out.add((lay, i, j))
    return out


bad = 0
for net, terms in sorted(L.nets.items()):
    for k, t in enumerate(terms):
        tn = nodes(t)
        if not tn:
            print(f"NOGRID {net} {t}")
            bad += 1
            continue
        bx = [xs[n[1]] for n in tn]
        by = [ys[n[2]] for n in tn]
        far = {("m2", i, j) for i, x in enumerate(xs) for j, y in enumerate(ys)
               if max(0, min(bx) - x, x - max(bx)) + max(0, min(by) - y, y - max(by)) > 4.0}
        R = mk()
        if not R.route_net(net, [tn, far], max_expand=2000000):
            print(f"TRAPPED {net} term{k} {t}")
            bad += 1
print("trapped terminals:", bad)
