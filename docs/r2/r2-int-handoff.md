# R2 integration handoff (MIL-362, branch `r2-int`, worktree /home/basil/tt-m3/r2int)

Base: `r2-b1-pack` 757deee (full chip green at 702a24c) + merge of `r2-c1-spk` f8c57aa (= 03e57fc; C1 RTL, pin freeze,
harden configs). `main` = fdcf2ad is the fallback and is not touched. Nothing is pushed or merged into a shared branch.

## Branches / worktrees
- `r2-int` (/home/basil/tt-m3/r2int): top level (lead).
- `r2-e2` (/home/basil/tt-m3/r2e2): E2 leakage cell `e2_leak` (sub-agent).
- `r2-e1` (/home/basil/tt-m3/r2e1): E1 fixed-bias S twin `e1_fb` (sub-agent).
- `r2-doc` (/home/basil/tt-m3/r2doc): cocotb GRP_EN / R2-address tests + docs/info.md (sub-agent).
- Rules for sub-agents: /home/basil/tt-m3/BRIEF_R2.md. Local Docker Desktop is down (2026-11-25), so all EDA runs on the
  VM queue (`vmrun.sh` / `vmwait.sh`); host KLayout Python: `PYTHONPATH=/tmp/b1r_kl ~/.venvs/audvec/bin/python`.

## Step 1: C1 variant a (41422c2)
- `macros/neuron_ctrl/*` = `c1spk_results_c1spk_a` (r2-c1-spk tree, untracked there): 166 × 166, rev E pins + 12 W pins
  (pincheck "OK: only additions"), utilization 0.934, setup +0.16 ns (ss/125 °C), hold +0.083 ns, DRC/LVS/antenna 0.
  GDS sha256 8f51a428….

## Step 1/2: top-level wiring + bay column (eb54d5a)
- **Bay column** (`fp.BAY`, x 80–108 from y 13, bottom → top):
  - by0 = S4 (cslot_ah), spk_in[16], SEL 16;
  - by1 = F4 (cslot_ah_f), spk_in[17], SEL 17;
  - by2 = E1 slot, spk_in[18], SEL 18. It is a plain cslot_ah until `e1_fb` (28 × 34.29) lands; that is the fallback
    if E1 is dropped.
- **Channel** x 108–129 (RESERVED RW removed).
- **Bay probe:** column `en` = `g_bay` = OR3(probe_sel_bay[2:0]) (bay glue row: or3_1 at (119.5, 58) over the x 121 /
  123.6 stripes), `rsel` = probe_sel_bay[k]. R1 pad enable `en_b` glue: NOR3 → NOR4 (+ g_bay).
- **Bay sub/sub_b:** `sub_b` is tied to the cell's vdd column (via2 in the band) and `sub` is left open. S/F have no
  PROBE_SUB = 1 tap, and no route was found for probe_sub / probe_sub_b into the bay. So on the bay any PROBE_SUB ≠ 3
  reads vm.
- **geom.bay():**
  - per cell, a Metal3 band (tracks 0–4 rt_out / rsel, 7 spk, 8 grp_en for E1) exits east (Metal2 stubs, 0.7 pitch)
    to router terminals;
  - column lines get Metal2 terminals at the stack top;
  - power: VSS Metal1 rails at the stack bottom and top → x 124.4 stack; the vdd column goes down to a Metal3 line at
    y 12.2 → x 121.8 via3.
- **Spare spk_in[19..23] tied low by `geom.ties()`:** via2/via1 per pin onto a Metal1 riser along the macro W edge
  (x 169.65), plus a Metal1 jumper onto AdEx's east vss ring. These pins are not routed: the AdEx/macro corner has no
  room for 5 escapes. Config `GEOM_TIES`; the netlist puts them on VGND.
