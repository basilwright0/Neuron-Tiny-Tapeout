# Top level: tt_um_basilwright0_analog_neurons (TTGF26c, gf180mcuD, analog 1×2)

Scripted, reproducible assembly of the whole tile from the block layouts. Geometry source of truth:
`floorplan/floorplan.py` (v2). Everything in `work/` is generated; `mag/`, `gds/`, `lef/` are written by the flow.

## Flow (repo root, Git Bash)

    scripts/eda.sh "nice -n 15 bash layout/top/build.sh"           # prep -> route -> assemble -> extract -> LVS
    scripts/eda.sh "nice -n 15 bash layout/top/build.sh noroute"   # re-assemble + LVS from work/routes.json
    scripts/eda.sh "nice -n 15 bash layout/top/drc.sh"             # KLayout (precheck deck + antenna) and magic DRC
    scripts/eda.sh "nice -n 15 bash scripts/precheck.sh"           # TT precheck on gds/<top>.gds

| Step | File | What it does |
|---|---|---|
| Floorplan | `floorplan/floorplan.py` | block boxes, stripes, std-cell rows, slot map; geometry checks |
| Config | `config.py` | which GDS / LVS netlist each block uses, FINAL vs PLACEHOLDER, placements, **net table** `nets()`, std cells |
| Prep | `prep.py` (KLayout) | per block: `work/gds/<cell>.gds` (subcells prefixed so blocks never clash; placeholders = pins only), `work/geo/<cell>.json` (pins, foreign metal); `work/gds/stdcells.gds` |
| Fixed geometry | `geom.py` | Metal4 stripes (ports), ua[0] hookup, array row bands (19 Metal3 tracks per row, via2 drops, west joins of the shared lines, east fan-outs), column-bottom stubs, power buses above the array, B1/R1/D1/AdEx/τ power, tie-high row, glue row |
| Router | `route.py` | gridded A* on Metal2/3/4 (0.14 µm grid, 0.28 wires, 0.38 via pads), legality against real block metal, keep-outs around blocks; Metal4 may cross analog blocks (not the macro) |
| Preview | `plot.py` | `work/top_preview.png` (optionally a zoom window) |
| Assembly | `assemble.py` → `work/assemble.tcl` (magic) | reads block GDS read-only, template DEF, places, paints, saves `mag/<top>.mag`, writes `gds/<top>.gds`, `lef/<top>.lef` (pin-only), extracts `work/top_ext.spice` |
| LVS reference | `netlist.py` | `work/top_ref.spice`: block LVS netlists, macro gate netlist on the PDK std cells, glue/tie cells, top subckt |
| Checks | `build.sh` (netgen), `drc.sh` | `work/lvs_report.txt`, `work/klayout_{main,antenna}.lyrdb`, `work/magic_drc.txt` |

## Block swap ("drop in final GDS + re-run")

1. The owner delivers the final block where `config.LIB` points (e.g. `layout/dendrite/out/dend_d1.gds` and
   `layout/dendrite/dend_d1_lvs.spice`), DRC/LVS clean in its own flow, with its pins as labels on the top cell.
2. Set `final=True` for that cell in `config.LIB` (slots: `_SLOT_FINAL`); drop any `PH_SHIFT` entry.
3. Re-run `build.sh` (full, so the router re-routes to the real pin positions), then `drc.sh` and the precheck.

Pins are read from the GDS labels, so moved pins are re-routed automatically. A block must stay inside its
floorplan box and keep its pins on the box edge (stubs are drawn 0.7 µm out of the edge).

## Top-level additions (owned here)

- **uio_oe tie-high row** (8 × `tieh` + `filltie`, y 318.4, under the uio_oe pins).
- **Glue row** in CH_BOT (x 170–203.6, y 5.5): `en_b = NOR(probe_en_c[3:0], probe_sel_d1, probe_sel_adex)` for R1's pad
  driver (or4 + nor3), and D1's tap selects `sel0/1/2 = probe_sel_d1 & decode(probe_sub_raw)` (3 × inv + 3 × nor3),
  because the macro exports neither. AdEx `en` is tied to `probe_sel_adex`, D1 `en` to `probe_sel_d1`.
