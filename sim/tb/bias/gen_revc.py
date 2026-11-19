#!/usr/bin/env python3
"""Deck generator for the B1 rev C benches (docs/research/B1-bias-report.md s8).

usage: gen_revc.py OUT.cir KIND --corner tt --temp 27 [--vdd 3.3] [--irefs 1e-6,...] [--mode 0|1|2|3]

KIND
  idac   bias_master + rails + ladder + bias_vi/string (for the internal reference) and the five
         current DACs (rev C allocation) with outputs held at realistic line voltages
         (vbn lines 0.6 V, vbp lines 2.6 V).  For every Iref and code:  D <iref> <code> I0..I4 Ist
         (A, magnitude), plus 'N' lines with the ladder node voltages.
  vout   bias_b1 top level (receivers inside), ib_r1 held at 2.5 V.  For every Iref (incl. 0 and the
         internal reference) and every code of the three resistor DACs and of the vth_ref VDAC:
         V <iref> <code> el vreset_src vth_cmp vth_ref   and   B <iref> vbn_prb I(ib_r1) tvi I(vdd)
  tran   bias_b1: bias_en 0 -> 1 at 10 us (startup), then code steps on the resistor DACs at 60 us
         and on vth_ref at 80 us; writes a wrdata file OUT.dat.
"""
import argparse

P = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
CORNER = {"tt": ("typical", "res_typical"), "ff": ("ff", "res_ff"), "ss": ("ss", "res_ss"),
          "fs": ("fs", "res_typical"), "sf": ("sf", "res_typical")}
MODES = {0: (1, 0, 0, 0), 1: (0, 1, 0, 0), 2: (0, 0, 1, 1), 3: (1, 0, 0, 1)}   # s0 s1 stim intref
IDACS = [(0, "p", "vgp5", 0.6), (1, "p", "vgp3", 0.6), (2, "n", "vgn5", 2.6), (3, "p", "vgp6", 0.6),
         (4, "n", "vgn3", 2.6)]


def header(a, title):
    mos, res = CORNER[a.corner]
    dio = {"ff": "ff", "ss": "ss"}.get(a.corner, "typical")
    L = [f"* {title}  corner={a.corner} temp={a.temp} vdd={a.vdd}",
         f".include {P}/design.ngspice",
         f".lib {P}/sm141064.ngspice {mos}", f".lib {P}/sm141064.ngspice {res}",
         f".lib {P}/sm141064.ngspice diode_{dio}",
         f".include {a.cells}/bias_all.spice",
         f".temp {a.temp}",
         ".option gmin=1e-18 abstol=1e-17 reltol=1e-5 itl1=1000 itl6=1000",
         f"Vdd vdd 0 {a.vdd}"]
    return L


def pad(a):
    s0, s1, st, ir = MODES[a.mode]
    L = ["Iref 0 pad DC 0" if a.mode in (0, 1) else "Rpad pad 0 1e12"]
    for n, v in (("s0", s0), ("s1", s1), ("stim", st), ("intref", ir), ("en", 1)):
        L.append(f"V{n} {n} 0 {a.vdd if v else 0}")
    return L


def idac_bench(a):
    L = header(a, "B1 rev C current DACs") + pad(a)
    L += ["Rst stimout 0 1e9", "Vibx ib_x2 0 0", "Vib1 ib_r1 0 2.5",
          "Xm pad in_n in_p vbp_st stimout iint s0 s1 stim intref en en_b vdd 0 bias_master",
          "Vst vbp_st 0 2.6",
          "Xr vsn vsp vgln vglp en_b vdd 0 bias_rails",
          "Xg in_n in_p vgn3 vgn5 vgp3 vgp5 vgp6 vsn vsp vgln vglp vdd 0 bias_ladder",
          "Xvi vgln vglp en ib_x2 el vr vc vt vbn_prb ib_r1 iint vdd 0 bias_vi",
          "Rel el 0 50k", "Rvr vr 0 45k", "Rvc vc 0 55k", "Rvt vt 0 70k"]
    for b in range(5):
        L.append(f"Vb{b} b{b} 0 0")
    bits = " ".join(f"b{b}" for b in range(5))
    for k, pol, g, v in IDACS:
        if pol == "n":
            L.append(f"Xi{k} o{k} vdd {bits} {g} vsn {a.ncas} vdd 0 idac_n")
        else:
            L.append(f"Xi{k} o{k} 0 {bits} {g} vsp {a.pcas} vdd 0 idac_p")
        L.append(f"Vo{k} o{k} 0 {v}")
    L += [".control", "set noaskquit"]
    meas = " ".join(f"$&i(vo{k})" for k, *_ in IDACS) + " $&i(vst)"
    codes = [int(c) for c in a.codes.split(",")] if a.codes != "all" else list(range(32))
    for iref in a.irefs:
        if a.mode in (0, 1):
            L.append(f"alter iref dc={iref}")
        prev = None
        for c in codes:
            for b in range(5):
                bit = (c >> b) & 1
                if prev is None or ((prev >> b) & 1) != bit:
                    L.append(f"alter vb{b} {a.vdd if bit else 0}")
            prev = c
            L.append("op")
            if c == codes[0]:
                L.append(f'echo "N {iref}" $&v(xm.nd) $&v(pad) $&v(in_n) $&v(in_p) $&v(vgp3) $&v(vgp5) $&v(vgp6) '
                         '$&v(vgn3) $&v(vgn5) $&v(vsn) $&v(vsp) $&v(iint)')
            L.append(f'echo "D {iref} {c}" {meas}')
            L.append("destroy all")
    L += ["quit", ".endc", ".end"]
    return L


