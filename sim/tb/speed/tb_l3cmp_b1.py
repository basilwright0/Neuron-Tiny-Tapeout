"""Level-3 CMP (docs/m2-level3-proposal.md 2.1): B1 top level (bias_b1) -> vbn_prb, the new CMP leg current
and the vth_cmp DAC range, across S (Iref, EXT /1), ib_x2 and BIAS_EN, per corner.

usage: python3 sim/tb/speed/tb_l3cmp_b1.py  -> sim/results/level3_cmp/b1_summary.txt
Loads on vbn_prb: three replicas of the slot_cmp_h leg (XNC nfet W/2 gate vbn_prb -> XPC pfet 1/2 diode), W = 1/2/4 u
(0.5 / 1 / 2 uA nominal), each with a det_cmp tail replica XPT (pfet 1/2 on the leg's vbp_cmp, drain 2.2 V).
vth_cmp: r2 code 0 and 31 (all other r/v codes at the tb_bias_top defaults).
"""
import os
import subprocess
from pathlib import Path

RES = Path(os.environ.get("L3_RESULTS", "/work/sim/results/level3_cmp"))
RES.mkdir(parents=True, exist_ok=True)
INC = "/work/cells/bias/bias_all.spice"
P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORN = {"tt": ("typical", "res_typical", "typical"), "ss": ("ss", "res_ss", "ss"), "ff": ("ff", "res_ff", "ff"),
        "sf": ("sf", "res_typical", "typical"), "fs": ("fs", "res_typical", "typical")}
CASES = [("tt", 27), ("ss", 0), ("ff", 85), ("sf", 0), ("fs", 85), ("ss", 85), ("ff", 0)]
IREFS = [0.1e-6, 1e-6, 10e-6, 100e-6]          # S = 10, 100, 1000, 10000
LEGS = {"i05": "1u", "i1": "2u", "i2": "4u"}


def deck(c, t):
    mos, res, dio = CORN[c]
    L = [f"* l3cmp b1 {c} {t}", f".include {P}/design.ngspice", f".lib {P}/sm141064.ngspice {mos}",
         f".lib {P}/sm141064.ngspice {res}", f".lib {P}/sm141064.ngspice diode_{dio}",
         f".include {INC}", f".temp {t}",
         ".option gmin=1e-18 abstol=1e-17 reltol=1e-5 itl1=1000 itl6=1000", "Vdd vdd 0 3.3", "Iref 0 pad DC 1u"]
    dig = []
    codes = {0: 9, 1: 14, 2: 16, 3: 9, 4: 8}
    for k in range(5):
        for b in range(5):
            n = f"i{k}_b{b}"; dig.append(n); L.append(f"V{n} {n} 0 {3.3 if (codes[k] >> b) & 1 else 0}")
    for k in range(3):
        for b in range(5):
            dig.append(f"r{k}_b{b}"); L.append(f"Vr{k}_{b} r{k}_b{b} 0 {3.3 if b == 4 else 0}")
    for b in range(6):
        dig.append(f"v0_c{b}"); L.append(f"Vv{b} v0_c{b} 0 {3.3 if b == 5 else 0}")
    for n, v in (("s0", 3.3), ("s1", 0), ("stim", 0), ("intref", 0), ("en", 3.3), ("ibx2", 0)):
        dig.append(n); L.append(f"V{n} {n} 0 {v}")
    ana = "vbn_leak vbn_ref vbp_syn vbn_ax vbp_w vbp_st vbn_prb vth_ref el vreset_src vth_cmp ib_r1 stimout pad"
    L.append("X1 " + " ".join(dig) + " " + ana + " vdd 0 bias_b1")
    L += ["Rst stimout 0 1e9", "Vib1 ib_r1 0 2.5"]
    for k, w in LEGS.items():
        L += [f"XNC{k} dn{k} vbn_prb 0 0 nfet_03v3 W={w} L=2u", f"Vl{k} c{k} dn{k} 0",
              f"XPC{k} c{k} c{k} vdd vdd pfet_03v3 W=1u L=2u",
              f"Vt{k} tt{k} 0 2.2", f"XPT{k} tt{k} c{k} vdd vdd pfet_03v3 W=1u L=2u"]
    L += [".control", "set noaskquit"]
    for en in (3.3, 0):
        for x2 in (0, 3.3):
            for i in IREFS:
                for code in (0, 31):
                    L += [f"alter ven dc={en}", f"alter vibx2 dc={x2}", f"alter iref dc={i}"]
                    L += [f"alter vr2_{b} dc={3.3 if (code >> b) & 1 else 0}" for b in range(5)]
                    L += ["op", f'echo "R {en} {x2} {i} {code}" $&v(vbn_prb) $&v(vth_cmp) $&v(vbp_st) '
                          + " ".join(f"$&i(vl{k}) $&i(vt{k}) $&v(c{k})" for k in LEGS), "destroy all"]
    L += ["quit", ".endc", ".end"]
    return "\n".join(L) + "\n"


def sim(c, t):
    tag = f"l3b1_{c}_{t}"
    cir = RES / f"{tag}.cir"
    cir.write_text(deck(c, t))
    p = subprocess.run(["ngspice", "-b", str(cir)], capture_output=True, text=True, cwd=RES)
    (RES / f"{tag}.log").write_text(p.stdout + p.stderr)
    rows = []
    for l in p.stdout.splitlines():
        if l.startswith("R "):
            x = l.split()
            rows.append([float(v) for v in x[1:]])
    return rows


L = ["Level-3 CMP leg off vbn_prb (bias_b1 top, EXT /1, Iref = S/100 uA). Columns: en ib_x2 S | vbn_prb (V) | "
     "vth_cmp code0 / code31 (V) | leg I and tail I (uA) for i05 / i1 / i2 | vbp_cmp(i1) (V) | vbp_st (V)"]
for c, t in CASES:
    rows = sim(c, t)
    L.append(f"--- {c} {t}C")
    by = {}
    for r in rows:
        by[(r[0], r[1], r[2], int(r[3]))] = r[4:]
    for en in (3.3, 0):
        for x2 in (0, 3.3):
            for i in IREFS:
                a, b = by[(en, x2, i, 0)], by[(en, x2, i, 31)]
                legs = " ".join(f"{abs(b[3 + 3 * j]) * 1e6:6.3f}/{abs(b[4 + 3 * j]) * 1e6:6.3f}" for j in range(3))
                L.append(f" en={int(en > 1)} x2={int(x2 > 1)} S={i / 1e-6 * 100:6.0f} | {b[0]:.4f} | {a[1]:.4f} / "
                         f"{b[1]:.4f} | {legs} | {b[3 + 3 * 1 + 2]:.3f} | {b[2]:.3f}")
txt = "\n".join(L)
print(txt)
(RES / "b1_summary.txt").write_text(txt + "\n")
