"""A1 sizing check: off-state leakage of a vw reset nfet / 2-stack (st2: 2 x 0.22/2, st3: 2 x 0.22/1; gate 0, drain 0.45 V)
vs the decay current Itau (3 x 0.22/15 stack on vbn_leak, Ib_leak 324 pA), at ff/fs/typical 85 C and typical 27 C.
usage: python3 sim/tb/tier2/tb_ioff.py"""
import sys
sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
import subprocess
from ngs import header
C = {"r05x028": (0.5, 0.28), "r022x1": (0.22, 1.0), "r022x2": (0.22, 2.0), "r022x4": (0.22, 4.0)}
for corner, temp in (("typical", 27), ("typical", 85), ("ff", 85), ("fs", 85)):
    L = [header(corner, temp), include("neuron/membrane.spice"), "Ibl 0 vb 324p", "Xbl vb 0 nmaster"]
    for k, (w, l) in C.items():
        L.append(f"V{k} d{k} 0 0.45\nX{k} d{k} 0 0 0 nfet_03v3 W={w}u L={l}u")
    L.append("Vtau dtau 0 0.45\nXt1 dtau vb m1 0 nfet_03v3 W=0.22u L=15u\nXt2 m1 vb m2 0 nfet_03v3 W=0.22u L=15u\n"
             "Xt3 m2 vb 0 0 nfet_03v3 W=0.22u L=15u")
    L.append("Vst2 dst2 0 0.45\nXs1 dst2 0 ms 0 nfet_03v3 W=0.22u L=2u\nXs2 ms 0 0 0 nfet_03v3 W=0.22u L=2u")
    L.append("Vst3 dst3 0 0.45\nXr1 dst3 0 mr 0 nfet_03v3 W=0.22u L=1u\nXr2 mr 0 0 0 nfet_03v3 W=0.22u L=1u")
    names = list(C) + ["st2", "st3", "tau"]
    txt = "\n".join(L) + "\n.control\nop\n" + "\n".join(f"print -i(V{k})" for k in names) + "\nquit\n.endc\n.end\n"
    p = OUT / f"ioff_{corner}_{temp}.cir"; p.write_text(txt)
    r = subprocess.run(["ngspice", "-b", str(p)], cwd=OUT, capture_output=True, text=True)
    vals = [ln.split("=")[1].strip() for ln in r.stdout.splitlines() if ln.strip().startswith("-i(")]
    print(corner, temp, dict(zip(names, vals)))
