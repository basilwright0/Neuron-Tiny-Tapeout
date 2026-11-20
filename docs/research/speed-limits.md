# Speed limits: S = 1000 and S = 10000 (characterization track, 2026-11-19)

**Question.** Does every analog block work at S = 1000 (τ_m = 10 µs) and at S = 10000 (τ_m = 1 µs)? For each block: what is its maximum speed, and what limits it?

**Method.** Simulation only, on the schematic netlists as of 2026-11-19, which include the §9 fixes (`det_ah` starved third stage, `leak_ota_deg` 4/1 + 8/1, EL/Vth/Vreset = 1.30/1.38/1.30 V). Every bias current is scaled by S/100 from the S = 100 values the existing benches use:

- I_leak = 324 pA × S/100;
- I_st = 100 nA × S/100;
- I_ref = 50 fF·1.35 V/(2 ms/S);
- synapse, axial and vbp_w currents scale the same way;
- the AH threshold (vsrc / vth_ref) is recalibrated per corner and speed, as bring-up would do.

The R1 biases (vsrc buffer, Vreset buffer, pad driver) and the probe bias come from `bias_vi`, so they do **not** scale with S.

**Corners.** Typical/27 °C plus the worst cases ss/0, ff/85 and sf/0 (fs/85 and ss/85 where relevant).

**Files.** Benches are in `sim/tb/speed/`; results and summaries are in `sim/results/speed/` (`*_summary.txt`, `*.out`, `fi_*.json`).

## Answer

- **The chip as a whole works at S = 1000** at the nominal operating point, with one exception: the leak OTA at ss/0 °C (and sf/0 °C), which §9 already flagged.
  - At ss/0 the near-rheobase rate is 25 % high (S slot) to 50 % high (CMP).
  - **Fix:** raise EL/Vth/Vreset by 0.2 V to 1.50/1.58/1.50 V. This is firmware only. It passes every leak-OTA corner at S = 1000.
- **The chip does not work as a whole at S = 10000.**
  - **First to fail** (all fail already at S = 2000–3000):
    1. **CMP comparator neuron.** At ff/85 it latches with spk stuck high at S = 3000; at S = 10000 it latches at every corner tested (tt/27, ss/0, ff/85).
    2. **Leak OTA tail headroom** at slow-nfet corners (ss, sf). The rheobase collapses to 13–30 % at S = 10000.
    3. **Shared vsrc line.** With 13 neurons spiking together, 6 idle neurons misfire at S = 3000 and S = 10000.
  - **Next to fail at S = 10000:**
    - the Vreset buffer plus reset switch (reset value 12–30 mV off at the end of t_ref);
    - D1 (plateau threshold +70–80 mV, no plateau at tt or ff);
    - AdEx (τ_w 2.3× too long).
  - The bias generator, synapse, AH slots (at raised EL) and readout (≤ 50 pF board) still work at S = 10000.
- **Maximum speed of the chip:** **S ≈ 1000 as designed; about 2000 with the EL = 1.5 V operating point if all 13 array neurons may fire together** (the CMP and vsrc limits). With raised EL, the AH slots alone reach S ≈ 3000 at every corner tested.

## Results table

The key number in each cell is the worst corner tested unless the cell says otherwise. "rate ratio" is f/f_ideal of the LIF with the nominal g, Vth−EL and t_ref.

