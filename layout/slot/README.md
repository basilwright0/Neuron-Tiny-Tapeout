# Neuron-array slots and the strip trim cells (gf180mcuD, 3.3 V devices)

## det_ah reset fix

The change is final, 2026-11-19, in `cells/neuron/lif.spice`, `det_ah`. Add one device after XN3:

    XK  pb  spk vdd vdd pfet_03v3 W=0.22u L=1u

XK is a weak keeper on the third-stage node pb, gated by spk.

**The problem it fixes.** With all biases off (BIAS_EN = 0, vbp_st un-driven), the starved XS3 is off and pb floated at about 1.5 V. Xi4 then drew 16–87 µA and spk sat at 0.4–2.9 V (the AdEx track's `sim/tb/tier2/tb_det_zero.py`).

**With XK** (`sim/tb/tb_slot_detoff.py`):
- **Bench:** vdd ramp, vm = vsrc = 0, vbp_st as an unpowered pmaster or at 3.3 V, all 5 corners × 0/27/85 °C.
- **Bias off:** spk < 50 mV and Idd ≤ 0.30 nA.
- **vm = 1.4 V at bias off:** spk = 3.3 V. That is a clean level with no crowbar; the detector is above its vsrc = 0 trip point.
- **Biases on:** XK is off while spk is high, so it only fights XN3 for the few-ns output edge. vsrc charge per spike changes by ≤ 1.5 fC (`sim/results/det/det_summary.txt`). The slot_ah f–I is unchanged within about 0.5 % over 5 corners × 0/27/85 °C at S = 100 and at S = 10/1000; it stays at 0.74–1.00× the ideal LIF rate (`sim/results/fi_*.log`).

**Full det_ah third stage now:**

    XS3 s3  vbp_st vdd vdd pfet_03v3 W=1u L=2u
    XP3 pb  p   s3  vdd pfet_03v3 W=1u L=0.28u
    XN3 pb  p   vsrc vss nfet_03v3 W=0.5u L=0.28u
    XK  pb  spk vdd vdd pfet_03v3 W=0.22u L=1u
    Xi4 pb  spk vdd vss inv3

## Changes 2026-11-19 (all slots)

- **Leak OTA** (`leak_ota_deg` in `cells/neuron/membrane.spice`, and `leak_ota_degx` in `slot.spice`): inputs 4/1, degeneration diodes 8/1, tail 2/4. Nominal EL/Vth/Vreset are now **1.30/1.38/1.30 V**.
  - Fixes the ss/0 °C tail-headroom collapse that the D1 track found.
  - In layout each 8/1 diode is two parallel 4/1 halves (`<name>a/b`, `slotgen.split_devs`); netgen adds the widths.
- **Detector** (`det_ah` in `cells/neuron/lif.spice`):
  - Third stage starved: `XS3` (pfet 1/2 on vbp_st); `XN3` stays on vsrc. This is R1's "st3"; "st3v" (XN3 to vss) cannot idle once vsrc > 0.55 V, which it is at the new Vth.
  - Keeper `XK` for the bias-off state; see "det_ah reset fix" above.
- **Probe tap** (`prb_tap` in `slot.spice`): adds `XSC`, a third series switch on `en` (prb → XSC → XSW → XSB → abus).
  - **Bug:** taps in the selected row's other columns (sel = sb = 1, en = 0) sourced current into abus through their followers. The reading was off by +65 mV with equal vm and up to +640 mV otherwise (`sim/tb/tb_slot_probe_row.py`).
  - **With XSC:** 0 mV error; readout settling (173 ns worst) and the en kick (−20.5 mV) are unchanged.
- **New variants:** F, CMP, AH50, AH800, REF, DUMMY (table below).
- **Generator changes:**
  - per-cell pins and straps (from the subckt ports), an optional MOM, and per-cell placement and n-well extensions;
  - gate heads drawn below the device (`HEAD_DOWN`) and Metal1 shield plates (`PLATES`) with a wide-metal halo;
  - in-line XPM switch chain (`PROBE_CHAIN=1`);
  - notch filler: also bridges same-net corner gaps and widens necks left after clipping;
  - P derivation: moved aux landings are re-centred on the aux column.

Schematics:
- `cells/neuron/slot.spice`: the slot cells. Sub-blocks come from `cells/neuron/synapse.spice` (input synapse, hold, membrane reset) and `cells/trim/trim_gap.spice` (gap trim).
- `cells/trim/trim_tau.spice`: the strip cell. It is built around B1's `trim4_n` (`cells/bias/bias_trim.spice`).

| Cell | What | Size (µm) |
|---|---|---|
| `slot_ah` | S slot: AH LIF, 200 fF, synapse A/B, hold, mreset, probe taps on vm and vr | 28.0 × 43.5 |
| `slot_ah_h` | H slot: S + 4-bit Vth−EL gap trim (`trim_gap4`, bits t0..t3) | 28.0 × 43.5 |
| `slot_ah_p` | P slot: H, but the leak OTA tail gate (and the gap-trim ladder gate) is the `aux` column line, giving a per-column leak-τ trim | 28.0 × 43.5 |
| `slot_ah_f` | F slot: S with the leak tail W/L halved (1/4 instead of 2/4) on the same `vbn_leak`, so τ_F = 2 τ_S by geometry | 28.0 × 43.5 |
| `slot_cmp_h` | CMP slot: comparator LIF (`det_cmp`, tail/starve on vbp_st), **no gap trim since 2026-11-20** (see below). Its threshold `vth_cmp` arrives on the `aux` line (column 1); vsrc feeds through. Pins as S | 28.0 × 43.5 |
| `slot_ah_50` | AH50: S with a 50 fF membrane (mcap 3.54 × 3.54) | 28.0 × 43.5 |
| `slot_ah_800` | AH800: S + `mcap_r` 11.7 × 11.6 (~540 fF) in the former trim space (gate head down, Metal1 vss shield), about 740 fF in total; the hold switch moves to row A | 28.0 × 43.5 |
| `slot_ref` | REF (slot 0,0): one `prb_tap` on `el` with sb = sub (PROBE_SUB = 3 → row 0, column 0, sub = 1); identical to the array taps; no neuron | 28.0 × 43.5 |
| `slot_dummy` | DUMMY (slot 0,3): S with no spk pin and both taps' en/sel/sb tied to vss (XSB still on abus, for a uniform bus load) | 28.0 × 43.5 |
| `trim_tau4` | leak-τ trim for one P column (TE strip, 3 cells side by side); drives that column's `aux` | 37.0 × 11.8 |
| `trim_el4` | **unused** since 2026-11-18 (the P second knob changed from EL to τ); kept for reference, built only on request | 28.0 × 10.6 |

Everything here is generated. Do not hand-edit `.mag` files.

## Flow (from the repo root, Git Bash)

    scripts/eda.sh "bash layout/slot/build.sh"           # all slot variants + trim_tau4: devices -> place/route -> DRC -> LVS -> PEX
    scripts/eda.sh "bash layout/slot/build.sh nogen"     # re-verify only
    scripts/eda.sh "bash layout/slot/build.sh reuse"     # re-emit geometry from out/route_cache_<cell>.json
    # options: CELLS="slot_ah_h" (subset), SKIPDEV=1 (keep devices/*.mag), P_AS_H=1 (cut the P group),
    #          ROUTE_FINE=0 (old 0.30 um wires / 0.70 um grid), SCHED_ROTATE=k (other negotiation order),
    #          PROBE_CHAIN=0 (old XPM switch placement)
    # Routing one cell takes 5-60 min. Run several cells in parallel (one python3 -u slotgen.py per cell, then
    # build.sh nogen). Never run two jobs on the SAME cell in one directory: they write the same files.

**Cutting the P group: `P_AS_H=1`.** Set this one flag and the build makes neither `slot_ah_p` nor `trim_tau4`. The P positions in the array then use `slot_ah_h` unchanged: the leak tail is back on `vbn_leak`, and `aux` becomes a pure feed-through. Nothing else changes: the pins and column lines are identical, and the TE strip and the τ nibbles 13–15 are simply left empty.

| Step | File |
|---|---|
| Unique transistor list for all cells | `slotgen.py devlist` -> `devices/devlist.tcl` |
| PDK device cells (`gf180mcu::{n,p}fet_03v3_draw`, guard 0, no gate contacts) | `gen_devices.tcl` -> `devices/*.mag` |
| Flatten to transistors and write the LVS reference without Cfb | `flatten.py` -> `<cell>_lvs.spice` |
| Slot placement, rings, column lines, MOM, pins, routing | `slotgen.py` + `router.py` |
| Strip-cell placement and routing | `elgen.py` (same machinery) |
| Escape check: every pin can get out | `escape.py` |
| Magic: draw, DRC `drc(full)`, GDS, LVS netlist, PEX | `build.tcl` -> `out/` |
| netgen LVS (PDK setup) and KLayout `gf180mcu.drc` (variant D, flat, all decks except density) | `out/<cell>_lvs_report.txt`, `out/<cell>_klayout_drc.lyrdb` |
| Cfb and vm wiring capacitance | `pex_summary.py` |
| Area breakdown | `SLOT_CELL=<cell> python3 area.py` |

**The router:**
- **Kind:** a gridded PathFinder router on Metal1, Metal2 and Metal3. Wires are 0.28 µm wide on a 0.56 µm base grid, plus every pin's centre line.
- **Metal3:** used only for local routing below the row band (y < 31.96) and never within 0.3 µm of the cell edge.
- **Legality:** every move is checked geometrically against real shapes, using square-corner spacing.
- **P slot:** `slot_ah_p` is not routed from scratch. It takes `slot_ah_h`'s routing, renames the vbn_leak gate tree to aux and moves its two landings to the aux column (`P_FROM_H=1`, the default). H must therefore be built first, which `build.sh` order guarantees.
- **Notch fill:** same-net notches and diagonal gaps are closed morphologically, and a filler never comes closer than the minimum spacing to another net.

## Frame, rails, columns

- **Rings and rails:** the VSS p-tap ring is on all edges, and the VDD Metal1 rail is at y = 21.32–21.92.
- **Main n-well:** 0.9–21.6 × 21.2–29.8, with its own n-tap ring.
- **N-well extensions:** each merges with the main well and is tapped by its ring:
  - the synapse well, 19.45–26.9 × 29.3–38.9;
  - the dump-pfet well, 14.75–19.45 × 32.5–35.1;
  - the hold-switch and trim-pfet well: 0.9–13.5 × 29.6–32.6 in H/P, 8.8–11.4 in S/F/AH50/CMP/DUMMY/REF, none in AH800;
  - CMP only: a bump 0.9–8.75 × 18.65–21.25 under the VDD rail for the comparator's hysteresis source XH2 (1/6).

**Column lines** are full-height Metal2 at a 0.7 µm pitch and connect by abutment. vdd is 0.6 µm wide; all the others are 0.3 µm.

| Line | x | Note |
|---|---|---|
| vbp_syn | 19.05 | **new**: synapse weight bias, from a p-IDAC into a 2/4 pmaster in B1 |
| vdd | 19.85 | |
| el | 20.65 | |
| aux | 21.35 | **P slot:** leak tail + gap-ladder gate (τ trim, columns 0 and 2, from `trim_tau4`). **CMP slot: `vth_cmp`** (column 1: the integrator connects B1's `vth_cmp` output to column 1's aux). Otherwise a feed-through. No column line was added; every variant has the same 12 lines. |
| vbn_leak | 22.05 | |
| vsrc | 22.75 | AH slots only (CMP and REF: feed-through) |
| vbp_st | 23.45 | |
| vbn_prb | 24.15 | |
| vbn_ref | 24.85 | |
| en | 25.55 | **now per-column probe select**: en_c = PROBE_EN & (SEL column == c) |
| vreset | 26.25 | |
| abus | 26.95 | |

## Row Metal3 band (shared with the top-level row router)

The band is y = 32.24–42.60. It has 19 tracks at the Metal3 minimum pitch: 0.28 wide, centres at 32.38 + 0.56·k. The cell has no Metal3 at y ≥ 31.96, and vm stays below that line too, so no vm metal lies under any track.

| Track k | Signal | Pin in the cell: Metal2 pad 0.4 × 0.4 at x (S, F, AH50, AH800, CMP / H, P). REF has only rsel and sub; DUMMY has no rsel, sub, sub_b or spk |
|---|---|---|
| 0 | sta (stim A, rt_out[0]) | 17.40 |
| 1 | stb (rt_out[1]) | 15.30 |
| 2 | hold (rt_out[2]) | 14.00 |
| 3 | mreset (rt_out[3]) | 17.40 / 18.30 |
| 4 | rsel: probe row select (row r: PROBE_EN & SEL row == r) | 15.30 |
| 5 | sub = PROBE_SUB[0] | 14.00 |
| 6 | sub_b = ~PROBE_SUB[0] | 17.40 / 15.30 |
| 7–10 | spk of the slot in column 0–3 | Metal2 strap at x = 16.60 over tracks 7–10 |
| 11–18 | trim bits: 4 per trimmed slot, at most 2 trimmed slots per row | H/P straps t3..t0 at x = 3.1 / 5.9 / 8.7 / 11.5, from the trim switches (y 31.95) up over tracks 11–18 |

Shared signals have fixed tracks; the row router drops a via2 on the pad. A pad's x may differ between slot variants, since the track spans the whole row. Signals whose track depends on the slot's column (spk and the trim bits) use straps.

**Track budget.** Before: 12 tracks, all taken by per-slot spk / sel / sel_vr. The row then needed 4 + 4 + 4 + 4 (rt) + 8 (trims) = 24. Now:
- **Probe selection** is row × column: one rsel track per row plus the existing `en` column line, which is now per column. A shared sub / sub_b pair picks the tap. The probe lines in a row go from 8 per-slot lines to 3 shared ones.
- **Rows** therefore need 4 spk + 3 probe + 4 rt + 8 trim = **19 tracks**, at 0.56 µm instead of 0.6.

What it costs:
- **In the slot:** a second and (2026-11-19) a third series switch in each tap (`prb_tap`, XSB on sub/sub_b and XSC on en, W/L 1/0.28; 4 transistors per slot). Local Metal3 above y = 31.96 is lost.
- **In the control logic:** the macro (or top-level glue) must output 4 rsel + 4 en_c instead of 16 one-hot lines, plus PROBE_SUB[0] and its complement. These live in RTL owned by the control-logic track.

## Safe state at reset / when deselected

Every slot input at 0 is a safe state:
- hold = 0: the leak is connected.
- sta = stb = 0: the weight current is dumped to vss.
- mreset = 0: normal operation.
- rsel = sub = sub_b = en = 0: the probe is disconnected and its follower is off.
- Gap-trim code 0: rest is shifted −22 mV, so the neuron is slower; it is not stuck.
- τ code 0: 0.5× leak current, so τ is 2× longer.

Firmware must rewrite the trims after every select, because TT powers the project down on deselect.

## Status (2026-11-19, new cells)

| Cell | Routed | Magic DRC | KLayout DRC | LVS | PEX: Cfb / vm wiring | Post-layout f–I (typ, 27 °C, S = 100), PEX/schematic over 1.5–8× rheobase |
|---|---|---|---|---|---|---|
| slot_ah | yes | 0 | 0 | match | 8.22 / 18.7 fF | 0.817–0.829 |
| slot_ah_h | yes | 0 | 0 | match | 7.92 / 21.4 fF | 0.824–0.843 |
| slot_ah_p | yes (H's routing, gate tree moved to aux) | 0 | 0 | match | 7.92 / 21.4 fF | 0.825–0.844 |
| slot_ah_f | yes (`SCHED_ROTATE=1`) | 0 | 0 | match | 8.16 / 17.8 fF | 0.837–0.842 |
| slot_cmp_h (no trim) | yes | 0 | 0 | match | – / 6.7 fF | 0.843–0.862 (rate 0.94–0.99× the ideal LIF in schematic) |
| slot_ah_50 | yes | 0 | 0 | match | 7.90 / 17.1 fF | 0.789–0.799 |
| slot_ah_800 | yes | 0 | 0 | match | 7.97 / 25.6 fF | 0.900–0.933 |
| slot_ref | yes | 0 | 0 | match | – | REF tap = S vm tap, PEX vs PEX: 0.00 mV over 1.0–2.0 V, gain 0.7031 (`sim/tb/tb_slot_ref.py`) |
| slot_dummy | yes | 0 | 0 | match | – / 18.1 fF | 0.831–0.836 (spikes counted on vm) |
| trim_tau4 | yes | 0 | 0 | match | – | – |

**slot_cmp_h has no in-slot gap trim (option 2 of the CMP decision, 2026-11-20).**

- **Why:** the trimmed CMP slot never routed in the 28 × 43.5 box: 23 attempts over two comparator placements.
  - Attempts covered all 5 negotiation orders, 150-iteration runs, trim nets routed first, and moving the sub_b/stb pads within their tracks.
  - The best runs ended with 2 conflicts. The congestion moved between the synapse corner, the band pins and the trim ladder.
- **The trimmed schematic** is kept as `slot_cmp_h_trim` in `cells/neuron/slot.spice`, unused.
- **What changed in `slot_cmp_h`:**
  - The `trim_gap4` (18 transistors: the 10-device ladder plus 8 switches) and the t0..t3 pins/straps are removed. Its pins are now S's.
  - The LVS reference `slot_cmp_h_lvs.spice` has no trim.
- **Top level:** nibble 6's four trim latches stay unconnected; the integrator parks them. The control macro, TRIM_MASK and floorplan are unchanged.
- **Placement** (kept from the option-1 re-placement): input pair XM1/XM2 at the right end of row A (x 16.1 / 18.6, y 23.4), next to the aux column; nfet mirror XN1/XN2 right under it (y 17.6); tail XPT above it in row B. XH2 (1/6) stays in the n-well bump under the VDD rail.
- **Bring-up:** CMP's threshold is set only by `vth_cmp` (B1's 5-bit DAC), which is shared by nothing else. Per-die calibration of vth_cmp therefore trims CMP directly, so there is no per-neuron need for nibble 6.

**Schematic checks of the new cells** (results in `sim/results/`):

- **Leak OTA** (`leak/slot_leak_summary.txt`):
  - S = 100: all 15 corner/temperature cases pass. g/Ib ≥ 5.20 S/A, linear range ≥ 76 mV, sourcing ≥ 98 %.
  - S = 1000: ss/0 °C (g/Ib 3.79, sourcing 36 %), sf/0 °C (70 %) and ss/27 °C (85 %) still lose tail headroom.
  - EL = 1.5 V restores them (≥ 98 %); 1.4 V is not enough at ss/0 °C (83 %). **Firmware: EL ≈ 1.5 V at S = 1000.**
- **AH f–I** (`fi_*.log`, slot_ah schematic): all 5 corners × 0/27/85 °C at S = 100 plus S = 10/1000 spike and are monotonic, at 0.74–1.00× the ideal LIF rate.
- **vsrc charge per spike** (`det/det_summary.txt`): 250–340 fC at S = 1000 (was 460–810) and 43 fC at S = 100 (was 2.1 pC).
- **F/S τ ratio** (`tau_f/tau_f_summary.txt`):
  - 1.89–2.08 over all corners at S = 10/100/1000; about 2.01 at 27 °C and about 1.89 at 85 °C (systematic).
  - Mismatch MC (N = 200): mean 2.016, σ 9.6 % (g_S cv 5.4 %, g_F cv 7.4 %).
  - The F OTA at half current is fine: Isat/Ib ≈ 0.47, linear range ≈ S's, and the leakage floor is 0.3 % of g_F at S = 10.
- **Gap trim** (`trim/trim_summary.txt`): range ±19 to ±29 mV, mean step 2.6–3.8 mV.
- **Gap-trim MC** (`mc_trim_summary.txt`, N = 40): rate cv 12.1 % → 1.9 %; 9/40 neurons at code 0 or 15.
- **τ trim** (`trim/trim_tau_summary.txt`, 0.84 µm mirror, 18 cases): monotonic; gain 0.49–0.54 at code 0, 0.97–1.05 at code 8, 1.39–1.50 at code 15; worst error vs ideal 7.1 % (ff, 0 °C).

**Areas.** All slots are 28.0 × 43.5 = 1,218 µm². `trim_tau4` is 37.0 × 11.8 = 437 µm² per cell. Device footprints from `area.py` (S unless noted):

| Block | µm² |
|---|---|
| membrane cap 200 fF (AH50: 21.1; AH800: + 161.3) | 65.9 |
| leak OTA (was 90.3; F 111.4) | 116.5 |
| AH detector (CMP comparator: 83.5) | 60.9 |
| gap trim (H/P) | 84.1 |
| Cfb MOM (AH slots) | 34.7 |
| routing, columns, spacing: S / H / CMP / AH800 / REF | 634 / 550 / 646 / 473 / 1065 |

**Readout with the three-switch tap** (`python3 sim/tb/tb_slot_readout.py slot`, all 15 corner/temperature cases, 32 taps):
- Worst 1 % settling is 173 ns, so the readout still meets its settling target.
- The kicks on a floating 50 fF node are −20.5 mV on en and −11.6 mV on sel/sub.

Simulation summaries:
- `sim/results/syn/syn_summary.txt`
- `sim/results/trim/trim_summary.txt`
- `sim/results/trim/trim_tau_summary.txt`
- `sim/results/mc_trim_summary.txt`

Test benches:
- `sim/tb/synapse/tb_syn.py`
- `sim/tb/trim/tb_trim.py` and `tb_trim_tau.py`
- `sim/tb/tb_lif_mc.py trim`
- `sim/tb/tb_slot_fi.py <corner> <T> <S> <cell>`
- `sim/tb/tb_slot_readout.py`
- `sim/tb/tb_slot_tau.py` (F/S τ ratio)
- `sim/tb/tb_slot_leak.py` (leak OTA)
- `sim/tb/tb_slot_det.py` (vsrc load, idle)
- `sim/tb/tb_slot_detoff.py` (bias-off)
- `sim/tb/tb_slot_ref.py` (REF vs S tap)
- `sim/tb/tb_slot_probe_row.py` (same-row probe error)
