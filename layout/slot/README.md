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
- `cells/trim/trim_tau.spice`: the strip cell, rev B (2026-11-20): self-contained, mirrors B1's `vbn_leak` on vss (no `trim4_n` / `trim_ref_n` any more).

| Cell | What | Size (µm) |
|---|---|---|
| `slot_ah` | S slot: AH LIF, 200 fF, synapse A/B, hold, mreset, probe taps on vm and vr | 28.0 × 43.5 |
| `slot_ah_h` | H slot: S + 4-bit Vth−EL gap trim (`trim_gap4`, bits t0..t3) | 28.0 × 43.5 |
| `slot_ah_p` | P slot: H, but the leak OTA tail gate (and the gap-trim ladder gate) is the `aux` column line, giving a per-column leak-τ trim | 28.0 × 43.5 |
| `slot_ah_f` | F slot: S with the leak tail W/L halved (1/4 instead of 2/4) on the same `vbn_leak`, so τ_F = 2 τ_S by geometry | 28.0 × 43.5 |
| `slot_cmp_h` | CMP **double slot** (since 2026-11-20, see below): comparator LIF (`det_cmp`, tail/starve on vbp_st) + 4-bit gap trim (`trim_gap4`, t0..t3, nibble 6). Its threshold `vth_cmp` arrives on the `aux` line (column 3); vsrc feeds through. Pins as H; rsel on the row-1 band | 28.0 × 87.0 |
| `slot_ah_50` | AH50: S with a 50 fF membrane (mcap 3.54 × 3.54) | 28.0 × 43.5 |
| `slot_ah_800` | AH800: S + `mcap_r` 11.7 × 11.6 (~540 fF) in the former trim space (gate head down, Metal1 vss shield), about 740 fF in total; the hold switch moves to row A | 28.0 × 43.5 |
| `slot_ref` | REF (slot 0,0): one `prb_tap` on `el` with sb = sub (PROBE_SUB = 3 → row 0, column 0, sub = 1); identical to the array taps; no neuron | 28.0 × 43.5 |
| `slot_dummy` | **unused since 2026-11-20** (its slot (0,3) is CMP's lower half): S with no spk pin and both taps' en/sel/sb tied to vss | 28.0 × 43.5 |
| `trim_tau4` | leak-τ trim for one P column (TE strip); mirrors `vbn_leak` (rev B, see below) and drives that column's `aux` | 37.0 × 11.8 |
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

## trim_tau4 rev B: referenced to vbn_leak (2026-11-20)

**Why.** Rev A mirrored from `vg`/`vsn` (the gate of a `trim_ref_n` carrying a copy of the leak-IDAC current). B1 rev C
has no such node (its leak IDAC `Xi0` feeds only the `rx_n4` master, 4 × nfet 2/4 diodes on vss), so both τ cells had
`vg`/`vsn` open and the trims were inert. B1 stays unchanged; the cell now mirrors `vbn_leak` itself.

**Schematic** (`cells/trim/trim_tau.spice`, self-contained), ports `aux vbn_leak c0 c1 c2 c3 vdd vss`:
- Mirror units on `vbn_leak`, sources on vss, all nfet L = 4 µm (the master's and the slot tails' device and length):
  base XB0 + XB1 (4/4 each, always on) = 8 LSB; bit 3 XU3a + XU3b (4/4 each) = 8; bit 2 XU2 4/4; bit 1 XU1 2/4;
  bit 0 XU0 1/4 (LSB = 1/4 = half a master unit). I_d = (8 + c) · I(1/4) ≈ (8 + c)/2 · I_tail(S).
- **Source switches** XS0..3 (nfet 0.5/0.5, unit source → vss) on c0..c3. An off branch is a two-transistor stack, so
  its leakage stays far below that of a drain switch at Vds ≈ 2.9 V (drain switches gave 0.61 instead of 0.50 at
  code 0, ff/85 °C, 36 pA tails).
- XPD0..3 (4 × pfet 1/2 diode) : XPM (pfet 0.83/2) ≈ 4 : 1 into the `aux` diode XNDa + XNDb (2 × 2/4, each identical to
  the slot tail XMT). So I_tail(P) = I_d/8 = (8 + c)/16 · I_tail(S), **τ_P = τ_S · 16/(8 + c)**, the same code meaning
  as rev A (0.50× … 1.44× leak current, 1.00× at code 8). XPM's 0.83 µm (not 1) cancels the ~+17 % systematic gain
  from the drain-voltage differences (units at ~2.9 V vs the master diode at ~0.4 V).
- Load on `vbn_leak`: 92 µm² of L = 4 gate per cell (184 µm² for both), roughly doubling the line's gate area.

**Verification** (`sim/tb/trim/tb_trim_tau.py` → `sim/results/trim/trim_tau_summary.txt`): the full `bias_b1` rev C LVS
reference (`layout/bias/out/ref_bias_b1.spice`: leak IDAC + `rx_n4` and everything feeding them, EXT ÷1) drives
`vbn_leak`, with no ideal source. A schematic S slot and a P slot (aux from the trim cell) are compared by their leak
conductance at vm = EL (τ = 200 fF/g); ratio = g_P/g_S = τ_S/τ_P, ideal (8 + c)/16. Leak codes 1 / 9 / 16 / 31 at
S = 100 (code 9 ≈ the S = 100 design τ):

| Corner | ratio at code 0 / 8 / 15 (leak codes 1 … 31) | max error vs ideal | min step / mean step | monotonic |
|---|---|---|---|---|
| typical 27 °C | 0.509–0.521 / 1.001–1.030 / 1.422–1.467 | 1.7–4.2 % | 0.96–0.97 | all |
| ss 0 °C | 0.526–0.536 / 1.022–1.055 / 1.348–1.494 | 5.2–7.1 % | 0.69–0.91 | all |
| ff 85 °C | 0.486–0.560 / 0.955–1.027 / 1.365–1.414 | 3.9–11.9 % | 0.88–0.92 | all |
| typical 27 °C, extracted bias_b1 (leak code 9) | 0.513 / 1.013 / 1.441 | 2.5 % | 0.96 | yes |

- ss/0 °C, leak code 31 (an S ≈ 340 tail current at EL = 1.30 V): the code-15 τ ratio is 1.348 while the tail-current
  ratio is 1.455; the P slot's leak OTA runs out of tail headroom (the known ss/0 °C limit, firmware rule EL ≈ 1.5 V
  above S ≈ 300). At S = 1000 with EL = 1.50 V (ss/0 °C, code 31): 0.516 / 0.989 / 1.348 (current ratio 0.501 / 0.988 / 1.401).
