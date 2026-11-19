"""Summarise magic PEX (ext2spice cthresh 0) for slot_ah: Cfb (spk-vm coupling) and vm node capacitance.

    python3 pex_summary.py [out/slot_ah_pex.spice]

Capacitors in the extracted netlist are wiring parasitics only (gate/junction caps live in the device
models), so the vm 'total' below = wiring C on vm. The membrane capacitor itself (mcap 7.07x7.07,
~200 fF) and the gate loads of the leak/detector/follower are added from the models in simulation.
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


path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("out") / "slot_ah_pex.spice")
txt = path.read_text()
# top subckt only
cell = sys.argv[2] if len(sys.argv) > 2 else "slot_ah"
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

cfb = pair.get(tuple(sorted(("spk", "vm"))), 0.0)
print(f"{len(caps)} parasitic capacitors in {path.name}")
print(f"Cfb  (spk-vm coupling, MOM + routing) = {cfb * 1e15:.2f} fF   (target 8 fF +-25 %: 6.0 .. 10.0)")
print(f"vm   total wiring capacitance          = {node['vm'] * 1e15:.2f} fF")
print("vm   breakdown (to other nodes):")
for (a, b), c in sorted(pair.items(), key=lambda kv: -kv[1]):
    if "vm" in (a, b):
        other = b if a == "vm" else a
        print(f"       {other:14s} {c * 1e15:8.3f} fF")
print(f"vr   total wiring capacitance          = {node['vr'] * 1e15:.2f} fF")
print(f"spk  total wiring capacitance          = {node['spk'] * 1e15:.2f} fF")
