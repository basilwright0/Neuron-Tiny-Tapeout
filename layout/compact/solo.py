"""Route every net alone on the static obstacles: nets that fail here are blocked by geometry, not congestion."""
import os
import cgen


def check(pl, G, verbose=False):
    xs, ys = cgen.make_grid(G, pl.H)
    R = cgen.CRouter(xs, ys, layers=("m1", "m2", "m3"), hw=0.14)
    for lay, r, net in G.obst:
        R.add_shape(lay, r, net)
    cgen.add_forbids(R, G, pl)

    def nodes(shapes):
        out = set()
        for lay, r in shapes:
            ii = [i for i, x in enumerate(xs) if r[0] - 1e-6 <= x <= r[2] + 1e-6]
            jj = [j for j, y in enumerate(ys) if r[1] - 1e-6 <= y <= r[3] + 1e-6]
            out |= {(lay, i, j) for i in ii for j in jj}
        return out
    bad = []
    for net, ts in cgen.merge_terms(G).items():
        tn = [t for t in (nodes(t) for t in ts) if t]
        if len(tn) < 2:
            continue
        if not R.route_net(net, tn, max_expand=400000):
            bad.append((net, 0, 0, 0))
            if verbose:
                print("BLOCKED", net)
        R.ripup(net)
    return bad


if __name__ == "__main__":
    cgen.set_params(cgen.sweep()[0])
    pl, c = cgen.place_one(int(os.environ.get("SEED", "0")), int(os.environ.get("STEPS", "30000")))
    print(len(check(pl, cgen.build_geometry(pl), verbose=True)), "blocked nets")
