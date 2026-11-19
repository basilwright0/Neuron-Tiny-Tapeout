# AdEx (A1, spike channel 3): RESUME HERE (paused 2026-11-19)

Schematic `adex.spice` (`adex_a1`), layout `layout/tier2/` (`adex_a1*`, generator `t2gen.py`, flow `build.sh`),
testbenches `sim/tb/tier2/`, report `docs/research/T2-area-estimate.md` (describes the 56 x 50 rev 2 layout;
it still needs updating for the items below).

## 1. Re-verification with the new shared cells: DONE (schematic)
These are the new shared cells, picked up unedited: `leak_ota_deg` 4/1 and 8/1, `det_ah` with the XS3-starved third stage, and EL/Vth/Vreset = 1.30/1.38/1.30 V.
- `adex.spice` now instantiates `leak_ota_deg` directly; the private copy `a1_leak` is removed.
- `t2common.py`: the vsrc calibration starts at 0.60 V. The tbs take the EL and VTH values from `dcommon`.
- **Nominal, typical 27 C** (`tb_adex_char.py nominal`):
  - I-V: gL 2.05 nS, rest 1.310 V, DT 44 mV, VT 1.404 V (trip 1.38 V), rheobase 88 pA.
  - Adapted/initial ISI ratio, hardware vs model:

    | Step | Hardware | Model |
    |---|---|---|
    | 250 pA | 2.16 | 2.21 |
    | 400 pA | 2.07 | 2.05 (fit) |
    | 700 pA | 1.77 | 1.69 |

  - b 44 pA, tau_w 0.83 ms (decay still tracks vbn_leak).
- **15 corners:**
  - Ratio 1.87-2.20, b 34-52 pA, tau_w 0.71-1.04 ms.
  - Rheobase 75-99 pA, rest 1.308-1.312 V.
  - No firing without input.
  - ss 0 C is fixed by the new OTA: gL 2.10 nS, rheobase 94 pA (was 46).
- **Monte Carlo** (no firing without input in any seed):

  | Run | Ratio | Rheobase |
  |---|---|---|
  | typical 27 C, 20 seeds | 2.06 +- 0.23 | min 56 pA |
  | ss 0 C, 12 seeds | 2.22 +- 0.33 | min 60 pA |

- **Functional checks:** probe decode, hold (-0.09 mV/ms) and mreset (clears vw) all OK.
- **vbp_w:** a 1.02 nA LSB with 32 nA full scale covers the needed 0.5-30 nA (nominal code 8, ratio about 2).

## 2. BLOCKER found in the shared det_ah (not an AdEx file; for the owner of cells/neuron)
**All-zero / bias-off state:** BIAS_EN = 0 puts vbp_st at vdd and vsrc at 0. With the new XS3 starve, stage 3 then has no pull-up, so `pb` floats at about 1.5 V.
- The output inverter Xi4 draws about **63 uA per neuron** (det_ah alone, `sim/tb/tier2/tb_det_zero.py`), and 118 uA in the AdEx all-zero tb.
- `spk` sits at 1.2-2.3 V, so the spike inputs are undefined.
- This hits every neuron that uses det_ah. Before the change, XP3 was sourced from vdd and pb was defined high.
- Needs a fix in `lif.spice` by its owner. One option is a weak pull-up on pb that is active when the bias is off.

## 3. 38 um-wide re-layout: IN PROGRESS, not yet routed
- **Generator (`t2gen.py`):** added the `SPINE_SIDE="left"` and `PIN_EDGE="bottom"` options. The bias/analog Metal2 spine is on the left with pins at the bottom edge.
- **HM3:** horizontal Metal3 lines with pins at the right edge, for sta, stb, en, mreset, sel_adex, sub0, sub1, hold and spk.
- **Placement check** handles the left spine. New device cells n_w4_l1 and n_w8_l1 were generated.
- **Config `CFG["adex_a1"]`:** W = 38.0, H = 61.4, 13 rows. The main n-well (9.0..36.6 x 34..59.8) also holds XCW. Placement is clean (0 issues). Preview: `layout/tier2/out/preview_place_adex_a1.png`.
- **Mid-run when paused:** the full build (`SKIPDEV=1 CELLS=adex_a1 bash layout/tier2/build.sh`). Its container was killed during routing schedule 2 of 3.
- **Why it was not converging:** schedules 0 and 1 left about 15 nets in conflict (vm, vw, vl, vr, spk, mreset, sub0, vdd, XA.vrb, ...). The 61.4 um height is too dense. No DRC/LVS on this shape yet.
- **Files in place now:** `adex_a1.mag`, `adex_a1_paint.tcl` and `out/adex_a1*` are from the PREVIOUS 56 x 50 build. That layout is DRC/LVS clean, but it is the old netlist with a1_leak 2/2 and the old det_ah, so it is stale. `adex_a1_lvs.spice` is from the new netlist.

## 4. Exact next steps
1. In `CFG["adex_a1"]`, raise H to about 72-75 um (allowed: <= ~80) and spread the rows. Suggested changes:
   - About 1.5 um more gap between band 3 (leak devices, y 14.2) and the three 0.22/15 XT rows.
   - Pitch the XT rows at 3.0 instead of 2.6.
   - About 1 um more between the pfet rows P1-P4.
   - Move the HM3 y values and REGIONS with the rows; keep HM3 lines >= 0.8 um apart.
2. `scripts/eda.sh "SKIPDEV=1 CELLS=adex_a1 bash layout/tier2/build.sh"` (about 80 min at this density). Need FAILED: none, magic DRC 0, LVS match, KLayout DRC 0.
3. PEX:
   - `python3 sim/tb/tier2/tb_adex_char.py pex`: check the adaptation ratio vs schematic and runts = 0.
   - `python3 sim/tb/tier2/tb_adex_func.py typical 27 layout/tier2/out/adex_a1_pex.spice`.
4. Update `docs/research/T2-area-estimate.md` with the new box, the re-verification numbers above and the det_ah blocker.
