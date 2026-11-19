"""Print the path of an LVS reference netlist for a B1 cell (writes out/ref_<cell>.spice).

The reference is cells/bias/*.spice (the schematic), with the cell's subckt and every subckt it
instantiates, junction parameters (ad/as/pd/ps) stripped."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
cell = sys.argv[1]
alias = "bias_b1" if cell.startswith("bias_b1_") else cell      # the two B1 shapes share one schematic
sub = {}
for f in sorted((ROOT / "cells" / "bias").glob("bias_*.spice")):
    if f.name == "bias_all.spice":
        continue
    cur = None
    for ln in f.read_text().splitlines():
        if ln.lower().startswith(".subckt"):
            cur = ln.split()[1]
            sub[cur] = [ln]
        elif cur:
            sub[cur].append(re.sub(r"\s+(ad|as|pd|ps)=\S+", "", ln))
            if ln.lower().startswith(".ends"):
                cur = None
need, todo = [], [alias]
while todo:
    c = todo.pop()
    if c in need:
        continue
    need.append(c)
    for ln in sub[c][1:]:
        t = ln.split()
        if t and t[0][0] in "Xx":
            m = [x for x in t[1:] if "=" not in x][-1]
            if m in sub:
                todo.append(m)
out = Path(__file__).resolve().parent / "out" / f"ref_{cell}.spice"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(l for c in reversed(need) for l in sub[c]) + "\n")
print(out)
