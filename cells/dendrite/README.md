# D1 dendritic neuron (`dend_d1`)

Schematic: `dendrite.spice` + `dtrim.spice`. Include after `neuron/membrane.spice`, `neuron/lif.spice`, `readout/readout.spice` and `neuron/synapse.spice`.
Testbenches are in `sim/tb/dendrite/`, results in `sim/results/dendrite/`, layout in `layout/dendrite/`.

**2026-11-19 cell update.**
- **Shared neuron cells:** `leak_ota_deg` now has 4/1 inputs and 8/1 degeneration diodes. `det_ah`'s third stage is starved and has the reset keeper XK. Nominal EL / Vth / Vreset are 1.30 / 1.38 / 1.30 V.
- **D1's own copies follow:** `ax_ota_h`, `leak_ota_dega` and the plateau detector `pdet`.
- **`pdet` additions:**
  - XS3 starve on the third stage. Peak vsrc current per crossing drops 43 → 10 µA.
  - XK keeper, gated by xb.
  - XQ weak pull-up (0.22/4, gated by p). The keeper alone left xb stuck high with 30–40 µA at ss/0, ss/27 and sf/0 with biases off.
- **Timer pFET XTP is now L = 2 µm** (was 0.28). This fixes the ff/85 plateau outlier.
- **The trims are part of `dend_d1`.** `dend_d1t` is kept only as an alias.

## Topology

- **Soma** `soma_h`: the axon-hillock LIF `lif_ah` (200 fF MOS cap, `leak_ota_deg`, `det_ah` + 8 fF MOM Cfb, refractory). Two additions:
  - The leak output reaches the membrane through a hold switch XHL.
  - XMR pulls the refractory node up on `mreset`, which resets the membrane, as the slot's `syn_in` does.
  - Spike channel 13.
- **Subunits d1, d2**, each with:
  - a 200 fF cap;
  - `leak_ota_dega`: `leak_ota_deg` with its mirror node `a` brought out, as the slot's `leak_ota_degx` does;
  - a synapse `syn_in` (cells/neuron/synapse.spice): the leak output `dl` reaches the subunit through the synapse's hold switch;
  - a gap trim `trim_gap4w`.
- **Axial coupling** `ax_pair`: two follower OTAs back to back (the leak OTA, tail on `vbn_ax`).
  - Conductance g_ax = 6.2 S/A·Iax, linear for |ΔV| ≲ 80 mV, saturating at ±Iax.
  - Each OTA output has a pFET hold switch XHO.
  - Why not a single diffusor transistor: on a 1.2 V voltage-mode membrane a subthreshold MOS conducts ∝ exp(−V_source/U_T). It loses about 20× when the soma depolarises 80 mV, so the dendrite could never drive the soma to threshold.
- **Star / chain:** soma–d1 is always connected. The d2 pair's far end `y2` is switched to the soma (star) or to d1 (chain).
- **Plateau** `dplat`, per subunit:
  - Detector: `det_ah`-type, without Cfb, plus about 20 mV of hysteresis. It sits on rail `vsrcp` (= the calibrated `vsrc`), so it tracks the soma threshold.
  - Drive: a 5T OTA toward `vep` = el + Vgs(4/1 nFET), with tail 8·Ib_leak, through three series switches: detector AND timer AND `pl_en`.
  - Output: through the hold pFET XHP.
  - Timer: 50 fF discharged by Ib_leak/2, which ends the plateau after about 1.5 ms. The plateau re-arms below threshold.
- **Stim steering** `bsteer`: transmission gates plus pull-downs.
  - Stim A always goes to d1's synapse.
  - Stim B goes to d1's second input (`D1_BSEL` = 0, clustered) or to d2's synapse (`D1_BSEL` = 1, distributed).
  - Both synapses share `vbp_syn`.
- **Probe taps** `prb_nsf` (4/2): `sel0` = soma (SUB 0), `sel1` = d2 (SUB 1), `sel2` = d1 (SUB 2).

## Config bits

| Bit | Port | Meaning | Reset (0) |
|---|---|---|---|
| ANA[4] PLATEAU_EN[0] | `pl_en` | Plateau on in both subunits | Off: plateau OTA tails open |
| ANA[5] PLATEAU_EN[1] | `chain` | 0 = star, 1 = chain soma–d1–d2 | Star |
| ANA[7] D1_BSEL | `d1_bsel` | 0 = stim B into d1 (clustered), 1 = into d2 (distributed) | Clustered |
| TRIM nibble 7 | `ta0..3` | d1 plateau-threshold gap trim | Code 0 (−44 mV rest shift). Any code is functional. |
| TRIM nibble 8 | `tb0..3` | d2 plateau-threshold gap trim | Code 0 |

`rt_out[3:0]` → `mreset`, `hold`, `stb`, `sta`.

## Bias lines

| Line | Type | Nominal (S = 100) | Range | Shared? |
|---|---|---|---|---|
| `vbn_ax` | nFET gate, from an n-IDAC into a 2/4 master | 647 pA (g_ax = 4 nS) | 65 pA – 6.5 nA | **new, D1 only** |
| `vbp_syn` | pFET gate (2/4 master, p-IDAC) | 1 nA | as the array | shared with the array |
| `vbn_leak` | nFET gate (2/4 master) | 324 pA | as the array | shared; also sets plateau current, duration, Ep and the trim |
| `vbp_st`, `vbn_ref`, `vbn_prb`, `el`, `vreset`, `vsrc` | as the array | | | shared |
| `vsrcp` | voltage | | | tie to `vsrc` |

## Results

S = 100, typical 27 °C unless noted.

