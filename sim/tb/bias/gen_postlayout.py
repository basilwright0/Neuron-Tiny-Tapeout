#!/usr/bin/env python3
"""Post-layout spot check (typical corner): extracted (PEX) leaf cells next to the schematic ones.

usage: gen_postlayout.py OUT.cir --mode idac|vdac|vdactran
 idac     : schematic master/rails/rangegen; idac_n + idac_p from the schematic AND from
            layout/bias/out/<cell>_pex.spice, same inputs, outputs held at 1 V; ranges 0 and 3, codes 0..31.
            echo "D r code In_sch Ip_sch In_pex Ip_pex"
 vdac     : schematic vref_string64; vdac6 schematic and PEX on the same taps; codes 0..63
            echo "D code v_sch v_pex"
 vdactran : code 0 -> 63 -> 32 -> 31 into 1 pF + 20 gates, schematic and PEX side by side.
PEX subckts are renamed <cell>_pex and instantiated by port name.
"""
import argparse
import re
from pathlib import Path
from gen_idac import header, chain, digital, set_range

ROOT = Path("/work")


def pex(cell):
    txt = (ROOT / f"layout/bias/out/{cell}_pex.spice").read_text()
    txt = re.sub(r"\n\+", " ", txt)
    m = re.search(rf"^\.subckt\s+{cell}\s+(.*)$", txt, re.M)
    ports = m.group(1).split()
    txt = re.sub(rf"^\.subckt\s+{cell}\b", f".subckt {cell}_pex", txt, flags=re.M)
    out = ROOT / f"sim/tb/bias/out/postlayout/{cell}_pex.spice"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt)
    return out, ports


ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--mode", default="idac")
a = ap.parse_args()
a.corner, a.temp, a.seed, a.iref, a.noshift = "tt", 27, 0, 8e-6, False
mode = a.mode
a.mode = 0
L = header(a, f"B1 post-layout spot check {mode}")
if mode == "idac":
    L += chain(a) + digital(a)
    gn = {f"g{r}": f"vgn{r}" for r in range(6)}
    gp = {f"g{r}": f"vgp{r}" for r in range(6)}
    common = {f"b{b}": f"b{b}" for b in range(5)}
    common.update(vdd="vdd", vss="0", VSUBS="0")
    for pol in ("n", "p"):
        f, ports = pex(f"idac_{pol}")
        L.append(f".include {f}")
        m = dict(common)
        if pol == "n":
            m.update(gn, vsn="vsn", vcas="vglp", dump="vdd", roff="roff", **{f"r{r}": f"r{r}" for r in range(6)})
        else:
            m.update(gp, vsp="vsp", vcas="vgln", dump="0", rboff="rboff", **{f"rb{r}": f"rb{r}" for r in range(6)})
        m["out"] = f"o{pol}x"
        L.append(f"XX{pol} " + " ".join(m[p] for p in ports) + f" idac_{pol}_pex")
        L.append(f"Vo{pol}x o{pol}x 0 1.0")
    seln = " ".join(f"r{r}" for r in range(6)) + " roff " + " ".join(f"b{b}" for b in range(5))
    selp = " ".join(f"rb{r}" for r in range(6)) + " rboff " + " ".join(f"b{b}" for b in range(5))
    L.append(f"XSn ons vdd {seln} " + " ".join(f"vgn{r}" for r in range(6)) + " vsn vglp vdd 0 idac_n")
    L.append(f"XSp ops 0 {selp} " + " ".join(f"vgp{r}" for r in range(6)) + " vsp vgln vdd 0 idac_p")
    L += ["Vons ons 0 1.0", "Vops ops 0 1.0", ".control", "set noaskquit"]
    for r in (0, 3):
        L += set_range(r)
        prev = None
        for code in range(32):
            for b in range(5):
                bit = (code >> b) & 1
                if prev is None or ((prev >> b) & 1) != bit:
                    L.append(f"alter vb{b} {3.3 if bit else 0}")
            prev = code
            L += ["op", f'echo "D {r} {code}" $&i(vons) $&i(vops) $&i(vonx) $&i(vopx)', "destroy all"]
    L += ["quit", ".endc", ".end"]
else:
    taps = " ".join(f"t{k}" for k in range(64))
    f, ports = pex("vdac6")
    L += [f".include {f}", "Vg en_b 0 0", f"Xs {taps} en_b vdd 0 vref_string64"]
    if mode == "vdac":
        L += [f"Vc{b} c{b} 0 0" for b in range(6)]
    else:
        seq = [(0, 0), (5e-6, 63), (15e-6, 32), (25e-6, 31)]
        for b in range(6):
            v0 = 3.3 if (seq[0][1] >> b) & 1 else 0
            pw = [f"0 {v0}"]; prev = v0
            for t, cc in seq[1:]:
                v = 3.3 if (cc >> b) & 1 else 0
                pw.append(f"{t:g} {prev} {t + 2e-9:g} {v}"); prev = v
            L.append(f"Vc{b} c{b} 0 PWL({' '.join(pw)})")
    m = {f"t{k}": f"t{k}" for k in range(64)}
    m.update({f"c{b}": f"c{b}" for b in range(6)}, vdd="vdd", vss="0", VSUBS="0", out="ox")
    L.append("XX " + " ".join(m[p] for p in ports) + " vdac6_pex")
    L.append(f"XS os {taps} " + " ".join(f"c{b}" for b in range(6)) + " vdd 0 vdac6")
    for o in ("ox", "os"):
        L.append(f"C{o} {o} 0 1p")
        for k in range(20):
            L.append(f"XG{o}{k} 0 {o} 0 0 nfet_03v3 W=2u L=1u")
    L += [".control", "set noaskquit"]
    if mode == "vdac":
        for code in range(64):
            for b in range(6):
                L.append(f"alter vc{b} {3.3 if (code >> b) & 1 else 0}")
            L += ["op", f'echo "D {code}" $&v(os) $&v(ox)', "destroy all"]
    else:
        L += ["tran 5n 35u", "set wr_singlescale", "set wr_vecnames", f"wrdata {a.out[:-4]}.dat v(os) v(ox)"]
    L += ["quit", ".endc", ".end"]
open(a.out, "w", newline="\n").write("\n".join(L) + "\n")
