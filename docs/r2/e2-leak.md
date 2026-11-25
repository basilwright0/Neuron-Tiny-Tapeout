# E2: `e2_leak` reset-switch leakage test cell (R2, MIL-362)

Two floating ~210 fF vm-like nodes, each with a probe tap copied from the array. Generator `layout/e2/e2gen.py`, flow
`layout/e2/build.sh` (magic + netgen + KLayout). Deliverables are in `layout/e2/final/`. Benches: `sim/tb/e2/`.

```
 vreset ─┬─[SA 1/0.5]─────────────── na ──┬── CA (nfet 8.56/5.84, S/D/B = vss)    na ── tap A (en_a)
         │                                └── tap A gate (SF 4/2)
         ├─[SB1 1/0.5]── mid ──[SB2 1/0.5]── nb ──┬── CB (same)                      nb ── tap B (en_b)
         └─[PC pfet 1/0.28, gate grp_en, body vdd]─┘ (mid)
   all switch gates = grp_en; PC is on while grp_en = 0, so it clamps mid to vreset (no inverter)
 tap (x2): vdd ─[MF 4/2, g = node]─ p ─[ME 1/0.28, en]─ s ─[MB 2/2, vbn_prb]─ vss
                                     p ─[SC en]─[SW rsel]─[SB sub]─ abus     (switches 1/0.28; as the array XPM_*)
```

**Clamp choice.** A single pMOS gated by `grp_en` replaces "nMOS clamp + local inverter". It is on exactly when
grp_en = 0 (|Vgs| = vreset = 1.0–1.5 V) and off when grp_en = 1. That saves two devices and the `grp_en_b` net, and the
cell has no inverter crossing current. Mid only has to be held against fA-level leakage, so a weak pMOS is enough.

**Cell:** 28.24 × 11.80 µm (333 µm²), 18 devices. Magic DRC 0, KLayout DRC 0 (gf180mcu deck, variant D, no density),
netgen "Circuits match uniquely". Logs: `layout/e2/final/e2_leak_{magic_drc,klayout_drc_summary,lvs_report}.txt`.

## Pins (labels on the top cell, each touching the cell edge; origin = lower-left corner)

| pin | layer | edge | x (centre) | width | pin | layer | edge | x | width |
|---|---|---|---|---|---|---|---|---|---|
| en_a | Metal2 | bottom | 2.00 | 0.30 | vbn_prb | Metal2 | bottom | 22.40 | 0.30 |
| rsel | Metal2 | bottom | 3.20 | 0.30 | grp_en | Metal2 | bottom | 23.60 | 0.30 |
| sub | Metal2 | bottom | 4.40 | 0.30 | vreset | Metal2 | bottom | 24.80 | 0.30 |
| abus | Metal2 | bottom | 5.60 | 0.30 | en_b | Metal2 | bottom | 26.00 | 0.30 |
| vss | Metal2 | left | y 6.00 | 0.40 | vdd | Metal2 | right | y 6.00 | 0.30 |

Bottom pins are on a 1.2 µm pitch (0.9 µm edge-to-edge gap). Routed metal stays ≥ 0.36 µm inside the box edge.
`na` and `nb` are Metal1 test labels (not ports). Top-level hookup: en_a = `en_c2`, en_b = `en_c3`, rsel = `probe_rsel[3]`,
sub = `probe_sub`, grp_en = one GRP_EN bit (the lead picks which one).

## Results (PEX, `sim/tb/e2/results/summary.md`)

