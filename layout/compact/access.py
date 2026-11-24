"""Pin-access check for a cgen placement: terminals with no legal first move (a via or a one-step wire)."""
import os
import cgen


def check(pl, G, verbose=True):
    xs, ys = cgen.make_grid(G, pl.H)
    R = cgen.CRouter(xs, ys, layers=("m1", "m2", "m3"), hw=0.14)
    for lay, r, net in G.obst:
        R.add_shape(lay, r, net)
    cgen.add_forbids(R, G, pl)
    bad = []
    for net, ts in cgen.merge_terms(G).items():
        for t in ts:
            nodes = set()
            for lay, r in t:
                for i, x in enumerate(xs):
                    if r[0] - 1e-6 <= x <= r[2] + 1e-6:
                        for j, y in enumerate(ys):
                            if r[1] - 1e-6 <= y <= r[3] + 1e-6:
                                nodes.add((lay, i, j))
            ok = False
            for n in nodes:
                l, i, j = n
                k = R.layers.index(l)
                moves = [(R.layers[q], i, j) for q in (k - 1, k + 1) if 0 <= q < 3]
                moves += [(l, i + di, j + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
                          if 0 <= i + di < len(xs) and 0 <= j + dj < len(ys)]
                for m in moves:
                    if m not in nodes and all(R.hard_ok(ll, rr, net) for ll, rr in R.move_shapes(n, m)):
                        ok = True
                        break
                if ok:
                    break
            if not ok:
                r = t[0][1]
                bad.append((net, round((r[0] + r[2]) / 2, 2), round((r[1] + r[3]) / 2, 2), len(nodes)))
    if verbose:
        print(f"{len(bad)} terminals without a legal first move")
        for b in sorted(bad, key=lambda b: (b[2], b[1])):
            print("  ", b)
    return bad


if __name__ == "__main__":
    seed = int(os.environ.get("SEED", "0"))
    pl, c = cgen.place_one(seed, int(os.environ.get("STEPS", "30000")))
    check(pl, cgen.build_geometry(pl))
