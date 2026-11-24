#!/usr/bin/env python3
"""MIL-319: summary of mc_cmp.py (sim/results/m3mc/mc_cmp_<corner>.jsonl) -> sim/results/m3mc/summary.txt.
Per corner: dies (seed > 0) passing at code 27 / 26 / either, dies that need 25 or 28 (26 and 27 fail, 25 or 28
passes), dies with no passing code; 95 % Wilson intervals; min-ratio statistics; trip / DAC offset spread."""
import json
import math
import sys
from pathlib import Path

D = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/sim/results/m3mc")


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def stats(x):
    x = [v for v in x if v == v]
    if len(x) < 2:
        return "n/a"
    m = sum(x) / len(x)
    s = math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))
    return f"mean {m:.3f} sd {s:.3f} min {min(x):.3f} max {max(x):.3f}"


L = []
for f in sorted(D.glob("mc_cmp_*.jsonl")):
    corner = f.stem.split("_")[-1]
    dies = {}
    for ln in f.read_text().splitlines():
        r = json.loads(ln)
        dies.setdefault(r["seed"], {})[r["code"]] = r
    nom = dies.pop(0, {})
    n = len(dies)
    cnt = {"27": 0, "26": 0, "either": 0, "both": 0, "needs25": 0, "needs28": 0, "none": 0, "err": 0}
    for s, cs in dies.items():
        p = {c: bool(r["ok"]) for c, r in cs.items()}
        if any(r["ok"] is None for r in cs.values()):
            cnt["err"] += 1
        cnt["27"] += p.get(27, False)
        cnt["26"] += p.get(26, False)
        cnt["both"] += p.get(27, False) and p.get(26, False)
        if p.get(27) or p.get(26):
            cnt["either"] += 1
        elif p.get(25):
            cnt["needs25"] += 1
        elif p.get(28):
            cnt["needs28"] += 1
        else:
            cnt["none"] += 1
    L.append(f"== {corner}: {n} dies (mismatch seeds), S = 10000, leak x 13/12, gate 0.7-1.4")
    L.append("  nominal (seed 0): " + "  ".join(
        f"c{c} {'PASS' if r['ok'] else 'FAIL'} {min(r['ratios']):.2f}-{max(r['ratios']):.2f}" if r["ratios"] else f"c{c} ERR"
        for c, r in sorted(nom.items())))
    for k in ("27", "26", "either", "both"):
        lo, hi = wilson(cnt[k], n)
        L.append(f"  pass at {k:6s}: {cnt[k]:3d}/{n} = {cnt[k] / n if n else float('nan'):.3f}  (95 % {lo:.3f}-{hi:.3f})")
    for k in ("needs25", "needs28", "none", "err"):
        L.append(f"  {k:14s}: {cnt[k]}")
    for c in (27, 26):
        mins = [min(cs[c]["ratios"]) for cs in dies.values() if c in cs and cs[c]["ratios"]]
        maxs = [max(cs[c]["ratios"]) for cs in dies.values() if c in cs and cs[c]["ratios"]]
        L.append(f"  code {c}: min ratio {stats(mins)}")
        L.append(f"           max ratio {stats(maxs)}")
    tr = [cs[26]["vtrip10k"] for cs in dies.values() if 26 in cs and cs[26]["vtrip10k"]]
    off = [1e3 * cs[26]["dac_off"] for cs in dies.values() if 26 in cs]
    L.append(f"  trip at S = 10000, code 26 (V): {stats(tr)}")
    L.append(f"  DAC offset at code 26 (mV): {stats(off)}")
    full = {s: cs for s, cs in dies.items() if len(cs) == 4}
    if full:
        L.append("  window (dies with all four codes): " + "; ".join(
            f"s{s} " + "".join(str(c)[-1] if cs[c]["ok"] else "." for c in (25, 26, 27, 28)) for s, cs in sorted(full.items())))
(D / "summary.txt").write_text("\n".join(L) + "\n")
print("\n".join(L))