- ff/85 °C, leak code 1 (36 pA tails): code 0 reads 0.560: the 2/4 tail's own off-state floor at that corner is
  ~3.3 pA, so ratios compress toward 1 near it. At S = 10 and leak code 1 (5.5 pA tails, ff/85 °C) the S neuron itself sits
  at that floor and the trim range collapses to 1.07–1.56 (still monotonic). Keep I_tail(S) ≳ 30 pA at hot fast silicon.
- **P vs S at the nominal code 8:** τ_S/τ_P = 1.013 (typical 27 °C, leak code 9), 0.955–1.055 over all corners and codes.
- **Mismatch MC** (typical 27 °C, S = 100, leak code 9, 20 dies; B1, S slot, P slot and trim cell all with mismatch):
  τ_S/τ_P mean 0.495 / 0.978 / 1.391 at codes 0 / 8 / 15, σ 14.4 % (code 8: 0.765–1.227), the same at every code;
  monotonic on 20/20 dies, smallest step 0.036 (mean 0.060); span code 15/code 0 2.70–2.90. The code shape is
  tight (σ of ratio/ratio(8): 0.7 % at code 0, 1.0 % at code 15), so the spread is a per-neuron gain, which the trim
  removes. Split: the two slots' leak OTAs ~9.4 %, the tail-copy current ratio 13.3 %, of which ~11 % is the trim chain
  (mostly the 1/2 pfet mirror; 2/4 pfets would give ~7 % but do not fit the 37 × 11.8 box).
