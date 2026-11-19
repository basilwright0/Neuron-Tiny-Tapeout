# Hardwiring experiment: protocol and area accounting

**Question:** can a neuron's parameters be fixed at design time instead of being configurable, and how much area would that save?

**Decided 2026-11-19:** answered with silicon measurements on the existing groups plus an area accounting from measured layouts. There is no separate hardwired circuit (see `08 Updated Plan.md`).

## 1. What "hardwired" means here

Every parameter is a fixed **ratio to one chip-wide reference**:
- currents are fixed mirror ratios;
- voltages are fixed taps of a supply-ratiometric divider;
- τ is set by geometry.

There are no DACs, no per-line codes and no per-neuron trims. A large hardwired chip would still keep one global reference, which here is the ua[0] reference current. That reference also scales speed, so a hardwired neuron still runs at S = 10…1000.

## 2. Silicon measurements (bring-up protocol)

Run all of these clock-off, at S = 100 first, then S = 10 and 1000, at room temperature. Repeat at a second temperature if the board allows.

| Step | Measurement | What it answers |
|---|---|---|
| 1 | **S group at nominal codes, uncalibrated.** Set every DAC to its design-nominal code (a fixed mirror ratio, electrically the same as a hardwired mirror), threshold code nominal, no per-die calibration. Measure f–I curves, rheobase, τ (step response through the probe) and EL (REF channel) for S1–S3. | How far a hardwired neuron lands from its target on a real die. This is the **die-level (systematic) error** of hardwiring. |
| 2 | **Same, after per-die calibration.** Calibrate the threshold code, EL and leak code on the REF channel and the S neurons, then repeat step 1. | How much of that error a single global calibration removes. A hardwired chip with one global trim knob gets this much. |
| 3 | **F group τ ratio.** Same leak line, half-size leak transistor. Measure τ_F/τ_S for each F–S pair and its spread across the die. Pairs are spread over rows and columns, so gradients separate from random mismatch. | How accurately **geometry alone** sets a parameter (NH EXP-46's "etch τ variants"). |
| 4 | **Neuron-to-neuron spread**, compared across groups: S (no trim), H (gap trim set), P (gap + τ trim set). Use the same metrics as step 1. | What per-neuron configurability buys over hardwired + global calibration. The Monte Carlo predicts 12 % → 2.4 % rate spread with the gap trim. |
| 5 | **Speed portability.** Keep the step-2 calibration, change only the ua[0] reference to S = 10 and 1000, then repeat step 1. | Whether a hardwired ratio design holds its calibration across speed. The Monte Carlo predicts the gap trim is portable; the threshold code may need re-setting per speed. |

**The result is a single table:** error vs target for each level (hardwired-uncalibrated → global calibration → per-neuron trim), at each speed. Set beside the area table in §3, it gives the accuracy-vs-area trade-off of hardwiring.

**Caveat:** a DAC at a fixed code adds about 1–2 % of its own mismatch (measured σ/I of the current DACs) compared with a dedicated fixed mirror. It also includes the DAC's switches. So step 1 slightly *over*-estimates hardwired error, which is the conservative direction.

## 3. Area accounting (fill in at G2 from measured layouts)

Configurability costs, from this chip's layouts. Estimates are marked *est.*

| Item | Configurable (this chip) | Hardwired equivalent | Source |
|---|---|---|---|
| Neuron slot core | 1,218 µm² (S slot, measured) | ~1,218 µm² (same core) | `layout/slot` |
| In-slot gap trim | ~84 µm² of devices + routing, inside the same slot box | 0 | `layout/slot/out/area.txt` |
| Trim storage | 4 latches × ~48 µm² ≈ 190 µm² per trimmed neuron | 0 | std-cell `latrnq` |
| τ trim (outside the array) | 437 µm² per P neuron | 0 | `trim_tau4`, measured |
| Bias generator | *~21k µm²* (rev C, est.; measured at G2) | fixed ladder + string + V-to-I, *~5–6k µm² est.* | `layout/bias` |
| Bias config storage | 41 bits × ~48 ≈ 2k µm² | 0 | regmap rev E |
| Config interface (shift register, decode) | ~1.4k µm² of cells | 0 | synthesis |

**How the saving scales with array size N.**

Per neuron:

- Configurable: A_core + A_trim + A_trim-storage + (A_B1,prog + A_bias-cfg + A_cfg-if) / N
- Hardwired: A_core + A_B1,fixed / N

On this chip (N ≈ 17 analog neurons) the shared overhead dominates: roughly 15–20k µm² of a ~105k µm² design (*est.*). On a large array the shared terms vanish, and the saving per neuron tends toward the trim plus its storage: about 270 µm² per trimmed neuron here, ~20 % of a slot. Silicon steps 1–4 say what accuracy that saving costs.

## 3b. Area per neuron by configurability, analog vs digital (estimate, 2026-11-19)

All figures are first-order estimates from this chip's GF180 layouts and synthesis.

**Building blocks:**

| Item | Area (µm²) |
|---|---|
| Analog neuron core (S slot: LIF, 200 fF, synapse, guard rings; includes 2 probe taps and reserved trim space a production array would drop) | ~1,200 |
| Gap trim | ~170 |
| τ trim | 437 |
| Full 5-bit wide-range current DAC | ~950 |
| Current-DAC voltage | ~1,000 |
| Storage | ~48 per bit (std-cell latch) |
| Shared bias generator, programmable | ~21k |
| Shared bias generator, fixed | ~5–6k |
| Digital LIF (12-bit, bit-serial, synthesized) | 7.36k of cells |
| Hardened digital (box / cells, measured on the control block) | ×1.5 |

**Analog, about 6 parameters per neuron.** Hardwired = fixed ratios to one global reference.

| Approach | Per-neuron extras | Per neuron, N = 17 | Per neuron, N = 1,000 | vs analog hardwired, N = 1,000 |
|---|---|---|---|---|
| Hardwired | none | ~1,550 | **~1,210** | 1.0× |
| Shared programmable (S group) | none; shared DACs + storage + interface ≈ 24k per chip | ~2,630 | ~1,220 | ~1.0× |
| Hybrid: shared + 1 gap trim (H group) | 170 + 4 bits | ~2,990 | ~1,580 | 1.3× |
| Shared + 2 trims (P group) | + 437 + 4 bits | ~3,620 | ~2,210 | 1.8× |
| Every parameter individual, as trim-style 4-bit scalers | 6 × (~300 + 190) | ~4,600 | ~4,150 | 3.4× |
| Every parameter individual, as full 5-bit DACs | 6 × (950 + 240) | ~8,300 | ~8,350 | ~7× |

**Digital, the same LIF in fixed point:**

| Approach | Per-neuron area | Per neuron, N = 1,000 | vs analog hardwired |
|---|---|---|---|
| Dedicated digital neuron (as on this chip): its own datapath + 43 param bits | 7.36k + 2.1k cells, ×1.5 hardened | **~14k** | ~12× |
| Time-multiplexed array, shared params, S = 100: 16 state bits per neuron in latches (770) + one datapath shared by ~9 neurons (bit-serial ≈ 46 clk/update at ~40 MHz, dt ≈ τ/10), ×1.5 hardened | ~(770 + 820) × 1.5 | **~2.4k** | ~2× |
| Time-multiplexed, shared params, S = 1 (biological time): one datapath serves ~900 neurons | ~(770 + 8) × 1.5 | **~1.2k** | ~1× |
| Time-multiplexed, every parameter individual (+36 param bits per neuron) | +36 × 48 × 1.5 ≈ +2.6k | ~5k (S = 100) | ~4× |

**Reading the two tables together:**
1. **Shared programmable biases are almost free at scale** for analog: ~25 µm² per neuron at N = 1,000. Per-neuron knobs are the real cost: +30 % for one trim, 3.4–7× for fully individual parameters.
2. **A dedicated digital neuron is ~12× a hardwired analog neuron** in this process. That is the "same I/O semantics" comparison this chip makes directly.
3. **Time-multiplexed digital narrows the gap,** to ~2× at S = 100 and ~1× at biological speed. It does so by trading update rate for area, and it gets *worse* as speed goes up, while analog area doesn't depend on speed. With latch storage, per-neuron state dominates. An SRAM macro would be denser per bit; GF180 SRAM density is not checked here.
4. **Per-neuron configurability costs about the same in either domain,** because it is mostly storage (~48 µm²/bit with std-cell latches). Fully individual parameters are 4× (digital) to 7× (analog) a hardwired neuron.
5. **This leaves out energy** (a likely analog advantage, measurable at bring-up only differentially), accuracy (digital is exact; analog is ~12 % untrimmed, ~2.4 % with one trim, from the Monte Carlo) and wiring to address per-neuron storage in a real array.

## 4. Deliverables

- **At G2:** fill in §3 with measured B1 rev C and control-block rev E areas.
- **At bring-up:** firmware routine for steps 1–5, plus a results table in this doc.