- **Routing** (host route.py; new mode `route.py extend <nets>` keeps every old wire and adds only the branches to new
  terminals):
  - rerouted, all digital (AdEx/macro corner, glue): g_any, g_nsel, g_ns0/1, en_b, probe_sel_adex/_d1,
    probe_sub_raw[0/1], d1_sel2, spk_in[3], rt_out[1], en_c0–3, cfg_out[6/39/40/41/42/63];
  - new: spk_in[16–18], probe_sel_bay[0–2], g_bay;
  - extended into the bay: vbn_leak vbn_ref vbp_syn vbp_st vbn_prb el vsrc vreset abus rt_out[0/2/3].
  - Order matters in the corner: AdEx-pin nets (probe_sel_adex, spk_in[3], rt_out[1]) first, then the 6 macro W-bottom
    nets, then probe_sub_raw[0/1], then the rest.
  - Result: `route.py check` 0 illegal; `conncheck.py` 200 tasks, 0 disconnected.
  - Route backups: /tmp/r2int_routes_*.json (not kept).
- **VM:** `r2int/top1` = `layout/top/vm_r2.sh` (assembly, LVS, KLayout/antenna, magic, TT precheck). Fetch with
  `cd /home/basil/tt-m3/r2int && bash /home/basil/tt-m3/vmwait.sh r2int top1`; logs go to layout/top/work/vmr2/.

## Next
1. Fetch top1, fix any DRC/LVS, then the PEX regression (B1 DC + probe benches vs 702a24c/fdcf2ad, ≤ 0.5 mV).
2. E2 (r2-e2) into RT strip x 64–120 above row 3: en_a = en_c2, en_b = en_c3, rsel = probe_rsel[3], sub = probe_sub,
   grp_en = cfg_out[0]. Shrink RESERVED RT.
3. E1 (r2-e1) into by2 (28 × 34.29; grp_en = cfg_out[1] on band track 8). Column-top terminals move up 4.87 µm, so
   re-extend the 10 column nets.
4. Merge r2-doc; full-chip PEX benches (S4/F4 firing, E1 f–I, E2 droop, ua[1] probe of the new addresses, bias-line
   settling at S = 10); Nov 28 checkpoint comment.

## Status 2026-11-25 ~01:20 UTC: integration chip green (19e5af2)
- **VM r2int/top3:** LVS match uniquely, KLayout 0, antenna 0, magic 0, TT precheck pass. GDS sha256 6c6c590d….
- **Fixes on the way:**
  - top1 (eb54d5a): VDPWR/VGND/uo_out[6] short. The tile stripes sat on rev E strap x; variant a's straps are 3.36 µm
    west. `fp.MACRO_STRAPS` now comes from the new LEF.
  - R1 vdd now hooks east to x 345: the pair-2 VDPWR stripe lies over the ua[1] strap.
  - Tie stubs = `route.edge_stub`, and the tie vias moved 0.85 µm off the macro.
  - Bay exit terminals are now only the on-grid column (M2.1 slivers).
  - top2 (4e3d117): antenna ANT.16_ii_ANT.4 on probe_sub. Variant a reaches the probe_sub driver through Metal4, so at
    the Metal3 stage the row bands + vr-tap gates had no diffusion. Fix: 2 × antenna cells (gant0/1, tie-row west
    end, Metal2 from the probe_sub join line).
- **Merged r2-doc** (cocotb 16/16 incl. `test_r2_grp_en_and_addresses`, lint OK, docs/info.md R2 section). E2
  addresses: node A = SEL 11 SUB 1 (PROBE 0x5B), node B = SEL 15 SUB 1 (0x5F).
- **Running:**
  - `r2-pex` (/home/basil/tt-m3/r2pex): full-chip PEX regression + bay benches (sub-agent, cap ~8 VM-h).
  - `r2-e2` / `r2-e1` cell designs.

## Status 2026-11-25 ~03:10 UTC: R2 content chip green (988c8d8)
- **VM r2int/top6:** LVS match uniquely, KLayout 0, antenna 0, magic 0, TT precheck pass. GDS sha256 b15b89f5….
- **E2** (r2-e2 rev B 4c5650c, `e2_leak` 30.83 × 11.8):
  - placed at (72, 304) above array columns 2–3. RESERVED RT dropped; CH_TOP_A trimmed to y ≥ 316.
  - taps: node A = SEL 11 SUB 1, node B = SEL 15 SUB 1; GRP_EN[0] charge, GRP_EN[2] node-B mid clamp (spare bit;
    deviation, see the checkpoint).
  - PEX: with vreset held, A = B = junction floor (tt −3.3 µV/s, ff/85 −9 mV/s). With vreset stepped to 0 V, B
    (clamp off) droops 1.2–1.3× slower than A.
