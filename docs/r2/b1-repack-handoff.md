# R2 B1 re-pack: handoff (MIL-344, branch `r2-b1-pack` off main `fdcf2ad`)

`main` is the submission candidate. Nothing here is merged or pushed.

## Step 1: measurement (fdcf2ad)
- **B1:** frame 242 × 114.5 at tile (103, 12), with notches N1 (R1, 40 × 42) and NB (28 × 40, empty).
  - Net area 25,030 µm²; the 19 leaves cover 16,875 µm² (67 %).
  - Column gaps are already tight (2.8–3.6 µm). The slack is in C4 + NB (local 131–159), above the rails
    (local 156–200 × 82–115), and in the east strips.
- **Tile free space** (M1–M3 empty, `area_free.py`; logs in untracked `work_b1r/`): 15,637 µm² (13.9 %), but
  fragmented.
  - Only NB (28 × 51.8, RESERVED RB) can take a 28-wide slot.
  - RW (22.8 × 104.6) is too narrow.
  - If top routing were ignored, CH_ROW (x 120–170, y 213–325) would be the next big area.
- **Neuron add requirements:**
  - All 16 `spk_in` channels and all 16 spike output pins (`uo_out`, `uio_out`) are used.
  - A full-peer neuron therefore needs a macro RTL change plus re-harden (`spk_in` width, output mux, SEL bit 4).
  - S/F/AH need no new B1 output and no config bits. H/P/CMP need trim nibbles: GRP_EN is one latched nibble that
    is currently unused.

## Step 2/3: options (detail in the Paperclip doc `b1-repack`)
- **A (chosen): west trim.**
  - C4 is removed: idac_p Xi0 goes to the top of C1, Xi1 goes over N1 rotated (above the rails), and the receivers
    are re-packed around Xi0 in C1.
  - The frame becomes 214 × 115 at tile (131, 12). B1's east group, R1/N1, the corridor, ua[0], vdd/vss and all
    digital pins keep their tile positions. The 10 analog outputs keep their local x.
  - Freed: one contiguous bay, tile x 80–129 × 12–116, which takes one column of 3 compact slots plus a ~20 µm
    channel.
- **B: in-place pocket.** Same leaf moves, west edge kept. This gives a 28 × ~106 pocket inside B1 with no side
  channel, and RW stays unusable.
- **C: also drop the corridor / compress the east group.** It cannot reach a second slot column with the current
  leaves.
- **D (tile, not B1):** a 5th array column at x 120–148 in rows 2–3 (CH_ROW), giving +2 compact slots. It is
  independent of B1.

## Step 4: implementation status
- `layout/bias/topgen.py`: `B1_R2=1` (the default on this branch) is the option A placement. `place_f` reports no
  overlaps: 214 × 115, net 22,930 µm².
- B1 full route is on the VM: jobs `r2b1s0/route` and `r2b1s1/route` (PYTHONHASHSEED 0 / 1), submitted 18:10 UTC
  2026-11-24. Results come back with `bash /home/basil/tt-m3/vmwait.sh r2b1s0 route` (into `layout/bias/out`,
  `bias_b1*.mag`).
