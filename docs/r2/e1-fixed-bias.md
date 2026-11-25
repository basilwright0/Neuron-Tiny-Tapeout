# E1: fixed-bias "regular-spiking" twin of the S slot (`e1_fb`, MIL-362)

The cell answers one question on silicon: how well does a neuron hold its parameters when nothing can be tuned? All of its
currents are fixed device ratios of one global line, `vbp_st`, which only the `ua[0]` speed reference sets. All of its
voltages come from local diodes on that line. It sits next to the tunable S/F slots (same die, same Cm, OTA, detector), so
the spread of τ, t_ref, threshold gap and rheobase can be compared directly.

Files:
- netlist: `cells/neuron/e1.spice` (`e1_fb`, `refrac_e1`, `det_ah_e1`, `syn_e1`);
- layout: `layout/compact` (`cgen.py`, CELL=e1_fb, layout cell `ce1_fb`); the VM script is `vm_e1.sh`;
- benches: `sim/tb/e1/tb_e1.py` (corners, mc, sweep, diag) and `mc_summary.py`;
- results: `sim/results/e1/` (git-ignored, force-added): `corners_S100.txt`, `pex_corners_S100.txt`, `mc_summary.txt`.

## 1. Schematic

Same as `slot_ah`: mcap 7.07 × 7.07 (200 fF), refractory cap 3.54 × 3.54 (50 fF), `leak_ota_degx`, AH detector with a
Cfb MOM, two-input synapse, vm probe tap (`prb_tap`, `sub_b`). The bias column lines `el vsrc vreset vbn_leak vbn_ref
vbp_syn aux` are **plain feed-throughs**. It uses only `vdd`, `vbp_st`, `vbn_prb` (probe sink only), `en` and `abus`.

| Block | Devices (W/L in µm) | Value at S = 100, tt/27 |
|---|---|---|
| leg 1 (EL stack, mirror master) | XP1 p 0.5/4 on vbp_st → XG1 n 0.5/0.28 (gate grp_en) → el_l → XE1 n 0.22/7 (diode) → mid → XE2 n 8/1 (diode) → vss | I_nd/32 = 31 nA; EL = Vreset = el_l = 1.40 V; mid 0.50 V |
| leak OTA tail | XL.XMT n 0.22/13, gate mid | 325 pA → g 2.1 nS |
| leak OTA mirror | XL.XP1/XP2 p 1/2 (slot_ah: 2/4, same W/L; shortened to fit the p rows) | |
| refractory sink | XR.XNR n 0.5/1.3, gate mid | ~2.9 nA |
| weight bias | XNW n 0.22/3.3 (gate mid) → XPW p 2/1 diode (vbw); weights XWA/XWB p 1/2 on vbw | 372 pA each (A, B) |
| leg 2 (threshold) | XP2 p 1/2 → XG2 → XV n 1/0.5 diode = vsl, the source of the detector's input nfet XNI | 125 nA; vsl 0.63 V |
| leg 3 (detector rail) | XP3 p 0.5/1 → XG3 → XV2 n 1/0.5 diode = vs2, the source of XN2/XN3 | ~125 nA |
| detector starve | XPS/XS2/XS3 p 1/2 on vbp_st (as slot_ah) | 130 nA, only around a spike |
| enable | XI (inv3) → gb; XEL n 0.5/0.28 (el_l → vss, gate gb); XMK n 0.5/0.28 (vdd → vr follower, gate gb) | |

The long-L copies of a short-L master carry 2–5× their W/L ratio in this PDK (reverse short-channel effect), so every
ratio was set by simulation (`tb_e1.py sweep`, logs `sim/tb/e1/sw1.out`, `sw2.out`, `c2.out`), not by W/L arithmetic.
XE1's length sets the threshold gap: about −45 mV per doubling of L (0.22/6: 94 mV, 0.22/8: 70 mV at tt/27).

**grp_en** (GRP_EN bit, `cfg_out[1]`). With grp_en = 0 (reset state) XG1–XG3 open all three legs. The mirror master is
then off, and so are all its copies. Nothing draws static current: the starve pfets on vbp_st only conduct while the
detector switches, and it is idle with vm low. XEL pulls EL to 0 V. XMK lifts vr to ~2.3 V, so the refractory switch
parks vm on EL = 0 V. abus sees only the probe tap. When grp_en rises, vr decays with I_ref, and vm is released after about
one refractory period.

**Deviations from the approved spec text (please confirm):**
1. **vsrc is a local diode (leg 2), not vss.** With vsrc = vss the trip point is one nfet Vgs: 0.63 / 0.77 / 0.44 V at
   tt/27, ss/0, ff/85 (`sim/tb/e1/explore.out`). Any 2-diode EL is ~1.3 V, above that. At EL = Vth − 80 mV ≈ 0.55 V
   the degenerated leak OTA has no headroom: g = 0.24 / 0.01 / 1.7 nS instead of ~4 nS for a 320 pA tail. The NMOS-cap
   Cm is also in depletion there (70–100 fF instead of 200 fF; `explore2.out`). One local diode under XNI lifts the trip
   point by one Vgs, so it sits ~80 mV above the 2-diode EL, and the two track over process (both are 2 nfet Vgs).
