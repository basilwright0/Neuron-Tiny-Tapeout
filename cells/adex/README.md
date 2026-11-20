# AdEx (A1, spike channel 3): status 2026-11-19 (rev 3, done)

- **Schematic:** `adex.spice` (`adex_a1`).
- **Layout:** `layout/tier2/` (`adex_a1*`, generator `t2gen.py`, flow `build.sh`).
- **Testbenches:** `sim/tb/tier2/`.
- **Full report:** `docs/research/T2-area-estimate.md`.

## Status
- **Shared cells:** built on the current shared cells, picked up unedited.
  - `leak_ota_deg` with 4/1 inputs and 8/1 diodes.
  - `det_ah` with the XS3-starved third stage and the XK reset keeper.
  - EL / Vth / Vreset = 1.30 / 1.38 / 1.30 V.
- **Layout:** 38.0 × 73.0 µm (2774 µm²); GDS extent 38.04 × 73.04.
  - magic DRC 0, KLayout `gf180mcu.drc` 0, LVS match (66 devices, 55 nets).
- **Pins:**
  - Bias and analog lines enter at the bottom edge, on a left Metal2 spine. Left to right: vdd, el, vbn_leak, vsrc, vbp_st, vbn_ref, vreset, vbn_prb, vbp_syn, vbp_w, abus.
  - vdd and vss are also on the full-width Metal1 rails and the ring.
  - Digital lines and spk leave at the right edge on Metal3: sta, spk, stb, en, mreset, sub0, sel_adex, sub1, hold.
- **Rebuild:** `scripts/eda.sh "SKIPDEV=1 CELLS=adex_a1 bash layout/tier2/build.sh"`. This takes about 30-80 min. Drop `SKIPDEV` after changing device sizes.
- **Firmware rule:** pulse MRESET after BIAS_EN. Cw is vdd-referenced, so the adaptation node vw comes up at about 3 V at power-up; mreset clears it.