- **E1** (r2-e1 2648516, `ce1_fb` 28 × 34.29) in bay slot by2, grp_en = GRP_EN[1] (band track 8).
  - PEX S = 100: τ 110 / 98 / 147 µs, t_ref 18 / 8 / 35 µs, gap 79 / 69 / 97 mV (tt / ss / ff).
  - Schematic MC 100: τ σ 9.6 %, gap σ 19 mV.
  - Spec deviations for approval: vsrc is a local diode (not vss); the detector has a second diode rail; a few
    devices are drawn 1/2.
- **Routing notes:**
  - `route.py extend` seeds are shrunk to centre-line nodes (corner slivers).
  - After a top-cell height change, clip the column-net branches out of the cell, then re-extend.
  - `cfg_out[1]` must route before `cfg_out[67]`, [0] and [2]; `cfg_out[67]` needs `ROUTE_MARGIN=250`.
  - /tmp/reach.py: BFS reachability per terminal group, which finds the trapped end of a "no path" net.
- **Next:** the final PEX on 988c8d8 (r2-pex agent), the Nov 28 checkpoint, and the user/Chief approvals (E1
  deviations, GRP_EN[2]); push or merge only after approval.

## Status 2026-11-26 ~00:55 UTC: after the overnight shutdown
- **What happened to `r2pex/final`** (PEX regression on 988c8d8, started 03:50Z Nov 25): no done marker. The VM was
  stopped externally at 06:31Z during the shutdown while the job was still running. No on-VM self-stop watcher had
  been armed; jobwrap's own idle stop did not fire (queue marker + keep-alive still live). Not a jobwrap bug.
- **Fetched** (VM up ~1 min, 00:48–00:49Z) into /home/basil/tt-m3/r2pex/sim/results/ (gitignored, local disk;
  tarball /tmp/r2pex_final_partial.tgz). Finished on 988c8d8 before the kill:
  - bay_fire tt/27: S4 by0 94.529 kHz and F4 by1 49.843 kHz = array cells to 0.00 % → PASS.
  - bias_step_S10 (with bay): worst line to 1 % vbp_st 3.33 ms, vbp_syn 2.94 ms, vbn_leak 2.70 ms; vreset 12 µs.
    The `_nobay` comparison was the job that got killed.
  - bias_spk_off (+nobay), bias_dc_S1000 (+nobay), s10k (+nobay): finished; compare against nobay is still to do.
  - e1short (full-chip E1, tt/27, S = 100): parked vm 0.000 mV with GRP_EN[1] = 0; EL 1.4135 V (block 1.407);
    rate 10.16 / 18.79 kHz for A / A+B (block +10.4 / +10.6 %). "Vth − EL 168 mV" is the transient vm peak
    (spike overshoot), not the DC trip point that the block 78.6 mV uses, so it is not comparable yet. To do: a DC
    trip sweep on the full chip.
  - **E2 open issue:** full-chip droop at tt/27 with vreset held is −58 mV/s on both na and nb (block PEX: µV/s at
    tt, −9 mV/s at ff/85). gear/gmin/tmax/norshunt variants give the same result, so it is not a simulator option.
    The e2_leakchk per-element listing gives a uniform 12.86 fA per element (270 fA total), which looks like an
    artifact of the check itself. Next: find the real DC path out of na on the full netlist (the X7497
    s01.vreset.t9/e2.grp_en switch and the naf0 gate-cap device are the first suspects). Diag files are in
    sim/results/r2final_diag/.
