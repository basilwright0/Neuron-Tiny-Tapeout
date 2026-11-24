# M2 phase 1c: 10000× level 3 design proposal (draft, 2026-11-22)

Status: **proposal only**. No cell, layout or RTL is changed, and nothing has been simulated for this note.
Base: `m2-compact` @ 330bf04. Sources: `docs/research/speed-limits.md` (results table and roadmap), `docs/10 Timeline.md` (1c and the gate), `docs/HANDOFF.md` §5, the netlists in `cells/`.
"1×" below means the slow end of the documented range: S = 10, with S = 100 as the bench reference. The fixed lines behave the same at S = 1.

## 1. Goal and what limits 10000×

Level 3 must make CMP, D1, AdEx, the `vsrc` line and Vreset pass at S = 10000 on typical and fast silicon (speed-limits, roadmap table). It adds **no new DAC codes**, so `docs/regmap.md` and the control macro stay as they are.
The root cause is the same for all five: every bias follows ua[0]. That is right for neural currents and wrong for infrastructure.

| Circuit | Bias today | Failure at S = 10000 (speed-limits.md) | Max S |
|---|---|---|---|
| CMP `det_cmp` | tail, hysteresis and starve on `vbp_st` (I_st ∝ S) | the DC trip falls 115–125 mV below vth_cmp, crosses Vreset, and spk latches high at tt/ss/ff. It already latches at 3000 ff/85. | ~2000 |
| D1 `pdet` | starve on `vbp_st`; XNI is half the W/L of the soma's | plateau threshold +57–78 mV over its S = 100 value, so there is no plateau at tt/ff | ~1000 |
| vsrc buffer + line | ib_r1 (4 µA, fixed): tail ~1.1 µA, pull-up ~16 µA | 13 neurons together: 5–6 idle neurons misfire, dip −150…−218 mV, ISI +31–40 % | 1000 (13 together) |
| Vreset buffer | 30 µA tail from ib_r1 (fixed) | membranes 10–30 mV off at 0.9 t_ref (with ib_x2: 10–16 mV). That run still had the W0.5 switch. | 3000–5000 |
| AdEx DPI decay | XT1..3 (3 × 0.22/15) on `vbn_leak` | τ_w 2.3× too long, b −32 % | 1000–3000 |

The leak OTA at ss/sf (level 4) is out of scope, so **ss/0 still fails at 10000 after level 3** (speed-limits, "Cheap fixes" 1).

## 2. Per-circuit changes

Design rule used here: wherever possible, take the fixed bias from **`vbn_prb`**. It is a bias_vi copy (~1 µA into a 2/2 diode, `cells/bias/bias_vi.spice:40-41`). It does not depend on ua[0] or ib_x2, and it is already a column net in every slot, D1 and AdEx (`layout/top/config.py:78,166,183`). A local mirror off `vbn_prb` therefore needs **no new column line or band track**.

### 2.1 CMP comparator: fixed tail (from `vbn_prb`)
- **Today:** `slot_cmp_h` XD connects det_cmp's vbp to `vbp_st` (`cells/neuron/slot.spice:142`). Inside det_cmp, XPT 1/2, XH2 1/6 and the inv3s starve all hang on that one vbp (`cells/neuron/lif.spice:40-50`).
- **Change:** add a local leg in `slot_cmp_h`: XNC nfet 2/2 (gate `vbn_prb`, 1:1 with XDB, ~1 µA) into XPC, a pfet 1/2 diode. That makes a net `vbp_cmp`, and XD's vbp moves from `vbp_st` to `vbp_cmp`. The det_cmp devices are unchanged. `vbp_st` stays as a feed-through.
  - Nominal tail: ~1 µA, which is the S = 1000 value where CMP passes (ratio 0.86–1.49, spike 27–35 ns).
  - Sweep 0.5 / 1 / 2 µA to choose.
  - Cost: +2 devices and ~3 µA per CMP at every S.
- **Expected effect:**
  - At 1×: the offset becomes a constant ~−45 mV (today −20 mV at S = 100), which a one-time vth_cmp calibration absorbs. The comparator is much faster than the neuron.
  - At 10000×: the offset stays ~−45 mV instead of −120 mV, so there is no latch.
  - Delay ~30 ns against τ_m = 1 µs and t_ref 200 ns: expect a ratio ~0.8–1.2. **Not simulated.**
