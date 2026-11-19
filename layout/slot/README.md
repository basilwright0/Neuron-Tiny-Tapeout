# Neuron-array slots and the strip trim cells (gf180mcuD, 3.3 V devices)

> **RESUME HERE (paused 2026-11-19 ~07:00 UTC).** The status table further down describes the OLD cells and is stale.
>
> **What changed in the cells (all slots use them):**
> - `leak_ota_deg` / `leak_ota_degx`: inputs 4/1, diodes 8/1, nominal EL/Vth/Vreset 1.30/1.38/1.30. In layout the 8/1 diodes are drawn as two 4/1 halves; netgen merges them.
> - `det_ah`: st3, i.e. XS3 starve plus XN3 kept on vsrc. st3v does not idle at vsrc > 0.55 V.
> - `prb_tap`: + XSC, a series switch on `en`. This is the same-row probe bug fix.
> - New variants: `slot_ah_f`, `slot_cmp_h` (vth_cmp on `aux`, column 1), `slot_ah_50`, `slot_ah_800`, `slot_ref`, `slot_dummy`.
> - `slotgen.py` defaults: re-packed leak row (y 12.7) and `PROBE_CHAIN=1` (XPM switches in order along y = 8).
>
> **Routed with the new cells and the default placement** (route caches valid; `FAILED: none`):
> - `slot_ah`, `slot_ah_f`, `slot_ah_50`, `slot_ref`, `slot_dummy` (out/<cell>_route.log);
> - `slot_ah_800` (out/slot_ah_800_route2.log; routed with `PROBE_CHAIN=1`, now the default).
> - DRC, LVS and PEX have NOT been run on any of these yet.
>
> **Mid-route when stopped** (killed; their .mag / paint / cache are STALE, from the 2026-11-18 cells):
> - `slot_ah_h`: schedule 2, iter 51, 4 conflicts (hold, sub, sub_b, vss).
> - `slot_cmp_h`: schedule 2, iter 38, 5 conflicts (hold, rsel, sub_b, vr, vss).
> - `slot_ah_p` was not started (it derives from H).
> - `out/route_cache_slot_ah_h.json` and `out/route_cache_slot_ah_p.json` are stale. Do not use `reuse`/`P_FROM_H` until H is rerouted.
>
> **Next commands** (Git Bash, repo root):
> 1. Verify the six routed cells (about 30 min):
>
>        scripts/eda.sh 'CELLS="slot_ah slot_ah_f slot_ah_50 slot_ah_800 slot_ref slot_dummy" bash layout/slot/build.sh nogen'
>
> 2. Route H and CMP. The run was converging slowly at about 2 min/iteration. If they fail all 5 schedules, the congestion is now at the hold/sub/sub_b pads (x 14.0 / 15.3) above the trim slices.
>
>        scripts/eda.sh 'cd layout/slot && for c in slot_ah_h slot_cmp_h; do SLOT_CELL=$c python3 -u slotgen.py > out/${c}_route.log 2>&1 & done; wait; SLOT_CELL=slot_ah_p python3 -u slotgen.py > out/slot_ah_p_route.log 2>&1'
>        scripts/eda.sh 'CELLS="slot_ah_h slot_cmp_h slot_ah_p trim_tau4" bash layout/slot/build.sh nogen'
>
> 3. Typical PEX f-I checks for each cell (EL 1.30):
>
>        scripts/eda.sh "python3 sim/tb/tb_slot_fi.py typical 27 100 <cell>"
>
>    For REF: `python3 sim/tb/tb_slot_ref.py typical 27 pex`.
> 4. Rewrite the status table below.
>
> **Schematic results already done** (sim/results):
> - `leak/slot_leak_summary.txt`
> - `det/det_summary.txt`
> - `tau_f/tau_f_summary.txt`
> - `trim/trim_summary.txt`
> - `mc_trim_summary.txt`
> - the f-I logs `fi_*_*_*.log`
> - `ro_*_slot_tap_*` (readout with XSC: 173 ns, kick -20.5 mV)
>
> Backup of the 2026-11-18 slot outputs (old cells): the session scratchpad `slot_backup/` (temporary).

Schematics:
- `cells/neuron/slot.spice`: the slot cells. Sub-blocks come from `cells/neuron/synapse.spice` (input synapse, hold, membrane reset) and `cells/trim/trim_gap.spice` (gap trim).
- `cells/trim/trim_tau.spice`: the strip cell. It is built around B1's `trim4_n` (`cells/bias/bias_trim.spice`).

