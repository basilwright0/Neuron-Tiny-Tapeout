# E2: `e2_leak` reset-switch leakage test cell (R2, MIL-362)

Two floating ~210 fF vm-like nodes, each with a probe tap copied from the array. Generator `layout/e2/e2gen.py`, flow
`layout/e2/build.sh` (magic + netgen + KLayout). Deliverables are in `layout/e2/final/`. Benches: `sim/tb/e2/`.

```
 vreset ─┬─[SA 1/0.5]──────────────────── na ──┬── CA (nfet 8.56/5.84, S/D/B = vss)   na ── tap A (en_a)
         ├─[SB1 1/0.5]── mid ──[SB2 1/0.5]── nb ──┬── CB (same)                     nb ── tap B (en_b)
         └─[NC 1/0.28, clamp_en]── cx ──[NG 1/0.28, gb]── mid
   SA/SB1/SB2 gates = grp_en;  gb = NOT grp_en (local CMOS inverter PI/NI 1/0.28, static)
 tap (x2): vdd ─[MF 4/2, g = node]─ p ─[ME 1/0.28, en]─ s ─[MB 2/2, vbn_prb]─ vss
                                     p ─[SC en]─[SW rsel]─[SB sub]─ abus     (switches 1/0.28; as the array XPM_*)
```

**Rev B modes (clamp_en = GRP_EN[2] = cfg_out[2]).** With clamp_en = 0 (the reset default), mid floats once grp_en
is released, so nb sits behind a plain 2-stack. With clamp_en = 1 and grp_en = 0, NC and NG hold mid at vreset, which
is the rev A behaviour. The clamp is now all-nMOS (gates at 3.3 V), so it passes vreset down to 0 V. The rev A pMOS
(gate = grp_en = 0) could only pull mid down to about |Vtp|. Neither mode has a static current: the inverter is CMOS
and the clamp only carries leakage.

**Cell:** 30.83 × 11.80 µm (364 µm²), 21 devices. Magic DRC 0, KLayout DRC 0 (gf180mcu deck, variant D, no density),
netgen "Circuits match uniquely". Logs: `layout/e2/final/e2_leak_{magic_drc,klayout_drc_summary,lvs_report}.txt`.

## Pins (labels on the top cell, each touching the cell edge; origin = lower-left corner)

| pin | layer | edge | x (centre) | width | pin | layer | edge | x | width |
|---|---|---|---|---|---|---|---|---|---|
| en_a | Metal2 | bottom | 2.00 | 0.30 | vbn_prb | Metal2 | bottom | 22.40 | 0.30 |
| rsel | Metal2 | bottom | 3.20 | 0.30 | grp_en | Metal2 | bottom | 23.60 | 0.30 |
| sub | Metal2 | bottom | 4.40 | 0.30 | vreset | Metal2 | bottom | 24.80 | 0.30 |
| abus | Metal2 | bottom | 5.60 | 0.30 | en_b | Metal2 | bottom | 26.00 | 0.30 |
| clamp_en | Metal2 | bottom | 27.20 | 0.30 | | | | | |
| vss | Metal2 | left | y 6.00 | 0.40 | vdd | Metal2 | right | y 6.00 | 0.30 |

Bottom pins are on a 1.2 µm pitch (0.9 µm edge-to-edge gap). Routed metal stays ≥ 0.36 µm inside the box edge.
`na` and `nb` are Metal1 test labels (not ports). Top-level hookup: en_a = `en_c2`, en_b = `en_c3`, rsel = `probe_rsel[3]`,
sub = `probe_sub`, grp_en = GRP_EN[0], clamp_en = GRP_EN[2] (cfg_out[2]). The rev A pins did not move;
clamp_en is new.

## Results (PEX; `sim/tb/e2/results/summary.md`, JSON per corner)

### Junction-leakage floor (vreset constant, clamp_en = 1; nb = na to 3 digits)