2. **det_ah_e1:** the same devices as det_ah, but XN2/XN3 source on a second diode rail (vs2, leg 3). With all three
   stages on one local diode, the stage-2/3 currents moved the stage-1 trip point. This formed a 3-stage loop, and the
   detector oscillated for the whole approach to threshold (`sim/tb/e1/d1.out`: 2 ns time steps). On the mirror node
   instead, the stage-2 crowbar raised every copy near threshold (+40 % rheobase).
3. The synapse weights (1/2) and the leak OTA mirror pfets (1/2) keep their W/L, but at half the size of slot_ah's,
   so the p rows fit (p-row use 98 % → 89 %).

## 2. Pins and layout (28.0 × 34.29 = 960 µm², `layout/compact/out/ce1_fb.gds`)

Column lines: Metal2, full height, the same x as cslot_ah / czslot_ah_f (labels at the top edge, y 33.69–34.09).

| Pin | Layer | x (µm) | Notes |
|---|---|---|---|
| vbp_syn el aux vbn_leak vsrc vbn_ref vreset | Metal2 column | 19.05 20.65 21.35 22.05 22.75 24.85 26.25 | feed-through |
| vdd vbp_st vbn_prb en abus | Metal2 column | 19.85 (0.6 wide) 23.45 24.15 25.55 26.95 | used |
| vss | Metal1 ring / bottom rail | label 2.0–3.0, y 0.1–0.5 | as the compact cells |

Row pins (0.4 × 0.4 Metal2 pads; band track k at y = H − 11.12 + 0.56 k = 23.17 + 0.56 k):

| Pin | Track | x | y |
|---|---|---|---|
| sta | 0 | 16.70 | 23.17 |
| stb | 1 | 15.30 | 23.73 |
| hold | 2 | 17.85 | 24.29 |
| mreset | 3 | 4.45 | 24.85 |
| rsel | 4 | 16.40 | 25.41 |
| sub | 5 | 9.00 | 25.97 |
| sub_b | 6 | 16.65 | 26.53 |
| **grp_en** | **8** | **6.35** | **27.65** (≥ 0.7 µm from every other row-pin x and the spk strap) |
| spk | strap, tracks 7–10 | 18.47 | 26.89–28.97 (Metal2 strap; via2 on track 7 at y 27.09) |

`sub` is a pin with no device on it (no vr tap: the bay leaves sub open and ties sub_b high).

Frame: compact generator with two short n rows (EXTRA_N=1: the long-L copies, switches), CHANS 0.93/0.93/0.935/0.935,
seed 6, MOM_STYLE=tall, CB_W 4, STEPS 40000. Reproduce:

    cd layout/compact && CELL=e1_fb EXTRA_N=1 CHANS=0.93,0.93,0.935,0.935 MOM_STYLE=tall CB_W=4 SEED=6 STEPS=40000 \
        FINAL_ITERS=60 python3 cgen.py final          # then: CELLS=e1_fb bash build.sh nogen  (in the EDA container)

## 3. Results (S = 100: I_nd = 1 µA, vbp_st = I_nd/16 into the 1/4 rx_p05 diode)

Bench `sim/tb/e1/tb_e1.py`. Definitions:
- EL is the zero-current vm of a DC sweep of a vm source; Vth is where spk trips in the same sweep.
- Rheobase is the current that holds vm at Vth; g = dI/dV at EL.
- τ is the 63 % time of a 0.25 × rheobase step.
- t_ref = ISI at 50 × rheobase − τ ln(50/49).
- Stimulus: an ideal current into vm at multiples of the rheobase, plus the cell's own fixed weights held on in DC mode
  (sta = 1: A; sta = stb = 1: A + B).

The other bias column lines are tied to deliberately wrong voltages in the bench, so any accidental use would show.