| corner | vreset | C na = nb | dV/dt na = nb | t −10 mV | t −100 mV | release step na / nb | reset to 1 mV na / nb | I(vdd), grp_en = 0 | tap offset A / B / array |
|---|---|---|---|---|---|---|---|---|---|
| tt/27 | 1.0 | 208 fF | -0.0033 mV/s | 50 min | 8.33 h | -6.2 / -15.0 mV | 4 / 9 ns | 0.158 pA | -811 / -803 / -809 mV |
| ss/0 | 1.0 | 193 fF | -3.5e-05 mV/s | 3.3 d | 33.3 d | -6.9 / -15.9 mV | 5 / 9 ns | 0.0027 pA | -900 / -891 / -897 mV |
| ff/85 | 1.0 | 218 fF | -9.1 mV/s | 1.09 s | 10.9 s | -5.9 / -14.9 mV | 5 / 10 ns | 92.8 pA | -697 / -689 / -695 mV |
| tt/27 | 1.5 | 213 fF | -0.0033 mV/s | 51.2 min | 8.54 h | -5.6 / -11.4 mV | 11 / 15 ns | 0.212 pA | -969 / -962 / -967 mV |
| ss/0 | 1.5 | 205 fF | -3.5e-05 mV/s | 3.26 d | 32.8 d | -5.8 / -11.7 mV | 8 / 16 ns | 0.00196 pA | -1068 / -1062 / -1066 mV |
| ff/85 | 1.5 | 220 fF | -9 mV/s | 1.11 s | 11.1 s | -5.9 / -12.7 mV | 12 / 14 ns | 124 pA | -844 / -838 / -843 mV |

C and dV/dt of na and nb agree to 3 digits in every row (see the finding below). ss/0 used DC gmin 1e-21 S, so its rate is an upper bound (floor ≈ 15 %). The tap is enabled into 5 pF + the pad pull-down: abus settles to 1 mV in 0.8–0.9 µs, the node takes a one-time +10 to +16 mV step (SF gate charge sharing), and the DC load is 0 (gate leakage is not modelled, igcmod = 0). I(vdd) at ff/85 (93–124 pA, also with the bias off) is the subthreshold leakage of the taps' off switches below the conducting SF, which every array tap shares. At tt it is 0.16–0.21 pA, and there is no static path.

Droop = DC leakage of each forced node, I(V), divided by C (from an AC run), integrated from the post-release
voltage. DC gmin is 1e-22 S (1e-15 would add 1 fA at 1 V). The 10 s transients (gmin 1e-18) agree at ff/85. At tt and ss
their ±0.1 mV/s numerical drift is larger than the real droop.

**Finding (open risk, spec level).** In the models, na and nb droop identically. With grp_en = 0 each switch has
Vgs = −V(node) ≈ −1 V, so its subthreshold current (~1e-25 A) is negligible. Both nodes lose charge only through the
reverse leakage of their own n+ diffusion (the 0.44 µm² switch source; Jss-limited, independent of V). The clamp holds
mid at vreset, so the inner switch SB2 has the same D/G/S/B voltages as SA. The two nodes are therefore electrically
equivalent by construction, and the a/b difference measures only mismatch or silicon effects that the models lack.
For a real a/b contrast, mid would have to follow nb (a bootstrapped buffer) or b would need a different junction area.
The cell still measures the absolute hold leakage of a vm-sized node with a 3.3 V reset switch, which is the number the
array needs.

## Chip measurement procedure

1. Bias on (BIAS_EN, the vbn_prb DAC as for the array taps), and set vreset (VDAC) to 1.0 V or 1.5 V.
2. Probe first, so the tap enable step happens while the node is held. PROBE (0x07): write 0x1B, then 0x5B
   (SEL = 11 = AH50, row 3 col 2 -> en_c2 = tap A / na, SUB = 1, EN = 1). For nb: 0x1F, then 0x5F (SEL = 15 = AH400, en_c3).
   Follow the break-before-make order of `docs/regmap.md` §3.
3. ANA (0x06): set E2's GRP_EN bit to 1, wait ≥ 10 µs (the reset settles in < 20 ns), then clear it. Record ua (abus)
   continuously or at fixed times: 1 s, 10 s, 100 s, 1000 s.
4. Node = abus − tap offset, where the offset is the same as the array tap (table). Take droop = abus(t) − abus(0+), so
   the offset and the −6 to −15 mV release step cancel. Repeat with the other tap. Do not toggle EN during a run,
   because each tap enable steps the node by +10 to +16 mV (SF gate charge sharing).
