#!/usr/bin/env python3
"""Deck generator for the B1 idac testbenches.

usage: gen_idac.py OUT.cir --corner tt --temp 27 [--vout 1.0] [--seed N] [--nidac K]
                   [--ranges 0,1,2,3,4,5] [--noshift] [--iref 8e-6] [--m 1]
                   [--vsweep]   (output-compliance sweep instead of code sweep)

The deck instantiates the full chain bias_master -> bias_rails -> bias_rangegen and
K idac_n + K idac_p instances whose outputs are held by voltage sources at --vout.
For every selected range and every fine code (0..31) one .op is run and a line
    D <range> <code> <I_n1> .. <I_nK> <I_p1> .. <I_pK>
is echoed (currents in A, positive = magnitude delivered/sunk at the output).
"""
import argparse

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORNER = {"tt": ("typical", "res_typical", "mimcap_typical"),
          "ff": ("ff", "res_ff", "mimcap_ff"),
          "ss": ("ss", "res_ss", "mimcap_ss"),
          "fs": ("fs", "res_typical", "mimcap_typical"),
          "sf": ("sf", "res_typical", "mimcap_typical")}


def header(a, title):
    mos, res, mim = CORNER[a.corner]
    L = [f"* {title}  corner={a.corner} temp={a.temp} seed={a.seed}",
         f".include {P}/design.ngspice"]
    if a.seed:
        L += [".param sw_stat_mismatch=1", f".option seed={a.seed}"]
    L += [f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
          f".lib {P}/sm141064.ngspice {mim}",
          ".include /work/cells/bias/bias_all.spice",
          f".temp {a.temp}",
          ".option gmin=1e-18 abstol=1e-17 reltol=1e-5 itl1=500 itl6=500",
          "Vdd vdd 0 3.3"]
    return L


def chain(a):
    L = [f"Iref 0 pad DC {a.iref}"]
    for k in range(4):
        L.append(f"Vm{k} m{k} 0 {3.3 if (a.m >> k) & 1 else 0}")
    L.append("Xm pad in_n in_p m0 m1 m2 m3 vdd 0 bias_master")
    if a.noshift:
        L += ["Vsn vsn 0 0", "Vsp vsp 0 3.3", "Xr vsnx vspx vgln vglp vdd 0 bias_rails"]
    else:
        L.append("Xr vsn vsp vgln vglp vdd 0 bias_rails")
    L.append("Xg in_n in_p " + " ".join(f"vgn{r}" for r in range(6)) + " "
             + " ".join(f"vgp{r}" for r in range(6)) + " vsn vsp vgln vglp vdd 0 bias_rangegen")
    return L


def digital(a):
    L = []
    for r in range(6):
        L.append(f"Vr{r} r{r} 0 0")
    L.append("Vroff roff 0 3.3")
    for b in range(5):
        L.append(f"Vb{b} b{b} 0 0")
    return L


def idacs(a):
    L = []
    sel = " ".join(f"r{r}" for r in range(6)) + " roff " + " ".join(f"b{b}" for b in range(5))
    for k in range(1, a.nidac + 1):
        L.append(f"XN{k} on{k} vdd {sel} " + " ".join(f"vgn{r}" for r in range(6)) + " vsn vglp vdd 0 idac_n")
        L.append(f"Von{k} on{k} 0 {a.vout}")
        L.append(f"XP{k} op{k} 0 {sel} " + " ".join(f"vgp{r}" for r in range(6)) + " vsp vgln vdd 0 idac_p")
        L.append(f"Vop{k} op{k} 0 {a.vout}")
    return L


def meas(a):
    n = " ".join(f"$&i(von{k})" for k in range(1, a.nidac + 1))
    p = " ".join(f"$&i(vop{k})" for k in range(1, a.nidac + 1))
    return n, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--corner", default="tt")
    ap.add_argument("--temp", type=float, default=27); ap.add_argument("--vout", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--nidac", type=int, default=1)
    ap.add_argument("--ranges", default="0,1,2,3,4,5"); ap.add_argument("--noshift", action="store_true")
    ap.add_argument("--iref", type=float, default=8e-6); ap.add_argument("--m", type=int, default=1)
    ap.add_argument("--vsweep", action="store_true"); ap.add_argument("--codes", default="all")
    a = ap.parse_args()
    L = header(a, "B1 idac DC") + chain(a) + digital(a) + idacs(a)
    L += [".control", "set noaskquit"]
    L.append("op")
    L.append('echo "RAILS" $&v(vsn) $&v(vsp) $&v(vgln) $&v(vglp) $&v(in_n) $&v(in_p) $&v(xm.nd)')
    L.append('echo "VGN" ' + " ".join(f"$&v(vgn{r})" for r in range(6)))
    L.append('echo "VGP" ' + " ".join(f"$&v(vgp{r})" for r in range(6)))
    L.append("destroy all")
    n, p = meas(a)
    codes = list(range(32)) if a.codes == "all" else [int(c) for c in a.codes.split(",")]
    L.append("alter vroff 0")
    for r in [int(x) for x in a.ranges.split(",")]:
        for rr in range(6):
            L.append(f"alter vr{rr} {3.3 if rr == r else 0}")
        if a.vsweep:
            for b in range(5):
                L.append(f"alter vb{b} {3.3 if (codes[0] >> b) & 1 else 0}")
            vs = [0.2 + 0.05 * i for i in range(59)]   # 0.2 .. 3.1 V
            for v in vs:
                for k in range(1, a.nidac + 1):
                    L.append(f"alter von{k} {v:.3f}"); L.append(f"alter vop{k} {v:.3f}")
                L.append("op")
                L.append(f'echo "V {r} {v:.3f}" {n} {p}')
                L.append("destroy all")
            continue
        prev = None
        for c in codes:
            for b in range(5):
                bit = (c >> b) & 1
                if prev is None or ((prev >> b) & 1) != bit:
                    L.append(f"alter vb{b} {3.3 if bit else 0}")
            prev = c
            L.append("op")
            L.append(f'echo "D {r} {c}" {n} {p}')
            L.append("destroy all")
    L += ["quit", ".endc", ".end"]
    open(a.out, "w", newline="\n").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
