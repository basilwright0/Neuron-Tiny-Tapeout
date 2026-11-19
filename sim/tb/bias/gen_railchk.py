#!/usr/bin/env python3
"""Rail re-check after the MIM -> MOS decap swap (rev B rails).

usage: gen_railchk.py OUT.cir --corner tt --temp 27 --mode ac|tran|glitch [--rails bias_rails]

Victims: one idac_n and one idac_p at range 3 code 19 (~150 pA design point), outputs held at 1 V.
 ac     : VDD carries AC 1 V; echo |dI/I| per volt of VDD at several frequencies + |v(vsn)|, |v(vsp)|.
 tran   : VDD steps +50 mV (1 ns edge) at 20 us and back at 120 us; victim currents and rails.
 glitch : six aggressor idacs (4 p, 2 n, range 0, the largest currents) switch code 0 <-> 31 together at
          20 us and back at 120 us (worst-case rail kick); victim currents and rails.
--rails selects the rail cell: bias_rails (rev B: accumulation caps to own supply), bias_rails_cross
(rev A orientation: vsn->vdd, vsp->vss), bias_rails_nocap.
"""
import argparse
from gen_idac import header, chain

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--corner", default="tt"); ap.add_argument("--temp", type=float, default=27)
ap.add_argument("--mode", default="ac"); ap.add_argument("--rails", default="bias_rails")
a = ap.parse_args()
a.seed = 0; a.iref = 8e-6; a.mode_ = a.mode; a.noshift = False
mode = a.mode
a.mode = 0
L = header(a, f"B1 rail check {mode} rails={a.rails}")
if mode == "ac":
    L[-1] = "Vdd vdd 0 DC 3.3 AC 1"
elif mode == "tran":
    L[-1] = "Vdd vdd 0 PWL(0 3.3 20u 3.3 20.001u 3.35 120u 3.35 120.001u 3.3)"
L += chain(a, rails=a.rails)
gn = " ".join(f"vgn{r}" for r in range(6))
gp = " ".join(f"vgp{r}" for r in range(6))
# victim selects: range 3 code 19
L += [f"Vv{r} vr{r} 0 {3.3 if r == 3 else 0}" for r in range(6)]
L += [f"Vvb{r} vrb{r} 0 {0 if r == 3 else 3.3}" for r in range(6)]
L += ["Vvoff vroff 0 0", "Vvboff vrboff 0 3.3"]
L += [f"Vc{b} c{b} 0 {3.3 if (19 >> b) & 1 else 0}" for b in range(5)]
cb = " ".join(f"c{b}" for b in range(5))
L.append(f"XVN on vdd {' '.join(f'vr{r}' for r in range(6))} vroff {cb} {gn} vsn vglp vdd 0 idac_n")
L.append(f"XVP op 0 {' '.join(f'vrb{r}' for r in range(6))} vrboff {cb} {gp} vsp vgln vdd 0 idac_p")
L += ["Von on 0 1.0", "Vop op 0 1.0"]
# aggressors: range 0, code toggled (glitch mode) or 0 (others)
L += [f"Va{r} ar{r} 0 {3.3 if r == 0 else 0}" for r in range(6)]
L += [f"Vab{r} arb{r} 0 {0 if r == 0 else 3.3}" for r in range(6)]
L += ["Vaoff aroff 0 0", "Vaboff arboff 0 3.3"]
if mode == "glitch":
    L.append("Vag ag 0 PWL(0 0 20u 0 20.005u 3.3 120u 3.3 120.005u 0)")
else:
    L.append("Vag ag 0 0")
ab = " ".join(["ag"] * 5)
for k in range(4):
    L.append(f"XAP{k} ap{k} 0 {' '.join(f'arb{r}' for r in range(6))} arboff {ab} {gp} vsp vgln vdd 0 idac_p")
    L.append(f"XRP{k} ap{k} vdd 0 rx_n4")
for k in range(2):
    L.append(f"XAN{k} an{k} vdd {' '.join(f'ar{r}' for r in range(6))} aroff {ab} {gn} vsn vglp vdd 0 idac_n")
    L.append(f"XRN{k} an{k} vdd 0 rx_p1")
L += [".control", "set noaskquit"]
if mode == "ac":
    L += ["op", "let in0 = -i(von)", "let ip0 = i(vop)",
          'echo "DC" $&v(vsn) $&v(vsp) $&in0 $&ip0',
          "ac dec 10 100 1e8"]
    fs = [100, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
    # unit gate-source disturbance (what modulates the unit current; the held-output current also
    # carries displacement current through junction caps, which is not a bias error)
    L += ["let sn = mag(i(von))", "let sp = mag(i(vop))", "let mvsn = mag(v(vsn))", "let mvsp = mag(v(vsp))",
          "let dgn = mag(v(vgn3)-v(vsn))", "let dgp = mag(v(vsp)-v(vgp3))"]
    for f in fs:
        L += [f"meas ac a_sn find sn at={f:g}", f"meas ac a_sp find sp at={f:g}",
              f"meas ac a_vn find mvsn at={f:g}", f"meas ac a_vp find mvsp at={f:g}",
              f"meas ac a_gn find dgn at={f:g}", f"meas ac a_gp find dgp at={f:g}",
              f'echo "F {f:g}" $&a_sn $&a_sp $&a_vn $&a_vp $&a_gn $&a_gp']
    L += ["meas ac pk_gn max dgn", "meas ac pk_gp max dgp", 'echo "PK" $&pk_gn $&pk_gp']
else:
    L += ["tran 20n 200u", "let in = -i(von)", "let ip = i(vop)",
          "set wr_singlescale", "set wr_vecnames",
          f"wrdata {a.out[:-4]}.dat in ip v(vsn) v(vsp) v(vgn3) v(vgp3)"]
L += ["quit", ".endc", ".end"]
open(a.out, "w", newline="\n").write("\n".join(L) + "\n")