| Item | Result |
|---|---|
| Passive transfer, star | R/model 0.98 (g/Ib of the new OTA is 6.33 vs the 6.18 S/A used to set Ib); attenuation d1→soma 0.543 (model 0.545) |
| Passive transfer, chain | R/model 0.98; attenuation 0.665 (model 0.667) |
| Transfer over corners (`corners_summary.txt`) | Attenuation 0.542–0.544 at all 15 corners (ss/0 0.543, sf/0 0.544; old cells gave 0.475 / 0.499) |
| Plateau threshold | 114.5 mV above EL, 92 mV above rest, 350 pA DC. Corners: 111–120 mV above EL, 89–95 mV above rest. |
| Plateau duration and burst | Detector high 1.6–1.9 ms (passive soma); 17–19 soma spikes at all 15 corners |
| Plateau level | d1 +520…+930 mV, soma +480…+890 mV (passive), over corners |
| MC, 30 seeds (typical 27; mixed old/new detector keeper, which does not affect the threshold) | Threshold above rest σ = 13.3 mV (d1), 11.7 mV (d2), trim mismatch included |
| Trim `trim_gap4w` (ladder input 2 × 0.5/0.6) with the new OTA, EL 1.3 V | 27 °C: −41.4…+53.6 mV (span 95), mean step 6.3 mV, max 11.1 mV, monotonic at all 15 corners. 0 °C: span 80 mV (ss/0 and sf/0 now normal: 83 / 82 mV). 85 °C: span 128 mV. |
| MC vs trim | ±47.5 mV at 27 °C = ±3.6σ (d1), ±4.0σ (d2). All 30 seeds fall inside. |
| Synapse test (`tb_synapse.py`), I_w 1 nA, 10 µs pulses | Clustered fires from N = 3 at typical 27 / sf/0 / ff/85 and from N = 2 at ss/0 (17–27 spikes). Distributed gives nothing up to N = 4 at all four. Post-layout (70 × 104 µm, PEX, typical 27): clustered from N = 4, distributed silent up to N = 6. The single-pulse EPSP is 45 mV vs 63 mV in schematic, because post-layout node C is 250 / 237 / 272 fF (d1 / d2 / soma) vs 221 / 223 / 213 fF (`tb_cnode.py`). |
| Bias off (`tb_doff.py`, whole D1, 5 corners × 0/27/85 × 2 vbp states) | spk and both xb = 0 mV; Idd ≤ 2.2 nA (ff/85) |
| Hold (`tb_hold.py`) | Drift ≤ 0.069 mV/ms on all three compartments over 5 ms; no spikes. Soma XHL, subunit leaks via the synapses' XHL, axial XHO and plateau XHP are all cut. |

## Leak OTA (`leak_ota_deg`) at cold slow-n (history: the fix below has been applied since 2026-11-19)

Run with `tb_leak_lin.py` (`leak_lin.txt`: 5 corners × 0/27/85 °C × 324/647 pA, plus fix variants), `tb_leak_hiS.py` (`leak_hiS.txt`: higher S), and the older `tb_leak_corners.py` / `tb_leak_fix.py`.

**Measured, current cell, EL 1.2 V:**

| Corner | g/Ib at 324 / 647 pA (S/A) | Linear range below EL (−10 % pt) | Isat+ (% Ib) |
|---|---|---|---|
| typical, ff, fs, all temperatures; ss/85; sf/85 | 4.9–6.9 | 80–111 mV | 98–102 |
| ss/0 | **2.78 / 1.56** | **21 / 19 mV** | **25 / 13** |
| sf/0 | 5.08 / 3.30 | 31 / 23 mV | 53 / 31 |
| ss/27 | 5.51 / 4.26 | 57 / 31 mV | 75 / 47 |
| sf/27 | 5.88 / 5.65 | 88 / 65 mV | 97 / 80 |

- Above EL (the OTA sinking) it stays fine: Isat− ≥ 98 %. The damage is all on the sourcing side.
- **It gets worse with speed** (Ib ∝ S): at ss/0, g/Ib is 1.08 at S = 300 and 0.34 at S = 1000. At ss/27 it is 3.3 / 1.2. Typical 27 is unaffected (5.7 at S = 1000).

**Cause:** the tail node `t` sits at 1–40 mV, so the tail nFET is in triode. el (1.2 V) minus the input Vgs minus the degeneration-diode Vgs leaves no headroom when the nFET Vt is high. As vm drops below EL, the vm-side branch turns off and the whole tail current has to flow through the el-side input + diode stack at an even lower `t`. That collapses the sourcing current and the linear range.

**Fix options (numbers in `leak_lin.txt` and `leak_hiS.txt`):**

| Option | Worst corner at S = 100 | S = 1000, ss/0 |
|---|---|---|
| EL 1.3 V only | ss/0: 4.2 S/A, Isat+ 41 %, linear range 26 mV | |
| Inputs 8/1 + diodes 8/1, EL 1.2 V | ss/0 647 pA: 5.4 S/A, Isat+ 58 %, 33 mV | |
| **Inputs 4/1 + diodes 8/1 (`wi=4u li=1u wd=8u ld=1u`) and EL 1.3 V** | **All 30 cases 5.2–7.2 S/A, linear range ≥ 75 mV, Isat+ ≥ 92 %** | 3.8 S/A, 36 % (sf/0: 5.9, 70 %) |

- The recommended fix is the last row. Per OTA it adds the area of 2×(8/1) plus 2×(4/1) in place of 4×(2/2). VL is unchanged (140–165 mV).
- EL is a DAC code, so the 1.3 V part costs no hardware. vth and vreset move up with it.
- Full S = 1000 at ss/0 would need still more headroom (EL ≈ 1.4 V, or a lower-Vt tail stack).
- **Applied** by the slot track on 2026-11-19, together with EL 1.3 V. D1's copies follow.
