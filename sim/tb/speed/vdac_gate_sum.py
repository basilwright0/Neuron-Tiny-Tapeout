#!/usr/bin/env python3
"""vdac (MIL-133): 10000x gate summary for sim/results/vdac/gate: per k, (f/f_ideal at S=10000) / (f/f_ideal at
S=100), same cell / corner / vth_cmp; pass = all k in 0.7-1.4.  -> summary.txt"""
import json, sys
from pathlib import Path
D = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/sim/results/vdac/gate")
L = []
for f100 in sorted(D.glob("fi_*_S100_*.json")):
    f10k = Path(str(f100).replace("_S100_", "_S10000_"))
    if not f10k.exists():
        continue
    a, b = json.loads(f100.read_text()), json.loads(f10k.read_text())
    r = [(y["rate"] / y["ideal"]) / (x["rate"] / x["ideal"]) if x["rate"] > 0 else float("nan")
         for x, y in zip(a["res"], b["res"])]
    ok = all(0.7 <= v <= 1.4 for v in r) and all(y["nspk"] >= 3 for y in b["res"])
    stuck = sum(y["stuck"] for y in b["res"])
    L.append(f"{f100.name[3:-5].replace('_S100', ''):44s} {min(r):.2f}-{max(r):.2f} {'PASS' if ok else 'FAIL'} "
             f"[{' '.join(f'{v:.2f}' for v in r)}] trip S100/S10k {a['vtrip']:.4f}/{b['vtrip']:.4f} "
             f"vmax10k {max(y['vm_max'] for y in b['res']):.3f} stuck {stuck}")
(D / "summary.txt").write_text("\n".join(L) + "\n")
print("\n".join(L))
