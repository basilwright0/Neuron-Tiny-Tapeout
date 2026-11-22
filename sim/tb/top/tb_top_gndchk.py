"""Check 4 cross-check of pgrid.py on magic's own resistive VGND network (device-terminal exact): VDPWR ideal,
VGND R network kept and grounded only at magic's 'VGND' port node = the bottom end (y 5) of the x 342.6 stripe,
which is the only ground hookup of B1 and R1. Prints the rise of B1 / R1 VSS terminals (mean / max).
  python3 sim/tb/top/tb_top_gndchk.py [S]"""
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402

S = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
own = defaultdict(set)
for l in T.load()["lines"]:
    if l[0] in "XD":
        t = l.split()
        nn = [q for q in t[1:] if "=" not in q][:-1]
        o = T.owner(nn)
        if o in ("b1", "r1"):
            for q in nn:
                if q.startswith("VGND"):
                    own[o].add(q)
body = B.chip(S, power="gndnet")
sv = sorted({f"v({T.san(q)})" for v in own.values() for q in v})
r = B.go(B.deck(body, "op", sv), f"gndchk_S{S:g}")
out = [f"VGND rise at device terminals, magic R network, ground at the x 342.6 stripe bottom end only, S = {S:g}:"]
for o, v in own.items():
    a = np.array([r[f"v({T.san(q)})".lower()][0] for q in v])
    out.append(f"  {o}: {len(a)} terminals, mean {a.mean() * 1e3:.2f} mV, max {a.max() * 1e3:.2f} mV")
print("\n".join(out))
(B.OUT / f"gndchk_S{S:g}.txt").write_text("\n".join(out) + "\n")
