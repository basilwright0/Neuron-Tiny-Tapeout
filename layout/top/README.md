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
- **Column 3 `aux` = B1 `vth_cmp`** (the CMP double slot, since 2026-11-20); columns 0/2 `aux` from the τ cells;
  column 1 `aux` floats (no user; `config.FLOAT_AUX`).
- **τ-cell reference = `vbn_leak`** (`trim_tau4` rev B, 2026-11-20): both τ cells' `vbn_leak` pin is on B1's
  `vbn_leak` net (routed from the bias channel); their vss is the cell's p-tap ring (Metal1 stubs in `geom.py`). The
  old `vg`/`vsn` pins are gone, so the former open item (τ trims inert, no `trim_ref_n` in B1) is closed without a
  B1 change.
- **CMP double slot** (28 × 87, column 3, rows 0–1; the dummy slot is gone): map position (1,3), instance `s13` placed
  at slot (0,3). Its row pins (rt_out, sub/sub_b, spk_in[12], trim bits of nibble 6) sit on the row-0 band, its rsel
  on the row-1 band (`geom.array` picks each cell's pins per band from the label y).

## Status (2026-11-20, τ cells rev B)

| Block | Used as | Source |
|---|---|---|
| neuron_ctrl (macro rev E) | FINAL | `macros/neuron_ctrl/` |
| bias_b1 (rev C) | FINAL | `layout/bias/out/bias_b1.gds` |
| r1_ua1 / r1_corner | FINAL | `layout/readout/out/r1_ua1.gds` |
| dend_d1 (70 × 104) | FINAL | `layout/dendrite/out/dend_d1.gds` |
| adex_a1 (rev 3, 38 × 73) | FINAL | `layout/tier2/out/adex_a1.gds` |
| trim_tau4 ×2 | FINAL | `layout/slot/out/trim_tau4.gds` |
| 8 slot variants in use; slot_cmp_h is the 28 × 87 double slot with its gap trim (`CMP_TRIM = True`); slot_dummy unused | FINAL | `layout/slot/out/*.gds` |

Router: negotiated congestion converges in 12 iterations (2716 s, one core) with the CMP double slot and the τ cells'
`vbn_leak` hookup (2026-11-20). `work/routes.json` is kept in git so `build.sh noroute`
rebuilds without routing. Results of the last full run (every block final; no placeholders left):

| Check | Result |
|---|---|
| netgen LVS, full chip (blocks hierarchical, macro at gate level on the PDK std cells) | **Circuits match uniquely** |
| KLayout gf180mcu deck as precheck runs it (gf180mcuD, deep, all decks but density/antenna) | **0** |
| KLayout antenna deck | **0** |
| magic `drc(full)` on the assembled GDS | **0** |
| `scripts/precheck.sh` (TT precheck, 12 checks) | **all pass** |

Post-processing in `assemble.py` that keeps the GDS clean: terminal patches (off-grid pin vs on-grid wire; kept
inside the stub's extent where the wire runs on past the stub end, 2026-11-20),
same-net notch fill (closing 0.15 µm, kept 0.28 µm from other nets), removal of same-net vias whose cuts are
closer than 0.27 µm (L-shaped bridge, refuses to build if no clear L), and wire-aligned narrow pads where two
same-net via pads sit diagonally closer than 0.28 µm.
Router rules that the checks needed: no Metal4 below y 1.7 (TT analog-pin ring check), Metal2/3 in the bias
channel reserved for the analog column lines, trim tracks broken by a Metal4 jumper next to each trimmed slot
(antenna), the τ-cell gap above D1 closed to Metal2/3 through-routing.

### Switches
- `config.CMP_TRIM` (True since the CMP double slot: cfg_out[31..34], nibble 6, drive CMP's t0..t3 on the row-0
  band). False only with the trimless fallback `slot_cmp_h_notrim`; nibble 6 is then left unconnected.
- `config.LIB[...]["final"]`, `_SLOT_FINAL`: placeholder vs final per block.

### Known gaps (block owners)
- `ua0_stim_out` (B1) has no consumer: left open.
- `GRP_EN` (cfg_out[0..3]): no block has a group-enable input: left open.
- Column 1 `aux` floats (no user in that column since CMP moved to column 3).
- Macro: N-edge pins were placed with a wrong TT-pin pitch (14.56 instead of 7.28, `floorplan.py` PINS_TOP, now
  fixed), and the S-edge code order differs from B1's top-edge order; both are absorbed by routing today, but a
  `mkpins.py` re-run + re-harden would shorten those jogs. `probe_en_b` and decoded D1 tap selects would let the
  top-level glue row go.

## PEX spot checks (in progress)

> **RESUME HERE (paused 2026-11-20).** Nothing committed. No containers running.
>
> **Extraction (done).** `sim/tb/top/ext_rc.tcl` (magic, final GDS flattened, `extract do resistance` + `extresist all`,
> all coupling C) -> `work/pexr/top_rc_flat.spice`: R networks on VDPWR / VGND (every device terminal) and on the
> nets extresist keeps (vsrc, abus, el, vreset, stb, ...); all other nets are one node with all their C.
> `ext_c.tcl` -> `work/pex/top_c_flat.spice` (C only). Benches use the R+C netlist through `sim/tb/top/topnet.py`
> (macro replaced by ideal drivers behind 1.5 k; glue row kept as transistors) and `topbench.py` (ua[0] current,
> ua[1] 500 ohm + 2 pF + 200 pF, nominal codes, schematic-B1 "precondition" switches released at 0.5 us because the
> full-chip op never converges by Newton and ngspice's transient-op leaves the nA bias lines unsettled).
> Bugs found and fixed in the benches before any valid run: vth_ref code (now 37 at S = 100, 48 at S = 1000;
> AH trip calibrated to Vth), macro outputs driven on the right flat aliases (`topnet.resolve`; the first round had
> the probe lines floating, so all earlier probe / kick / icur results were discarded).
>
> **Results so far (typical 27 C):**
> - **Check 4, IR drop** (`pgrid.py`: KLayout trace + 0.2 um raster mesh, device-terminal currents from
>   `tb_top_icur.py`; PDN at the Metal4 stripe ends / top ends only / whole stripe): slots <= 0.01 mV, D1 / AdEx
>   < 0.01 mV, R1 with the pad driver on and IB_X2 (R1 544 uA) VDD 5.9 / 7.2 mV, VSS 4.2 / 4.9 mV mean / max
>   (top-ends-only PDN 12-16 mV). **B1: VSS rise 16 / 23 mV, VDD drop 12 / 18 mV in every PDN model -> FAIL.**
>   B1's power enters only at its east edge (0.8 um stripes x 342.6 / 345) and its receivers sit at the west end:
>   receiver ground is ~22 mV above the far mirrors' ground (VDD ~14 mV low), i.e. n-line mirror currents ~x1.9,
>   p-lines ~x1.5 versus the DAC (`sim/results/top/pgrid_*.txt`, "bias mirrors"). **Proposed fix (not applied):**
>   via3 drops from the Metal4 stripes that already cross B1 (x 121.0 VDPWR / 123.6 VGND) onto B1's Metal3 vdd / vss
>   under them; what-if (`pgrid.py ... b1vias_w`): offsets 0.1-0.8 mV (1.5 mV top-only PDN). Needs a DRC-clean pad
>   placement on B1's Metal3 (pieces at y 40-45 / 46.6-55.5 under those stripes) and build / drc / precheck.
>   Macro 1 mA into its straps moves the array rails by < 2 uV (B1 / R1 ~1 mV/mA with a top-only PDN).
> - **Check 3, static coupling** (`tb_top_coupling.py`, `sim/results/top/coupling.txt`, top-level-added C only):
>   **stim A (rt_out[0], row-band track 0) adds 550-680 aF to the vm of H1/H2/H3/P2/P3 and 176-328 aF to AH50/CMP
>   -> 8-10 mV estimated kick per edge (FAIL vs "a few mV")**; cause: those slots run vm on Metal3 up to y 31.5,
>   0.74 um below track 0. Fix options: Metal4 hop of track 0 over the vm segments (top level) or move the vm
>   Metal3 down / add a Metal3 shield in the slot. All other digital lines add <= 1.5 mV per neuron. Shared bias
>   lines see large digital C on high-impedance nodes (e.g. vbn_leak 31.8 fF of 293 fF, 3.2 fF from HOLD; vbp_syn
>   2.1 fF from stim A of 185 fF): tens of mV kicks estimated, to be confirmed by the transient.
> - **Check 2, DC** (`tb_top_bias.py dc`, `bias_dc_S*.txt`): far end - driver end at S = 100 / 1000: el +0.16 mV,
>   vsrc <= 0.45 mV, vreset <= 0.05 mV, all other lines are single nodes (0 by construction) -> << 1 LSB from wiring;
>   the real DC error is the B1 rail offset above. Code-step settling (`bias_step_S1000.txt`) is preliminary: that
>   run wrapped r1 (+4 codes from 30); 0.5 LSB settling at S = 1000 was ~15 us (vbn_leak), 29 us (vbn_ref), 7 us
>   (vbp_syn), 35 us (vbn_ax), x10 at S = 100. Rerun with -4 codes was stopped.
>
> **Not yet run validly:** check 1 probe chain (`tb_top_probe.py dc|step [corner T]`, incl. ss 0), check 3 transient
> (`tb_top_kick.py`), check 2 spiking neighbours (`tb_top_bias.py spk on|off`), `tb_top_bias.py step 1000` (-4
> codes), magic-network cross-check of the B1 ground rise (`tb_top_gndchk.py`), ss / 0 C IR drop
> (`tb_top_icur.py ss 0` then `pgrid.py`). Each full-chip transient takes ~10 min to its op plus 10-60 min;
> run at most ~5 at once (`scripts/eda.sh "nice -n 15 python3 sim/tb/top/<bench> ..."`).
> **Next step:** launch those runs, then write the final tables here and the firmware rules into `docs/info.md`;
> report the B1 via3 fix and the track-0 kick for approval before any layout change. Also still open:
> `sim/tb/tb_readout.py` PEX port map lacks `vth_ref` / `vsrc`.
>
> Benches: `sim/tb/top/` (topnet, topbench, ext_c.tcl, ext_rc.tcl, pgrid, tb_top_icur, tb_top_coupling,
> tb_top_bias, tb_top_kick, tb_top_probe, tb_top_gndchk). Outputs: `sim/results/top/` (git-ignored) and
> `layout/top/work/pex*/` (git-ignored).

## M2 full-chip PEX (layout B, 2026-11-22)

Typical 27 °C, S = 100, branch `m2-compact` @ 38d6092; M1 = post-stim-A-fix run (`sim/results/top/batch_fix`,
bias DC / probe from `vm_2026-11-20`). Compared by neuron name (M1 used another slot map); M1 AH800 -> M2 AH400.
Spiking-neighbour benches (`tb_top_bias.py spk on|off`): done, see the note at the end. Edge kicks in mV (20-60 ns after
the edge).

| Event | Tall cells H/P/CMP: M1 -> M2 | Compact cells S/F: M1 (tall) -> M2 | AH50 | AH800 -> AH400 | D1 vs / d2 | AdEx vm |
|---|---|---|---|---|---|---|
| HOLD on / off | +8.9..+10.3 / -10.2..-14.6 -> +7.5..+8.7 / -7.7..-12.4 | +3.8..+4.1 / -4.8..-5.5 -> +4.7..+8.6 / -5.3..-10.8 | +9.4/-12.1 -> **+14.4/-24.1** | +1.7/-2.2 -> +1.8/-2.3 | -43.0/-13.6 -> -26.0/**-19.1** | -4.1 -> -4.1 |
| PROBE_EN on, unselected same column | -2.5 -> **-5.9 (P2)** | -> **-5.7 (S1)** | +0.7 -> +0.8 | | | |
| SEL / SUB | H1 SEL +3.8 -> +2.1; SUB <= +2.0 | <= 1.5 | <= 0.9 | | 0 | SUB -7.3 -> -7.0 |
| LOAD (H1 trim / IDAC) | H1 +19.2 -> +19.2 (own trim); others <= 1.6 | 0 | 0 | 0 | 0 | 0 |
| stim A on / off | H1 +3.6/-7.7 -> +3.2/-6.5; H2 +6.9/-10.2 -> +4.1/-6.7; P2 +6.9/-10.2 -> +7.0/-9.6; CMP +7.2/-8.3 -> +4.7/-7.3 | S1 +3.2/-6.5 -> **+6.4/-9.3**; S3 +4.9/-8.3 -> +5.9/-8.8; F3 +2.9/-6.3 -> **+5.1/-9.2**; F1/F2 +7.0..7.3/-9.7..-10.6 | +10.5/-16.2 -> **+17.5/-19.7** | +0.6/-2.0 -> +2.3/-4.3 | vs +1.2/-1.2 -> **+3.6/-3.5** | +10.8/-14.9 -> +12.7/-17.1 |

**Stimulus-A decomposition** (M2; ramp = intended synapse charge, from step - edge of the off event; asym = on + off
edge = non-cancelling in-slot charge injection; net = vm change left by one 2 us pulse; checked against the M1 waveform).

| Neuron | on edge | top-level rt_out[0] (coupling.txt) | in-slot rest | ramp (syn charge) | asym | net per pulse |
|---|---|---|---|---|---|---|
| H1 / P3 / H2 / H3 | +3.2..+4.1 | 1.4 / 1.4 / <= 1.6 / <= 1.6 | 1.8..2.6 | 5.5..5.7 (~1.2 fC) | -2.6..-3.3 | +2.4..+2.9 |
| P2 | +7.0 | **3.7** (249 aF) | 3.3 | 5.4 | -2.6 | +2.8 |
| CMP | +4.7 | <= 2.5 | >= 2.2 | 5.7 | -2.6 | +3.1 |
| S1..S3, F1..F3 | +5.1..+7.3 | <= 1.0 | 4.4..6.9 | 5.8..6.3 | -2.6..-4.0 | +2.1..+3.7 |
| AH50 (50 fF + 9.9 fF) | +17.5 | 1.0 (19 aF) | 16.5 | 14.8 (~0.9 fC) | -2.2 | +12.6 |
| AH400 (471 fF) | +2.3 | 0.3 | 2.0 | 2.9 | -2.0 | +0.9 |
| D1 vs | +3.6 | **4.1** (284 aF, new) | ~0 | (stim A -> d1) | 0 | 0 |

- The kick bench's "stim A off" *step* (-12..-17 mV, AH50 -34.5) is mostly an artefact: its drift correction extends the
  synaptic ramp (~2.9 mV/us) past the off edge. The real state after a pulse is **+2..+4 mV** (AH50 +12.6): ramp minus
  ~3 mV of in-slot injection, i.e. ~50 % of the ramp at 2 us pulses.
- Shared lines: vbp_syn sits +13 mV during the pulse (M1 +15.6) -> I_w ~30 % low (nominal ~2 fC -> ~1.3 fC seen);
  el / vreset / vbn_ref +7..+9 mV recover in 2 us (< 0.2 mV on vm). They set the charge, not the edge.
- Verdict: the edge is **in-slot** (block level) except P2 (53 % top-level) and D1 vs (all top-level); H1/P3/H2/H3
  ~40 % top-level. A top-level-only fix can remove ~3 mV on P2 and D1 vs and ~1.4 mV on H/P; compact cells and AH50
  need a cell change. Compact cells kick ~2x the tall cells (stim A and HOLD) although their pin-pair `blk` Cc is only
  58-69 aF: likely sta/hold coupling into internal nodes (da, vl) - confirm with a block-level kick sim of `cslot_ah`.
- AH50 -16.2 -> -19.7 (off): node C 68.9 -> 59.9 fF (vm wiring 18.9 -> 9.9 fF in the compact cell) = +15 %, effective
  Cc 338 -> 358 aF = +6 %. On edge +66 % (220 -> 317 aF effective); HOLD off -12.1 -> -24.1 (253 -> 437 aF); top-level adds
  only 46 aF over all lines.

**Other changes.** Static top-added coupling, all lines together: array 8-35 mV -> 2.0-12.2 mV (AH50 34.6 -> 2.6), CMP
16.9 -> 15.6, D1 d1 32.2 -> 34.3. Worst single line CMP vm <- probe_sub_b 3.8 -> 5.4 mV (existed in M1); sub / sub_b
switch in antiphase (net 145 aF), measured SUB kick on CMP +0.9 -> +1.4 mV. Hold-window drift: H/P -36..-44 -> -66..-68
mV/ms, F3 -5.7 -> -10.9, AH50 -35 -> -46, CMP -115 -> -63. vbp_st at HOLD +-10 -> +-24 mV (back in 2.3 us); vbp_syn at
HOLD on +154 -> +178 mV. Bias DC unchanged (el +0.161, vreset <= +0.004, vsrc -0.039..-0.048 mV). Probe step worst
1969 ns (M1 1965) -> PASS, 31 ns margin.

**Spiking neighbours** (`tb_top_bias.py spk on|off`, S = 1000; victim H2 (s11) at 2x rheobase, H1 / P2 / H3 / S2 at 4x;
M1 = `vm_2026-11-20`, pre-stim-A-fix, other slot map). Neighbours on vs off: victim rate **+10.5 %** (50.38 -> 55.65 kHz,
ISI 19.85 -> 17.97 us, jitter +-0.2 -> +-26.7 ns); M1 -0.7 % (+-71 ns jitter). Shared-line ripple p-p with neighbours on,
M1 -> M2 (mV): vreset 79 -> 97, vsrc 86 -> 90, vbn_ref 23.9 -> 28.6, vbp_st 17.0 -> 19.5, el 11.1 -> 16.2, vbn_leak
9.3 -> 12.3, vbn_prb 5.4 -> 7.6, vbp_syn 14.1 -> 9.2. Mean shifts are <= 1.7 mV (vreset, vbn_ref; M1 <= 1.1). Quiet
neuron S1 vm p-p 5.4 mV (M1 s20 5.2). Open: the +10 % rate pull is new in M2 and its cause is not identified yet
(spike lines into s11 or the shared-line ripple). Find it before calling this acceptable.

**Stim-A reroute** (after the M2 PEX, not yet DRC-checked): the P2 coupling was stim A's west join line (Metal2, 0.4 um
off column 0); the D1 coupling was its router branch running Metal2 1.1 um along D1's west edge. The join line now sits
west of the other shared joins (`geom.JOIN_OUTER`, x 3.11) and its bottom end is a router terminal. Router keep-outs
(`route.NET_KO`) hold rt_out[0] Metal2/3 3 um off D1 and the array. VGND Metal2 shields fill the two vacated places so the
lines behind them see the same neighbours as before. `route.py reroute 'rt_out[0]'` keeps the run-4 east branch
(`route.KEEP`). Local RC PEX, rt_out[0] top-added: P2 vm 249 -> 96 aF (3.69 -> 1.42 mV, same as the other tall cells),
D1 vs 284 -> 81 aF (4.11 -> 1.17), D1 d1 143 -> 19, d2 96 -> 4, S1 42 -> 1, F2 67 -> 55. No victim / aggressor pair got
worse (largest change +0.0 aF). LVS matches.
