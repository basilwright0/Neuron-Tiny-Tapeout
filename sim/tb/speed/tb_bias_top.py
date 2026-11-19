"""Speed track: B1 rev C top level (bias_b1, receivers inside) -> neuron-side currents vs master current.

usage: python3 sim/tb/speed/tb_bias_top.py   -> sim/results/speed/bias_top_summary.txt
bias_b1 in EXT /1 mode, I_nd = Iref = 1, 3, 10, 30, 100 uA (S = 100 ... 10000), codes fixed at the S = 100
nominal (tt 27): leak 9, ref 14, syn 16, ax 9, w 8. Each gate line drives one consumer replica:
  vbn_leak -> nfet 2/4, drain 0.5 V (leak tail; neuron = line/4)    vbn_ref -> nfet 2/4, drain 2.0 V (line/2)
  vbp_syn  -> pfet 2/4, drain 1.34 V (weight, 1:1)                  vbn_ax  -> nfet 2/4, drain 0.5 V (1:1)
  vbp_w    -> pfet 1/2, drain 1.3 V (AdEx XPW)                      vbp_st  -> pfet 1/2, drain 1.5 V (det starve)
Ratio = I_consumer(S) / (I_consumer(S = 100, same corner) * S/100): 1.0 = the line tracks the master.
Also code 31 (max) and the code a per-die calibration would need (nominal code / ratio; > 31 = out of range).
The cells' gate lines also carry the real array load only as gates (DC: no current), so DC is exact.
"""
import sys

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402

import subprocess  # noqa: E402

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORN = {"tt": ("typical", "res_typical", "typical"), "ss": ("ss", "res_ss", "ss"), "ff": ("ff", "res_ff", "ff"),
        "sf": ("sf", "res_typical", "typical"), "fs": ("fs", "res_typical", "typical")}
CODES = {0: 9, 1: 14, 2: 16, 3: 9, 4: 8}
IREFS = [1e-6, 3e-6, 10e-6, 30e-6, 100e-6]
LINES = ["leak", "ref", "syn", "ax", "w", "st"]
CASES = [("tt", 27), ("ss", 0), ("ff", 85), ("sf", 0), ("fs", 85), ("ss", 85)]


def deck(c, t, code_over=None):
    mos, res, dio = CORN[c]
    L = [f"* bias top {c} {t}", f".include {P}/design.ngspice", f".lib {P}/sm141064.ngspice {mos}",
         f".lib {P}/sm141064.ngspice {res}", f".lib {P}/sm141064.ngspice diode_{dio}",
         ".include /work/cells/bias/bias_all.spice", f".temp {t}",
         ".option gmin=1e-18 abstol=1e-17 reltol=1e-5 itl1=1000 itl6=1000", "Vdd vdd 0 3.3",
         "Iref 0 pad DC 1u"]
    dig = []
    for k in range(5):
        code = CODES[k] if code_over is None else code_over
        for b in range(5):
            n = f"i{k}_b{b}"
            dig.append(n)
            L.append(f"V{n} {n} 0 {3.3 if (code >> b) & 1 else 0}")
    for k in range(3):
        for b in range(5):
            dig.append(f"r{k}_b{b}"); L.append(f"Vr{k}_{b} r{k}_b{b} 0 {3.3 if b == 4 else 0}")
    for b in range(6):
        dig.append(f"v0_c{b}"); L.append(f"Vv{b} v0_c{b} 0 {3.3 if b == 5 else 0}")
    for n, v in (("s0", 3.3), ("s1", 0), ("stim", 0), ("intref", 0), ("en", 3.3), ("ibx2", 0)):
        dig.append(n); L.append(f"V{n} {n} 0 {v}")
    ana = "vbn_leak vbn_ref vbp_syn vbn_ax vbp_w vbp_st vbn_prb vth_ref el vreset_src vth_cmp ib_r1 stimout pad"
    L.append("X1 " + " ".join(dig) + " " + ana + " vdd 0 bias_b1")
    L += ["Rst stimout 0 1e9", "Vib1 ib_r1 0 2.5",
          "Vc0 c0 0 0.5\nXc0 c0 vbn_leak 0 0 nfet_03v3 W=2u L=4u",
          "Vc1 c1 0 2.0\nXc1 c1 vbn_ref 0 0 nfet_03v3 W=2u L=4u",
          "Vc2 c2 0 1.34\nXc2 c2 vbp_syn vdd vdd pfet_03v3 W=2u L=4u",
          "Vc3 c3 0 0.5\nXc3 c3 vbn_ax 0 0 nfet_03v3 W=2u L=4u",
          "Vc4 c4 0 1.3\nXc4 c4 vbp_w vdd vdd pfet_03v3 W=1u L=2u",
          "Vc5 c5 0 1.5\nXc5 c5 vbp_st vdd vdd pfet_03v3 W=1u L=2u",
          ".control", "set noaskquit"]
    for i in IREFS:
        L += [f"alter iref dc={i}", "op",
              f'echo "R {i}" $&i(vc0) $&i(vc1) $&i(vc2) $&i(vc3) $&i(vc4) $&i(vc5) $&v(vbn_leak) $&v(vbn_ref) '
              '$&v(vbp_syn) $&v(vbn_ax) $&v(vbp_w) $&v(vbp_st)', "destroy all"]
    L += ["quit", ".endc", ".end"]
    return "\n".join(L) + "\n"


def sim(c, t, code_over=None):
    tag = f"biastop_{c}_{t}_{'nom' if code_over is None else code_over}"
    cir = RESULTS / f"{tag}.cir"
    cir.write_text(deck(c, t, code_over))
    p = subprocess.run(["ngspice", "-b", str(cir)], capture_output=True, text=True, cwd=RESULTS)
    (RESULTS / f"{tag}.log").write_text(p.stdout + p.stderr)
    out = {}
    for l in p.stdout.splitlines():
        if l.startswith("R "):
            x = l.split()
            out[float(x[1])] = [abs(float(v)) for v in x[2:8]] + [float(v) for v in x[8:14]]
    return out


L = ["B1 rev C top level, EXT /1: neuron-side current ratio I(S)/(I(S=100)*S/100) at the S = 100 codes "
     f"{CODES} (leak ref syn ax w), consumer replicas; 'need' = code a recalibration needs (>31: out of range)"]
for c, t in CASES:
    nom = sim(c, t)
    mx = sim(c, t, 31)
    L.append(f"--- {c} {t}C   I at S=100 (pA): " + " ".join(f"{n} {nom[1e-6][k]*1e12:.0f}" for k, n in enumerate(LINES)))
    L.append("   S     " + " ".join(f"{n:>6s}" for n in LINES) + "  | need code: leak ref syn ax w | code31/nominal-target: leak ref syn ax w | line V: leak ref syn ax w st")
    for i in IREFS:
        S = i / 1e-6 * 100
        r = [nom[i][k] / (nom[1e-6][k] * S / 100) for k in range(6)]
        need = [CODES[k] / r[k] for k in range(5)]
        head = [mx[i][k] / (nom[1e-6][k] * S / 100) for k in range(5)]
        L.append(f" {S:6.0f} " + " ".join(f"{x:6.3f}" for x in r) + "  | " + " ".join(f"{x:4.1f}" for x in need)
                 + " | " + " ".join(f"{x:5.2f}" for x in head) + " | " + " ".join(f"{v:.2f}" for v in nom[i][6:]))
txt = "\n".join(L)
print(txt)
(RESULTS / "bias_top_summary.txt").write_text(txt + "\n")