| Cell | What | Size (µm) |
|---|---|---|
| `slot_ah` | S slot: AH LIF, 200 fF, synapse A/B, hold, mreset, probe taps on vm and vr | 28.0 × 43.5 |
| `slot_ah_h` | H slot: S + 4-bit Vth−EL gap trim (`trim_gap4`, bits t0..t3) | 28.0 × 43.5 |
| `slot_ah_p` | P slot: H, but the leak OTA tail gate (and the gap-trim ladder gate) is the `aux` column line, giving a per-column leak-τ trim | 28.0 × 43.5 |
| `trim_tau4` | leak-τ trim for one P column (TE strip, 3 cells side by side); drives that column's `aux` | 37.0 × 11.8 |
| `trim_el4` | **unused** since 2026-11-18 (the P second knob changed from EL to τ); kept for reference, built only on request | 28.0 × 10.6 |

Everything here is generated. Do not hand-edit `.mag` files.

## Flow (from the repo root, Git Bash)

    scripts/eda.sh "bash layout/slot/build.sh"           # slot_ah slot_ah_h slot_ah_p trim_tau4: devices -> place/route -> DRC -> LVS -> PEX
    scripts/eda.sh "bash layout/slot/build.sh nogen"     # re-verify only
    scripts/eda.sh "bash layout/slot/build.sh reuse"     # re-emit geometry from out/route_cache_<cell>.json
    # options: CELLS="slot_ah_h" (subset), SKIPDEV=1 (keep devices/*.mag), P_AS_H=1 (cut the P group),
    #          ROUTE_FINE=0 (old 0.30 um wires / 0.70 um grid), SCHED_ROTATE=k (other negotiation order)

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
  - the hold-switch and trim-pfet well: 0.9–13.5 × 29.6–32.6 in H/P, 8.8–11.4 in S.

**Column lines** are full-height Metal2 at a 0.7 µm pitch and connect by abutment. vdd is 0.6 µm wide; all the others are 0.3 µm.

| Line | x | Note |
|---|---|---|
| vbp_syn | 19.05 | **new**: synapse weight bias, from a p-IDAC into a 2/4 pmaster in B1 |
| vdd | 19.85 | |
| el | 20.65 | |
| aux | 21.35 | P slot: leak tail + gap-ladder gate (τ trim); otherwise a feed-through |
| vbn_leak | 22.05 | |
| vsrc | 22.75 | |
| vbp_st | 23.45 | |
| vbn_prb | 24.15 | |
| vbn_ref | 24.85 | |
| en | 25.55 | **now per-column probe select**: en_c = PROBE_EN & (SEL column == c) |
| vreset | 26.25 | |
| abus | 26.95 | |

## Row Metal3 band (shared with the top-level row router)

The band is y = 32.24–42.60. It has 19 tracks at the Metal3 minimum pitch: 0.28 wide, centres at 32.38 + 0.56·k. The cell has no Metal3 at y ≥ 31.96, and vm stays below that line too, so no vm metal lies under any track.

| Track k | Signal | Pin in the cell: Metal2 pad 0.4 × 0.4 at x (S / H, P) |
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
- **In the slot:** a second series switch in each tap (`prb_tap`, XSB, W/L 1/0.28; 2 transistors per slot). Local Metal3 above y = 31.96 is lost.
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

## Status (2026-11-18)

| Cell | Routed | Magic DRC | KLayout DRC | LVS | PEX | Post-layout f–I (typ, 27 °C, S = 100, PEX/schematic) |
|---|---|---|---|---|---|---|
| slot_ah | yes | 0 | 0 | match | Cfb 8.22 fF, vm wiring 17.5 fF | 0.845–0.851 over 1.5–8× rheobase |
| slot_ah_h | yes | 0 | 0 | match | Cfb 7.89 fF, vm wiring 20.0 fF | 0.824–0.830 |
| slot_ah_p | yes (H's routing, gate tree moved to aux) | 0 | 0 | match | Cfb 7.89 fF, vm wiring 20.0 fF | 0.826–0.831 |
| trim_tau4 | yes | 0 | 0 | match | – | – |

**Areas.** All slots are 28.0 × 43.5 = 1,218 µm². `trim_tau4` is 37.0 × 11.8 = 437 µm² per cell, so three cells make 1,310 µm², filling the 112 × 12 TE strip. Device footprints from `area.py`:

| Block | µm² |
|---|---|
| membrane cap 200 fF | 65.9 |
| leak OTA | 90.3 |
| AH detector | 47.8 |
| refractory | 29.0 |
| Cr 50 fF | 21.1 |
| probe tap vm / vr, each | 33.2 |
| input synapse + hold/reset | 66.6 |
| gap trim (H/P only) | 84.1 |
| Cfb MOM | 34.7 |
| p-tap ring | 84.4 |
| n-tap ring | 33.1 |
| routing, columns, spacing: S / H | 679 / 595 |

**Readout with the two-switch tap** (`python3 sim/tb/tb_slot_readout.py slot`, all 15 corner/temperature cases, 32 taps):
- Worst 1 % settling is 173 ns, so the readout still meets its settling target.
- The kicks on a floating 50 fF node are −20.5 mV on en and −11.7 mV on sel/sub.

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