- **Settling** (S = 10, leak code 9, 30 pA tails): `aux` after a τ-code step 0 → 15 / 15 → 0: 0.18 / 0.45 ms (27 °C),
  0.19 / 0.47 ms (85 °C). `vbn_leak` after a leak-code step 1 → 9 / 9 → 1 with an approximate array load: 0.83 / 5.0 ms
  without the trim cells, 1.35 / 8.2 ms with both (27 °C); 0.95 / 5.7 → 1.56 / 9.4 ms at 85 °C.

**Layout** (`elgen.py`, same 37.0 × 11.8 box): row A the L = 4 units (5 × 4/4, then 2/4 under 1/4), row B the four
source switches under the pfet row, aux diodes at the left, pfets in an n-well at the top right with an n-tap. Pins are
Metal2 straps from the top edge: aux 6.20, vbn_leak 12.20, c2 15.20, c3 21.60, c1 27.60, c0 31.00, vdd 35.20; vss is
the p-tap ring. Routed on the first schedule; magic DRC 0, KLayout DRC 0, LVS match.

## Frame, rails, columns

- **Rings and rails:** the VSS p-tap ring is on all edges, and the VDD Metal1 rail is at y = 21.32–21.92.
- **Main n-well:** 0.9–21.6 × 21.2–29.8, with its own n-tap ring.
- **N-well extensions:** each merges with the main well and is tapped by its ring:
  - the synapse well, 19.45–26.9 × 29.3–38.9;
  - the dump-pfet well, 14.75–19.45 × 32.5–35.1;
  - the hold-switch and trim-pfet well: 0.9–13.5 × 29.6–32.6 in H/P/CMP, 8.8–11.4 in S/F/AH50/DUMMY/REF, none in AH800;
  - CMP only: a bump 0.9–8.75 × 18.65–21.25 under the VDD rail for the comparator's hysteresis source XH2 (1/6).

**Column lines** are full-height Metal2 at a 0.7 µm pitch and connect by abutment. vdd is 0.6 µm wide; all the others are 0.3 µm.