| | sch tt/27 | sch ss/0 | sch ff/85 | **PEX** tt/27 | **PEX** ss/0 | **PEX** ff/85 |
|---|---|---|---|---|---|---|
| EL / Vth (V) | 1.405 / 1.486 | 1.745 / 1.820 | 0.976 / 1.068 | 1.407 / 1.486 | 1.750 / 1.820 | 0.971 / 1.068 |
| Vth − EL (mV) | 80.4 | 74.3 | 92.4 | 78.6 | 69.4 | 97.1 |
| g (nS) / τ_m (µs) | 2.14 / 108 | 2.20 / 102 | 1.84 / 129 | 2.20 / 110 | 2.41 / 98 | 1.70 / 147 |
| rheobase (pA) | 156 | 148 | 154 | 157 | 153 | 149 |
| t_ref (µs) | 16.4 | 7.6 | 28.3 | 18.0 | 8.0 | 34.9 |
| f at 1.1/1.5/2/3/5/8 × rheo (kHz) | 2.3/5.3/8.1/12.5/19.2/26.1 | 2.8/6.3/9.8/15.8/26.2/38.5 | 1.8/4.1/6.1/9.2/13.4/17.4 | 2.1/4.8/7.4/11.6/17.6/23.9 | 2.6/6.1/9.5/15.5/25.6/37.5 | 1.5/3.4/5.0/7.6/11.1/14.3 |
| f, weight A / A+B (kHz) | 9.9 / 18.4 | 12.1 / 24.8 | 7.3 / 12.8 | 9.2 / 17.0 | 12.6 / 25.2 | 5.8 / 10.2 |
| copies: I_leak / I_ref / I_w | 325 pA / 2.9 nA / 372 pA | 308 / 2.8 / 354 | 327 / 3.0 / 364 | | | |
| I_vdd at rest, grp_en = 1 | 363 nA | 366 nA | 361 nA | 365 nA | 370 nA | 357 nA |
| **grp_en = 0:** I_vdd, vm | 2.2 pA, 0 V | 0.4 pA, 0 V | 0.88 nA (leakage), 0.7 µV | 10 pA, 0 V | 6 pA, 0 V | 0.89 nA, 0.8 µV |
| first spike after grp_en ↑ (sta = 1) | 109 µs | 92 µs | 143 µs | 116 µs | 88 µs | 180 µs |

0.9 × rheobase never fires at any corner (sch or PEX). PEX/schematic rate at 2 × rheobase: 0.92 / 0.98 / 0.83. The PEX Cfb is
6.37 fF (MOM; schematic 8 fF), as in cslot_ah (6.14 fF).

**MC, 100 dies** (schematic; statistical corner = global process + mismatch, one seed per die, tt/27; PEX MC was not run,
`sim/results/e1/mc_summary.txt`):

| | mean | σ | σ/mean | p5 – p95 | min – max |
|---|---|---|---|---|---|
| τ_m (µs) | 110.8 | 10.6 | 9.6 % | 94 – 130 | 82 – 134 |
| t_ref (µs) | 16.9 | 3.4 | 20 % | 12.1 – 22.5 | 9.9 – 26.9 |
| Vth − EL (mV) | 80.6 | 19.4 | 24 % | 47 – 112 | 40 – 141 |
| rheobase (pA) | 152 | 32 | 21 % | 88 – 204 | 83 – 236 |
| EL (V) | 1.405 | 0.067 | | 1.29 – 1.53 | |
| f at 2 × rheo (kHz) | 7.84 | 0.83 | 10.6 % | 6.5 – 9.3 | |
| f, weight A (kHz) | 10.2 | 2.75 | 27 % | 5.9 – 15.0 | 4.4 – 17.4 |

**Reading the numbers:**
- τ holds far better than expected (σ 10 %, p5–p95 −15 / +17 %, against the ±20–35 % estimate). The leak current is a
  ratio of vbp_st within ~±5 % over the corners (308–327 pA), and g/I_b is set by the OTA.
- The large die-to-die spreads are the threshold gap (σ 19 mV) and, through it, the rheobase and the fixed-weight
  firing rate.
- EL moves with the process by ±0.4 V over the corners (two nfet Vgs). Vth tracks it, but t_ref does not. The refractory
  switch releases when vr ≈ EL + Vt, so t_ref = Cr (3.3 V − EL − Vt) / I_ref runs from 8 µs (ss/0) to 28–35 µs (ff/85).

## 4. Chip measurement procedure

1. Set S: `ua[0]` EXT ÷1 at 1 µA (S = 100). E1 depends on nothing else; leave every DAC at its default.
2. Probe vm: select E1's probe address (its row select `rsel`, the bay's column enable; PROBE_SUB = 0). Read ua[1].
   With GRP_EN[1] = 0, vm reads 0 V (parked).
3. Set GRP_EN[1] = 1. After ~20 µs vm settles to **EL** (≈ 1.40 V at tt/27). Record EL.
4. **Threshold and gap:** hold sta = 1 (weight A, DC). vm ramps and spikes. The sawtooth peak just before the reset is Vth
   (the probe follower lags by ~1–2 µs at S = 100; use S = 10 for the threshold reading). Gap = Vth − EL.
5. **τ_m:** pulse sta for a short time T (e.g. 20 µs) from rest. Fit the decay of vm back to EL: V(t) − EL ∝ exp(−t/τ).
6. **f–I and rheobase:** count spikes on the vm sawtooth with sta = 1, sta = stb = 1 (A + B ≈ 2 × A), and short
   sta/stb pulse trains with duty cycle d (mean input d × I_w). Rheobase ≈ the input where firing stops
   (I_w = 372 pA nominal, A ≈ 2.4 × rheobase).
7. **t_ref:** with sta = stb = 1, measure the flat reset segment of the sawtooth (vm clamped at EL after each spike).
   Or drive mreset: one pulse clamps vm, and the release comes about one t_ref after the falling edge.
8. Repeat at S = 10 and 1000 (`ua[0]` = 0.1 / 10 µA). τ and t_ref should scale as 1/S if the ratios hold. Also repeat
   at a second temperature. Compare with S1–S3 at nominal codes on the same die.
