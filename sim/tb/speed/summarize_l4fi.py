"""Level 4: one line per f-I case in sim/results/level4/fi/fi_*.json -> sim/results/level4/fi_summary.txt
Pass (speed-limits / level-3 proposal 6): f/f_ideal 0.7-1.4 against the S = 100 baseline of the same cell, variant,
corner and EL (per-k ratio / S = 100 ratio, every k = 1.1 .. 8); spikes at every k; rheo = DC rheobase / nominal.
"""
import glob
import json
import re

rows = {}
for f in sorted(glob.glob("sim/results/level4/fi/fi_*.json")):
    d = json.load(open(f))
    tag = f.split("/fi_", 1)[1][:-5]
    m = re.match(r"(slot_\w+?)_(typical|ss|ff|sf|fs)_(\d+)_S(\d+)(_EL[0-9.]+)?_(\w+)$", tag)
    if not m:
        continue
    cell, corner, temp, S, el, var = m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5) or "_EL1.30", m.group(6)
    r = {x["k"]: x for x in d["res"]}
    rat = {k: (r[k]["rate"] / r[k]["ideal"] if r[k]["ideal"] else float("nan")) for k in r}
    fires = all(r[k]["nspk"] >= 3 and r[k]["rate"] > 0 for k in r)
    rows[(cell, var, el, corner, temp, S)] = dict(d=d, r=r, rat=rat, fires=fires)

L = ["cell variant EL corner T S: f/f_ideal at k = 1.1 1.5 2 3 5 8 | min-max normalised to S=100 [per k] | rheo meas/nom | "
     "t_ref meas/nom | verdict"]
for key in sorted({k[:3] for k in rows}):
    L.append(f"=== {key[0]} {key[1]} EL{key[2][3:]}")
    for corner, temp in (("typical", 27), ("ss", 0), ("ff", 85), ("sf", 0)):
        for S in (10, 100, 1000, 3000, 10000):
            x = rows.get(key + (corner, temp, S))
            if not x:
                continue
            base = rows.get(key + (corner, temp, 100))
            ks = sorted(x["rat"])
            if base and base["fires"] and x["fires"]:
                nr = [x["rat"][k] / base["rat"][k] for k in ks]
                nmin, nmax = min(nr), max(nr)
                nrs = " ".join(f"{v:4.2f}" for v in nr)
                ok = 0.7 <= nmin and nmax <= 1.4
            else:
                nmin = nmax = float("nan")
                nrs = ""
                ok = False
            verdict = "PASS" if ok else ("NO-FIRE" if not x["fires"] else "FAIL")
            d, r = x["d"], x["r"]
            L.append(f" {corner:7s} {temp:2d} S={S:5d}: " + " ".join(f"{x['rat'][k]:5.2f}" for k in ks)
                     + f" | {nmin:5.2f}-{nmax:5.2f} [{nrs}] | {d['rheo_meas'] / d['rheo']:5.3f} | {r[8]['t_ref'] / d['tref_nom']:5.2f} | {verdict}")
txt = "\n".join(L)
print(txt)
open("sim/results/level4/fi_summary.txt", "w").write(txt + "\n")
