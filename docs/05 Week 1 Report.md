# Week 1 report: schematic-level primitives (2026-11-08)

Everything here is **pre-layout ngspice on gf180mcuD** in the pinned `iic-osic-tools:2026.08` image. No layout, LVS or PEX has been done yet.
All numbers come from commands listed in §6.

## 1. Status against gate G1

| G1 criterion | Result | Status |
|---|---|---|
| Comparator LIF matches `model/reference.py` (rate error <10 % above 1.5× rheobase) at S = 10/100/1000 | Typical corner: within ±10 % at 0 and 27 °C at all three speeds (0.999–1.089 at 27 °C); 85 °C: 0.960–1.142. Other corners: 0.87–1.50 at fixed biases, a global die-level offset that one per-die leak-bias calibration removes. | **Pass at typical; corners need global calibration** |
| Axon-hillock (AH) LIF, same criterion | With fixed vsrc it fails at most corners: the trip point shifts ±100 mV with process and ~60 mV over 0–85 °C. With per-die vsrc calibration, 3 spot-checked corners give 0.82–1.01. Full calibrated sweep: §3. | **Pass only with per-die calibration** |
| Readout settles to 1 % in <1 µs into the pad load at every corner | Worst case 202 ns (15 corner × temperature cases, 25 pF + 500 Ω load) | **Pass** |

## 2. Cells designed

All are SPICE subcircuits under `cells/`.

| Cell | File | Topology | Key numbers (typical, 27 °C) |
|---|---|---|---|
| `mcap` | `neuron/membrane.spice` | Thick-oxide NMOS gate cap. MIM is unusable because it needs Metal5. | 4.0 fF/µm², flat to ±1 % for Vg ≥ 1.0 V. 200 fF = 7.07×7.07 µm. |
| `leak_ota_deg` | `neuron/membrane.spice` | 5-transistor subthreshold follower-integrator with diode source degeneration | Linear range VL ≈ 155 mV; g/I_b = 6.2 S/A (±5 % across ff/ss/85 °C); offset ≈ 4 pA |
| `lif_cmp` | `neuron/lif.spice` | Membrane + leak + PMOS-input 5T comparator with hysteresis + starved inverter + shared reset/refractory block | S = 100: I_rest 0.30 µA (100 nA biases, tunable); ~16 pJ per extra spike at 30 kHz |
| `lif_ah` | `neuron/lif.spice` | Same membrane, leak and reset; axon-hillock detector (starved inverter, vsrc-referenced stages, Cfb = 8 fF) | I_rest 0.26 µA. Feedback-cap kick puts effective reset at 1.10 V, so rate is ~0.88× reference: an intrinsic AH property, modelled as such. |
| `ah_replica` | `neuron/lif.spice` | Replica servo for vsrc | **Unverified, latches up.** Kept for later; per-die calibration is used instead. |
| `prb_nsf`, `pad_psf`, `refchan` | `readout/readout.spice` | In-cell NMOS follower → NMOS pass mux → PMOS pad follower. No feedback loops. | Gain 0.69–0.73, linearity ≤5 mV over 1.0–1.6 V, 202 ns worst settling. Enabling a probe kicks a floating 50 fF node by 2.1 mV. |
| Bias generator (B1) | `bias/*.spice` | ua[0] master → Bult-Geelen ladders (6 ranges ×8) → 5-bit current DACs; shifted-source rails; 6-bit voltage DACs from a shared poly string; 4-bit trim cells | See §4 |

Design problems found and fixed in simulation this week:
- comparator partial-spike stalemate (fixed with hysteresis);
- AH stuck in reset (trip point at 0.5 V; fixed with vsrc level shift);
- crowbar currents of µA in slow-input inverters (fixed with starved stages);
- 5T comparator output low level at 0.85 V (fixed by switching to a PMOS input pair);
- AH stages referenced to ground failing at ff (fixed by referencing to vsrc);
- a static 11 µA path at ff/85 °C (fixed).

## 3. LIF corner and speed sweep

Source: `sim/results/sweep_fi_summary.txt`. The cells are the ratio of SPICE rate to the reference model for inputs from 1.5× to 8× rheobase.

The comparator LIF runs with fixed nominal biases, i.e. no per-corner calibration. All rows are S = 100 except the last.