| Line | x | Note |
|---|---|---|
| vbp_syn | 19.05 | **new**: synapse weight bias, from a p-IDAC into a 2/4 pmaster in B1 |
| vdd | 19.85 | |
| el | 20.65 | |
| aux | 21.35 | **P slot:** leak tail + gap-ladder gate (τ trim, columns 0 and 2, from `trim_tau4`). **CMP slot: `vth_cmp`** (column 3: the integrator connects B1's `vth_cmp` output to column 3's aux; column 1's aux floats). Otherwise a feed-through. No column line was added; every variant has the same 12 lines. |
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

| Track k | Signal | Pin in the cell: Metal2 pad 0.4 × 0.4 at x (S, F, AH50, AH800 / H, P, CMP). REF has only rsel and sub; CMP has rsel on its row-1 band; DUMMY has no rsel, sub, sub_b or spk |
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
- Gap-trim code 0: rest is shifted −22 mV (CMP: −26 mV), so the neuron is slower; it is not stuck.
- τ code 0: 0.5× leak current, so τ is 2× longer.

Firmware must rewrite the trims after every select, because TT powers the project down on deselect.

## Status (2026-11-19, new cells)

| Cell | Routed | Magic DRC | KLayout DRC | LVS | PEX: Cfb / vm wiring | Post-layout f–I (typ, 27 °C, S = 100), PEX/schematic over 1.5–8× rheobase |
|---|---|---|---|---|---|---|
| slot_ah | yes | 0 | 0 | match | 8.22 / 18.7 fF | 0.817–0.829 |
| slot_ah_h | yes | 0 | 0 | match | 7.92 / 21.4 fF | 0.824–0.843 |
| slot_ah_p | yes (H's routing, gate tree moved to aux) | 0 | 0 | match | 7.92 / 21.4 fF | 0.825–0.844 |
| slot_ah_f | yes (`SCHED_ROTATE=1`) | 0 | 0 | match | 8.16 / 17.8 fF | 0.837–0.842 |
| slot_cmp_h (double slot, with trim) | yes (schedule 0, 9 iterations) | 0 | 0 | match | – / 9.9 fF | 0.820–0.832 (rate 0.93–0.99× the ideal LIF in schematic) |
| slot_ah_50 | yes | 0 | 0 | match | 7.90 / 17.1 fF | 0.789–0.799 |
| slot_ah_800 | yes | 0 | 0 | match | 7.97 / 25.6 fF | 0.900–0.933 |
| slot_ref | yes | 0 | 0 | match | – | REF tap = S vm tap, PEX vs PEX: 0.00 mV over 1.0–2.0 V, gain 0.7031 (`sim/tb/tb_slot_ref.py`) |
| slot_dummy (unused) | yes | 0 | 0 | match | – / 18.1 fF | 0.831–0.836 (spikes counted on vm) |
| trim_tau4 (rev B, vbn_leak reference) | yes (schedule 0, first try) | 0 | 0 | match | – | – |

**slot_cmp_h is a 28 × 87 double slot with its gap trim (2026-11-20, the user's choice after option 2).**

- **History:** the trimmed CMP never routed in 28 × 43.5 (23 attempts over two comparator placements, best 2
  conflicts); option 2 (no trim) was committed in d0641c1 and is kept as `slot_cmp_h_notrim` in
  `cells/neuron/slot.spice` (fallback; `CMP_TRIM = False`).
- **Now:** CMP takes the dummy slot's area: column 3, rows 0–1 (`floorplan.DOUBLE`). CMP and S2 swapped positions:
  CMP's map position is (1,3), S2 is at (1,1). Spike channels and trim nibbles are unchanged (CMP = 12, CMP.VTH =
  nibble 6). The macro's probe decoder is fixed, so **probe SEL 4 reads CMP and SEL 12 reads S2**.
- **Cell** (`slotgen.py`, `DOUBLE = CMP`): the lower half is the CMP slot as before, with H's switch slices (XP at
  y 31.3, XN at 33.8, straps t3..t0 at x 3.1 / 5.9 / 8.7 / 11.5) and H's pad x (mreset 18.30, sub_b 15.30); the
  R-2R ladder (legs, XR*, XLT, XRA/XRB) moves up 10 µm into the upper half (y 46–50.4). Second VDD rail at
  y 64.82–65.42 (abuts F1's rail), p-tap ring on the 28 × 87 perimeter, the same 12 column lines full height.
- **Bands:** both row bands (y 32.24–42.60 and 75.74–86.10) are Metal3-free and vm-free; Metal3 is allowed between
  them. Row pins (sta/stb/hold/mreset, sub/sub_b, spk strap, t0..t3 straps) sit on the **row-0** band (row 0 now has
  two trimmed slots, H1 and CMP: CMP's bits on tracks 15–18); **rsel** is a pad on the **row-1** band
  (x 15.30, track 4), so the probe address is row 1 / column 3.
- **Routed** on the first schedule in 9 iterations (no conflicts).
- **Gap trim on the comparator** (`sim/tb/trim/tb_trim_cmp.py`, typical 27 °C, S = 100, vth_cmp = 1.38 V; summary
  `sim/results/trim/trim_cmp_summary.txt`): rest shift vs code 8 is −25.6 … +19.5 mV in schematic and −25.6 … +19.4 mV
  in PEX, monotonic, mean step 3.0 mV (2.4–5.5). Rate at 2× rheobase, code 0 / 8 / 15: 8726 / 10602 / 12143 Hz
  (schematic), 7188 / 8751 / 10178 Hz (PEX).

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
- **τ trim** rev B: see "trim_tau4 rev B" below.

**Areas.** All slots are 28.0 × 43.5 = 1,218 µm², except CMP (28.0 × 87.0 = 2,436 µm²). `trim_tau4` is 37.0 × 11.8 = 437 µm² per cell. Device footprints from `area.py` (S unless noted):

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
