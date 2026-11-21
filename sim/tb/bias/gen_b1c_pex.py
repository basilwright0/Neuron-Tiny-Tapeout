#!/usr/bin/env python3
"""b1c (MIL-133): IDAC re-pack PEX check.  The rev C current-DAC bench of gen_revc.py (master, rails,
ladder, V-to-I, the five DACs at their taps and line voltages), with each DAC instantiated three times on
the same gate line: schematic, extracted baseline layout (m2-compact 960e089) and extracted re-packed
layout.  All 32 codes.   echo "D iref code  I0..I4(sch)  I0..I4(base)  I0..I4(new)"

usage: gen_b1c_pex.py OUT.cir --corner tt --temp 27 --irefs 1e-7,1e-6
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_revc as R   # noqa: E402

ROOT = Path("/work")
SRC = {"base": ROOT / "sim/tb/bias/out/b1c/basebias/layout/bias/out",
       "new": ROOT / "layout/bias/out"}


def pex(cell, tag):
    txt = (SRC[tag] / f"{cell}_pex.spice").read_text()
    txt = re.sub(r"\n\+", " ", txt)
    ports = re.search(rf"^\.subckt\s+{cell}\s+(.*)$", txt, re.M).group(1).split()
    # rename every subckt (device wrappers too) so the two extractions cannot collide
    names = re.findall(r"^\.subckt\s+(\S+)", txt, re.M)
    for nm in sorted(set(names), key=len, reverse=True):
        txt = re.sub(rf"(?<![\w]){re.escape(nm)}(?![\w])", f"{nm}_{tag}", txt)
    out = ROOT / f"sim/tb/bias/out/b1c/{cell}_{tag}_pex.spice"
    out.write_text(txt)
    return out, ports


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
    ap.add_argument("--irefs", default="1e-7,1e-6")
    a = ap.parse_args()
    a.vdd, a.mode, a.pcas, a.ncas, a.cells, a.codes = 3.3, 0, "vgln", "vgln", "/work/cells/bias", "all"
    a.irefs = [float(x) for x in a.irefs.split(",")]
    L = R.idac_bench(a)
    ctl = L.index(".control")
    body, tail = L[:ctl], L[ctl:]
    inc, extra = [], []
    bits = {f"b{b}": f"b{b}" for b in range(5)}
    for tag in ("base", "new"):
        ports = {}
        for cell in ("idac_n", "idac_p"):
            f, ports[cell] = pex(cell, tag)
            inc.append(f".include {f}")
        for k, pol, g, v in R.IDACS:
            cell = f"idac_{pol}"
            m = dict(bits, out=f"o{k}{tag}", dump="vdd" if pol == "n" else "0", g=g, vsn="vsn", vsp="vsp",
                     vcas="vgln", vdd="vdd", vss="0")
            extra.append(f"X{tag}{k} " + " ".join(m[p] for p in ports[cell]) + f" {cell}_{tag}")
            extra.append(f"Vo{k}{tag} o{k}{tag} 0 {v}")
    meas_old = " ".join(f"$&i(vo{k})" for k, *_ in R.IDACS) + " $&i(vst)"
    meas = " ".join(f"$&i(vo{k}{t})" for t in ("", "base", "new") for k, *_ in R.IDACS)
    tail = [ln.replace(meas_old, meas) for ln in tail if not ln.startswith('echo "N')]
    open(a.out, "w", newline="\n").write("\n".join(body + inc + extra + tail) + "\n")


if __name__ == "__main__":
    main()
