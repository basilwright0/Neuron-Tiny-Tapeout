#!/usr/bin/env python3
"""MIL-133 vdac: schematic sweep of vdacr_vc R_base (same 5 bits, LSB 2/3 sq) at tt/ss/ff x 0/27/85.
One bias_rails + bias_vi chain feeds one vdacr_vc copy per candidate base (each copy gets its own vth_cmp
mirror output: the bias_vi vth_cmp output drives the first candidate; the others are fed by identical bias_vi copies).
usage: vdac_rbase_sweep.py OUT.cir --corner tt --temp 27 --bases 53,59,60,61
prints  P <code> v_<base> ...
"""
import argparse, re
from pathlib import Path
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORNER = {"tt": ("typical", "res_typical", "typical"), "ff": ("ff", "res_ff", "ff"), "ss": ("ss", "res_ss", "ss")}
src = Path("/work/cells/bias/bias_vi.spice").read_text()
vc = re.search(r"^\.subckt vdacr_vc .*?^\.ends vdacr_vc$", src, re.M | re.S).group(0)


def sq2l(sq, W=1.0):
    return round(sq * (W - 2 * 0.0148) / 0.005) * 0.005


def variant(base):
    pieces = int(-(-base // 15))
    body = [ln for ln in vc.splitlines() if not ln.startswith("XRB")]
    nodes = ["out"] + [f"rb{i}" for i in range(1, pieces)] + ["n0"]
    rb = [f"XRB{i} {nodes[i]} {nodes[i+1]} vss ppolyf_u_1k r_width=1u r_length={sq2l(base / pieces):.3f}u"
          for i in range(pieces)]
    body = [body[0].replace("vdacr_vc", f"vdacr_vc{base}")] + rb + body[1:-1] + [f".ends vdacr_vc{base}"]
    return "\n".join(body)


ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", default="27")
ap.add_argument("--bases", default="53,59,60,61")
a = ap.parse_args()
bases = [int(x) for x in a.bases.split(",")]
mos, res, dio = CORNER[a.corner]
L = [f"* vdac R_base sweep {a.corner} {a.temp}", f".include {P}/design.ngspice",
     f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}", f".lib {P}/sm141064.ngspice diode_{dio}",
     ".include /work/cells/bias/bias_all.spice", f".temp {a.temp}", ".option gmin=1e-15 reltol=1e-5",
     "Vdd vdd 0 3.3", "Ven en 0 3.3", "Venb en_b 0 0", "Vibx ib_x2 0 0"]
L += [f"Vc{b} c{b} 0 0" for b in range(5)]
for B in bases:
    L.append(variant(B))
    t = f"b{B}"
    L.append(f"Xr{t} vsn{t} vsp{t} vgln{t} vglp{t} en_b vdd 0 bias_rails")
    L.append(f"Xvi{t} vgln{t} vglp{t} en ib_x2 el{t} vr{t} vc{t} vt{t} prb{t} ibr{t} iint{t} vdd 0 bias_vi")
    L += [f"Vib{t} ibr{t} 0 2.5", f"Rii{t} iint{t} 0 100k", f"Xel{t} el{t} c0 c1 c2 c3 c4 vdd 0 vdacr_el",
          f"Xvr{t} vr{t} c0 c1 c2 c3 c4 vdd 0 vdacr_vr", f"Xvt{t} vt{t} c0 c1 c2 c3 c4 0 vdd 0 vdacr_vt"]
    L.append(f"Xd{t} vc{t} c0 c1 c2 c3 c4 vdd 0 vdacr_vc{B}")
L += [".control", "set noaskquit"]
prev = None
for code in range(32):
    for b in range(5):
        bit = (code >> b) & 1
        if prev is None or ((prev >> b) & 1) != bit:
            L.append(f"alter vc{b} dc={3.3 if bit else 0}")
    prev = code
    L += ["op", f'echo "P {code}" ' + " ".join(f"$&v(vcb{B})" for B in bases), "destroy all"]
L += ["quit", ".endc", ".end"]
Path(a.out).write_text("\n".join(L) + "\n")