| corner | vreset | C (na = nb) | dV/dt | t −10 / −100 mV | release step na / nb | reset to 1 mV | I(vdd), grp_en = 0 | tap offset A / B / array |
|---|---|---|---|---|---|---|---|---|
| tt/27 | 1.0 | 208 fF | -0.0038 mV/s | 44 min / 7.3 h | -5.4 / -12.8 mV | ≤ 9 ns | 0.788 pA | -811 / -804 / -809 mV |
| ss/0 | 1.0 | 193 fF | -3.5e-05 mV/s | 3.3 d / 33 d | -6.2 / -13.7 mV | ≤ 9 ns | 0.00364 pA | -900 / -891 / -897 mV |
| ff/85 | 1.0 | 217 fF | -9.2 mV/s | 1.1 s / 11 s | -5.3 / -12.8 mV | ≤ 9 ns | 424 pA | -696 / -690 / -695 mV |
| tt/27 | 1.5 | 213 fF | -0.0033 mV/s | 51 min / 8.5 h | -4.9 / -9.3 mV | ≤ 15 ns | 0.843 pA | -968 / -963 / -967 mV |
| ss/0 | 1.5 | 205 fF | -0.0073 mV/s | 23 min / 3.9 h | -5.0 / -9.6 mV | ≤ 16 ns | 0.00389 pA | -1068 / -1062 / -1066 mV |
| ff/85 | 1.5 | 220 fF | -9 mV/s | 1.1 s / 11 s | -5.2 / -10.6 mV | ≤ 14 ns | 455 pA | -844 / -839 / -843 mV |

The droop is the DC leakage I(V) of each forced node, divided by C (from an AC run) and integrated from the post-release
voltage. DC gmin is 1e-22 S where it converges. Some cases need a larger gmin; a value is shown only if the gmin floor
(gmin · V / C) is under 10 % of it. The 10 s transients agree at ff/85. The tap is enabled into 5 pF + the pad
pull-down: abus settles to 1 mV in 0.8–0.9 µs, and the node takes a one-time +10 to +16 mV step. I(vdd) at ff/85
(~0.1 nA, also with the bias off) is the subthreshold leakage of the taps' off switches under the conducting SF. Every
array tap shows the same behaviour; there is no static path.

### Rev B: charge to V1 = 1.5 V, release, step vreset 1 ms later (dV/dt at V1, t to −10 / −100 mV)

| corner | vreset after step | na: dV/dt, t10 / t100 | nb clamp off | nb clamp on |
|---|---|---|---|---|
| tt/27 | 1.5 V | -0.00326 mV/s, 51 min / 8.5 h | ≈ junction floor (DC floor-limited) | -0.00325 mV/s, 51 min / 8.5 h |
| tt/27 | 1.2 V | ≤ 0.004 mV/s (floor) | ≈ junction floor (DC floor-limited) | ≤ 0.004 mV/s (floor) |
| tt/27 | 0.9 V | ≤ 0.004 mV/s (floor) | ≈ junction floor (DC floor-limited) | ≤ 0.004 mV/s (floor) |
| tt/27 | 0.0 V | -33.8 mV/s, 0.30 s / 3 s | -27.2 mV/s, 0.37 s / 3.7 s | -33.8 mV/s, 0.30 s / 3 s |
| ss/0 | 1.5 V | ≤ 0.0073 mV/s (floor) | ≈ junction floor (DC floor-limited) | ≤ 0.0073 mV/s (floor) |
| ss/0 | 1.2 V | ≤ 0.0073 mV/s (floor) | ≈ junction floor (DC floor-limited) | ≤ 0.0073 mV/s (floor) |
| ss/0 | 0.9 V | ≤ 3.5e-05 mV/s (floor) | ≈ junction floor (DC floor-limited) | ≤ 3.5e-05 mV/s (floor) |
| ss/0 | 0.0 V | -0.119 mV/s, 1.4 min / 14 min | -0.102 mV/s, 1.6 min / 17 min | -0.119 mV/s, 1.4 min / 14 min |
| ff/85 | 1.5 V | -9.04 mV/s, 1.1 s / 11 s | -9.68 mV/s, 1 s / 10 s | -9.03 mV/s, 1.1 s / 11 s |
| ff/85 | 1.2 V | -9.04 mV/s, 1.1 s / 11 s | -9.89 mV/s, 1 s / 10 s | -9.03 mV/s, 1.1 s / 11 s |
| ff/85 | 0.9 V | -9.04 mV/s, 1.1 s / 11 s | -10.2 mV/s, 0.98 s / 9.8 s | -9.03 mV/s, 1.1 s / 11 s |
| ff/85 | 0.0 V | -3.13e+04 mV/s, 0.32 ms / 3.2 ms | -2.37e+04 mV/s, 0.42 ms / 4.3 ms | -3.13e+04 mV/s, 0.32 ms / 3.2 ms |

