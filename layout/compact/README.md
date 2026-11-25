# Compact layout generator (M2)

Generates the neuron-array slots from the schematic with no hand placement:
- shared diffusion: chains with uncontacted series nodes, width steps, dog-bone narrow devices, staggered gate heads;
- common well strips: n and p rows hanging from shared p-tap / n-tap strips, one n-well per pair of p rows;
- row-based placement: simulated annealing on weighted HPWL with hard penalties;
- P&R search: each candidate placement is scored by a trial route (PathFinder on Metal1–3), run in parallel.

    scripts/eda.sh "cd layout/compact && MOM_STYLE=tall CB_W=4 SEED=1 SWEEP='CHAN=1.8;CONG=0' bash build.sh final"  # S (baseline)
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

| Cell | Size | Placement | Magic DRC | KLayout DRC | LVS | PEX |
|---|---|---|---|---|---|---|
| cslot_ah (S), **baseline, level 2 (XSW 1 µm)** | 28.0 × 31.22 (874 µm², −28 % vs 1218) | MOM_STYLE=tall, seed 1, CHAN 1.8 | 0 | 0 | match | Cfb 6.14 fF, vm wiring 11.0 fF; f–I 0.887–0.896 |
| cslot_ah (S), smallest | 28.0 × 29.42 (824 µm², −32 %) | gate MOM, seed 2, CHAN 1.2 | 0 | 0 | match | Cfb 5.0 fF (below 6–10), vm 9.0 fF |
| cslot_ah_f (F) | 28.0 × 31.22 | MOM_STYLE=tall, seed 1, CHAN 1.8 | 0 | 0 | match | Cfb 6.30 fF; f–I 0.885–0.906 (old 0.837–0.842) |
| cslot_ah_50 (AH50) | 28.0 × 31.22 | single-finger cap kept west of the column band, MOM_STYLE=tall, seed 2, CHAN 1.8 | 0 | 0 | match | Cfb 2.95 fF (on 50 fF); f–I 0.742–0.847 (old 0.789–0.799) |
| cslot_ref (REF) | 28.0 × 31.22 | seed 0, CHAN 1.8 | 0 | 0 | match | – |
| ce1_fb (E1, MIL-362: fixed-bias S twin, docs/r2/e1-fixed-bias.md) | 28.0 × 34.29 | two short n rows (EXTRA_N=1), CHANS 0.93/0.93/0.935/0.935, seed 6, CB_W 4, STEPS 40000 | 0 | 0 | match | Cfb 6.37 fF; PEX/sch f at 2× rheo 0.83–0.98 |
| cslot_ah_h (H) | 35.36 / 37.76 tried; ladder rows moved below the band (`SHORT_ROWS=low`) | CHAIN_MAX 13, STEPS 80000 | **not routed**: best 12 nets fail at 37.76 | | | |

Post-layout f–I (typical 27 °C, S = 100), PEX/schematic over 1.5–8× rheobase: baseline **0.850–0.860**, smallest
0.876–0.889 (old layout 0.817–0.829). Baseline vm swing 1.254–1.475 V (schematic 1.230–1.496).

**Open:** H routability (then P), CMP, AH800, corner sims. Edit `slot.spice`
only when no search is running (trials re-read the netlist). Router gaps are Euclidean at corners since 2026-11-21.
A search worker needs ~0.85 GB: at most 2 workers fit the 2.5 GB `millstone-heavy` cap.
