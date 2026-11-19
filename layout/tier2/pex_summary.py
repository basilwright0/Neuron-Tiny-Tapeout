"""Summarise magic PEX (ext2spice cthresh 0) for a Tier-2 cell: wiring capacitance of selected nodes and
selected pair couplings (MOM capacitors: Cfb = spk-vm/vs, SC caps = ca-vss / cl-vss).

    python3 pex_summary.py out/<cell>_pex.spice <cell> node1,node2,... a-b,c-d,...

Capacitors in the extracted netlist are parasitics only (gate/junction caps live in the device models).
For the SC caps the MOM's own capacitance to vss IS the wanted capacitor, so 'ca total' = C_A (+ wiring).
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

SI = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "a": 1e-18}


def val(s):
    m = re.fullmatch(r"([-+0-9.eE]+)([fpna]?)[fF]?", s)
    if not m:
        raise ValueError(s)
    return float(m.group(1)) * SI.get(m.group(2), 1.0)


path, cell = Path(sys.argv[1]), sys.argv[2]
nodes = sys.argv[3].split(",") if len(sys.argv) > 3 else []
pairs = [tuple(p.split("-")) for p in sys.argv[4].split(",")] if len(sys.argv) > 4 else []
txt = path.read_text()
m = re.search(r"^\.subckt\s+" + cell + r"\s.*?^\.ends", txt, re.S | re.M | re.I)
body = m.group(0)
caps = []
for ln in body.splitlines():
    t = ln.split()
    if t and t[0][0] in "Cc" and len(t) >= 4:
        try:
            caps.append((t[1], t[2], val(t[3])))
        except ValueError:
            print("skip:", ln)
node = defaultdict(float)
pair = defaultdict(float)
for a, b, c in caps:
    node[a] += c
    node[b] += c
    pair[tuple(sorted((a, b)))] += c
print(f"{len(caps)} parasitic capacitors in {path.name}")
for a, b in pairs:
    print(f"C({a}-{b}) = {pair.get(tuple(sorted((a, b))), 0.0) * 1e15:.2f} fF")
for nd in nodes:
    print(f"{nd:4s} total = {node[nd] * 1e15:6.2f} fF; largest:", ", ".join(
        f"{(b if a == nd else a)} {c * 1e15:.2f}" for (a, b), c in sorted(pair.items(), key=lambda kv: -kv[1])
        if nd in (a, b))[:200])
