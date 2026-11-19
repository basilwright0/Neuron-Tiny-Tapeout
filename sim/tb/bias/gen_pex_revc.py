#!/usr/bin/env python3
"""PEX spot check (rev C): extracted bias_vi + vdacr_el + vdacr_vt (layout/bias/out/<cell>_pex.spice, all
coupling caps) next to the schematic cells, each chain on its own bias_rails.  DC code sweeps of el (32)
and vth_ref (64), plus a 0 -> full-scale step transient.

usage: gen_pex_revc.py OUT.cir [--corner tt --temp 27]
prints  P <code> el_sch el_pex vt_sch vt_pex   and wrdata OUT.dat for the transient
"""
import argparse
import re
from pathlib import Path

ROOT = Path("/work")
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CELLS = ["bias_vi", "vdacr_el", "vdacr_vt"]


def pex(cell):
    txt = (ROOT / "layout" / "bias" / "out" / f"{cell}_pex.spice").read_text()
    lines = txt.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(f".subckt {cell} "))
    head = lines[i].split()[2:]
    for ln in lines[i + 1:]:
        if not ln.startswith("+"):
            break
        head += ln[1:].split()
    ports = head
    txt = re.sub(rf"\b{cell}\b", f"{cell}_pex", txt)
    return txt, ports


def inst(name, cell, ports, conn):
    return f"{name} " + " ".join(conn.get(p, p) for p in ports) + f" {cell}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--corner", default="typical"); ap.add_argument("--temp", default="27")
    ap.add_argument("--tran", action="store_true")
    a = ap.parse_args()
    L = [f"* B1 rev C PEX spot check {a.corner} {a.temp}", f".include {P}/design.ngspice",
         f".lib {P}/sm141064.ngspice {a.corner}", f".lib {P}/sm141064.ngspice res_typical",
         ".include /work/cells/bias/bias_all.spice", f".temp {a.temp}",
         ".option gmin=1e-15 reltol=1e-5", "Vdd vdd 0 3.3",
         "Ven en 0 PWL(0 0 2u 0 2.01u 3.3)" if a.tran else "Ven en 0 3.3",
         "Venb en_b 0 PWL(0 3.3 2u 3.3 2.01u 0)" if a.tran else "Venb en_b 0 0",
         "Vibx ib_x2 0 0"]
    ports = {}
    for c in CELLS:
        txt, ports[c] = pex(c)
        p = Path(a.out).parent / f"{c}_pex.inc"
        p.write_text(txt)
        L.append(f".include {p}")
    for b in range(6):
        L.append(f"Vc{b} c{b} 0 PWL(0 0 10u 0 10.01u 3.3)" if a.tran else f"Vc{b} c{b} 0 0")
    for tag, suf in (("s", ""), ("p", "_pex")):
        L.append(f"Xr{tag} vsn{tag} vsp{tag} vgln{tag} vglp{tag} en_b vdd 0 bias_rails")
        conn = {"vgln": f"vgln{tag}", "vglp": f"vglp{tag}", "en": "en", "ib_x2": "ib_x2", "el": f"el{tag}",
                "vreset_src": f"vr{tag}", "vth_cmp": f"vc{tag}", "vth_ref": f"vt{tag}", "vbn_prb": f"prb{tag}",
                "ib_r1": f"ibr{tag}", "iint": f"iint{tag}", "vdd": "vdd", "vss": "0", "VSS": "0", "VDD": "vdd"}
        cvi = "bias_vi" + suf
        L.append(inst(f"Xvi{tag}", cvi, ports["bias_vi"] if suf else
                      "vgln vglp en ib_x2 el vreset_src vth_cmp vth_ref vbn_prb ib_r1 iint vdd vss".split(), conn))
        L += [f"Rvr{tag} vr{tag} 0 45k", f"Rvc{tag} vc{tag} 0 55k", f"Vib{tag} ibr{tag} 0 2.5", f"Rii{tag} iint{tag} 0 100k"]
        ce = {"out": f"el{tag}", "vdd": "vdd", "vss": "0", **{f"b{b}": f"c{b}" for b in range(5)}}
        ct = {"out": f"vt{tag}", "vdd": "vdd", "vss": "0", **{f"b{b}": f"c{b}" for b in range(6)}}
        L.append(inst(f"Xe{tag}", "vdacr_el" + suf, ports["vdacr_el"] if suf else "out b0 b1 b2 b3 b4 vdd vss".split(), ce))
        L.append(inst(f"Xt{tag}", "vdacr_vt" + suf, ports["vdacr_vt"] if suf else "out b0 b1 b2 b3 b4 b5 vdd vss".split(), ct))
        L += [f"Cl{tag}e el{tag} 0 2p", f"Cl{tag}t vt{tag} 0 2p"]
    L += [".control", "set noaskquit"]
    if a.tran:
        L += ["tran 5n 20u", f"wrdata {a.out[:-4]}.dat v(els) v(elp) v(vts) v(vtp)", "quit", ".endc", ".end"]
        Path(a.out).write_text(chr(10).join(L) + chr(10))
        return
    prev = None
    for code in range(64):
        for b in range(6):
            bit = (code >> b) & 1
            if prev is None or ((prev >> b) & 1) != bit:
                L.append(f"alter vc{b} dc={3.3 if bit else 0}")
        prev = code
        L += ["op", f'echo "P {code}" $&v(els) $&v(elp) $&v(vts) $&v(vtp)', "destroy all"]
    L += ["quit", ".endc", ".end"]
    Path(a.out).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
