# T2: AdEx (A1) area and status, and the cut SC dendrite

## Rev 3 (2026-11-19): current status. Sections 1–7 below are the rev 2 record (56 × 50, EL 1.20 V).

**Shared cells.** Rev 3 uses the current shared cells, unedited: `leak_ota_deg` with 4/1 inputs and 8/1 degeneration diodes, and `det_ah` with the XS3-starved third stage and the XK reset keeper. EL / Vth / Vreset are 1.30 / 1.38 / 1.30 V. The private `a1_leak` copy is gone; AdEx now instantiates `leak_ota_deg` directly.

**Layout** (floorplan column between the array and the control block):

| Item | Value |
|---|---|
| Box | **38.0 × 73.0 µm = 2774 µm²** (GDS extent 38.04 × 73.04) |
| magic DRC | 0 |
| KLayout `gf180mcu.drc` (variant D, flat, no density) | 0 |
| LVS | match: 66 devices, 55 nets |
| Bias/analog pins | bottom edge, from a left Metal2 spine: vdd, el, vbn_leak, vsrc, vbp_st, vbn_ref, vreset, vbn_prb, vbp_syn, vbp_w, abus |
| Digital pins + spk | right edge, Metal3 at y = 9.7 sta, 10.5 spk, 14.0 stb, 14.8 en, 26.0 mreset, 29.4 sub0, 30.2 sel_adex, 33.4 sub1, 58.1 hold |

Generator options added in `t2gen.py`: `SPINE_SIDE="left"`, `PIN_EDGE="bottom"`, and `HM3` (horizontal Metal3 lines with pins on the right edge).

**Schematic re-verification at S = 100.** Model = reference.py AdEx equations, with b fitted at 400 pA.

| Check | Result |
|---|---|
| I–V (exponential term) | gL 2.05 nS, rest 1.310 V, ΔT 44 mV, VT 1.404 V (trip 1.38 V), rheobase 88 pA |
| Adaptation, 250 pA | adapted/initial ISI 2.16 (model 2.22) |
| Adaptation, 400 pA | 2.07 (model 2.05) |
| Adaptation, 700 pA | 1.77 (model 1.69) |
| Adaptation parameters | b 44 pA, τ_w 0.83 ms; decay still a fixed ratio of vbn_leak |
| 15 corners | ratio 1.87–2.20, b 34–52 pA, τ_w 0.71–1.04 ms, rheobase 75–99 pA; ss 0 °C now 94 pA (46 with the old OTA) |
| MC typical 27 °C, 20 seeds | ratio 2.14 ± 0.33, b 45 ± 10 pA, τ_w 0.84 ± 0.06 ms, rheobase min 52 pA |
| MC ss 0 °C, 12 seeds | ratio 2.22 ± 0.33, rheobase min 60 pA |
| Firing with no input | none, in all corners and MC seeds |
| vbp_w range | the 1.02 nA LSB / 32 nA full-scale DAC covers 0.5–30 nA; code 8 gives ratio ≈ 2 |

**All-zero (bias-off) state.** With the XK keeper in `det_ah`, supply current is 3 pA (schematic) / 10 pA (PEX), spk stays at 0 and abus is disconnected. Without XK, pb floated and the detector drew 63 µA per neuron (`sim/tb/tier2/tb_det_zero.py`). vw comes up near vdd until MRESET clears it; that is a firmware rule.

**PEX at 400 pA** (typical 27 °C, all coupling caps):

| | Ratio | b | τ_w | No-adaptation ISI | spk runts |
|---|---|---|---|---|---|
| Schematic | 2.07 | 44 pA | 0.83 ms | 79 µs | 0 |
| PEX | 1.96 | 42 pA | 0.89 ms | 101 µs | 0 |

The PEX firing rate is lower from vm wiring (27 fF, Cfb 8.4 fF). That falls under the per-die calibration.

**PEX functional checks:**
- Probe decode: correct for all 8 codes.
- Hold: vm drift −0.04 mV/ms.
- mreset: vm goes to vreset and vw to 0.

---

AdEx is spike channel 3, outside the array (docs/08 Updated Plan.md §3). Schematic `cells/adex/adex.spice` (`adex_a1`), layout `layout/tier2/` (`adex_a1*`, flow `build.sh` / `t2gen.py`), testbenches `sim/tb/tier2/`, results `sim/results/tier2/adexc_*.json`, `adexf_*.json`.

## 1. Area and verification

| Cell | Box (µm) | Area (µm²) | magic DRC (`drc(full)`) | KLayout `gf180mcu.drc` (variant D, flat, no density) | LVS (netgen) |
|---|---|---|---|---|---|
| **`adex_a1`** (rev 2, this report) | **56.0 × 50.0** (GDS extent 56.04 × 50.04: well/tap overhang 0.02 per side) | **2800** | 0 | 0 | match, 64 devices, 54 nets, no floating pins |
| `scdend_s1` (CUT, for the record) | 56.0 × 47.0 | 2632 | 0 | 0 | match |
| `scdend_s1w` (CUT, same netlist, wide/low variant) | 72.0 × 40.0 | 2880 | 0 | 0 | match |

