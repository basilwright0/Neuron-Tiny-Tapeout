# dend_d1: D1 dendritic neuron layout (gf180mcuD, 3.3 V devices)

Schematic: `cells/dendrite/dendrite.spice` (notes in `cells/dendrite/README.md`). Everything here is generated; do not hand-edit the `.mag` files.

## RESUME HERE (2026-11-19, paused for the night)

**State of the new neuron cells** (det_ah stage-3 starve, leak_ota_deg 4/1 + 8/1, EL/Vth/Vreset 1.30/1.38/1.30):

- **Schematic: done, not yet written into cells/dendrite/README.md.**
  - Changes:
    - `ax_ota_h` and `leak_ota_dega` were resized to match (4/1 inputs, 8/1 diodes).
    - The `pdet` third stage is starved (XS3). Peak vsrc current per crossing dropped from 43 to 10 µA (`tb_pdet_q.py`).
    - The trims are now inside `dend_d1` (XR1/XR2). `la*/dl*` are no longer ports, and `dend_d1t` is an alias.
    - `dcommon.py` uses EL 1.30; `vsrc` calibrates to about 0.58 V.
  - 15 corners (`sim/results/dendrite/corners_summary.txt`; the old run is in `corners_v1_el12/`):
    - Attenuation is 0.538–0.544 everywhere (ss/0 0.538, sf/0 0.544). R/model is 0.98 at typical 27, because g/Ib is 6.33 vs 6.18.
    - Plateau threshold is 110–119 mV above EL, 88–94 mV above rest. Duration is 1.6–1.8 ms with 16–18 spikes, except **ff/85: 2.3 ms and 27 spikes (outlier, not investigated yet)**.
  - Clustered vs distributed (typical 27, ss/0, sf/0, ff/85): clustered fires from N = 2–3. Distributed is silent up to N = 4 at every corner.
- **Layout: NOT done.**
  - The new cell does not fit 62.5 µm wide: three rows overflow by 2–5 µm.
  - `dendgen.py` now places everything, both trims included (no keep-outs), at **W = 62.5 + DW, DW = 7.5 (env `D1_DW`), H = 104**. The widest row ends at x 53.2.
  - The floorplan has room from about x 128 to 198, between the Metal4 strap pairs. **Report the box as 70 × 104 if it routes.**
  - The diodes are drawn as two W = 4 fingers (`split_wide`), and netgen merges them.
  - `place` passes with no overlaps.
- **Mid-run when stopped:** the full build (`build.sh`) was routing region 0 (iteration 5, 51 conflicts, slow on the 449-wide grid). It was killed. `out/route_region*.json` are deleted. `out/*.gds/.spice/.mag` and `dend_d1_paint.tcl` are still the OLD 62.5 µm clean cell (169 devices; trims not drawn; old OTAs). `dend_d1_lvs.spice` is already the new 211-device reference.
- **Next steps:**
  1. Run `scripts/eda.sh "SKIPDEV=1 bash layout/dendrite/build.sh"` in the background. It takes about 1–3 h per region.
     - If region 0 or 2 will not converge: lower the trim-row density (rows 30.2 / 33.8 / 36.2 and 99.4), or raise DW.
     - Watch for DRC near the soma-well pocket (well split at x 34.5, y 29.0) and the 0.6 µm ndiff–well gap at the top row y 99.4.
  2. Get DRC (magic + KLayout) to 0 and LVS clean. `short_check.py` / `short_path.py` help with shorts; the `PATCHES` list is empty now.
  3. PEX, then `tb_synapse.py typical 27 pex` (it now maps all ports by name, trims included).
  4. Optionally try a smaller DW (≥ 5 needed: the vep feed sits at 48.45 + DW, and row 88.6 ends at 53.2).
  5. Update `cells/dendrite/README.md` (results above), this README's Frame and Status sections, and re-run `tb_mc.py` with the new cells.

## Flow (repo root, Git Bash)

    scripts/eda.sh "bash layout/dendrite/build.sh"          # devices -> place/route -> magic DRC -> GDS -> LVS -> KLayout DRC -> PEX
    scripts/eda.sh "bash layout/dendrite/build.sh reuse"    # re-emit geometry from out/route_cache_dend_d1.json (no re-route)
    scripts/eda.sh "bash layout/dendrite/build.sh nogen"    # re-verify only
    # SKIPDEV=1 keeps devices/*.mag

| File | Role |
|---|---|
| `dendgen.py` | Builds the layout. It does row placement (`ROWS`), the VSS ring and stripes, n-wells with VDD rails, the spine, feeds, MOM Cfb and keep-outs. Routing is region by region (`REGIONS`): each region's wires become obstacles for the next. Notch and same-net-gap fill follow. |
| `router.py` | Copy of `layout/slot/router.py`. It adds a per-net A* search window, with an unbounded retry if the window fails. |
| `flatten.py` | Writes the LVS reference `dend_d1_lvs.spice` (Cfb omitted; it is a MOM). |
| `diag_alone.py` | Placement diagnostic. It routes each net of one region alone, so you can tell a net blocked by placement from one that is merely congested. |
| `pex_summary.py` | Reports Cfb and compartment wiring capacitance. |

