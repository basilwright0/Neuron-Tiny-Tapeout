"""b1c (MIL-133): unit-device mismatch MC for the IDAC unit-size study.

N instances per geometry in one .op; with sw_stat_mismatch=1 every instance gets its own draw.
nfet: source 0.30 V (vsn), gate vgn, drain 1.0 V.  pfet: source 3.00 V (vsp), gate vgp, drain 2.3 V.
usage (in the EDA container): python3 b1c_unit_mc.py OUT.cir N SEED VGN VGP [nomm]
"""
import sys

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
G = [(2, 2), (2, 1), (1, 2), (1, 1)]


def main():
    out, n, seed, vgn, vgp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    mm = len(sys.argv) < 7
    L = ["* b1c unit MC", f".include {P}/design.ngspice"]
    if mm:
        L += [".param sw_stat_mismatch=1", f".option seed={seed}"]
    L += [f".lib {P}/sm141064.ngspice typical", ".temp 27", ".option gmin=1e-18 abstol=1e-17 reltol=1e-6",
          "Vsn sn 0 0.3", "Vsp sp 0 3.0", f"Vgn gn 0 {vgn}", f"Vgp gp 0 {vgp}", "Vdn dn 0 1.0",
          "Vdp dp 0 2.3", "Vdd vdd 0 3.3"]
    pr = []
    for (w, l) in G:
        for k in range(n):
            t = f"{w}{l}x{k}"
            L += [f"Vn{t} dn n{t} 0", f"XN{t} n{t} gn sn 0 nfet_03v3 W={w}u L={l}u",
                  f"Vp{t} p{t} dp 0", f"XP{t} p{t} gp sp vdd pfet_03v3 W={w}u L={l}u"]
            pr += [f"i(Vn{t})", f"i(Vp{t})"]
    L += [".control", "op", "set width=400"]
    L += [f"print {v}" for v in pr]
    L += [".endc", ".end"]
    open(out, "w").write("\n".join(L) + "\n")


main()