The plan budget for AdEx is 2.8k µm²; the cell is exactly on it. Metal1–3 only; pins: Metal2 spine at the top edge (el, vbn_leak, vsrc, vbp_st, vbn_ref, vreset, vbn_prb, vbp_syn, vbp_w, abus, mreset, spk, vdd) and Metal3 lines from the top edge (en, sta, stb, hold, sel_adex, sub0, sub1). vss = the p-tap ring, vdd also on the Metal1 rails at the left/right edges. The S1 files were not touched.

Rebuild: `scripts/eda.sh "SKIPDEV=1 CELLS=adex_a1 bash layout/tier2/build.sh"` (route ~8 min).

## 2. What changed from the rev 1 layout (previous session)

| Rev 1 | Rev 2 | Why |
|---|---|---|
| bias line `vbp_adw` | `vbp_w` | plan name (B1 IDAC5, former `vbp_spare`, pfet 1/2 receiver, 1:1 into XA.XPW) |
| ports `sel0`, `sel1` (pre-decoded) | `sel_adex` + `sub0`, `sub1` (= `probe_sub_raw[1:0]`), in-cell decode `a1_pmux` | plan §5: own select line; SUB 0 = vm, 1 = vw, 2/3 = nothing |
| vw tap = nfet follower | vw tap = pfet source follower (2/0.5, ~100 nA from vbp_st) | vw lives at 0–0.5 V, below an nfet follower's range: the old tap read ~0 V |
| gap-trim keep-out + `la`, `vl`, `t0..t3` | removed | plan §5: no AdEx trim nibble (TRIM_MASK drops nibble 1) |
| exp-term output and adaptation sink on vm | on vl (leak output, behind the synapse hold switch) | hold = 1 now freezes vm against leak, exp and adaptation (drift −0.05 mV/ms PEX) |
| XE1 0.22/4 | 0.22/8 | ss 0 °C mismatch: 9/16 seeds had no stable rest with 0.22/4; now min rheobase 15 pA |
| no vw reset | XA.XR1/XR2 (2 × 0.22/2 series, gate mreset) | Cw is vdd-referenced: power-up drags vw to ~2.8–3.1 V (vm clamped low, ~50 ms to recover); a single 0.5/0.28 switch leaks 21 pA at ff 85 °C (2× Itau), the stack 0.9 pA |
| XA.Xi.XN next to the detector | moved left | its output vrb coupled 0.9 fF into detector nodes; PEX showed a 1 ns runt on spk every spike (two edges per spike) |

The decay is a fixed ratio of `vbn_leak` (3 × 0.22/15 stack, 10 pA at Ib_leak 324 pA), the DPI gain node is also `vbn_leak`: no separate DAC, as frozen.

## 3. Behaviour at S = 100 (typical 27 °C, schematic)

Bias: EL 1.20 V, Ib_leak 324 pA (gL 1.97 nS), AH trip 1.28 V (vsrc calibrated), Iin = 8 nA on vbp_w. `tb_adex_char.py nominal`.

**Exponential term** (vm forced, leak replica subtracted): I_exp = gL·ΔT·exp((V−VT)/ΔT) fits over 1.12–1.27 V with **ΔT = 44 mV, VT = 1.30 V** (20 mV above the AH trip). Rest 1.210 V (EL + 6 mV); rheobase 84 pA vs 160 pA for the plain LIF (gL × 80 mV): the exponential bends the I–V and halves the rheobase, but VT sits past the trip, so the spike is still made by the axon-hillock detector (Vpeak = 1.28 V), not by the exponential runaway. ΔT is ~2× the reference default (20 mV); the 80 mV EL-to-trip window on this chip leaves no room for more.

**Spike-frequency adaptation** (current steps, ISI first → adapted):

| Step | HW no adaptation | HW adaptation | Model (reference.py AdEx eqs + t_ref) |
|---|---|---|---|
| 250 pA | 126 µs | 152 → 327 µs, ratio 2.15 | 140 → 306, ratio 2.19 |
| 400 pA | 80 µs | 86 → 176 µs, ratio 2.04 | 87 → 176, ratio 2.03 (fitted) |
| 700 pA | 52 µs | 53 → 92 µs, ratio 1.73 | 61 → 101, ratio 1.66 |

Measured on an Iw replica: b = 44 pA per spike (38–46 over the three steps), τ_w = 0.83 ms (τ_w/τ_m ≈ 8), a = 0. Model: the reference AdEx equations with the fitted gL, EL, VT, ΔT, τ_w, t_ref = 34 µs (fitted on the 400 pA no-adaptation ISI), and b_eff = 51 pA (fitted on the 400 pA adapted ISI; 16 % above the replica b, the DPI increment is not exactly constant). With that one fit the 250 pA and 700 pA adaptation curves follow (ratio within 0.07). Plot: `sim/results/tier2/adexc_nominal.png`.

**Adaptation strength vs vbp_w** (`sweepw`, 400 pA step):

