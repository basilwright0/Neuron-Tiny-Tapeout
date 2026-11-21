#!/usr/bin/env python3
"""b1a (M3): DC rail voltages of the extracted bias_rails (current layout) vs bias_rails_c (re-pack) vs schematic.

usage (in the EDA container, from the repo root):  python3 sim/tb/bias/gen_rails_pex.py sim/tb/bias/out/b1a
Runs ngspice .op at tt/ss/ff x 0/27/85 C, en_b = 0, with an optional DC load on each rail
(vsn sinks +iload, vsp sources -iload: the IDAC return currents) and prints one table.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORNER = {"tt": ("typical", "res_typical"), "ff": ("ff", "res_ff"), "ss": ("ss", "res_ss")}
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
NETS = ["vsp", "vgln", "vglp", "vsn"]


def pex(cell):
    lines = (ROOT / "layout/bias/out" / f"{cell}_pex.spice").read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(f".subckt {cell} "))
    head = lines[i].split()[2:]
    for ln in lines[i + 1:]:
        if not ln.startswith("+"):
            break
        head += ln[1:].split()
    txt = re.sub(rf"\b{cell}\b", f"{cell}_pex", "\n".join(lines))
    (OUT / f"{cell}_pex.inc").write_text(txt + "\n")
    return head


ports = {c: pex(c) for c in ("bias_rails", "bias_rails_c")}
sch_ports = "vsn vsp vgln vglp en_b vdd vss".split()
rows = []
for corner in ("tt", "ss", "ff"):
    for temp in (0, 27, 85):
        for iload in (0.0, 2e-6):
            mos, res = CORNER[corner]
            L = [f"* rails pex {corner} {temp} iload={iload}", f".include {P}/design.ngspice",
                 f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
                 ".include /work/cells/bias/bias_rails.spice"]
            L += [f".include {OUT}/{c}_pex.inc" for c in ports]
            L += [f".temp {temp}", ".option gmin=1e-15", "Vdd vdd 0 3.3", "Ven en_b 0 0"]
            for tag, cell, pp in (("s", "bias_rails", sch_ports), ("a", "bias_rails_pex", ports["bias_rails"]),
                                  ("b", "bias_rails_c_pex", ports["bias_rails_c"])):
                m = {n: f"{n}_{tag}" for n in NETS}
                m.update(en_b="en_b", vdd="vdd", vss="0")
                L.append(f"X{tag} " + " ".join(m[p] for p in pp) + f" {cell}")
                L.append(f"Iln{tag} 0 vsn_{tag} {iload}")      # idac_n return current flows into vsn
                L.append(f"Ilp{tag} vsp_{tag} 0 {iload}")      # idac_p draws its current out of vsp
            L += [".control", "op", "print " + " ".join(f"v({n}_{t})" for t in "sab" for n in NETS), ".endc", ".end"]
            f = OUT / f"rails_{corner}_{temp}_{int(iload*1e6)}u.cir"
            f.write_text("\n".join(L) + "\n")
            o = subprocess.run(["ngspice", "-b", str(f)], capture_output=True, text=True).stdout
            v = {k.lower(): float(x) for k, x in re.findall(r"v\((\w+)\)\s*=\s*([-+0-9.eE]+)", o)}
            rows.append((corner, temp, iload, [v[f"{n}_{t}"] for t in "sab" for n in NETS]))
with open(OUT / "rails_pex_summary.txt", "w") as fh:
    hdr = "corner T iload | " + " ".join(f"{n}_sch" for n in NETS) + " | dV(old pex - sch) mV | dV(new pex - old pex) mV"
    print(hdr); fh.write(hdr + "\n")
    worst = 0.0
    for c, t, il, v in rows:
        s, a, b = v[0:4], v[4:8], v[8:12]
        worst = max(worst, max(abs(y - x) for x, y in zip(a, b)))
        ln = (f"{c} {t:2d} {il*1e6:.0f}u | " + " ".join(f"{x:.4f}" for x in s) + " | "
              + " ".join(f"{(y-x)*1e3:+.2f}" for x, y in zip(s, a)) + " | " + " ".join(f"{(y-x)*1e3:+.3f}" for x, y in zip(a, b)))
        print(ln); fh.write(ln + "\n")
    fh.write(f"worst |new - old| = {worst*1e3:.3f} mV\n"); print(f"worst |new - old| = {worst*1e3:.3f} mV")
