"""Check 4, step 1: DC supply current of every device power terminal (full-chip PEX, one ammeter per VDPWR /
VGND terminal of every analog / glue device; the macro is modelled separately).

  python3 sim/tb/top/tb_top_icur.py [corner] [T]
Cases: S = 100 nominal, probe off; S = 1000, probe on (far slot S3), IB_X2 = 1 (R1 pad driver 800 uA).
Writes sim/results/top/icur_<corner>_<T>.json: case -> {"terms": {terminal: I}, "blocks": {block: [I_vdd, I_vss]}}
(I > 0 = drawn from VDD / sunk into VSS), used by sim/tb/top/pgrid.py for the IR-drop solve.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, "/work/sim/tb/top")
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402

CORNER = sys.argv[1] if len(sys.argv) > 1 else "typical"
TEMP = int(sys.argv[2]) if len(sys.argv) > 2 else 27
CASES = {"S100_probe_off": dict(S=100.0, probe=None, ib_x2=0),
         "S1000_probe_on_ibx2": dict(S=1000.0, probe=dict(row=3, col=0, sub=0), ib_x2=1)}
VM = ["s01", "s02", "s10", "s11", "s12", "s13", "s20", "s21", "s22", "s23", "s30", "s31", "s32", "s33"]
res = {}
for case, kw in CASES.items():
    T._cache.pop("pterms", None)
    body = B.chip(kw["S"], probe=kw["probe"], ib_x2=kw["ib_x2"], power="perdev")
    terms = sorted(T._cache["pterms"])
    el = 1.50 if kw["S"] >= 300 else 1.30
    ns = "\n".join(f".nodeset v({T.vnode(f'{s}.vm')})={el}" for s in VM) + f"\n.nodeset v(d1.vs)={el}\n"
    save = [f"i(vpt_{T.san(x).lower()})" for x in terms] + ["i(vvdd)", "i(vvss)", f"v({T.vnode('en_b')})",
                                                            "v(pad)", f"v({T.vnode('abus')})"]
    d = B.deck(body, "op", save, corner=CORNER, temp=TEMP)
    r = B.go(d, f"icur_{case}_{CORNER}_{TEMP}")
    I = {}
    for x in terms:
        v = float(r[f"i(vpt_{T.san(x).lower()})"][0])
        I[x] = -v if x.startswith("VDPWR") else v
    # block totals (device owner by position)
    own = {}
    for l in T.load()["lines"]:
        if l[0] in "XD":
            t = l.split()
            nn = [q for q in t[1:] if "=" not in q][:-1]
            o = T.owner(nn) or "other"
            for q in nn:
                if q in I:
                    own[q] = o
    blk = defaultdict(lambda: [0.0, 0.0])
    for x, v in I.items():
        blk[own.get(x, "other")][0 if x.startswith("VDPWR") else 1] += v
    res[case] = dict(terms=I, blocks=dict(blk))
    enb, ab = r[f"v({T.vnode('en_b')})".lower()][0], r[f"v({T.vnode('abus')})".lower()][0]
    print(f"{case}: total I_vdd {sum(v[0] for v in blk.values()) * 1e6:.1f} uA, I_vss "
          f"{sum(v[1] for v in blk.values()) * 1e6:.1f} uA; en_b {enb:.2f} V, pad {r['v(pad)'][0]:.3f} V, abus {ab:.3f} V")
    for b in sorted(blk):
        print(f"  {b:8s} vdd {blk[b][0] * 1e6:9.3f} uA   vss {blk[b][1] * 1e6:9.3f} uA")
(B.OUT / f"icur_{CORNER}_{TEMP}.json").write_text(json.dumps(res, indent=1))
