# Compact layout generator (M2)

Generates the neuron-array slots from the schematic with no hand placement:
- shared diffusion: chains with uncontacted series nodes, width steps, dog-bone narrow devices, staggered gate heads;
- common well strips: n and p rows hanging from shared p-tap / n-tap strips, one n-well per pair of p rows;
- row-based placement: simulated annealing on weighted HPWL with hard penalties;
- P&R search: each candidate placement is scored by a trial route (PathFinder on Metal1–3), run in parallel.

    scripts/eda.sh "cd layout/compact && CB_W=4 SEED=2 SWEEP='CHAN=1.2;CONG=0' bash build.sh final"   # S slot (clean)
    millstone-heavy --project "Tiny Tapeout" -- env CB_W=4 SWEEP="CHAN=1.2" SEEDS=4 python3 -u cgen.py searchonly  # local search
    scripts/eda.sh "cd sim/tb && PEX_NAME=cslot_ah python3 tb_slot_fi.py typical 27 100 slot_ah"       # PEX f–I

Resource rule (MIL-6 `gpu-vm-schedule` rev 5): at most 4 local workers (JOBS is capped at 4 unless ON_BOAT=1), heavy
local jobs under `millstone-heavy`; bigger searches and PEX batches on one boat VM, stopped right after.

Outputs land in `out/` (git-ignored): `<name>_paint.tcl`, `.gds`, `_lvs.spice` (reference; netgen merges the folded
fingers), `_ext.spice`, `_pex.spice`, DRC and LVS reports. The layout cell is named `c<cell>` (`cslot_ah`) while it is in
development, so it never clashes with `layout/slot`.

| File | What |
|---|---|
| `geom.py` | design rules (from the PDK device generator), finger folding, chain drawing, greedy / merge chainers |
| `cgen.py` | frame (ring, rows, wells, 12 column lines, row band), placement, band pins, MOM, routing, search, outputs |
| `crouter.py` | copy of `layout/slot/router.py` with a persistent static-legality cache (~20× faster) |
| `access.py`, `solo.py` | pre-checks per trial: first-move pin access; every net routed alone on the static geometry |
| `slotgen_fill.py` | same-net notch fill (from `slotgen.py`) and metal minimum-area repair |
| `test_geom.py` | DRC / extraction test cell for the chain geometry |

## Frame rules that make it routable
- **vm stays below the Metal3 row band** (no vm metal under the tracks). The p rows and the cap row are below it; the
  band rows (Metal1/Metal2 only) take n devices without vm.
- **Membrane cap flush east, under the Metal2 column lines,** with a Metal1 vss shield over its gate. Devices under the
  column lines can only escape on Metal1, and the cap needs no escape. The Cfb MOM sits on the west finger.
- **Column-band escape penalty** (`CB_W`, per µm of Metal1 escape) for other terminals under the column lines.
- **Band pins:** pad and strap x positions are chosen after placement (the top-level router reads the labels). Straps
  use a reserved lane just west of the column lines.
- Every trial is pre-checked for pin access and solo routability; failing seeds are dropped before routing.

## Status (2026-11-21)

| Cell | Size | Route | Magic DRC | KLayout DRC | LVS | PEX |
|---|---|---|---|---|---|---|
| cslot_ah (S) | 28.0 × 29.42 (824 µm², −32 % vs 1218) | seed 2, CHAN 1.2, clean | 0 | 0 | match | Cfb 5.0 fF (**below the 6–10 window**), vm wiring 9.0 fF (was 18.7) |

Post-layout f–I (typical 27 °C, S = 100), PEX/schematic over 1.5–8× rheobase: **0.876–0.889** (old layout 0.817–0.829).
vm swings 1.263–1.455 V in PEX vs 1.230–1.496 in schematic.

**Open:**
- **Cfb.** The larger MOM styles (`MOM_STYLE=tall|head`) give more Cfb but no seed has routed them clean yet (best: 2
  nets). Options: the 1.8 µm channel placement (H 31.2, routed clean with the small MOM), MOM tuning per seed, or
  accept a smaller Cfb after a detector check.
- **Not yet:** the other variants (H/P/F/CMP/AH50/AH800/REF), the level-2 reset-switch width (`wsw`), corner sims.