| Corner | 0 °C | 27 °C | 85 °C |
|---|---|---|---|
| typical | 1.00–1.03 | 1.00–1.07 | 0.98–1.13 |
| ff | 0.94–0.95 | 0.93–0.99 | 0.90–1.06 |
| ss | 1.12–1.28 | 1.08–1.15 | 1.06–1.20 |
| fs | 0.96–0.97 | 0.96–1.02 | 0.92–1.08 |
| sf | 1.06–1.11 | 1.05–1.12 | 1.03–1.18 |
| S = 1000 (worst corner) | ss: up to 1.50 | | |

The AH LIF uses per-die calibrated vsrc. All 45 configurations fire with no failures. Rows are S = 100; the last row is S = 1000.

| Corner | 0 °C | 27 °C | 85 °C |
|---|---|---|---|
| typical | 0.85–0.96 | 0.87–0.94 | 0.89–0.94 |
| ff | 0.77–0.88 | 0.82–0.87 | 0.82–0.87 |
| ss | 1.00–1.10 | 0.95–1.04 | 0.95–1.00 |
| fs | 0.81–0.92 | 0.85–0.90 | 0.86–0.91 |
| sf | 0.90–1.01 | 0.90–0.99 | 0.91–0.96 |
| S = 1000 (worst corner) | ss: 1.09–1.34 | | |

The AH runs consistently about 10–15 % slow. That is its feedback-cap kick (effective reset ≈ 1.10 V vs 1.20 V nominal), which a reference model with the measured Vreset would absorb. Rest current is 0.25–0.30 µA at S = 10/100 and ~2.7 µA at S = 1000 with biases scaled 10×.

**Interpretation:**
- The comparator threshold is an explicit reference voltage, so its corner sensitivity comes only from the leak g/I_b ratio and offsets. One global calibration fixes it.
- The AH threshold is device-defined. It needs a per-die (and per-temperature) vsrc calibration, which costs one shared DAC and no per-neuron hardware.
- This is the threshold-architecture comparison from conversation turn 2, now with numbers.

## 4. Bias generator (agent report: `docs/research/B1-bias-report.md`)

- **Current DAC:** 6 ranges × 5-bit fine. LSB from 3.5 nA down to 0.16 pA. Monotonic at all 27 corner/temperature/Vout cases. Leakage floor 8.6 fA (n) and 51 fA (p) at 85 °C, which needs the shifted-source rails.
- **Compliance:** ±2 % over 0.45–3.1 V.
- **Accuracy:** ±10 % absolute over corners, plus ~10 % die-common σ, so each die is calibrated.
- **Mismatch:** σ/I between instances is 1.1–1.7 % at codes ≥ 16. Worst DNL is −0.99 LSB, which leaves no monotonicity margin across many dies.
- **Settling:** 150 pA lines settle in ~3 ms to 1 %. That is the receiver's time constant and inherent at these currents.
- **Voltage DACs:** within 7.5 mV of ideal at every corner.
- **Trim cell:** gain 0.505–1.48, σ(gain) 1.8–3.3 %.
- **Area:** about 10.2k µm² for core + 4 n-DACs + 2 p-DACs + 3 voltage DACs; 16 trims add 2.7k µm².
- **Open:**
  - Vreset needs a buffer: 20 resetting membranes kick the line up 715 mV.
  - Master input must stay ≤ ~1 µA into the ladder (add a ÷16 option).
- **Fixed today:** the agent's 1 pF MIM decaps were replaced with MOS-gate decaps. The DC behaviour is unchanged; the AC response has not been re-simulated.

## 5. Mismatch Monte Carlo: which knob to trim

40 instances per configuration, S = 100, mismatch only, seeds 1–40. Source: `sim/results/mc_summary.txt`.

| | cmp 200 fF | AH 200 fF | cmp 50 fF |
|---|---|---|---|
| σ threshold | 7.5 mV | 8.4 mV | 7.5 mV |
| σ leak offset | 8.0 mV | 8.0 mV | 8.1 mV |
| cv leak g | 7.4 % | 7.4 % | 7.6 % |
| cv rate @ 2× rheobase | 10.9 % | 12.9 % | 11.1 % |
| cv rate @ 4× rheobase | 7.6 % | 7.5 % | 7.8 % |
| Variance of log rate explained by threshold | 88 % | 62 % | 87 % |
| … by leak offset | 26 % | 25 % | 27 % |
| … by leak g | 3 % | 5 % | 2 % |

Percentages overlap because threshold and offset are correlated.