- **Still to do after the route:**
  1. Pick the clean seed. Check magic DRC, KLayout DRC and LVS from the job logs. Adapt `chk_frame.py` (no NB,
     214 frame, pins = shifted `b1_pins_242.json`).
  2. Top level:
     - `floorplan.py`: B1_BOX (131, 12, 345, 126.5), notches = R1 only, RESERVED RW → bay (80, 12, 129, 116),
       drop RB; update `b1_rects()`.
     - `geom.py blocks_power`: the bx = 103 assert; the east vss/vdd hookup local x −28; re-derive the west power
       entry, because the x 121/123.6 stripes are no longer over B1 (use the 185.9/189.2 strap-pair-0 stripes and
       trace B1's Metal3 vdd/vss lines).
     - `route.py reroute` of the 10 analog outputs and any nets that `route.py check` flags.
  3. VM: `layout/top/vm_top3.sh` (LVS, KLayout/antenna, magic, TT precheck) plus B1 PEX DC with
     `sim/tb/bias/b1int_pex3.py` (new vs M3 PEX).
  4. Renders: `tools/render_labeled.py` from branch `renders` on the new GDS (before/after).

## Route log (2026-11-24, VM bx_s2uyuv76)
- DX=28, full corridor: stalled at 8 conflicts (iter 23); stopped. PYTHONHASHSEED does not change the run.
- DX=25 and DX=22 (Xi1 y 82.3), 35 iters × 2 schedules: FAILED 5 / 6 nets. Metal2 congestion over the rails
  (local y ~45 and ~51) under the Metal3-free corridor.
- Fix (d06302a): the top level has no Metal3 in the corridor (R1 feed-throughs are Metal4 at tile x 276–296), so
  B1's corridor keep-out is now only local y 42–43.5 (`B1_CORR_TOP`). `fp.B1_CORRIDOR` = (276, 54, 302, 55.5).
- Running: `r2b1e28/route` and `r2b1e25/route` (40 iters × 2 schedules + chk_frame → `out/r2_chk_frame.txt`).
  Fetch with `cd /home/basil/tt-m3/r2b1 && bash /home/basil/tt-m3/vmwait.sh r2b1e28 route`.
- If both fail: run a fast tier first (3–4 variants, ROUTE_QUICK=10, one schedule) and abort any variant whose
  conflict count isn't falling. Only then do a full route.
- Knobs: `B1_R2DX` (trim), `B1_XI1_Y`, `B1_CORR_TOP`, `ROUTE_ITERS` / `ROUTE_NSCHED`. Floorplan B1_BOX x0 must equal
  103 + DX (currently set for 28).

## Status 2026-11-24 ~20:50 UTC (handoff for the next session)
- **B1 verified once** (e28, 4cfd7f8): 214 × 114.5, magic 0, KLayout 0, LVS match, frame PASS 68/68.
- **PEX DC on e28** (`sim/tb/bias/out/r2/pex3/summary.txt`): new − fdcf2ad PEX ≤ 0.01 mV at every settled point
  (S = 1000/10000, mid/full codes, all 12 outputs). Unsettled code-0 / S = 100 points differ by ≤ 6.2 mV, inside
  their own 6–8 mV drift, as in b1int.
- **Top-level reroute** (local, host mode: `PYTHONPATH=/tmp/b1r_kl ~/.venvs/audvec/bin/python prep.py`, then
  `route.py check` / `route.py reroute <nets>`, about 40 s):
  - With outputs on B1's top edge, 3 of the 9 analog lines get no path: the Metal3 band at tile y 127–140 is full.
  - So (aaa8b79) the analog outputs now leave B1's **west edge**, local y 113.5 → 104.5 (vbn_leak first), into the
    empty corner tile x 101–131 × 116–126.5.
  - B1 re-route `r2b1f/route` was submitted 20:42. A duplicate started at 20:43 and was killed, so check
    vm_events for two "end r2b1f/route" lines and use the survivor's result.
  - Then repeat the frame check (it reads `out/b1_pins_r2.json`) and the B1 PEX (`r2_pex_vm.sh`; its result
    paths include `sim/tb/bias/out/r2`).
- **Next:**
  1. Fetch `r2b1f`; local prep + check + reroute (cfg_out[40/42/64/66] first, then the 9 analog nets:
     vbp_syn el vbn_leak vbp_st vbn_prb vbn_ref aux3 vbn_ax vbp_w).
  2. Commit `routes.json`, then `vmrun r2b1top2 build "bash layout/top/vm_r2.sh"`. Submit **once**: the
     first-use ssh error is printed, but the job still goes in.
  3. PEX again on the final B1.
  4. Renders: `tools/render_labeled.py` (now also draws fp.RESERVED free areas), host klayout.
  5. `b1-repack` Paperclip doc and the Nov 26 verdict.
- **C1 redesign** (branch `r2-c1-spk`, worktree `/home/basil/tt-m3/c1spk`, `docs/r2/c1-redesign-handoff.md`):
  - Step 2 is done (eeabade): N_SPK = 24, OUT_BANK @0x17 bit 0 (uo ↔ ch16–23), PROBE[7] = SEL[4]
    (bay k = 0–2, column 4 rows 2/3).
  - cocotb 15/15 and lint pass. Area +474 µm² (yosys); expected utilization about 96 %.
  - Step 3 = re-harden. Freeze all existing pin positions from the committed `pin_order.cfg` / `config_fp.json`
    and only add the new pins. Don't regenerate the others, because `mkpins` output already differs from the
    hardened macro.

## Status 2026-11-24 ~21:45 UTC
- **B1 final** (1049261): analog outputs on the west edge; VM r2b1f: route converged at iter 9; magic 0, KLayout 0,
  LVS match, frame PASS 68/68.
- **Top-level routes** (1049261; host `route.py`): r1_b0, v0_c0 and the 9 analog outputs rerouted. vbn_ax and
  vbn_ref keep their shipped D1 Metal4 escapes (`route.KEEP`). Working order: … then `vbn_prb vbp_st vbp_syn el`
  last. `route.py check` gives 0 illegal; conncheck: 193 tasks, 0 disconnected.
- **VM jobs submitted 21:38–21:40** (one each):
  - `r2b1top2/build`: full-chip LVS, DRC/antenna, precheck → `layout/top/work/vmr2/steps.log`.
  - `r2b1pex/pex2`: B1 PEX DC on the final B1 → `sim/tb/bias/out/r2/pex3/summary.txt`.
  - `c1spk/harden`: C1 re-harden (branch r2-c1-spk). E-edge pins are unconstrained, so check
    `c1spk_results/pin_diff_lef.txt`.
- **Fetch:** `cd /home/basil/tt-m3/r2b1 && bash /home/basil/tt-m3/vmwait.sh r2b1top2 build 2` (and
  `r2b1pex pex2`); for C1, `cd /home/basil/tt-m3/c1spk && bash /home/basil/tt-m3/vmwait.sh c1spk harden 2`.
  The VM self-stops, so resume it first if it is stopped and log the resume in vm.log.
- **Then:**
  - renders (`tools/render_labeled.py --gds gds/... --out docs/r2/renders`, host klayout
    `PYTHONPATH=/tmp/b1r_kl`);
  - the `b1-repack` doc and the Nov 26 verdict;
  - the daily report `tiny-tapeout-2026-11-24`;
  - VM-h on MIL-6.

## Status 2026-11-24 ~23:20 UTC
- **B1** (fe98f90, VM r2b1g):
  - Top pin row kept clear. Converged at iter 13; magic 0, KLayout 0, LVS match, frame PASS 68/68.
  - **PEX DC:** settled points ≤ 0.02 mV vs fdcf2ad. The max values (≤ 6 mV) are only on the unsettled S = 100 rows.
- **Top routes** (b417c67): only v0_c5 needed a reroute; check 0, conncheck 0 / 193.
  - geom power hookups now come from the B1 route cache.
  - The full-chip `r2b1top3/build` was submitted at 23:18.
- **C1** (r2-c1-spk 03e57fc): harden_a and harden_b both pass (DRC, LVS, antenna 0; pins: only 12 added, 0 moved).
  - **Chosen: a** (side margins 6 sites, density 90, keeps the input buffers): utilization 0.934, setup +0.16 ns ss/125C,
    hold +0.083 ns.
  - b has more setup slack (+1.70 ns) but drops the input buffers.
  - Next: copy a's LEF/GDS/netlist into macros/neuron_ctrl on the C1 branch, then the info.md docs (user approved
    OUT_BANK and SEL[4], 22:21).