## Frame

- **Cell size:** 62.5 × 104.0 µm, equal to the floorplan's D1 box (docs/06).
- **VSS:** p-tap ring on the edge, plus p-tap stripes at y = 38.0 and 63.4 between the soma, d1 and d2 regions.
- **VDD:** Metal1 rails along each n-well bottom. They run to both cell edges, ready for the Metal4 stripes at x 125.5 / 197.9 at top level. The top well's rail runs to the left edge only.
- **Spine:** vertical Metal2. Pins sit at the top edge (y = 104), facing CH_MID and the macro.
  - Order (x = 50.9 + 0.7·k): el, vbn_leak, vsrc, vsrcp, vbp_st, vbn_ax, vbn_ref, vreset, vbn_prb, (free), abus, sel0, sel2, mreset, spk; then vdd (0.6 wide).
  - Metal3 digital lines from the top edge at x = 30.0 + 0.7·k: en, pl_en, chain, sel1, d1_bsel, sta, stb, hold, ta0..3, tb0..3. vbp_syn is on Metal3 at x 22.6.
  - Signal lines are cut at y = 20/46/72/96 by Metal3 jumpers (antenna: about 100 µm of Metal2 on small gates).
- **Feeds** (Metal2):
  - d1: x 50.0, y 10–58.
  - y2: x 49.3, y 15–96. This is d2's far end, going down to the star/chain switches.
  - vep: x 48.6, y 15–87.
- **Metal3:** Cfb MOM (42.1–48.8 × 1.6–6.8), spine jumpers, the digital lines above, vbp_syn, and internal jumpers b1, la1, dl1, la2, dl2 (x 41.2–44.0). No Metal4/5.
- **Pins:** d1 and d2 are Metal2 pads at (9.45, 39.70) and (9.45, 65.10), next to the synapses. vs is labelled on a routed vs wire.

## Keep-outs (comment layer; nothing placed or routed inside)

The synapses (`syn_in` ×2) and the stim-B steering (`bsteer`) are now inside the cell (rows in the d1/d2 regions and top left); only the trims remain as keep-outs.

| Name | Box | Area | For |
|---|---|---|---|
| TRIM1_KEEPOUT | 25.6–47.4 × 29.4–37.2 | 170 µm² | `trim_gap4w` (cells/dendrite/dtrim.spice) for d1, nibble 7. Pins inside: `la1`, `dl1` (Metal3 jumper ends, labelled) and `ta0..3` (Metal3 line ends at y 33.6); vbn_leak/vdd/vss nearby. |
| TRIM2_KEEPOUT + TRIM2b_KEEPOUT | 35.6–47.4 × 92.0–102.8 and 11.0–35.6 × 98.2–102.8 | 127 + 113 µm² | `trim_gap4w` for d2, nibble 8. Pins: `la2`, `dl2`, `tb0..3` (y 100.6). |

The trims are in the schematic wrapper `dend_d1t` but **not yet drawn**: 18 devices each (10 ladder nfets W 0.5, L 0.6–3; 4 nfet + 4 pfet switches, the pfets need n-well). They must be laid out into the keep-outs (or the top level) before tape-out.

## Status (2026-11-18, rebuilt with synapses, bsteer, hold routing)

| Check | Result |
|---|---|
| magic DRC `drc(full)` | 0 |
| KLayout gf180mcu (variant D, flat, all decks except density, antenna included) | 0 |
| netgen LVS | Circuits match uniquely (169 devices, 119 nets) |
| PEX Cfb (spk–vs) | 8.11 fF |
| Wiring C | vs 24.5 fF, d1 25.6 fF, d2 14.7 fF |
| Post-layout synapse test (typical 27, `tb_synapse.py typical 27 pex`) | Clustered: plateau + 16 spikes from N = 3 per input (schematic: N = 2). Distributed: nothing up to N = 4. |

Fixes in this rebuild:
- `stb` and `d1_bsel` Metal3 drops moved from the d2 detector row (y 74) to y 93, next to `bsteer`. The old drops blocked region 2, which never converged.
- The vdd labels of the two local (synapse) well rails were placed at x = 0 on the vss ring, which shorted vdd to vss in extraction. They are now dropped.
- The synapse-well taps stop 0.5 µm short of the well edge, which fixes an NP.1 notch against the timer cap.
- `PATCHES` in `dendgen.py`: two hand bridges for diagonal same-net corner gaps (hold M1, XS.XD.pb M2), each spacing-checked. They belong to the current route cache, so re-check them after any re-route.
- `short_check.py` / `short_path.py`: shape-level net-touch check and a GDS vdd–vss short tracer.
