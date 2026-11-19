# D1 dendritic neuron (`dend_d1`)

Schematic: `dendrite.spice` + `dtrim.spice`. Include after `neuron/membrane.spice`, `neuron/lif.spice`, `readout/readout.spice` and `neuron/synapse.spice`.
Testbenches are in `sim/tb/dendrite/`, results in `sim/results/dendrite/`, layout in `layout/dendrite/`.

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
| Passive transfer, star | R/model 1.008–1.019; attenuation d1→soma 0.542 (model 0.545) |
| Passive transfer, chain | R/model 1.008–1.019; attenuation 0.664 (model 0.667) |
| Transfer over corners | Attenuation 0.541 ± 0.001 at 13 of 15 corners. At ss/0 and sf/0 it is 0.46 / 0.49 (leak OTA headroom, see below). |
| Plateau threshold | 111 mV above EL, 92 mV above rest, 344 pA DC. Corners: 107–117 mV above EL. |
| Plateau duration and burst | 1.5–1.7 ms; 16–19 soma spikes |
| Plateau level | Soma +430 mV vs model +428 mV (model plateau_g = 20 nS) |
| MC, 30 seeds (trims at code 8, lr 0.6u) | Threshold above rest σ = 15.8 mV (d1), 14.9 mV (d2), trim mismatch included |
| Trim `trim_gap4w` (ladder input 2 × 0.5/0.6, about 3× the slot trim's current) | 27 °C: rest shift −43.8…+54.8 mV (span 98.6), mean step 6.6 mV, max step 11.4 mV, monotonic at all 15 corners. 0 °C: span 84 mV (5.6 mV/step); 85 °C: span 132 mV. ss/0 has a long negative tail (−176 mV), caused by the leak OTA (see below). |
| MC vs trim | Trim covers ±49 mV at 27 °C, i.e. ±3.1σ (d1) and ±3.3σ (d2). All 30 seeds fall inside. At 0 °C the span is 84 mV (±42). |
| Synapse test (`tb_synapse.py`), I_w 1 nA, 10 µs pulses | Schematic: clustered gives a plateau and a 17-spike burst from N = 2 per input; distributed gives nothing up to N = 4 (both plateau at N = 6). Post-layout (PEX, typical 27): clustered fires from N = 3 (16 spikes); distributed gives nothing up to N = 4. |
| Hold (`tb_hold.py`) | Drift ≤ 0.073 mV/ms on all three compartments over 5 ms; no spikes. Soma XHL, subunit leaks via the synapses' XHL, axial XHO and plateau XHP are all cut. |

## Leak OTA (`leak_ota_deg`) at cold slow-n: shared with the neuron array

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
- **Not applied** (cells/neuron/membrane.spice belongs to the array track). D1 uses the same cell, so the attenuation drop at ss/0 and sf/0 (0.475 / 0.499 vs 0.542) follows it.