- **Catch: vth_cmp range.** The `vdacr_vc` range tops out at 1.511 V (`bias_vi.spice:113`). At the raised-EL point (Vth 1.58 V) CMP needs ~1.62 V.
  - Either shift the vth_cmp DAC up by ~+0.12 V (R_base 53 → ~57 sq, same 5 bits; see §3),
  - or run CMP only at EL 1.3 V (tt/ff).
- **Layout:**
  - `slot_cmp_h` is a **tall** double slot (28 × 87 µm, `layout/slot/README.md:56,233`). It routed in 9 iterations at that size; the 43.5 µm version never routed.
  - Adding ~10 µm² of devices needs a re-place and re-route of this one cell, which is likely to succeed at 87 µm. `vbn_prb` is already a pin there (prb_tap XMB).
  - No new column line, band track or top-level change.

### 2.2 D1 `pdet`: tracking input (no new bias)
- A fixed starve does **not** fix pdet. vsrc is recalibrated per S for the soma, so a fixed-starve pdet would drift the other way by ΔVgs_soma(S).
- **Change:** match pdet's first stage to det_ah:
  - XNI 1/1 → 1/0.5 (`cells/dendrite/dendrite.spice:62`; soma XNI 1/0.5 at `lif.spice:60`);
  - hysteresis XNH 1/1 → 1/0.5 (`dendrite.spice:83`), which keeps the ×2 hysteresis ratio.
- The pdet trip then equals the soma trip at every S and corner. The +20–25 mV plateau offset that geometry used to give comes from the existing gap trims ta/tb (nibbles 7/8, `trim_gap4w`):
  - The trims set a voltage that is ratiometric to vbn_leak, so the offset does not change with S.
  - Span −44…+55 mV, step 6.6 mV at 27 °C (`cells/dendrite/dtrim.spice:3`). +25 mV is about code 10 of 15.
  - Trim code 0 (−44 mV) keeps the plateau safely above the soma threshold.
- **Expected effect:**
  - At 1×: unchanged after calibration. The resting current rises slightly (~10 → ~20 nA).
  - At 10000×: the plateau-threshold shift drops from +57–78 mV to roughly the matching error (estimate < 15 mV). The tt/ff plateau should return; ss/0 stays leak-limited.
- **Layout:** same device count and +0.5 µm² gate. It rides on the phase-2 regeneration of D1 (70 × 104), with no new lines.

### 2.3 vsrc buffer and line: S-scaled pull-up and decap, fixed part kept
- **Today:** XT 0.22/2 and XU 1.6/1 on R1's vbp (`cells/vsrc/vsrc_buf.spice:19,25`). R1 is 40 × 40 and "filled edge to edge" (`layout/readout/README.md:36`). The R1 notch has only 2 µm of slack (`floorplan.py:43,48`).
- **Change A (no R1 change):**
  - Add an S-scaled pull-up on the vsrc line: XU2, 2 × pfet 1/2 on `vbp_st`, ≈ 25 µA at S = 10000 and 25 nA at S = 10.
  - Place it in B1 beside the R1 corridor (`B1_CORRIDOR`, `floorplan.py:44`), which the vsrc line already passes. It is a DC source, so its position on the line doesn't matter.
  - Add a decap on the vsrc line: 0.5–1 pF mcap (~125–250 µm² at ~4 fF/µm²), in B1's phase-2 sub-block next to the corridor.
- **Change B (only if A fails):** an S-scaled leg in parallel with the stage-1 tail.
  - It needs an R1 abutment pin on the tail node t and R1 re-layout.
  - Cap it at ~3× so f_u = gm1/Cc stays below the shunt pole (PM ≥ 60°).
- **Expected effect:**
  - At 1×: unchanged (the scaled parts are < 1 %).
  - At 10000×: pull-up slew rises ~2.5×. The dip should be roughly halved, but the 13-neuron burst charge (~0.3 pC/spike) is far beyond any practical decap, so **a pass with 13 neurons is not certain**. The fallback is the existing firmware rule of at most ~4 neurons stimulated together.

### 2.4 Vreset buffer: measure first
- The only 10000× data point predates level 2. At 60 µA with ib_x2 the line recovered in 90 ns, but the membranes were still 10–16 mV off, which points at the W0.5 switch that 68c3efa widened to W1.
- **Step 0:** rerun `tb_vreset.py` at wsw = 1u with ib_x2.
- **If it still fails:** add a scaled tail leg on `vbp_st` (pfet 2 × 1/2, ≤ 30 µA at 10000) on XPT's node (`cells/vreset/vreset_buf.spice:40`).
  - This needs an R1 pin and R1 re-layout (as 2.3 B).
  - Check tail headroom at vin = 1.5 V, ss/0: Vov rises with current, and the input range already tops out at 1.5 V.