## Status 2026-11-25 ~00:00 UTC: step 1 complete
- **Full chip verified** (702a24c, VM r2b1top5): LVS match, KLayout 0, antenna 0, magic 0, TT precheck passed.
  - GDS sha256 af1fbcb7….
- **Fixes on the way:**
  - stale `_stubs` after reroute: `reroute` now refreshes them (ecff004);
  - Metal3 Z-joint fill in `assemble.py` (9998b78).
- **Renders:** before/after in `docs/r2/renders/` (7050a4f).
- **Free space:** 15,637 → 17,663 µm²; largest rectangle 50.8 × 103.8 at x 80–131.
- **Report:** MIL-344 document `b1-repack`. Daily report MIL-2 `tiny-tapeout-2026-11-24`. VM-h booked on MIL-6 (≈ 4.75).
- **Next step (new task):**
  1. Integrate C1 variant a (r2-c1-spk 03e57fc, `rtl/librelane/c1spk_results_c1spk_a`) into `macros/neuron_ctrl`.
  2. Top-level config for the new spk_in/probe pins.
  3. Place the 3 bay neurons (one slot column at x ~80–108, channel x ~108–129); feed column lines from B1's west-edge outputs.
  4. Full-chip checks + PEX benches; `docs/info.md` for OUT_BANK and SEL[4].
