# dend_d1: D1 dendritic neuron layout (gf180mcuD, 3.3 V devices)

Schematic: `cells/dendrite/dendrite.spice` (notes in `cells/dendrite/README.md`). Everything here is generated; do not hand-edit the `.mag` files.

## Flow (repo root, Git Bash)

    scripts/eda.sh "bash layout/dendrite/build.sh"          # devices -> place/route -> magic DRC -> GDS -> LVS -> KLayout DRC -> PEX
    scripts/eda.sh "bash layout/dendrite/build.sh reuse"    # re-emit geometry from out/route_cache_dend_d1.json (no re-route)
    scripts/eda.sh "bash layout/dendrite/build.sh nogen"    # re-verify only
    # SKIPDEV=1 keeps devices/*.mag

| File | Role |
|---|---|
| `dendgen.py` | Builds the layout. It does row placement (`ROWS`), the VSS ring and stripes, n-wells with VDD rails, the spine, feeds, MOM Cfb and keep-outs. Routing is region by region (`REGIONS`): each region's wires become obstacles for the next. Notch and same-net-gap fill follow. |
| `router.py` | Copy of `layout/slot/router.py`. It adds a per-net A* search window (with an unbounded retry if the window fails), a weighted heuristic (`ROUTE_HW`, 1.5 used), and **Metal3 as a third routing layer** (via2 from Metal2; `ROUTE_M3=0` turns it off; nets in `NO_M3` stay off it). |
| `flatten.py` | Writes the LVS reference `dend_d1_lvs.spice` (Cfb omitted; it is a MOM). |
| `diag_alone.py` | Placement diagnostic. It routes each net of one region alone, so you can tell a net blocked by placement from one that is merely congested. |
| `pex_summary.py` | Reports Cfb and compartment wiring capacitance. |
| `route_try.py`, `prof_route.py` | Trial-route one region alone (early routability signal) / time one routing iteration per net. |
| `near_check.py`, `short_check.py`, `short_path.py` | Shapes near a point; net-touch check; GDS vdd–vss short tracer. |

Build used: `scripts/eda.sh "ROUTE_HW=1.5 SKIPDEV=1 bash layout/dendrite/build.sh"` (about 40 min from scratch with Metal3 routing). `D1_DW` sets the extra width (default 7.5).

## Frame (2026-11-19: 70 × 104 µm)

- **Cell size:** 70.0 × 104.0 µm. The old 62.5 µm box no longer held the rows after two changes: the leak/axial OTAs grew (4/1 inputs, 8/1 diodes drawn as two W = 4 fingers, which netgen merges) and the trims moved into the cell. The 70 µm box is accepted (tile x 8–78, y 12–116).
- **VSS:** p-tap ring on the edge, plus p-tap stripes at y = 38.0 and 63.4 between the soma, d1 and d2 regions.
- **VDD:** Metal1 rails along each n-well bottom, to both cell edges (synapse wells: local rails).
- **Spine:** vertical Metal2 at x = 58.4 + 0.7·k. Pins at the top edge (y = 104).
  - Order: el, vbn_leak, vsrc, vsrcp, vbp_st, vbn_ax, vbn_ref, vreset, vbn_prb, (free), abus, sel0, sel2, mreset, spk; then vdd (0.6 wide).
  - Signal lines are cut at y = 20/46/72/96 by Metal3 jumpers (antenna).
- **Metal3 digital lines** from the top edge at x = 30.0 + 0.7·k: en, pl_en, chain, sel1, d1_bsel, sta, stb, hold, ta0..3 (drop y 33.3), tb0..3 (drop y 98.3). vbp_syn is on Metal3 at x 22.6. Internal Metal3 jumpers (x 41.2–44.0): b1, la1, dl1, la2, dl2.
- **Feeds** (Metal2): vep x 56.1 (y 15–87), y2 x 56.8 (y 15–91), d1 x 57.5 (y 10–58).
- **Trims:**
  - Trim 1 (d1, nibble 7): ladder and switches in one nmos row at y 34.8 (above the soma well); its 4 pfet switches at the end of the soma pmos row y 30.4.
  - Trim 2 (d2, nibble 8): ladder in the top row y 99.4 (after the stim-B steering nmos); switches at the end of the d2-axial row y 88.6; pfets in the top well row y 94.8.
  - There are no keep-outs any more.
- **Detector reset devices:** XK/XQ of each plateau detector sit in a short second pmos row (y0 + 21.0, x 44.5) in the subunit well. The soma det_ah XK is in the soma pmos row y 25.6.
- **Routing:** Metal1/2/3, region by region. The trim bits (`ta*`, `tb*`) and the synapse internal nodes (`XY*.da/db/h`, routed first) are kept off Metal3. The trim bits are an antenna fix: ta1 failed ANT.16 with routed Metal3 on top of its 71 µm line. No Metal4/5.
- **Pins:** d1 and d2 are Metal2 pads at (9.45, 39.70) and (9.45, 65.10). vs is labelled on a routed vs wire.

## Status (2026-11-19, new cells, 70 × 104 µm)

| Check | Result |
|---|---|
| magic DRC `drc(full)` | 0 |
| KLayout gf180mcu (variant D, flat, all decks except density, antenna included) | 0 |
| netgen LVS | Circuits match uniquely (213 devices, 148 nets; trims, synapses, steering, keepers all in) |
| PEX Cfb (spk–vs) | 8.21 fF |
| Wiring C | vs 22.3 fF, d1 24.7 fF, d2 13.4 fF |
| Effective node C with hold on (`sim/tb/dendrite/tb_cnode.py`, junctions included) | Schematic: vs 213, d1 221, d2 223 fF. Post-layout: vs 272, d1 250, d2 237 fF. |
| Post-layout synapse test (typical 27, `tb_synapse.py typical 27 pex`) | Clustered: plateau and a 17-spike burst from N = 4 per input (schematic: N = 3). Distributed: nothing up to N = 6. Single-pulse EPSP 45 mV (schematic 63). |

There are no hand patches (`PATCHES` is empty). Closing fills that would violate other-net spacing are now dropped automatically.