- **No ib_r1 scaling:** scaling the shared ib_r1 would also scale the Vreset tail and the 400 µA pad driver past their headroom.

### 2.5 AdEx DPI decay: geometry-true ratio (stays S-tracking)
- The decay is a **neural** time constant, so it must keep scaling with S. No fixed bias here.
- **Hypothesis:** the 0.22 µm stack carries ~3× its W/L share in weak inversion (narrow-width effect, `adex.spice:35-36`). That bonus fades in moderate inversion at 100× current, so Itau falls ~2–3× and τ_w doubles.
- **Change:** replace XT1..XT3 (`cells/adex/adex.spice:58-60`) with 4 × nfet 1/16 in series (W/L 1/64, no narrow-width effect). That gives the same Itau ≈ 10 pA at Ib_leak 324 pA, and a ratio that holds in every inversion level.
  - Optionally widen XW 0.22/8 (`adex.spice:62`) so it stays in weak inversion at 100× Iw.
- **Expected effect:**
  - At 1×: τ_w unchanged after calibration. Off-leakage of the wider stack at ff/85 must stay < 10 % of Itau at S = 10 (1 pA).
  - At 10000×: τ_w error drops from 2.3× to within the ±25 % calibration range (target; **unverified**).
- **Layout:** about +60 µm² of gate (+2–4 % of AdEx's 38 × 73). It rides on the phase-2 AdEx regeneration, with no new lines.
- **Cheap check first:** `sim/tb/tier2/tb_itau.py` at Ib_leak × 100 confirms or refutes the hypothesis in minutes.

## 3. B1 changes (all inside the phase-2 B1 split)
- Two pfet legs on `vbp_st` (vsrc pull-up XU2, optional Vreset tail), with drains to the vsrc line and the R1 tail pin. This is ~4 devices plus a 0.5–1 pF decap: ~150–300 µm² next to the corridor.
- `vbn_ref` LSB ×2 (§5). Optionally `vbp_syn` too.
- vth_cmp DAC up by +0.12 V (`vdacr_vc` R_base, `bias_vi.spice:113`): same bits, about 4 sq of poly.
- **Pins:** no new B1 output to the array or the macro. At most one abutment pin per changed R1 node (B options only).
- The bias_b1 subckt port list (`cells/bias/bias_b1.spice:12`) is unchanged unless the B options are taken.

## 4. Control macro
- No new code bits, no new mode lines, no regmap change.
- The macro↔B1 code lines (regmap.md:245) are untouched, so **no re-hardening is needed**.
- Only the meaning of some codes changes:
  - the vbn_ref (and vbp_syn) LSB;
  - the vth_cmp range;
  - S up to 10000 (info.md currently says 10–1000).
- Those go into `docs/regmap.md` §3.2 and the `docs/info.md` firmware rules.

## 5. Level-2 leftovers (prerequisites)
1. **The `vbn_ref`/`vbp_syn` tap change was never committed.**
   - bias_b1 is unchanged since rev C: `vbn_ref` is still on vgp3/rx_n2 and `vbp_syn` on vgn5/rx_p24 (`bias_b1.spice:21-24`, last touched in 946cd68).
   - `docs/08 Updated Plan.md:192` lists it as a future item only.
   - **Still needed for `vbn_ref`:** it needs code ≤ 23.8 at S = 10000 ss/0 at EL 1.3, and 1.5–2× that at EL 1.5, which is more than 31.
   - vgp3 is already the n-ladder's highest tap (`gen_cells.py:242`). The simplest equivalent is a receiver swap, rx_n2 → rx_n1 (both exist in `bias_rx.spice`).
   - `vbp_syn` (max weight 1.2× at 10000) is optional: rx_p24 → rx_p05.
   - Cost: half the code resolution at every S (t_ref steps ~7 %).
2. **The W1 reset switch is in the slots only.**
   - AdEx (`adex.spice:118`) and the D1 soma (`dendrite.spice:135`) instantiate `refrac` with its default wsw = 0.5u (`lif.spice:28`).
   - Add `wsw=1u` to both, in the phase-2 D1/AdEx regeneration.
3. **Level 1** (EL 1.5 V, Iref 100 µA ÷1, ≤ 30 pF on ua[1], ib_x2) is firmware and board work. The gate benches must use it.

## 6. Verification plan
Each stage must pass before the next starts. ngspice runs in the `scripts/eda.sh` container.

| Stage | Benches (reuse) | Cases | Where, runtime (estimate) |
|---|---|---|---|
| 0 pre-checks | `tier2/tb_itau.py`, `speed/tb_vreset.py` (wsw 1u), `speed/tb_bias_top.py` (rx swap) | S 100/10000, tt/27, ss/0 | local, < 1 h |
| 1 schematic | `speed/tb_fi.py` via `run_fi.sh` (slot_cmp_h, slot_ah, the variants), `speed/tb_d1.py`, `speed/tb_adex.py`, `speed/tb_vsrc.py` (n = 1/4/13), `speed/tb_vreset.py`, `tb_slot_detoff.py` / `tier2/tb_det_zero.py` (BIAS_EN = 0 state of the CMP leg) | S = 10, 100, 1000, 10000 × tt/27 and ss/0 (plus ff/85 for CMP and vsrc) | local, JOBS 8–12 of 20 cores: ~4–6 h |
| 2 cell post-layout | `tb_slot_fi.py` (PEX_NAME for slot_cmp_h), the D1/AdEx PEX variants of tb_d1/tb_adex | 1000/10000, tt/27, ss/0 | local, ~2 h |
| 3 gate | full chip: `sim/tb/top/vm_pex.sh` + `run_batch.sh` with a new S = 10000 mode (topbench S parameter; f-I per neuron type, 13-neuron vsrc burst, Vreset) | 10000, tt/27, ff/27, ss/0 | Boat VM (large), build+extract ~1 h, batch ~4–8 h; self-stop; ~10–20 VM-h of ~365 |

Pass criteria (proposed):
- f/f_ideal 0.7–1.4 against the S = 100 baseline;
- no latch;
- D1 plateau present, threshold within the trim span;
- τ_w within ±25 %;
- 0 idle misfires at n = 4 (n = 13 reported);
- reset error ≤ 5 mV at 0.9 t_ref.

## 7. Effort and schedule
About **3.5–4.5 working days**:

| Work | Effort |
|---|---|
| Stage 0 | 0.5 d |
| Netlist changes and stage 1 | 1–1.5 d |
| CMP relayout | 0.5 d |
| D1/AdEx/B1 deltas inside phase 2 | +0.5–1 d |
| Gate-bench S mode + VM gate | 1 d |

Against the Timeline (M2 ~Dec 1):

| By | Milestone |
|---|---|
| Nov 25 | stages 0–1 done |
| **Nov 28 checkpoint** | schematic level 3 verified, CMP cell DRC/LVS clean, B1/D1/AdEx deltas in the phase-2 netlists |
| Nov 29–30 | post-layout and the VM gate |
| Dec 1 | submittable |

This only works if the phase-2 B1 split and D1/AdEx regeneration land by ~Nov 29. If they slip, the **Timeline fallback** applies: level 3 goes onto the existing layouts. CMP and the B1 receiver swap still fit; D1/AdEx need small cell edits.

## 8. Risks
- The vsrc 13-neuron burst may not pass even with A + decap. Then the ≤4-neurons rule stays.
- The CMP fixed tail fails at ss/0 (the leak OTA dominates there anyway).
- vth_cmp at the raised EL needs the DAC shift.
- R1 is full: any B option means re-laying R1 or enlarging the notch.
- The AdEx hypothesis may be wrong. If so, a separate scaled decay leg would cost a new line, which is a scope change.
- Larger devices on D1/AdEx raise their node capacitance (already 237–272 fF in D1).
- Full-chip runs at 10000 converge less well (precond switches, `HANDOFF.md` §6).
- The VM gate has a single shot before Dec 1.

## 9. Reversible choices vs real gates
- **Reversible (sizing or netlist parameters, changeable until tapeout):**
  - CMP tail current;
  - pull-up size, decap size;
  - XW width;
  - the AdEx stack L;
  - D1 trim default code;
  - vth_cmp range shift;
  - choosing rx swaps over ladder taps.
- **Real gates (need the user's decision):**
  1. **Gate definition.** The Timeline 1c gate includes ss/0 °C, but levels 1–3 cannot pass ss/0 at 10000 (that needs the leak OTA, level 4, which is not planned). Proposal: pass at tt/ff 27 °C, report ss/0. The alternative is to add level 4, which changes M2 scope and dates.
  2. **`vbn_ref` (and `vbp_syn`) LSB ×2** halves refractory/weight code resolution at every speed. The register format is unchanged, but the code meaning changes.
  3. **Conditional:** if Vreset or vsrc still fail, either re-lay R1 (+~1 d) or accept feature rules at 10000: t_ref ≥ 0.5 µs instead of 200 ns, and ≤ 4 neurons stimulated together.
  4. **Conditional:** if phase 2 slips, level 3 falls back to the existing layouts per the Timeline.

## Step-0 pre-check results (2026-11-22, schematic, local; logs in sim/results/level3_step0/)
- **AdEx decay current (tb_itau.py): the §2.5 hypothesis is refuted.** The 3 x 0.22/15 stack keeps 0.75x (tt/27) / 0.74x (ss/0) of linear scaling from S = 100 to 10000 (Itau 10.06 pA -> 758 pA). The predicted 2-3x collapse doesn't happen. A 1.33x shortfall can't explain the measured 2.3x tau_w error, so the main cause is elsewhere (likely the DPI / Ig path). The 4 x 1/16 stack holds 0.91x but gives 15.6 pA instead of 10 pA; it fixes only ~20 % of the error. **Next:** find the real tau_w cause before changing AdEx.
- **Vreset with the 1 µm reset switch (tb_vreset.py, S = 10000, 15 corner/temperature cases): conditional pass, no R1 change.** The line settles within 0.2 mV everywhere (recovery 67-91 ns). The remaining error is the switch fading, so a buffer tail leg wouldn't help.
  - At Vreset 1.30 V: worst error 5.67 mV at ss/85 (tt/27 0.98 mV, ss/0 3.65 mV), against 15.6 mV with the 0.5 µm switch.
  - At 1.50 V with nominal I_ref: 26.2 mV, fail.
  - At 1.50 V with I_ref recalibrated for t_ref (x0.66 tt, x0.5 ss): tt/27 1.57 mV, ss/0 4.63 mV, ss/85 5.09 mV (0.09 over the 5 mV spec).
- **vbn_ref code range (tb_bias_top.py):** the receiver swap (rx_n2 -> rx_n1) works (code 31 = 1.99-3.60x target), but it **is probably not needed**. Raising EL to 1.5 V shortens t_ref (0.50-0.66x), which calls for *less* I_ref (about code 12 at ss/0 with no swap), not the 1.5-2x more assumed in §5.1. Baseline at EL 1.3, ss/0: code 23.8 needed, code 31 = 1.00x. **Decision (reversible, taken overnight under Chief's rule):** don't swap. This keeps the full code resolution; revisit only if the post-layout tref check needs more than code 31.
- Runtime ~4 min in total.

## Step-1 results, schematic (2026-11-22)
- **CMP (`36be54a`):** det_cmp runs on a fixed ~0.5 µA tail from a local `vbn_prb` mirror (+2 devices, no pin change).
  - S = 10000 passes at tt/27 and ff/85 (EL 1.3), and at all corners at EL 1.5; ss/0 at EL 1.3 is leak-OTA-limited (see the gate question).
  - BIAS_EN = 0: the tail is off.
  - To do: the B1 vth_cmp DAC needs +0.12 V (R_base 53 → 59 sq), plus the slot_cmp_h re-place/route and its LVS netlist.
  - Open, existing behaviour: CMP spk sits at 3.3 V with bias off.
- **D1:** the plateau-detector input XNI is now L 1 → 0.5 µm, matched to the soma (results: sim/results/level3_d1/).
  - The trip shift (pdet − soma) is 0.0–0.1 mV at every S and corner, against +31–110 mV before.
  - XNH is kept at 1/1. This is the variant with the smaller hysteresis: 16/23/42 mV at S = 100/1000/10000, giving 49 mV of re-arm margin at 10000. It is a reversible choice taken overnight. Shortening XNH too grows the hysteresis to 69 mV and latches the detector at code 8.
  - **D1 trim code (PLAT1/PLAT2, nibbles 7/8): use code ~3, not 8.** A higher code raises the d1 rest and lowers the threshold. Code 3 restores the ~+25 mV offset and gives a plateau at S = 100/1000/10000 for tt/ss/ff. Code 0 fails ss/0 at 10000.
  - S = 100 at code 3: threshold 330 vs 350 pA, plateau 1219 vs 1203 µs, burst rate −7 %. No worse than before.
  - Layout: gate length only, on 2 devices (the 2 XNI). This fits the 70 × 104 footprint; it needs a poly edit and a DRC/LVS rerun.

## Step-1 AdEx (2026-11-22, schematic; sim/results/level3_adex/summary.txt, F5real_*/F5r_* logs)
- **Root cause of tau_w 2.27x (tt) / 2.54x (ss) at S = 10000:** tau_w = nUT_eff · C_vw / I_net. XW 0.22/8 leaves weak inversion at 10-20 nA (nUT_eff 1.70x tt, 1.81x ss) and the 3 x 0.22/15 stack keeps only 0.756 of linear Itau scaling (1.32x); C_vw +1.6 %, leakage 0.1 %. Product 2.28 (measured 2.27). The §2.5 stack hypothesis alone explains only 1.32x.
- **Fix F5 (applied in cells/adex/adex.spice, pins unchanged):** XW 0.22/8 → 4/{lw}, lw default 2u; stack XT1..3 3 x 0.22/15 → XT1..5 5 x 0.5/10; XPA L 1 → 2 µm; XPB W 4 → 32 µm. The tb_adex_char.py Iw replica follows XW (4/2).
- **Verification (tb_adex.py, tau_w in S = 100 units, vs each corner's baseline at S = 100: tt 0.827, ss 0.770, ff 0.890 ms; b 43.9/46.8/39.2 pA):**

| corner | tau_w S=100 / 1000 / 10000 (ms) | b S=100 / 1000 / 10000 (pA) | tau_w ±20 % |
|---|---|---|---|
| tt/27 | 0.785 / 0.811 / 0.967 (−5/−2/+17 %) | 44.4 / 45.5 / 37.3 | pass |
| ss/0 | 0.716 / 0.741 / 0.854 (−7/−4/+11 %) | 49.0 / 50.7 / 40.6 | pass |
| ff/85 | 0.881 / 0.944 / 1.125 (−1/+6/**+26 %**) | 38.5 / 39.7 / 32.9 | **fail** |
| ff/85, lw = 1u | 0.849 / 0.896 / 1.047 (−5/+1/+18 %) | 53.3 / 56.3 / 49.8 (+36 %) | pass (tt +7 %, ss +6 % at 10000) |
- ff/85 residual: the stack ratio is worse there (dvw/dt 0.83x at S = 10000) and nUT_eff +8 %. A 4 x 0.5/12.5 stack is identical to F5 (ff 1.130, within 0.5 %), so stack count doesn't matter. **lw = 1u (XW 4/1) passes tau_w at all 9 points** but raises b ~+30 % at the same code (Ig scales with XW). b is code-trimmable (vbp_w −23 %). Open decision: lw = 1u + b code, or accept ff/85 +26 %.
- **vbp_w code:** at S = 10000 the ISI ratio rises 2.2 → 3.4 (F5; 4.1 with lw = 1u). About −40 % Iin (vbp_w code) restores ratio 2.35/2.39 (tau 0.958/0.869). This needs a per-S code in the firmware table.
- **Layout impact:** gate area +36 µm² by W·L (task estimate ~+46 µm² incl. spacing). XPB 2 → 16 µm², stack 9.9 → 25 µm², XW 1.8 → 8 µm². The 5-device stack needs a 4th row in adex_a1. A 4 x 0.5/12.5 stack is electrically equivalent and may fit 3 rows. Needed: t2gen re-placement, then the full rebuild (DRC/LVS/PEX, chip LVS, precheck). Until then the layout/ adex_a1 is LVS-stale against cells/.
- **AdEx decision (reversible, overnight):** XW = 4/1 (lw = 1u), not 4/2. Reason: F5 with lw = 2u fails τ_w at ff/85 (+26 % at S = 10000); lw = 1u passes all 9 corner/S points (S = 10000: tt +7 %, ss +6 %, ff +18 %). Cost: b +30 % at the same vbp_w code, recovered by ~23 % lower code (calibration only, no new codes). The AdEx layout (layout/tier2 adex_a1) does not match this netlist yet; the full-chip LVS still uses the old adex_a1_lvs.spice until the AdEx block is rebuilt (generator re-placement: stack needs a 4th row, or the 4 × 0.5/12.5 stack variant, which gives the same result).