| Iin on vbp_w | 0.25 nA | 0.5 | 1 | 2 | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|---|---|---|
| adapted/initial ISI | 1.04 | 1.08 | 1.15 | 1.29 | 1.54 | 2.05 | 2.93 | 3.61 | (stops firing) |
| b (pA) | 0.1 | 1.5 | 5.4 | 12 | 23 | 43 | 74 | 112 | — |

**Range needed on vbp_w at S = 100: ~0.5 nA to ~30 nA** (off = code 0). A 5-bit IDAC with a ~1 nA LSB (full scale 31 nA) covers it; 8 nA (code 8) is the nominal ratio-2 point. All the DPI currents (Itau, the gain node, the increment pulse length t_on = refractory) track vbn_leak/vbn_ref, so the needed Iin should scale ∝ S like the other DAC lines (not simulated at other S).

## 4. Corners and mismatch

`tb_adex_char.py corners` (vsrc calibrated per corner as on silicon), 400 pA step:

| | ratio adapted/initial | b (pA) | τ_w (ms) | rheobase (pA) | rest (V) | f no-adapt (kHz) |
|---|---|---|---|---|---|---|
| 5 corners × 0/27/85 °C | 1.85–2.13 | 34–52 | 0.71–1.04 | 46–94 | 1.208–1.216 | 11.7–14.1 |
| worst case | ff 85: 1.85 | sf 85: 34 | ff 0: 0.73 / sf 85: 1.04 | ss 0: 46 | ss 0: 1.216 | |

No case fires without input. ss 0 °C is the weak spot: the shared leak OTA's gL drops to 0.94 nS there (also an open item for the array, "ss/0 leak-OTA check"), which pulls the AdEx rest toward the exponential region.

Monte Carlo, local mismatch (`mc 24`, typical 27 °C, 24 seeds; `mc 16 ss 0`, 16 seeds):

| | ratio | b (pA) | τ_w (ms) | rheobase (pA) | rest (V) | self-firing |
|---|---|---|---|---|---|---|
| typical 27, 24 seeds | 2.14 ± 0.36 (1.69–3.11) | 46 ± 10 | 0.84 ± 0.06 | 78 ± 20 (min 47) | 1.211 ± 0.011 | 0 / 24 |
| ss 0 °C, 16 seeds | 2.23 ± 0.39 (1.74–3.35) | 50 ± 12 | 0.79 ± 0.06 | 40 ± 13 (min 15) | 1.220 ± 0.011 | 0 / 16 |

The ratio spread (±17 %) is mostly the DPI increment mismatch (b ±22 %); it is tuned per die with the vbp_w code. (The ΔT/VT fits are not meaningful under mismatch because the leak replica has its own offset; rest and rheobase come from the neuron's own I–V.)

## 5. Interface and functional checks (`tb_adex_func.py`, schematic and PEX)

- **Probe:** abus = 0 for sel_adex = 0 (all SUB) and for SUB 2/3; SUB 0 = vm follower (0.42 V at vm 1.12 V, 10 MΩ test load); SUB 1 = vw pfet follower (0.99 V at vw 0.45 V; offset ≈ +0.5 V into 10 MΩ, larger into the real gate load). The vm follower bias is `en` (tie to sel_adex or PROBE_EN); the vw follower runs (~100 nA) whenever sub0 = 1.
- **Hold:** vm frozen at 1.262 V (between rest and trip, vw = 0.3 V) drifts −0.05 mV/ms (PEX), no spike; with hold = 0 it relaxes at −50 mV/ms. vw keeps decaying during hold (only vm is frozen).
- **mreset:** vm → vreset, vw → 0 while high; one adaptation increment follows its release (vr decays as after a spike).
- **All-zero state** (bias lines off, logic 0, vdd ramp): 3–8 pA supply current, spk low, abus disconnected, no spikes; vw comes up at 2.8–3.1 V through the vdd-referenced Cw, which holds vm low until MRESET clears it (cleared to 0 in the 20 µs pulse). **Firmware rule: pulse MRESET after BIAS_EN.**

## 6. PEX spot check (typical 27 °C, 400 pA)

| | no adaptation ISI | adapted: first → last, ratio | b | τ_w |
|---|---|---|---|---|
| schematic | 79.6 µs | 86 → 176 µs, 2.04 | 44 pA | 0.83 ms |
| PEX (all coupling caps) | 98.4 µs | 108 → 214 µs, 1.98 | 47 pA | 0.91 ms |

Adaptation survives extraction (ratio −3 %, τ_w +9 % from 15 fF of vw wiring). The firing rate is 19 % lower in PEX: vm carries 21 fF of wiring (Cfb 7.95 fF is on target) and the vm–vr coupling slows the post-refractory ramp; this is the same per-die rate calibration as the array (spot check only: the static I–V is identical). No spk runts after the vrb placement fix (0 extra edges).

## 7. Open points

- The exp term is soft (VT above the trip): a sharper onset needs a larger EL-to-trip window than the chip's 80 mV.
- ss 0 °C margin (min rheobase 15 pA in MC) depends on the array's leak-OTA ss/0 behaviour.
- vbp_w scaling with S assumed, not simulated.
- vw probe offset depends on the abus load (R1 input); readings of vw are relative.