- **Column 1 `aux` = B1 `vth_cmp`**; columns 0/2 `aux` from the τ cells; column 3 `aux` floats (no user).

## Status (2026-11-19, evening)

| Block | Used as | Source |
|---|---|---|
| neuron_ctrl (macro rev E) | FINAL | `macros/neuron_ctrl/` |
| bias_b1 (rev C) | FINAL | `layout/bias/out/bias_b1.gds` |
| r1_ua1 / r1_corner | FINAL | `layout/readout/out/r1_ua1.gds` |
| dend_d1 (70 × 104) | FINAL | `layout/dendrite/out/dend_d1.gds` |
| adex_a1 (rev 3, 38 × 73) | FINAL | `layout/tier2/out/adex_a1.gds` |
| trim_tau4 ×2 | FINAL | `layout/slot/out/trim_tau4.gds` |
| all 9 slot variants incl. slot_cmp_h (no in-slot trim, `CMP_TRIM = False`) | FINAL | `layout/slot/out/*.gds` |

Router: 189 tasks (187 signal nets + τ/D1/AdEx vdd hookups + 4 stripe-island ties); negotiated congestion
converges in ~12 iterations (~30 min, one core). `work/routes.json` is kept in git so `build.sh noroute`
rebuilds without routing. Results of the last full run (every block final; no placeholders left):

| Check | Result |
|---|---|
| netgen LVS, full chip (blocks hierarchical, macro at gate level on the PDK std cells) | **Circuits match uniquely** |
| KLayout gf180mcu deck as precheck runs it (gf180mcuD, deep, all decks but density/antenna) | **0** |
| KLayout antenna deck | **0** |
| magic `drc(full)` on the assembled GDS | **0** |
| `scripts/precheck.sh` (TT precheck, 12 checks) | **all pass** |

Post-processing in `assemble.py` that keeps the GDS clean: terminal patches (off-grid pin vs on-grid wire),
same-net notch fill (closing 0.15 µm, kept 0.28 µm from other nets), removal of same-net vias whose cuts are
closer than 0.27 µm (L-shaped bridge, refuses to build if no clear L), and wire-aligned narrow pads where two
same-net via pads sit diagonally closer than 0.28 µm.
Router rules that the checks needed: no Metal4 below y 1.7 (TT analog-pin ring check), Metal2/3 in the bias
channel reserved for the analog column lines, trim tracks broken by a Metal4 jumper next to each trimmed slot
(antenna), the τ-cell gap above D1 closed to Metal2/3 through-routing.

### Switches
- `config.CMP_TRIM` (now False: the final slot_cmp_h has no in-slot gap trim). cfg_out[31..34] (nibble 6,
  CMP.VTH) are left unconnected at the macro's W edge; macro / TRIM_MASK / floorplan unchanged.
- `config.LIB[...]["final"]`, `_SLOT_FINAL`: placeholder vs final per block.

### Known gaps (block owners)
- **τ-trim reference:** `trim_tau4` needs `vg` / `vsn` (the leak-IDAC `trim_ref_n` gate and shifted source rail);
  bias_b1 rev C does not export them, so both τ cells have `vg`/`vsn` open (P leak-τ trims inert). B1 owner.
- `ua0_stim_out` (B1) has no consumer: left open.
- `GRP_EN` (cfg_out[0..3]): no block has a group-enable input: left open.
- Column 3 `aux` floats (no user in that column).
- Macro: N-edge pins were placed with a wrong TT-pin pitch (14.56 instead of 7.28, `floorplan.py` PINS_TOP, now
  fixed), and the S-edge code order differs from B1's top-edge order; both are absorbed by routing today, but a
  `mkpins.py` re-run + re-harden would shorten those jogs. `probe_en_b` and decoded D1 tap selects would let the
  top-level glue row go.