10 s transients: tt/27, vreset → 0 V gives na −330 mV, nb clamp off −264 mV, nb clamp on −329 mV. At ff/85,
vreset → 1.2 / 0.9 V gives na −90.4 mV, nb off −97.6 / −99.8 mV, nb on −90.4 mV. Rows marked "floor" are below the DC
gmin floor. With clamp_en = 0 the floating mid node prevents a DC solution at tt/ss for small steps. In those rows the
switch current is far below the junction leakage, as the ff/85 rows show, so the droop equals the floor row above.

**Does "na ≫ nb (clamp off), nb (clamp on) ≈ na" hold?** Only half of it.
- nb with the clamp on equals na in every case. Holding mid at vreset makes SB2 identical to SA.
- na ≫ nb (clamp off) does **not** hold in the models. For vreset steps to 1.2 V or 0.9 V the switches stay
  deeply off (Vgs = −vreset ≤ −0.9 V, ~1e-24 A). Every node droops at the junction rate (n+ diffusion, 0.44 µm²); at
  ff/85 nb with the clamp off is even 7–13 % faster, because the floating mid sags.
- Only with vreset stepped to 0 V (R-DAC code 0) does switch subthreshold dominate: na −34 mV/s at tt/27, −0.12 mV/s
  at ss/0, −31 V/s at ff/85. The 2-stack with a floating mid then gains only 1.2–1.3×: nb −27 / −0.10 / −24 V/s. The
  3.3 V L = 0.5 µm switch has little DIBL, so the stack effect is weak.
- The measurable contrast on silicon is therefore the vreset → 0 V case: na ≈ nb (clamp on) vs nb (clamp off)
  about 20–25 % slower. If silicon switch leakage is larger than modelled (GIDL, defects), the smaller steps may also
  show it.

## Chip measurement procedure

1. Bias on (BIAS_EN, the vbn_prb DAC as for the array taps). Set vreset_src (r1_b0..4) to 1.5 V (or 1.0 V). Set
   GRP_EN[2] = clamp_en (0 = floating mid, 1 = clamped).
2. Probe first, so the tap enable step happens while the node is held. PROBE (0x07): write 0x1B, then 0x5B
   (SEL = 11 = AH50, row 3 col 2 -> en_c2 = tap A / na, SUB = 1, EN = 1). For nb: 0x1F, then 0x5F (SEL = 15 = AH400, en_c3).
   Follow the break-before-make order of `docs/regmap.md` §3.
3. ANA (0x06): set GRP_EN[0] = 1 (charge; it settles in < 20 ns), wait ≥ 10 µs, then clear GRP_EN[0] and keep
   GRP_EN[2] as set.
4. About 1 ms later, step vreset_src to the measurement level. Use code 0 (≈ 0 V) for the switch-leakage contrast, and
   the same 1.5 V for the junction floor (1.2 / 0.9 V give the floor in the models).
5. Record ua (abus) continuously, or at 1 s, 10 s, 100 s, 1000 s. Droop = abus(t) − abus(0+), which cancels the tap
   offset (as the array tap) and the −6 to −15 mV release step. Do not toggle EN during a run, because each tap enable
   steps the node by +10 to +16 mV. Repeat for nb with clamp_en = 0 and 1, and for na.