- **Resumed:** `r2pex/final2` = the same vm_pex.sh without FORCE (it skips finished benches), submitted 00:50Z, cap 300 min.
  It runs bias_step_S10_nobay, probe_step, bay_probe, kick, gndchk, coupling, pgrid and bias_dc_S100 on 988c8d8.
  The VM self-stops 10 min after the queue empties. Fetch: `cd /home/basil/tt-m3/r2pex && bash /home/basil/tt-m3/vmwait.sh r2pex final2 5`.
- **Next:** fetch final2 → ≤ 0.5 mV regression table vs 702a24c; E2 droop root cause; E1 full-chip DC gap; Nov 28
  checkpoint comment; approvals (E1 deviations, GRP_EN[2]).
- **02:20Z update:**
  - final2 has finished bias_step_S10_nobay, bay_probe and probe_step on 988c8d8, and is running the full r2blk_e1_typ27
    (130 min cap, from 01:11Z).
  - Found that kick, icur_pgrid, gndchk, coupling, bias_dc_S100 and bias_dc_S100_r2c22 were marked done from the
    **19e5af2 (pre-E1/E2) batch**. `vm_pex.sh` lines 50–52 re-create `.ok` files from any rc=0 line in
    `batch/summary_pex.txt`, so those six never ran on 988c8d8.
  - `r2pex/final4` waits for final2, moves the summary aside (`summary_pex_pre_final4.txt`), deletes those six `.ok`
    files and reruns them. Fetch both: `vmwait.sh r2pex final2 5` and then `vmwait.sh r2pex final4 5`.
  - Queue hygiene: removed stale `q/r2pex_final` (from the killed overnight job), which would have blocked the self-stop
    forever. final3 was cancelled (rc 130 marker written).
  - **Lesson:** after an external VM kill, clear its `q/` marker; before a "resume", check that `.ok` timestamps are
    after the netlist extraction.
- **02:25Z, E2 droop root cause (local netlist diff, Sonnet sub-agent, no VM):** it is a testbench artifact.
  topbench.py hard-coded `rshunt=1e14`, which gives 12.9 fA per node = −59 mV/s on 217 fF. The na/nb layout matches
  the block. Fix: r2-pex bc6bd96. Notes: /home/basil/tt-m3/e2diag/findings.md (full-chip 988c8d8 netlists are also
  in /home/basil/tt-m3/e2diag/). Confirming job `r2pex/e2fix` is queued in the same boot as final2/final4; fetch with
  `vmwait.sh r2pex e2fix 5`.

## Status 2026-11-26 ~04:00 UTC: full-chip PEX regression on 988c8d8 complete
- Fetched final2 / final4 / e2fix into /home/basil/tt-m3/r2pex/sim/results/top. Table:
  `sim/results/top/r2_vs_m3_988c8d8.txt` (`r2_compare.py` vs M3 /home/basil/tt-m3/top3/sim/results/top).
- **PASS:**
  - bias DC S = 100: worst +0.004 mV (19e5af2 had +0.047);
  - probe step levels: 0.10 mV;
  - probe settling: 1754 vs 1759 ns;
  - bias_spk off rate ≤ 1 % (it failed on 19e5af2; the vsrc fix holds);
  - VGND rise: max 1.01 mV.
- **E2 confirmed (e2fix):**
  - tt/27 na −0.009 mV/s (rshunt 1e20); the 1e13 control gives −566 mV/s;
  - ff/85 nb −8.84 mV/s (block −9.0);
  - release steps na/nb −7.5 / −14.1 mV.
- **FAIL 1, kick edges** (vs M3; criterion 0.5 mV): worst −2.93 mV on D1 vs (PROBE D1 on). Single-line kicks:
  - D1 d1 ← cfg_out[41] is 6.42 mV vs 4.82 in M3. It was already 6.44 on 19e5af2, so it comes from C1 variant a
    routing, not E1/E2.
  - New: AdEx vm ← cfg_out[0] (GRP_EN[0]) 4.76 mV and H1 vm ← cfg_out[67] 3.54 mV.
  - E1 vm ← cfg_out[68] is E1's own stimulus.
  - Next: check whether these lines toggle in normal use (the cfg latch is static after configuration, so the kick
    happens once, at configuration time). Propose either accepting it as "config-time only" or shielding/re-routing
    cfg_out[0]/[41].