| Block | S = 100 | S = 1000 | S = 10000 | Max S | Limiting factor | Change needed to pass 10000 |
|---|---|---|---|---|---|---|
| **B1 bias generator** (all 5 IDAC lines + vbp_st, top level with receivers) | pass | **pass**: lines track the master to 0.79–0.97; recalibrated codes leak 9→9.5, ref 14→15, syn 16→20, ax 9→9.6, w 8→10 | **pass (recalibrate)**: ratios 0.59–0.91; codes leak ≤12.2, ref ≤23.8 (ss/0), syn ≤26, ax ≤12.3, w ≤11 (all ≤31). vbn_ref at ss/0 has no headroom left (code 31 = 1.00× target). syn max weight only 1.2× the S=100 code-16 weight (1.9× at S=100). | ~10000, ÷1 mode only | Ladder/tap compression in strong inversion (vbp_syn and vbp_w taps worst); vbn_ref idac_p headroom at ss/0. ÷16 mode needs Iref = 1.6 mA at S = 10000: pad at 5.3–6.2 V, so ÷16 is unusable above S ≈ 1000 (fine for S ≤ 1000: 160 µA, pad 1.1–1.5 V) | External reference: **Iref = 100 µA in EXT ÷1** (pad 1.16–1.34 V, 0.1 V across the 1 kΩ ESD R). For more headroom on vbn_ref and vbp_syn: one LSB tap higher (×2) on those two DACs. |
| **Leak OTA** (all slots, D1, AdEx); g/Ib ≥ 5, lin ≥ 75 mV, Isat+ ≥ 90 % | pass (15/15) | **fail at ss/0, ss/27, sf/0** (ss/0: g/Ib 3.8, lin 24 mV, sources 36 %); passes all 15 cases at EL = 1.5 V | **fail at 8 of 15 cases** (ss/0: g/Ib 0.5, sources 4 %); EL = 1.5 V: still fails ss/* and sf/0, sf/85 (min g/Ib 4.1, Isat+ 42 %) | 300 at EL 1.3; ~3000 at EL 1.5 | Tail-node headroom: input 4/1 + diode 8/1 Vgs stack under EL, Vgs rising with Ib (weak → moderate inversion). OTA bandwidth is not a limit (f3dB = g/2πC at every case). | EL/Vth/Vreset +0.2 V (firmware) gets to ~3000. For 10000: wider input and diode devices (e.g. 16/1 and 32/1, same g/Ib in weak inversion at 10× current) or a lower-Vt tail; i.e. a redesign. |
| **AH slots** S/H/F/AH50/AH800 (f–I) | rate ratio 0.84–1.01 (S); AH50 0.57–0.97, AH800 0.97–1.21 (geometry, also at S=100) | **pass**: S slot 0.80–1.25 (1.25 = ss/0 at 1.1× rheo, leak OTA); rheobase 0.75–0.87 of nominal; t_ref 0.76–1.13 of nominal (recalibrate the vbn_ref code); spike 14–17 ns (w/ISI ≤ 0.005) | **fail at ss/0, sf/0** (rate at 1.1× rheo 1.8–2.4× ideal, rheobase 10–29 %); tt and ff pass (0.86–1.25). **At EL = 1.5 V all three corners tested (ss/0, sf/0, tt/27) give rheobase 0.76–0.85, ratios 0.94–1.33** (t_ref then 0.5–0.66 of nominal, recalibrated with vbn_ref). Spike 7–10 ns, w/ISI ≤ 0.033. | 1000 (EL 1.3); 3000 everywhere, 10000 at tt/ff (EL 1.5) | Leak OTA (above). The detector and refractory scale fine: spike width ∝ 1/S down to ~7 ns, and t_ref follows I_ref. | EL +0.2 V; leak-OTA resize for ss at 10000. At high S, vbn_ref must be ~1.5–2× code (t_ref shortens at higher Vreset). |
| **CMP slot** (comparator LIF) | ratio 0.93–1.23; spike 91–94 ns | **pass**: ratio 0.86–1.49 (1.49 = ss/0 at 1.1× rheo); spike 27–35 ns | **fail**: spk latched high at tt/27, ss/0, ff/85 (DC trip falls to 1.25–1.34 V, at or below Vreset = 1.30 V). With vth_cmp raised to 1.50 V it fires again, but at 0.26–0.61× the ideal rate (below 0.7× at every current). **Already fails at S = 3000 ff/85** (latched); S = 2000 still fires at all 3 corners (ratios 0.84–1.77) | **~2000** | det_cmp systematic offset grows with its tail current (I_st): its DC trip falls 20 mV (S=100) → ~45 mV (1000) → 60–75 mV (3000) → 115–125 mV (10000) below vth_cmp, and the spike widens (130 ns at S=3000, w/ISI 0.11) until the threshold meets Vreset and the output latches | Do not scale the comparator tail with S (give det_cmp a fixed or separately-ratioed bias instead of vbp_st). Recalibrating vth_cmp per speed is not enough at 10000. |
| **Synapse** syn_in (charge per pulse, I_w × S/100, widths × 100/S) | gain 1.01; fixed charge −0.7…+0.3 fC | **pass**: gain 0.99, fixed charge −0.5…+0.4 fC (the same fC as at S=100, i.e. the same relative error), residual ≤ 0.8 fC | **pass (−10 % gain)**: gain 0.90–0.91 at all corners (calibratable); fixed charge −0.1…+0.8 fC; compliance flat (1.00) to 1 µA | >10000 | Weight gain drops at strong inversion (hold switch XPH drop): 0.91 at 100 nA, 0.72 at 1 µA. A pulse's charge is set by the external stimulus pulse width (combinational `rt_out`): a 1 ms-bio pulse is 100 ns at S=10000, so the driver's edge timing (few ns) matters, not the cell. | none (calibrate the weight gain) |
| **D1 dendrite** (axial g scaled with S) | plateau threshold +110–119 mV over EL; plateau 1.15–1.82 ms (bio); attenuation 0.54; burst 17–27 spikes | **pass**: threshold +129–137 mV (+19 mV, within the gap trim); plateau 1.17–1.20 ms; attenuation 0.54–0.56; burst 17–20 spikes | **fail**: threshold +167–197 mV (+57–78 mV over S=100); at tt and ff the 8 rheobase-scaled pulse no longer triggers a plateau (d1 max +175–183 mV); ss/0 plateaus (1.6 ms) but its leak OTA has collapsed. Attenuation still 0.53–0.60. | ~1000 (3000 likely with trim) | pdet trip (starved detector, half-W/L input) rises faster with I_st than the soma's calibrated trip; leak OTA | Give pdet the same input W/L as the soma detector (tracking), or a pdet starve ratio that does not scale with S; leak-OTA fix |
| **AdEx** (adaptation ratio, τ_w in S=100 units) | ratio 1.87–2.20; τ_w 0.77–0.89 ms; b 39–47 pA | **pass**: ratio 2.15–2.30; τ_w 0.97–1.13 ms (+22–27 %); b 38–43 pA | **fail**: τ_w 1.88–2.02 ms (2.3× of S=100); b 29–30 pA (−32 %); ratio 1.97–2.23 (the two errors partly cancel); ss/0 rheobase 9 pA (leak); ΔT 78–86 mV at ss and ff | ~1000–3000 | The DPI decay is a fixed ratio of vbn_leak and cannot be trimmed separately; its time constant drifts in moderate inversion. The leak OTA. | DPI decay from its own (scalable) bias, or keep the DPI devices in weak inversion at 100× current (wider). |
| **vsrc buffer + shared line** (17 detectors; 1/4/13 spiking together) | – (earlier R1 track: fine) | **pass**: n = 1/4: peak +13–56 mV, back within 2 mV in 40–60 ns (tt), no idle misfires, ISI +1–2 %; n = 13: peak +60–146 mV, dip −60…−113 mV, ISI +2–5 %, **0 idle misfires**; ss/0 sub-threshold load shifts vsrc +46 mV before the spike | **fail**: n = 13: **5–6 idle neurons misfire**, ISI +31–40 %, dip −150…−218 mV, +50–59 mV DC shift with the line loaded; n = 4: ISI +12 %, no misfire. Also, at ss/sf the calibrated vth_ref is 0.265–0.27 V, below the 0.35–0.75 V VDAC window (0.44 V at EL 1.5). **S = 3000**: n = 13 already gives 6 idle misfires at tt, ss and ff; n = 4 is fine (ISI +3–5 %) | **1000** (13 together); ~3000 (≤4 together) | The detector load scales with S (2×I_st per neuron near threshold, spike surge), but the buffer bias (ib_r1 = 4 µA → 16 µA pull-up, ~1 µA tail) is fixed. The dip below vin pulls every idle detector's threshold down. | Scale the vsrc buffer with S (bias it from the master, or at least `ib_x2`); a larger shunt and pull-up or a local decap on the line; a non-scaling detector starve |
| **Vreset buffer** (20 simultaneous resets) | – | **pass**: line back within 5 mV in ≤133 ns (t_ref = 2 µs); membrane error at 0.9 t_ref ≤ 0.5 mV. S = 3000 (t_ref 667 ns): ≤ 0.64 mV | **fail**: line recovers in 96–125 ns, but at 0.9 t_ref (180 ns) the membranes are still 10–30 mV off (AH800 worst; 200 fF slot ~4 mV at tt). With `ib_x2` (8 µA): 90 ns, still 10–16 mV | ~3000–5000 | Fixed 30 µA tail (from ib_r1, not ∝ S) against t_ref ∝ 1/S, plus the per-neuron reset switch (W0.5/L0.5) fading as vr decays in 200 ns | Bias the buffer tail from the master (∝ S) and a wider reset switch, or treat t_ref ≥ 0.5 µs (S·t_ref_bio) as a rule |
| **Readout** (enabled slot tap → abus → pad_psf → 500 Ω TT mux → board) | – | **pass** (20 and 100 pF): pad gain 0.67, lag ≪ 1 µs, peak within 1 mV | **pass at CB ≤ ~50 pF** (20 pF: lag ~20 ns, reset step settles in ~80–100 ns of a 0.66 µs ISI); **marginal at 100 pF** (lag ~150 ns, settles in ~200–250 ns ≈ 35 % of the ISI, pre-spike peak ~16 mV low vm-referred) | ~10000 (20 pF), ~3000–5000 (100 pF) | Off-chip pole: TT mux 500 Ω × (5 + CB) pF ≈ 50 ns at 100 pF, plus the pad follower (400 µA) into the same C. In-cell follower and bus are not the limit. | Board: ≤ 30 pF on ua[1] (short trace, active probe). `ib_x2` helps only the follower part. |
| **Power** (analog VDD, probe off; rough) | ~160 µA | ~180 µA | ~350 µA | – | B1 ~110 µA fixed (bias_vi copies + strings) + ~0.8×I_nd; R1 ~50 µA fixed; neurons ~0.12 / 0.8 / 6.6 µA per slot at S = 100 / 1000 / 10000 (detector stage-1 ~0.6×I_st) × ~17 detector-equivalents. **+400 µA** while the pad driver is on. Iref (0.1–100 µA) comes from the ua[0] source. | – |

## Details by block

### 1. Bias generator (`tb_bias_top.py`, `run_bias.sh` + `analyze_bias.py`)

`bias_b1` was run at the top level, with the receivers inside and consumer replicas on each line, at I_nd = 1–100 µA.

**Line current vs S.** Each line's current tracks the master to:
- 0.92–0.97 at S = 1000;
- 0.62–0.91 at S = 10000, worst on `vbp_syn` (0.62–0.65) and `vbp_w`, `vbn_leak`, `vbn_ax` (0.73–0.81). `vbn_ref` reads 0.59 at ss/0.

The 5-bit codes absorb this gain loss. Every line stays at code ≤ 26, except `vbn_ref` at ss/0 °C, which needs 23.8 with code 31 = 1.00× target. That leaves no margin for the extra I_ref the raised-EL point needs at high S.

**Pad voltage and ÷16 mode.** At Iref = 100 µA (÷1) the pad sits at 1.16–1.34 V.

÷16 works only up to S ≈ 1000:
- at Iref = 160 µA it is within 5 % and the pad is at 1.1–1.5 V;
- at 480 µA the pad is at 1.98–4.7 V;
- at 1.6 mA the pad clamps at 5–6 V and the currents collapse to 0.2–0.3.

**What S = 10000 needs:** a 100 µA external reference on ÷1. Nothing in B1 breaks.

**Fixed-ratio line.** `vbp_st` tracks to 0.91 at S = 10000. Its line falls to 0.77–1.05 V; the starve pfets are then in strong inversion at ~13 µA, which is still fine.

### 2. Neuron slots (`tb_fi.py`, `summarize_fi.py`, `fi_summary.txt`)

The reference is the ideal LIF with the nominal g, Vth − EL and t_ref = 2 ms/S, with Vreset = EL.

**Baseline at S = 100.** The deviations from the ideal at S = 100 are geometry, not speed: AH50 runs at 0.57–0.85 because of its 8 fF Cfb on 50 fF, and CMP/AH800 fire 1.2× high at 1.1× rheobase. Judge every speed against this baseline.

**What does not limit speed.** Spike width falls with S (S slot: 52 → 14 → 7 ns). It stays ≤ 3.3 % of the ISI at 8× rheobase even at S = 10000, so spike width vs ISI is not a limit.

**Refractory period.** t_ref follows I_ref to within 0.7–1.15 of nominal at every S. That is per-die calibration of the vbn_ref code.

**What limits the AH slots.** The leak OTA does (§9 known issue, quantified here).

**The CMP slot is the first neuron to fail.** As S rises, its comparator trip point sinks toward Vreset and its spike widens, until the comparator latches:
- latched at S = 3000 ff/85;
- latched at S = 10000 at tt/27, ss/0 and ff/85 (sf/0 not run).

### 3. Synapse (`tb_syn.py`)

Q(t_w) stays linear when pulses shrink with S. The fixed charge is about ±0.5 fC at every S. Because the bio-equal charge does not change with S, the relative error does not grow either.

The only effect of speed is a 9–10 % weight-gain loss at S = 10000, which is a calibration.

### 4. D1 and AdEx (`tb_d1.py`, `tb_adex.py`)

**D1** is unchanged at S = 1000 apart from a +19 mV higher plateau threshold, which the trim can absorb.

At S = 10000 the plateau detector's threshold has moved +57–78 mV. Note the earlier mistake: a first D1 run did not scale g_ax, which made the attenuation look 5× worse. Its output is kept as `d1_gaxbug.out` and should be ignored.

**AdEx** keeps its adaptation ratio at S = 1000; τ_w is +22 % there, within calibration. At S = 10000 τ_w doubles (2.3× the S = 100 value).

### 5. vsrc line (`tb_vsrc.py`)

The idle-neuron misfires come from the **negative dip** of vsrc after the simultaneous spike surge (−150 to −218 mV at S = 10000). That dip lowers every idle detector's trip point.

### 6. Vreset (`tb_vreset.py`)

The pass/fail criterion is the reset value a neuron keeps when its switch lets go, not the line alone.

### 7. Readout (`tb_readout.py` + the manual waveform read in `readout_summary.txt`)

The automatic error metrics in that bench were too strict and its S = 10000 linear fit failed. The figures in the table come from reading the waveforms directly.

## Cheap fixes, in order of value

1. **Operating point EL/Vth/Vreset = 1.50/1.58/1.50 V for S > 300.** This is firmware and calibration only.
   - It fixes the leak OTA at S = 1000 at every corner and up to ~3000 at every corner except ss/0 (marginal: lin 73 mV, Isat+ 87 %); at S = 10000 ss and sf corners still fail.
   - It restores AH rheobase at S = 10000 (0.76–0.85).
   - It brings vth_ref back into its 0.35–0.75 V window at slow corners (0.44 V).
   - Cost: t_ref shortens to 0.5–0.7 of nominal (recalibrate the vbn_ref code; at S = 10000 ss/0 this exceeds code 31).
   - The Vreset buffer's input range tops out at 1.5 V. (EL 1.4 V gets about half the benefit; see `leak_summary_EL1.4.txt`.)
2. **Firmware rule: at most ~4 array neurons stimulated synchronously above S = 1000.** Otherwise the vsrc dip makes idle neurons misfire. Use `ib_x2` at high S; it helps Vreset and the pad, and costs only R1 current.
3. **Design changes if S = 10000 matters** (not made):
   - give det_cmp and pdet a bias that does not scale with S (or a smaller ratio of I_st);
   - bias the vsrc and Vreset buffers from the master instead of `bias_vi`;
   - widen the leak-OTA input and diode devices;
   - one tap higher for `vbn_ref` and `vbp_syn`.

## Caveats

- **Schematic only.** No PEX was run at speed.
  - The existing PEX netlists were not used because the layout tracks are re-routing them.
  - Line parasitics are lumped: vsrc as 3 × (33 Ω, 20 fF); Vreset as 300 Ω + 250 fF.
- **Corner coverage.**
  - Variant slots (AH50, AH800, F, H) were run at tt/27 and ss/0 only.
  - CMP and S slots were run at four corners.
  - The CMP DC "rheobase" column is not meaningful: the comparator's DC trip is offset from its transient threshold.
- **Power is a rough budget.** It is built from bench supply currents and earlier B1 numbers, not a full-chip run.
- **Inconsistency found, not changed.**
  - §9 of the plan says `det_ah`'s XN3 moves to vss, but `cells/neuron/lif.spice` keeps XN3 on vsrc (the `st3v` variant was rejected there). These results use the cell as it is.
  - `bias_b1` uses `rx_p05` on `vbp_w`, while the `adex.spice` header says `rx_p1`.


## Roadmap to S = 10000 (future chip; parked 2026-11-19)

**Root cause.** Every bias is scaled with the ua[0] reference. That is right for the *neural* currents (leak, synapse, refractory), which set the time constants. It is wrong for the *infrastructure* circuits (comparators, detectors, buffers): at high S they either run at the wrong bias, or stay too weak for the faster currents around them.

**Design lesson:** decide up front which biases track speed and which don't.

| Level | Change | Effect | Cost |
|---|---|---|---|
| 1. Free (firmware, board) | EL/Vth/Vreset +0.2 V (1.50/1.58/1.50 V). Iref = 100 µA on EXT ÷1 (÷16 needs 5–6 V on the pad). ≤ 30 pF on ua[1]. ≤ ~4 neurons stimulated at once. `ib_x2`. | **~3000× on this chip** | none |
| 2. Small silicon | `vbn_ref` and `vbp_syn` one ladder tap higher. Wider per-neuron reset switch (W0.5 → ~W1). | Refractory and weight headroom; reset completes within t_ref | ~½ day each; the reset switch touches every slot layout |
| 3. Separate infrastructure biases | Comparator (`det_cmp`) tail on a fixed bias from the V-to-I path. D1 `pdet` input matched to the soma detector, or a non-scaling starve. `vsrc` and Vreset buffers biased from the scaled master, plus a local decap on `vsrc`. AdEx DPI decay on its own bias, or wider devices. | CMP, D1, AdEx, `vsrc` and Vreset pass at 10000× on typical and fast silicon | ~2–3 days; new bias lines, regmap/control block, CMP column wiring |
| 4. Leak OTA | Inputs ~16/1 and diodes ~32/1, or a lower-Vt tail | 10000× at every corner, slow silicon included | ~3+ days; bigger devices in every neuron, so slots likely grow ~10 % and every slot, D1 and AdEx is re-laid out |

| Target | Needs |
|---|---|
| ~3000× | Level 1 |
| 10000× on typical/fast silicon | Levels 1–3 (~1 week) |
| 10000× at every corner | Levels 1–4 |

Analog supply at 10000× is ~350 µA, plus 400 µA with the pad driver on, so power is not a limit.