**Findings:**
1. **Threshold (more precisely, the Vth − EL gap) is the dominant per-neuron error**, not τ or leak conductance. Two remedies follow:
   - The hybrid group's single trim should be a **threshold/offset trim**: 4-bit, ~±16 mV range, ~2 mV steps.
   - Alternatively, larger comparator and leak input devices: σ ∝ 1/√(WL), so 4× area halves it. That is an area-vs-reproducibility arm for the parameter-economy experiment.
2. **Capacitance barely matters for static mismatch** (50 fF ≈ 200 fF), since the dominant terms are transistor offsets. C will matter for noise, drift and parasitics, which only silicon shows.
3. This refines NH EXP-46 rather than contradicting it. EXP-46 found network-level gain/excitability is the sensitive quantity, and in this circuit threshold-offset mismatch is what sets each neuron's excitability. A gain trim can compensate at one operating point. Comparing threshold-trim and gain-trim portability across speeds is the next simulation.

## 6. Control plane (C1 + digital LIF, `rtl/`, agent rev B)

- **Interface:** SPI with 16-bit `{RW, ADDR[6:0], DATA[7:0]}` frames into 20 writable byte registers. Register map in `docs/regmap.md`.
- **Spike outputs:** 4 selectable spike outputs plus OR, digital LIF, probe-valid and heartbeat. Stretched or raw-toggle capture.
- **Other:** 16-bit counter; bit-serial 12-bit digital LIF.
- **Tests:** 11/11 cocotb pass (`scripts/eda.sh "bash test/run_tests.sh"`). Lint clean.
- **Area:** 36.8k µm² of standard cells (yosys, gf180mcu 7-track, tt 3.3 V).
  - **Digital LIF alone: 7,314 µm² at 12 bits, 6,234 µm² at 8 bits.** This is the digital half of the area comparison.
- **Hardening (LibreLane, Metal4 max):** closes only at **290×290 µm** (71 % utilization), DRC/LVS/antenna clean. Timing ≈ 38.8 MHz at ss/125 °C.
- **Floorplan problem:** 84k of the 112.8k µm² 1×2 tile was taken by digital.

**Rev C (2026-11-08, replaces rev B; rev B kept in `rtl/revB/`).** Decision: stay on 1×2, keep the digital LIF, move everything else to the demo-board microcontroller.
- **Kept on chip:**
  - digital LIF;
  - write-only config (SCK/DATA/LOAD shift register into 198 latches: 6 IDACs, 3 VDACs, 16×4-bit trims, probe, enables, LIF params);
  - 16-way probe decoder (firmware does break-before-make);
  - 16 spike pins wired direct (uio[6]/[7] muxed with LIF spike / config echo);
  - LIF tick on ui[7];
  - SC clock divider.
- **Moved off chip:** SPI oversampling, read-back, counters, spike selects/OR, stretchers, BBM sequencer.
- **Area:** 21.7k µm² cells (W=12, NTRIM=16); 18.5k at W=8/NTRIM=4.
- **Hardened:** **182×182 µm (33.1k µm²)**, 93 % utilization, DRC/LVS/antenna clean, ss setup slack +2.6 ns at 25 ns.
- **Analog budget:** leaves ~79k µm² of the 1×2 tile for analog.
- **Tests:** 14/14 cocotb pass.
- **Register map:** `docs/regmap.md`.

## 7. Next (week 2, after the tile decision)

1. Tile decision, then floorplan.
2. Layout of N1 (LIF cell), R1 (readout) and B1.
3. Threshold-trim cell (4-bit) and a portability simulation (trim at S = 100, check at S = 10/1000).
4. Vreset buffer.
5. Dendrite D1 schematic: star with diffusor coupling and a plateau bit.
6. Re-check the bias settling and rails after the MOS-decap change.

## Commands

From the repo root in Git Bash:

| Purpose | Command |
|---|---|
| Leak I-V | `scripts/eda.sh "python3 sim/tb/tb_leak_iv.py"` |
| f-I, one corner | `scripts/eda.sh "python3 sim/tb/tb_lif_fi.py <cmp\|ah> <corner> <temp> <S>"` |
| Full sweep | `scripts/eda.sh "python3 sim/tb/sweep_fi.py"`, then `summarize_fi.py` |
| Mismatch MC | `scripts/eda.sh "python3 sim/tb/tb_lif_mc.py <cmp\|ah> 40 <7.07u\|3.54u>"` |
| Readout | `scripts/eda.sh "python3 sim/tb/tb_readout.py"` |
| Bias | `scripts/eda.sh "bash sim/tb/bias/run_all.sh"` |
| RTL | `scripts/eda.sh "bash test/run_tests.sh"` |
