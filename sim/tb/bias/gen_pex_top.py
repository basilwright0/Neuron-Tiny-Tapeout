#!/usr/bin/env python3
"""Top-level PEX spot check (rev C): extracted bias_b1 (layout/bias/out/bias_b1_pex.spice, all coupling caps)
next to the schematic bias_b1, identical stimuli.  DC at tt 27 C for S = 10 / 100 / 1000 (EXT /1) and three
code sets (all codes 0, mid, full scale); prints every analog output of both.

usage: gen_pex_top.py OUT.cir
prints  T <iref> <set> <out1_sch> <out1_pex> ...   (outputs in OUTS order; currents for ib_r1)
"""
import sys
from pathlib import Path

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
OUTS = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w", "vbp_st", "vbn_prb", "vth_ref", "el",
        "vreset_src", "vth_cmp"]


def ports_of(txt, cell):
    lines = txt.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(f".subckt {cell} "))
    head = lines[i].split()[2:]
    for ln in lines[i + 1:]:
        if not ln.startswith("+"):
            break
        head += ln[1:].split()
    return head


def main():
    out = sys.argv[1]
    sch = Path("/work/cells/bias/bias_b1.spice").read_text()
    sports = ports_of(sch, "bias_b1")
    ptxt = Path("/work/layout/bias/out/bias_b1_pex.spice").read_text()
    pports = ports_of(ptxt, "bias_b1")
    import re
    # every subckt defined in the PEX file gets a _pex suffix (leaf names collide with the schematic cells)
    for name in sorted(set(re.findall(r"^\.subckt (\S+)", ptxt, re.M)), key=len, reverse=True):
        ptxt = re.sub(r"(?<![\w.])" + re.escape(name) + r"(?!\w)", name + "_pex", ptxt)
    inc = Path(out).parent / "bias_b1_pex.inc"
    inc.write_text(ptxt)
    dig = [p for p in sports if re.match(r"(i\d|r\d)_b\d|v0_c\d|ua0_s0|ua0_s1|ua0_stim$|ua0_int|bias_en|ib_x2", p)]
    L = ["* B1 rev C top-level PEX spot check, tt 27 C", f".include {P}/design.ngspice",
         f".lib {P}/sm141064.ngspice typical", f".lib {P}/sm141064.ngspice res_typical",
         f".lib {P}/sm141064.ngspice diode_typical",
         ".include /work/cells/bias/bias_all.spice", f".include {inc}", ".temp 27",
         ".option gmin=1e-18 abstol=1e-17 reltol=1e-5 itl1=1000 itl6=1000", "Vdd vdd 0 3.3"]
    for d in dig:
        v = 3.3 if d in ("ua0_s0", "bias_en") else 0
        L.append(f"V_{d} {d} 0 {v}")
    for tag, cell, ports in (("s", "bias_b1", sports), ("p", "bias_b1_pex", pports)):
        conn = {p: p for p in dig}
        conn.update({o: f"{o}_{tag}" for o in OUTS})
        conn.update({"ua0": f"pad_{tag}", "ib_r1": f"ibr_{tag}", "ua0_stim_out": f"so_{tag}", "vdd": "vdd",
                     "vss": "0", "VSS": "0", "VDD": "vdd"})
        missing = [p for p in ports if p not in conn]
        assert not missing, missing
        L.append(f"X{tag} " + " ".join(conn[p] for p in ports) + f" {cell}")
        L += [f"Iref_{tag} 0 pad_{tag} DC 1e-6", f"Vib_{tag} ibr_{tag} 0 2.5", f"Rso_{tag} so_{tag} 0 1e9"]
        for o in ("el", "vreset_src", "vth_cmp", "vth_ref"):
            L.append(f"C{o}_{tag} {o}_{tag} 0 2p")
    sets = {"zero": 0, "mid": 16, "full": 31}
    L += [".control", "set noaskquit"]
    for iref in (1e-7, 1e-6, 1e-5):
        L += [f"alter iref_s dc={iref}", f"alter iref_p dc={iref}"]
        for nm, code in sets.items():
            for d in dig:
                m = re.match(r"(i\d|r\d)_b(\d)", d) or re.match(r"(v0)_c(\d)", d)
                if m:
                    c = code * 2 + (1 if code == 31 else 0) if m.group(1) == "v0" else code
                    L.append(f"alter v_{d} dc={3.3 if (c >> int(m.group(2))) & 1 else 0}")
            L.append("op")
            vals = " ".join(f"$&v({o}_s) $&v({o}_p)" for o in OUTS) + " $&i(vib_s) $&i(vib_p)"
            L.append(f'echo "T {iref} {nm}" {vals}')
            L.append("destroy all")
    L += ["quit", ".endc", ".end"]
    Path(out).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
