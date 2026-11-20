# Updated design plan (frozen 2026-11-19)

This records the design decisions made 2026-11-17 to 19, after measured layouts showed the original bias generator (~39k µm²) and MVP (~130k µm²) could not fit the 1×2 tile. It supersedes the conflicting parts of `04 Design Plan.md` and `06 Floorplan.md`. The floorplan doc will be updated with measured areas at G2.

## 1. Target

- **Tile:** TTGF26c, gf180mcuD, **analog 1×2** (346.64 × 325.36 µm = 112.8k µm²).
- **Pins:** 2 analog pins. The analog section runs on VDPWR (3.3 V). VAPWR was rejected because the pgvaa template is 17.9 µm narrower and its voltage on GF is unknown (`07 TT Discord Answers.md`).
- **Fallback:** 2×2, +€140. Use it only if measured areas at G2 leave less than about 5 % margin.

## 2. What the chip tests (unchanged)

1. Silicon-only analog behaviour: noise, drift, hold leakage, gradients, real capacitance, temperature (NH Phase 0 → 1 gate, criterion #3).
2. Parameter economy: how much per-neuron control analog neurons need (F / S / H / P groups).
3. Building blocks: the dendritic nonlinearity (CS EXP-08), comparator vs axon-hillock spike generation, AdEx adaptation, and the analog vs digital LIF.
4. Hardwiring: how well design-time-fixed parameters work, and what they save. This is answered by a bring-up protocol on the S and F groups plus an area accounting, with no extra circuit (`09 Hardwiring Experiment.md`).

## 3. Neuron complement (16 spike channels)

| Channel | Neuron | Notes |
|---|---|---|
| 0, 4, 8 | S1–S3 | shared bias |
| 1, 5, 9 | F1–F3 | **fixed geometry: same shared `vbn_leak` line, leak-tail W/L halved, so τ_F = 2·τ_S is set by geometry** (the NH EXP-46 "etch τ variants" test; the τ_F/τ_S spread across the die measures how well geometry sets τ) |
| 2, 6, 10 | H1–H3 | shared bias + in-slot gap trim |
| 7, 11 | P2, P3 | gap trim + leak-τ trim (via `aux`); **P is 2 neurons now** |
| **3** | **AdEx** | replaces P1; sits outside the array |
| 12 | CMP | comparator LIF |
| 13 | D1 soma | dendrite |
| 14, 15 | AH50, AH800 | capacitance spread; on uio[6]/[7] via OUT_MUX |

- **Array slot (row 0, col 3)**, formerly P1, becomes a **dummy S slot**. It has no spike channel and no probe index, and it keeps the array uniform.
- **REF** stays at (0,0) and is probed with PROBE_SUB = 3.
- **Tier 2:** the switched-capacitor dendrite S1 is **cut**, and with it the control block's SC clock divider. The small network W1 was already cut.

## 4. Bias generator (B1 rev C)

**Fixed range per current DAC.**
- Each DAC is hardwired to one ladder tap, with a 5-bit fine code; fine code 0 = off.
- **Speed (S = 10…1000) is set by the ua[0] reference current**, using the ext ÷1 and ÷16 modes.
- The range selector (`bias_rangegen`) and its 36 decoded lines are removed.

**Current DACs (5-bit each):**

| Line | Function |
|---|---|
| `vbn_leak` | leak |
| `vbn_ref` | refractory |
| `vbp_syn` | synapse weight |
| `vbn_ax` | D1 axial coupling |
| `vbp_w` (former spare IDAC5) | AdEx adaptation increment |

The AdEx adaptation decay is a fixed ratio of `vbn_leak`.

`vbp_st` (detector starve) becomes a fixed ratio off the master, like `vbn_prb`.

**Voltages: the hybrid path.**
- **The one remaining resistor string** (supply-ratiometric) feeds **one 6-bit voltage DAC for the threshold reference `vth_ref`**, over a narrow window of about 0.35–0.75 V, giving about 6 mV steps (about 8 mV of threshold).
- **A fixed string tap** drives a V-to-I converter (I = V_tap / R₀).
- **EL, `vreset_src` and `vth_cmp`** (the comparator neuron's threshold, ~1.28 V) are made by three 5-bit current DACs fed from that current into resistors (V ∝ V_tap · code · R₁/R₀). This is speed-independent and ratio-accurate.
- **Per-die calibration** of EL and the threshold uses the REF probe channel. The threshold code is recalibrated for each speed setting.

**Kept as before:** ESD on ua[0], the ua[0] modes, BIAS_EN safe power-up, `ib_r1` / `ib_x2` and `vbn_prb`.

**`vsrc` needs a buffer.** The threshold reference has to be buffered before driving the detector stages, because `ah_replica` is unverified and latches up. This is a new small cell, owned by the R1 track.

**Layout:** a tighter assembly target (routing overhead ×1.3 instead of ×1.5).

## 5. Control block (rev E)

**Removed:**
- IDAC range bits and decode;
- the SC clock divider;
- trim storage the design doesn't use (TRIM_MASK keeps nibbles 0, 2–8, 14, 15).

**Trim nibbles in use:**

| Nibble | Trim |
|---|---|
| 0, 2, 4 | H1, H2, H3 gap trims |
| 3, 5 | P2, P3 gap trims |
| 6 | CMP |
| 7, 8 | D1 subunits |
| 14, 15 | P2, P3 leak-τ |

**Interface changes:**
- The bias ports regenerate from B1 rev C's `bias_b1.spice`.
- AdEx gets its own probe select line, like D1. PROBE_SUB 0 is its membrane and 1 its adaptation node.
- The probe channel → slot table changes: channel 3 is AdEx; slot (0,3) is the dummy.
- **Kept:** the digital LIF (12-bit), the row × column probe select, `D1_BSEL`, `D1_CHAIN` and `ib_x2`.

## 6. Floorplan changes (applied at G2 with measured areas)

- **East channel CH_E:** narrowed from 21 to about 6 µm. It carries only clk and rst_n.
- **Other channels and guard gaps:** tightened once real block pins are known.
- **Tier-2 zone:** goes away. The bottom band holds B1, D1, R1 and AdEx. The control block shrinks (estimate ~29k) and moves into the freed east channel, which gives back height under it for the band.
- **τ-trim strip:** 2 cells, columns 0 and 2.

**Area budget (estimates in italics):**

| Block | Area (µm²) |
|---|---|
| Control block | *~29k* |
| Bias generator | *~21k* |
| Neuron array | 19.5k |
| D1 | 6.5k |
| AdEx | 2.8k |
| R1 | 1.6k |
| τ strip | 1.3k |
| **Blocks** | **~81.7k** |
| Overhead after tightening | *~23k* |
| **Total** | **~105k of 112.8k (~7 % margin)** |

## 7. Work tracks and schedule

| Gate | Date | Content |
|---|---|---|
| G2 | Nov 22 | Every block DRC/LVS clean with measured area. Final floorplan; **1×2 vs 2×2 confirmed on measured numbers.** |
| G3 | Nov 29 | Top-level assembly in magic, full LVS, PEX spot checks, precheck green, `docs/info.md`, GitHub repo (user) + CI. |
| G4 | Dec 5 | Final checks, user submits and pays (shuttle closes Dec 7). |

| Track | Owns | Next |
|---|---|---|
| Bias (B1) | `cells/bias`, `layout/bias` | rev C as in §4; assemble, route and LVS `bias_b1` |
| Control | `rtl`, `test`, `macros/neuron_ctrl` | rev E as in §5; re-harden as small as it closes |
| Slots | `cells/neuron`, `layout/slot` | F (local-mirror), CMP, AH50, AH800, REF and dummy variants |
| R1 | `cells/readout`, `cells/vreset`, `layout/readout` | `vsrc` buffer |
| Dendrite | `cells/dendrite`, `layout/dendrite` | 2× trim, ss/0 leak-OTA check, stim-B steering, hold |
| AdEx | `cells/adex`, `layout/tier2` | integrate as channel 3: adaptation on `vbp_w`, probe/synapse, corners |
| Integrator (me) | `floorplan`, top level, docs | re-floorplan at G2, then top-level assembly |

## 8. Firmware rules collected so far

- Rewrite the whole configuration after every project enable. The chip is unpowered when deselected.
- Before changing probe select, disable the probe; re-enable after the change.
- Set BIAS_EN = 0 while changing bias codes.
- Change digital LIF parameters only while LIF_EN = 0.
- Stop clk during analog measurements.
- Calibrate per die (and per speed setting): the threshold code via the REF channel and firing-rate checks, then EL, then the trims.

## 9. Neuron-core revision (decided 2026-11-19)

Two fixes go into the shared neuron cells. Every neuron layout is redone with them: all slot variants, D1 and AdEx.

1. **Axon-hillock detector (`det_ah`).** Its third stage is starved from `vbp_st`. XN3 stays on `vsrc` (the "st3" variant). Moving it to vss ("st3v") was rejected: once vsrc > ~0.55 V, the spike output sticks high.
   - **Why:** the unstarved stage drew ~40 µA for ~0.3 µs per spike into the shared `vsrc` line. With 13 neurons firing together at S = 1000, the line oscillated and neurons re-fired.
   - **R1 track's simulation of the fix:** +58–79 mV with 13 neurons, no oscillation.
2. **Leak OTA (`leak_ota_deg`).** Input devices 4/1 and degeneration diodes 8/1, plus **nominal EL = 1.30 V**. Nominal threshold and reset move to 1.38 / 1.30 V.
   - **Why:** at ss/0 °C the old OTA dropped to 2.8 S/A and could source only 25 % of its bias, because the tail had 1–40 mV of headroom.
   - **D1 track's simulation of the fix:** all 15 corner/temperature cases pass at S = 100. At S = 1000 it still falls short at ss/0 °C (3.8 S/A, 36 %), so cold, slow-silicon operation above about S = 300 stays outside the guaranteed envelope.

**Other confirmed results from this round:**
- **Control block rev E:** 166 × 166 µm.
- **AdEx:** 2.8k µm²; `vbp_w` covers 0.5–30 nA at S = 100.
- **`vsrc` buffer:** fits inside the R1 corner, which now has pins `vth_ref` and `vsrc`.
- **Dendrite D1:** layout clean, **but its two plateau trims (`trim_gap4w`) still have to be drawn.**

## 10. Floorplan v2 (2026-11-19, from measured shapes)

All coordinates are tile µm.

| Block | Box | Notes |
|---|---|---|
| Neuron array (NA) | x 8–120, y 140–314 | Moved up 4 µm. Bias lines arrive along a ~7 µm channel at y ~131–138. |
| D1 | x 8–70.5, y 12–116 | |
| τ-trim cells | col 0: x 8–45, y 118–130; col 2: x 64–101, y 118–130 | The col 2 cell sits in a notch of B1. |
| B1 bias generator | x 73.5–345, y 12–127, ~115 tall, notched | Notches: R1 corner (x 262–302, y 12–54) and τ cell (x 73.5–103, y 116–127). ua[0] at x 327. Feed-through for vreset, vsrc, abus and en_b from R1 to its top edge. |
| R1 corner | x 262–302, y 12–54, inside B1's notch | ua[1] strap at x 280.6–286.6. |
| AdEx | x 129–167, y 140 up, ~38 × 75 | Re-laid out tall and thin. |
| Control block (166 × 166) | x 170–336, y 151–317 | clk and rst_n move to the north edge, so the macro needs a pin-order update and re-harden. The east channel goes away. |

The Metal4 power stripes may cross any block, because every block uses Metal1–3 only.

## 11. Speed envelope (2026-11-19, `docs/research/speed-limits.md`)

Schematic simulation, biases scaled ×S/100, threshold recalibrated per corner and speed.

| Speed | Result |
|---|---|
| **S = 10–1000** | Supported. At S ≥ ~300, use the operating point EL / Vth / Vreset = **1.50 / 1.58 / 1.50 V** (firmware only), so the leak OTA passes every corner. |
| **S ≈ 2000** | Reachable with the same operating point. |
| **S = 10000** | **Not supported.** Limits, in order: the CMP comparator trip point falls with its scaled bias and latches; the shared `vsrc` line misfires idle neurons after a 13-neuron burst; Vreset settling; D1 plateau threshold; AdEx τ_w. |

**Firmware rules above S = 1000:**
- Stimulate at most ~4 array neurons at the same moment.
- Set `ib_x2`.
- Use the ÷1 ua[0] mode. The ÷16 mode needs more than 5 V on the pad above ~S = 1000.

**10,000× is parked (2026-11-19).** It is out of scope for this tapeout. It will be revisited later as a design study for a future chip. The starting list is in `docs/research/speed-limits.md`:
- an S-independent comparator / plateau-detector bias;
- `vsrc` and Vreset buffers biased from the scaled master;
- a wider leak OTA;
- `vbn_ref` / `vbp_syn` moved one ladder tap higher.

## 12. Open items to resume (2026-11-19, end of day)

1. **Blocker in the shared `det_ah` (owner: slot track).** With BIAS_EN = 0 the starved third stage has no pull-up. Its node floats at ~1.5 V, the output inverter draws ~63 µA per neuron (~1 mA for the array), and `spk` sits at 1.2–2.3 V, so the reset state is neither safe nor defined. Found by the AdEx track (`sim/tb/tier2/tb_det_zero.py`). Fix: a weak pull-up on that node that is active when the bias is off. **Re-verify every det_ah user afterwards**: slots, D1's plateau detectors and AdEx.
2. **D1 needs 70 × 104 µm**, up from 62.5. With the bigger OTAs plus both trims, it doesn't fit 62.5 wide. Floorplan v2 then moves B1's left edge to about x 80, which leaves ~265 µm against the ~264 B1 needs. The τ-trim notch moves with it. Check against B1's final width.
3. **D1 plateau at ff/85 runs long:** 2.3 ms and 27 spikes, against 16–18 everywhere else. Not yet investigated.
4. **AdEx 38 µm-wide re-layout** didn't route at 61 µm tall. Next try is ~72–75 µm tall.
5. **Slots:** H and CMP need re-routing, then P. DRC, LVS and PEX haven't been run yet on the 6 routed variants.
6. **B1** notched layout: status in `layout/bias/README.md`.
7. **Top level:** control block pin-order change (clk and rst_n to the north edge), then re-harden; then assembly.

The resume notes are at the top of each track's README (`layout/slot`, `layout/dendrite`, `layout/bias`, `cells/adex`).
8. **Integration note:** CMP's `vth_cmp` comes in on column 1's `aux` line, since column 1 has no τ-trim cell. Connect B1's `vth_cmp` to column 1 `aux` at top level. The probe tap gained a third series switch (XSC) to fix a cross-column leak bug.
9. **Control block pins (floorplan v2, run revE2_166):** spk_in[3] (AdEx) and spk_in[13] (D1) moved to the west end of the macro's south edge, next to probe_sel_adex and the D1 lines. The rest of the array lines are on the west edge at tile y 221–315.

## 13. Status update (2026-11-19, evening)

Items 1–5 of §12 are resolved, except CMP:
- **det_ah reset fix:** done (keeper XK). Re-verified in the slots (15 cases with biases off: ≤ 0.3 nA) and in AdEx (10 pA in PEX). D1's plateau detectors also needed a weak pull-up XQ (0.22/4, gated by the second-stage node).
- **D1:** 70 × 104 µm, DRC/LVS clean, both trims inside. The ff/85 plateau outlier is fixed (XTP L = 2 µm).
- **AdEx:** 38 × 73 µm, DRC/LVS clean.
- **Slots:** 8 of 9 variants plus trim_tau4 are DRC/LVS clean. AH800's capacitor is now ~740 fF. **CMP** is being re-placed, about 4 h allowed; if it doesn't come out clean, CMP drops its gap trim (nibble 6 is left unconnected at the top level; the macro, TRIM_MASK and the floorplan are unchanged).

**Decision: post-layout node capacitance is accepted as is.**
- D1 measures 237–272 fF against the 200 fF design, so its time constants run 15–30 % long and a single-pulse EPSP is 45 mV instead of 63 mV. Clustered input needs N = 4 pulses instead of 3; distributed input stays silent up to N = 6.
- Reasons for keeping it: the clustered vs distributed discrimination survives, the synaptic weight (vbp_w) is programmable, and τ is measured on silicon.
- The slots likely see a similar offset (their post-layout f–I is 0.79–0.93× schematic). Per-die calibration covers it.

**Update 2026-11-20:**
- **CMP double slot (done):** CMP keeps its 4-bit gap trim (nibble 6) in a 28 × 87 µm slot at column 3, rows 0–1, the
  former dummy slot's area; the dummy slot is gone. CMP and S2 swapped places (CMP (1,3), S2 (1,1)); spike channels
  and trim nibbles are unchanged, `vth_cmp` now rides on column 3's `aux` (column 1's floats). The control macro was not
  re-hardened, so **probe SEL 4 reads CMP and SEL 12 reads S2** (docs/info.md, docs/regmap.md §3.1). Cell DRC/LVS
  clean; post-layout f–I 0.82–0.83× schematic; gap-trim range −25.6 … +19.5 mV, monotonic (layout/slot/README.md).
  Full chip rebuilt with `CMP_TRIM = True`: LVS unique match (see layout/top/README.md for DRC/precheck).
- ~~**B1 τ-trim reference (blocked, decision needed):** `trim_tau4` needs `vg` = the gate of a `trim_ref_n` (16 × 1/2 nfet
  diodes on `vsn`) carrying the leak-IDAC current. B1 rev C has no such device: the leak IDAC (`Xi0`, idac_p) drives only
  the `vbn_leak` master `rx_n4` (4 × 2/4 diodes to vss); `vsn` exists, `vg` does not. Exporting it needs a B1 schematic
  change (e.g. a second idac_p on i0's code into a `trim_ref_n`, ~25 × 35 µm + ~110 µm²), so the P leak-τ trims stay inert.~~
  **Resolved the same day (user decision: re-reference the trim, B1 unchanged):** `trim_tau4` rev B mirrors `vbn_leak`
  on vss directly (L = 4 nfet units like the `rx_n4` master, source switches, 4 : 1 pfet mirror into a 2 × 2/4 `aux`
  diode). Code meaning unchanged: τ_P = τ_S · 16/(8 + c), 0.50× … 1.44× leak current. Verified with the full B1 rev C
  netlist on `vbn_leak`: monotonic at every corner and leak code, τ_S/τ_P 0.49–0.56 / 0.96–1.06 / 1.35–1.49 at
  codes 0 / 8 / 15; mismatch σ 14 % (a per-neuron gain, what the trim corrects). Same 37 × 11.8 cell, DRC/LVS clean;
  both τ cells' `vbn_leak` pins are routed to B1's `vbn_leak` at the top level. Details: `layout/slot/README.md`
  "trim_tau4 rev B".