def top_inst(a):
    dig = ([f"i{k}_b{b}" for k in range(5) for b in range(5)] + [f"r{k}_b{b}" for k in range(3) for b in range(5)]
           + [f"v0_c{b}" for b in range(6)] + ["s0", "s1", "stim", "intref", "en", "ibx2"])
    ana = ("vbn_leak vbn_ref vbp_syn vbn_ax vbp_w vbp_st vbn_prb vth_ref el vreset_src vth_cmp ib_r1 "
           "stimout pad").split()
    L = ["X1 " + " ".join(dig + ana) + " vdd 0 bias_b1", "Rst stimout 0 1e9", "Vib1 ib_r1 0 2.5"]
    for n in [f"i{k}_b{b}" for k in range(5) for b in range(5)]:
        L.append(f"V{n} {n} 0 {a.vdd if n.endswith('b4') else 0}")       # current DACs at code 16
    for k in range(3):
        for b in range(5):
            L.append(f"Vr{k}_{b} r{k}_b{b} 0 0")
    for b in range(6):
        L.append(f"Vv{b} v0_c{b} 0 0")
    L.append("Vibx2 ibx2 0 0")
    for c in ("vth_ref", "el", "vreset_src", "vth_cmp"):
        L.append(f"C{c} {c} 0 2p")
    return L


def vout_bench(a):
    L = header(a, "B1 rev C voltage path") + pad(a) + top_inst(a)
    L += [".control", "set noaskquit"]
    for iref in a.irefs:
        if a.mode in (0, 1):
            L.append(f"alter iref dc={iref}")
        prev = None
        for c in range(64):
            rc = min(c, 31)
            for b in range(6):
                bit = (c >> b) & 1
                if prev is None or ((prev >> b) & 1) != bit:
                    L.append(f"alter vv{b} {a.vdd if bit else 0}")
                if b < 5:
                    rbit = (rc >> b) & 1
                    if prev is None or ((min(prev, 31) >> b) & 1) != rbit:
                        for k in range(3):
                            L.append(f"alter vr{k}_{b} {a.vdd if rbit else 0}")
            prev = c
            L.append("op")
            if c == 0:
                L.append(f'echo "B {iref}" $&v(vbn_prb) $&i(vib1) $&v(x1.vglp) $&i(vdd) $&v(x1.x) $&v(x1.xvi.vgvi) '
                         '$&v(x1.xvi.vbt) $&v(x1.xvi.ns) $&v(pad)')
            L.append(f'echo "V {iref} {c}" $&v(el) $&v(vreset_src) $&v(vth_cmp) $&v(vth_ref)')
            L.append("destroy all")
    L += ["quit", ".endc", ".end"]
    return L


def tran_bench(a):
    L = header(a, "B1 rev C startup / settling") + pad(a)
    L = [x if not x.startswith("Ven ") else "" for x in L]
    L = [x.replace("Ven en 0 3.3", "") for x in L]
    L = [x for x in L if not x.startswith("Ven")]
    L.append(f"Ven en 0 PWL(0 0 10u 0 10.01u {a.vdd})")
    L += top_inst(a)
    # resistor DAC codes 0 -> 31 at 60 us, vth_ref 0 -> 63 at 80 us
    L = [x for x in L if not (x.startswith("Vr") or x.startswith("Vv"))]
    for k in range(3):
        for b in range(5):
            L.append(f"Vr{k}_{b} r{k}_b{b} 0 PWL(0 0 60u 0 60.01u {a.vdd})")
    for b in range(6):
        L.append(f"Vv{b} v0_c{b} 0 PWL(0 0 80u 0 80.01u {a.vdd})")
    if a.mode in (0, 1):
        L = [x if not x.startswith("Iref") else f"Iref 0 pad DC {a.irefs[0]}" for x in L]
    L += [".control", "set noaskquit", "tran 20n 100u",
          f"wrdata {a.out[:-4]}.dat v(el) v(vreset_src) v(vth_cmp) v(vth_ref) v(vbn_prb) i(vib1) v(x1.xvi.vgvi) "
          "v(x1.vglp) v(vbp_st) v(vbn_leak)", "quit", ".endc", ".end"]
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("kind")
    ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
    ap.add_argument("--vdd", type=float, default=3.3); ap.add_argument("--mode", type=int, default=0)
    ap.add_argument("--irefs", default="1e-7,1e-6,1e-5"); ap.add_argument("--codes", default="0,1,2,4,8,16,31")
    ap.add_argument("--pcas", default="vgln")   # idac_p switch level (vgln as in bias_b1; vglp tested, no change)
    ap.add_argument("--cells", default="/work/cells/bias")
    ap.add_argument("--ncas", default="vgln")   # idac_n switch level (vgln as in bias_b1 rev C)
    a = ap.parse_args()
    a.irefs = [float(x) for x in a.irefs.split(",")]
    L = {"idac": idac_bench, "vout": vout_bench, "tran": tran_bench}[a.kind](a)
    open(a.out, "w", newline="\n").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
