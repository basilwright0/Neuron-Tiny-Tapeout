#!/usr/bin/env python3
"""MIL-133 B1-b: PEX DC check of the re-packed vdacr_* leaves against the current (M2) layout.

Three identical schematic chains (bias_rails + bias_vi) each feed the 4 DACs: schematic (s), extracted
current layout (old) and extracted re-packed layout (new); all coupling caps kept.  64 codes (5-bit DACs see
code & 31).  PEX netlists: layout/bias/m3pack/{old,new}_vdacr_<k>.spice (from m3pack/pex.sh).

usage: gen_pex_pack.py OUT.cir --corner tt --temp 27
prints  P <code> el_s el_old el_new vr_s ... vt_new
"""
import argparse
import re
from pathlib import Path

ROOT = Path("/work")
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORNER = {"tt": ("typical", "res_typical", "typical"), "ff": ("ff", "res_ff", "ff"), "ss": ("ss", "res_ss", "ss")}
DACS = {"el": 5, "vr": 5, "vc": 5, "vt": 6}
VIOUT = {"el": "el", "vr": "vreset_src", "vc": "vth_cmp", "vt": "vth_ref"}


def pex(tag, k, outdir):
    cell = f"vdacr_{k}_{tag}"
    txt = (ROOT / "layout/bias/m3pack" / f"{tag}_vdacr_{k}.spice").read_text()
    subs = [m.group(1) for m in re.finditer(r"^\.subckt (\S+)", txt, re.M) if m.group(1) != cell]
    for s in subs:   # device subckts are shared names between files -> make them unique
        txt = re.sub(rf"(?<![\w#]){re.escape(s)}(?![\w#])", f"{s}__{tag}{k}", txt)
    lines = txt.splitlines()
    i = next(j for j, ln in enumerate(lines) if ln.startswith(f".subckt {cell} "))
    ports = lines[i].split()[2:]
    for ln in lines[i + 1:]:
        if not ln.startswith("+"):
            break
        ports += ln[1:].split()
    p = Path(outdir) / f"{cell}.inc"
    p.write_text(txt)
    return cell, ports, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", default="27")
    a = ap.parse_args()
    mos, res, dio = CORNER[a.corner]
    L = [f"* B1-b vdacr re-pack PEX check {a.corner} {a.temp}", f".include {P}/design.ngspice",
         f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
         f".lib {P}/sm141064.ngspice diode_{dio}",
         ".include /work/cells/bias/bias_all.spice", f".temp {a.temp}",
         ".option gmin=1e-15 reltol=1e-5", "Vdd vdd 0 3.3", "Ven en 0 3.3", "Venb en_b 0 0", "Vibx ib_x2 0 0"]
    for b in range(6):
        L.append(f"Vc{b} c{b} 0 0")
    sig = []
    for tag in ("s", "old", "new"):
        L.append(f"Xr{tag} vsn{tag} vsp{tag} vgln{tag} vglp{tag} en_b vdd 0 bias_rails")
        L.append(f"Xvi{tag} vgln{tag} vglp{tag} en ib_x2 el{tag} vr{tag} vc{tag} vt{tag} prb{tag} ibr{tag} "
                 f"iint{tag} vdd 0 bias_vi")
        L += [f"Vib{tag} ibr{tag} 0 2.5", f"Rii{tag} iint{tag} 0 100k"]
        for k, nb in DACS.items():
            conn = {"out": f"{k}{tag}", "vdd": "vdd", "vss": "0", "VSUBS": "0", **{f"b{b}": f"c{b}" for b in range(nb)}}
            if tag == "s":
                cell, ports = f"vdacr_{k}", ["out"] + [f"b{b}" for b in range(nb)] + ["vdd", "vss"]
            else:
                cell, ports, inc = pex(tag, k, Path(a.out).parent)
                L.append(f".include {inc}")
            L.append(f"X{k}{tag} " + " ".join(conn[p] for p in ports) + f" {cell}")
    for k in DACS:
        sig += [f"$&v({k}{t})" for t in ("s", "old", "new")]
    L += [".control", "set noaskquit"]
    prev = None
    for code in range(64):
        for b in range(6):
            bit = (code >> b) & 1
            if prev is None or ((prev >> b) & 1) != bit:
                L.append(f"alter vc{b} dc={3.3 if bit else 0}")
        prev = code
        L += ["op", f'echo "P {code}" ' + " ".join(sig), "destroy all"]
    L += ["quit", ".endc", ".end"]
    Path(a.out).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