- **FAIL 2, s10k rates:** S2 +3.53 %, S3 +1.87 % (criterion 2 %). NOBAY gives S2 −0.5 %. Spike counts are identical
  (S2 8/8); the rate is (N−1)/(t_last − t_first), so one spike moving shifts it by about 3 %. The likely cause is by0/by1
  firing (peak I_VDD 1479 vs 1257 µA), which couples onto vreset (p-p 98.6 vs 78.5 mV), el and vbp_syn. To do: a
  longer window or a firing-off bay run to tell measurement quantisation from a real shift.
- **Bench artifact fixed:** in icur S10000, by2 (E1) showed I_vss 144 µA. The 1.5 V / 100 Ω vm precharge was fighting
  E1's GRP_EN = 0 park clamp (Spre23 → by2.vm → XR_XSW → el_l → X6467 → VGND). E1 draws 0.21 µA from VDD, which is
  correct. Fix: r2-pex eec6305, E1 excluded from the vm precharge. Rerun icur in the next boot.
- `r2blk_e1_typ27` (the full-length E1 bench) times out at 120 min on the full chip twice; drop it in favour of
  e1short (done) plus an E1 DC trip bench.
- **Next boot (single, self-stopping):** AH50 top run (assembly/LVS/DRC/precheck), E1 full-chip DC trip, icur S10000
  rerun, s10k with bay firing off, AH50 firing + bias_step_S10 with the AH50 load.
- **Next local step:** AH50 (`czslot_ah_50`) into bay by1 in place of F4 (fp.bay_cells, config.py:81/124); re-extend the
  column nets; `route.py check` / conncheck.

## Status 2026-11-26 ~04:30 UTC: bay = S4 / AH50B / E1 (user mix), one VM boot running
- **Layout (c91f33e):**
  - by1 = AH50B (`czslot_ah_50`, 34.29), so the stack is y 13–111 (98.0 of 103.8).
  - E1 is probe-only: its spk pin is open and spk_in[18] is tied low (SPK_TIED 18–23).
  - `route.py check` 0 illegal; conncheck 204 tasks, 0 disconnected.
  - Recipe, for the next height change:
    - drop spk_in[18] routes;
    - clip the column nets out of x 79.5–108.5, y 105–112.2 (`/tmp/clipbay.py`, see the commit message);
    - reroute **g_bay first** (extending the column nets first boxes its column-top terminal in);
    - extend cfg_out[1], probe_sel_bay[1/2], rt_out[0–3] and the column nets;
    - reroute spk_in[17];
    - bridge the 0.28 µm gaps left at the old band-terminal positions in the rt_out channel lines (`/tmp/bridge.py`).
- **Tests/docs (80aab43, Sonnet sub-agent):** regmap/test_ctrl AH50B; info.md/regmap.md AH50B, E1 probe-only,
  configuration-time kick note (Chief decided for the user 04:08Z: accept the cfg_out[41]/[0] kicks, no re-route).
  cocotb runs on the VM (no simulator locally).
- **Benches (r2-pex 8af6984 + 0fadc3d, Sonnet sub-agents):**
  - bay fire compares by1 AH50B against array AH50 s32;
  - E1 spikes come from vm resets (spk open);
  - new `r2blk e1trip` (full-chip E1 EL / Vth from a 1 mV/µs up/down vm ramp through 1 kΩ);
  - new `S10K_BAYQUIET=1` (by0/by1 vm held at EL);
  - s10k saves bay spikes;
  - r2blk_e1_typ27 replaced by r2blk_e1short_typ27.
- **VM boot (04:24Z):**
  - `r2int/top7`: vm_r2.sh + cocotb. Fetch: `cd r2int && vmwait.sh r2int top7 5`.
  - `r2pex/ah50`: FORCE re-extract + pex batch, skipping bias_spk_on, fullglue and r2blk_e2. Results in
    sim/results/top/vm_ah50. Fetch: `cd r2pex && vmwait.sh r2pex ah50 5`, then `r2_compare.py` vs top3.
