"""Level-3 CMP: one line per f-I case in sim/results/level3_cmp/fi/fi_*.json -> sim/results/level3_cmp/fi_summary.txt
Pass (proposal 6): f/f_ideal 0.7-1.4 against the S = 100 baseline (same variant, corner, vth_cmp setting), i.e. the
per-k ratio divided by the S = 100 ratio, at every k = 1.1 .. 8; no latch (spikes at every k, spk not stuck high).
"""
import glob
import json
import re

rows = {}
for f in sorted(glob.glob("sim/results/level3_cmp/fi/fi_*.json")):
    d = json.load(open(f))
    tag = f.split("fi_", 1)[1][:-5]
    m = re.match(r"slot_cmp_h_(\w+?)_(\d+)_S(\d+)(.*)", tag)
    corner, temp, S, rest = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    key = re.sub(r"_iprb[0-9.]+u", "_iprb(B1)", rest)  # e.g. _i1, _EL1.50_i1, _iprb0.816u_i1 -> _iprb(B1)_i1
    r = {x["k"]: x for x in d["res"]}
    rat = {k: (r[k]["rate"] / r[k]["ideal"] if r[k]["ideal"] else float("nan")) for k in r}
    fires = all(r[k]["nspk"] >= 3 and r[k]["rate"] > 0 for k in r)
    rows[(key, corner, temp, S)] = dict(d=d, r=r, rat=rat, fires=fires)

L = ["case: DC trip (V) | f/f_ideal at k = 1.1 1.5 2 3 5 8 | min-max normalised to S=100 | spike w (ns), w/ISI8 | "
     "bench Idd at 3x (uA) | verdict"]
for key in sorted({k[0] for k in rows}):
    L.append(f"=== variant{key}")
    for corner, temp in (("typical", 27), ("ss", 0), ("ff", 85), ("sf", 0)):
        for S in (10, 100, 1000, 2000, 3000, 10000):
            x = rows.get((key, corner, temp, S))
            if not x:
                continue
            base = rows.get((key, corner, temp, 100))
            ks = sorted(x["rat"])
            if base and base["fires"] and x["fires"]:
                nr = [x["rat"][k] / base["rat"][k] for k in ks]
                nmin, nmax = min(nr), max(nr)
                ok = 0.7 <= nmin and nmax <= 1.4
            else:
                nmin = nmax = float("nan")
                ok = False
            verdict = "PASS" if ok else ("LATCH/NO-FIRE" if not x["fires"] else "FAIL")
            d, r = x["d"], x["r"]
            L.append(f" {corner:7s} {temp:2d} S={S:5d}: trip {d['vtrip']:.3f} | "
                     + " ".join(f"{x['rat'][k]:5.2f}" for k in ks)
                     + f" | {nmin:5.2f}-{nmax:5.2f} | {r[8]['w_spk'] * 1e9:6.1f} {d['w_over_isi8']:.3f} | "
                     f"{r[3]['idd'] * 1e6:6.2f} | {verdict}")
txt = "\n".join(L)
print(txt)
open("sim/results/level3_cmp/fi_summary.txt", "w").write(txt + "\n")
