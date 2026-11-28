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
- **04:45Z, top7 on c91f33e/80aab43: GREEN.** LVS match uniquely, KLayout DRC 0, antenna 0, magic 0, TT precheck rc=0,
  gate ok; cocotb 16/16 (test/r2_ah50_tests.log). r2pex/ah50: build noroute LVS match, extraction done, node check
  0 missing, batch running since 04:28Z (results in r2pex sim/results/top, steps in vm_ah50/pex_steps.log).

## Status 2026-11-26 ~08:20 UTC: PEX on the AH50B bay (r2pex/ah50, c91f33e)
- Batch 04:28–07:50Z, 20 benches rc=0 (JOBS=2). Fetched with a 1 min resume; VM stopped. Table:
  r2pex `sim/results/top/r2_vs_m3_c91f33e.txt`.
- **PASS:**
  - bias DC S = 100: worst +0.004 mV;
  - probe step: 0.10 mV, 1754 ns;
  - bias_spk off ≤ 1 %;
  - s10k vs M3: worst −1.35 % (F2). The earlier +3.5 % is gone; normal / bayquiet / nobay S2 = 0.849 / 0.884 / 0.861,
    i.e. one-spike quantisation;
  - bay_fire: S4 = S1–S3 and AH50B = AH50 s32 (165.0 kHz), both ratio 1.0000;
  - bay_probe: 1719 ns, pad − tap ≤ 0.03 mV;
  - icur S10000: by2 (E1) 0 / 0 µA at GRP_EN = 0 (off at reset proven); by0 / by1 0.34 / 0.16 µA.
- **E1 full chip:**
  - e1trip: EL 1.420 V, Vth 1.509 V, gap 89.1 mV (block 1.407 / 1.486 / 78.6). +10.5 mV is within MC σ 19 mV and the
    corner range 69–97 → accept. The e1trip rheobase printout (−1.2e7 pA) is a bench bug.
  - e1short: EL 1.411 V; rate +11.6 / +7.5 % vs block.
- **bias_step S = 10:** worst vbp_st 3.44 ms with the bay (3.45 without). vbp_syn is 2.96 vs 2.76 ms (AH50B load).
- **FAIL, kick edges:** worst +5.19 mV on D1 vs at HOLD on (10.97 → 16.16 mV vs M3). HOLD = rt_out[2] is a run-time
  line, so the 04:08Z config-time waiver does not cover it. Suspect the rt_out[2] extend/bridge in the bay channel or
  new coupling near D1. **Next: debug in a fresh wake** (local netlist coupling check on rt_out[2] vs d1.vs first, then
  one fix + top + kick bench run in one boot at JOBS=3).
- The outer job rc=1 with 0 failed benches: vm_pex exit code; check with the next run.
- **08:45Z, kick D1 vs ← HOLD +5.19 mV: extraction artifact, not a layout change** (Sonnet sub-agent, local netlists
  in /home/basil/tt-m3/kickdiag, plus my spot check).
  - D1's chain-select node (`d1/a_318_18520#`, RC deck `a_1912_20076`) connects to d1.vs through X8892 (chain = 0) and
    has 388 aF to `d1/hold`, inside the D1 cell.
  - In 988c8d8 / M3, magic `extresist` gave this net resistors (988c8d8 RC deck: 4 R, 0 hold caps), which writes its C
    to VGND and drops the hold coupling. In c91f33e the net got no resistors (0 R, the hold cap is kept).
  - C-only couplings on d1.vs / d1.d1 / d1.d2 are identical between the two netlists; rt_out[2] only gained via pads
    32 µm east of D1. 388 aF × 3.3 V on ~270 fF ≈ 4.7 mV, matching the +5.2 mV.
  - So the physical kick is ~16 mV in every version, including M3 / main fdcf2ad.
  - **Proposal:** re-baseline the D1 vs HOLD kick reference to the c91f33e values (+16.2 / −24.3 mV) and document it
    in info.md (HOLD toggle → wait ≥ 1 τ on D1); no layout change.
  - Bench hygiene for later: make kick-victim nets get consistent resistance in ext_rc.tcl.
  - Optional: shield `d1/hold` from the chain-select node inside D1 (≈ 11 mV); not needed for the gate.

## Status 2026-11-26 ~10:30 UTC: checkpoint prep (Chief #43)
- **Decision #43 applied:** D1 vs ← HOLD kick re-baselined to c91f33e (+16.16 / −24.32 mV) in r2_compare.py
  (`KICK_REBASE`, r2-pex 0f4025f); info.md firmware rule "after HOLD toggles wait ≥ 1 τ before reading D1" (5b98daf).
- **e1trip fix (0f4025f):** Vth was read on the spike upstroke through the 1 kΩ force R. Re-processed from the saved
  data: **EL 1.4197 V, Vth 1.4960 V, gap 76.3 mV** (block 78.6 → PASS; the earlier "89 mV" was wrong). Rheobase
  344 pA vs block 156 pA, still to understand (cell current peaks near 1.489 V before takeoff).
- **vm_pex.sh exit code (0f4025f):** the trailing `[ -n "$1" ] && selfstop` returned 1 when no VM id was given. It
  now exits 0 only if the batch reports 0 failed.
- **Kick edges after the re-baseline:** FAIL, worst −2.66 mV (AdEx vm at HOLD off; HOLD on +2.30). The kick compare
  has failed by 2–3 mV in every R2 version (19e5af2 +2.95 D1 vs PROBE off, 988c8d8 −2.93 D1 vs PROBE on, c91f33e
  −2.66 AdEx HOLD off). This is a criterion question: the description's 0.5 mV rule covers the probe/bias benches,
  which all pass. Asked Chief.
- **Option D facts** (CH_ROW x 120.5–169.5, y 213.5–317):
  - a cslot + czslot stack (28 × 63.7 µm) fits rows 2–3 at x 120–148, leaving a ~21 µm channel to the macro;
  - 49 routed nets cross that strip and would need re-routing;
  - the macro already has spk_in[22/23] and probe_en_c4 pins (no re-harden);
  - estimate 2–3 layout sessions + 1–2 VM boots; risk medium-high.
  - **Recommendation: no option D for Dec 7** (keep 22–23 tied as documented reserve).

## Item 1 (MIL-103 01:15Z plan), 2026-11-27 ~01:50Z: AdEx vm ← HOLD kick (+2.30 / −2.66 mV) = REAL routing change
- Sonnet sub-agent (local netlists; notes /home/basil/tt-m3/kickdiag/notes/adex_hold.txt) + my check of routes.json:
  - **93e4490** (E1 into by2, the cfg_out[0/1/2/67] reroute) put **rt_out[2] (HOLD) on Metal4
    [138.35, 9.84, 138.63, 235.1]**, crossing AdEx (129.08–167.08 × 140–213) over its west half (vm / vw / vbp_w).
  - The same commit put cfg_out[0] on Metal4 at x 155.6 (y 124.8–217) and an rt_out[3] (MRESET) jog at
    x 165.4–167.1 over AdEx. In 19e5af2 none of them crossed AdEx, and the AdEx/HOLD kick matched M3 (+7.69 / −8.99 mV).
  - Coupling HOLD ↔ ax.vm: 286 aF (M3 / 19e5af2) → 457 aF (988c8d8 / c91f33e); ΔC 171 aF × 3.3 V / ~270 fF ≈ 2.1 mV,
    matching the observed miss. vbp_w +228 aF. Not an extresist artifact: lumped caps, C-only = RC.
  - The 988c8d8 "AdEx vm ← cfg_out[0] 4.76 mV" and MRESET +1.4 mV come from the same reroute.
- **Proposed fix (folds into item 3's branch and boot):** a router keep-out over AdEx on Metal4 (x 129.0–167.1,
  y 140–213) for the run-time / digital nets rt_out[0..3] and cfg_out[0..2], then reroute rt_out[2], rt_out[3] and
  cfg_out[0] around it (e.g. the east band at x ≥ 167.5 as in 19e5af2, or the CH_NAE lines x 120.5–128.5).
  Expected: AdEx/HOLD back to ≈ M3, and the cfg_out[0] → AdEx kick reduced too. Verify in the item 3 boot (top + kick).

## Item 2, 2026-11-27 ~02:20Z: E1 rheobase 344 vs 156 pA = bench artifact
- Sonnet sub-agent (notes /home/basil/tt-m3/kickdiag/notes/e1_rheo.txt) plus my recheck on the saved
  r2blk_e1trip_typical_27.dat.
- Below 1.478 V the full-chip E1 current is a straight 2.49 nS leak line (residual ≤ 8 pA). Just below Vth, a hump of
  up to 359 pA appears: about 2.5 fC of detector first-stage feedback (~1 fF to vm × ~2.5 V swing), so at a 1 mV/µs
  ramp it reads as current. A DC sweep has no hump.
- Leak-line extrapolation to Vth − 1 mV gives **192 pA**, and the raw value reproduces at 344 pA. The +23 % vs the
  block's 156 pA is consistent with full-chip vbp_st 2.4091 V vs the block bench's 2.4165 V (7.4 mV more gate drive
  → +10–20 % currents, also EL +13 mV, rate +11 %).
- Extraction: by2.vm has the same 9 device terminals as the block, no extra DC path, coupling within 1 fF. No fix needed.
- Bench: r2-pex 780c85e prints a DC estimate plus the raw value. info.md: full-chip expected values plus the
  quasi-static measurement note.

## Item 3, 2026-11-27 ~02:40Z: branch `r2-shield` (worktree /home/basil/tt-m3/r2shield, off r2-int ce5830f)
- **AdEx keep-out (1e4659e):**
  - route.py `NET_KO` now takes a box. `ADEX_W` = Metal4 x 128–156.1, y 139–214 for rt_out[2] (HOLD) and cfg_out[2].
  - Both are rerouted off AdEx's west half (rt_out[2] 575 µm; cfg_out[2] 769 µm with ROUTE_MARGIN=250, routed after cfg_out[0]).
  - cfg_out[0] keeps its x 155.6 lane: it has no path out of the corner with the keep-out, and it's a config-time
    line (waived #40).
  - check 0 illegal; conncheck 204 / 0 disconnected.
  - Lesson: `extend` does not rejoin a net cut in the middle; use `reroute`.
- **cfg_out[41] shield dropped:** cfg_out[41] is D1's tb2 trim bit (it must land on D1), and its Metal4 trunk at
  x 47.6 over D1 is identical in M3 fdcf2ad. It is config-time and waived (#40).
- **D1 HOLD shield (in-cell):** deferred until the AdEx kick result is in.
- **r2-pex merged in (3a53a63).**
- **Boot `r2shield/top1` (02:36Z):** vm_r2.sh, then PEX (FORCE) with only kick / coupling / probe_step / bias_dc_S100(+r2c22) /
  gndchk at JOBS=3. Fetch: `cd r2shield && vmwait.sh r2shield top1 5`, then
  `r2_compare.py /home/basil/tt-m3/top3/sim/results/top sim/results/top sim/results/top/r2_vs_m3_shield.txt`.
- **New worktree needs** untracked `layout/top/work/geo` and `.tools` copied from r2int, or the first vmrun sync fails
  (tar error).

## Item 3 result, 2026-11-27 ~04:10Z: r2-shield merged into r2-int (c5adf74)
- **r2shield/top2 (5c29bb0):** LVS unique, KLayout 0, antenna 0, magic 0, precheck rc 0, gate ok.
- **PEX (kick, coupling, probe_step, bias_dc, gndchk):**
  - AdEx vm ← HOLD +7.66 / −8.90 mV (M3 +7.71 / −8.91; c91f33e +10.01 / −11.57);
  - none of 270 kick edges worse than c91f33e by > 0.5 mV;
  - coupling AdEx vm 26.40 → 23.99 mV and vw 10.96 → 9.46 mV, others unchanged;
  - bias DC +0.004 mV; probe 0.10 mV / 1754 ns.
- **D1 vs ← HOLD** is +16.14 / −24.32 mV (identical to c91f33e). top1's 10.99 mV was the same extresist net-selection
  flip (it moved with the cfg_out[2] route), so the #43 re-baseline stands.
- **MRESET edges:** +0.6–0.9 mV vs M3 on 11 victims. MRESET resets every membrane by design (excluded).
- **Shields:** cfg_out[41] dropped (route identical to M3, config-time); D1 HOLD shield not done (the kick equals the
  fallback, and it's an extraction effect).
- **Still to run on c5adf74 at the Dec 1–2 gate:** the full PEX batch (s10k, bias_spk, bay, e1, icur, bias_step…),
  plus cocotb; JOBS=3.
- **r2_compare follow-ups:** exclude MRESET edges in the kick verdict, and apply the ≤ 3 mV kick tolerance (#44), so
  the gate report reads PASS/FAIL directly.

## E3 (user request via MIL-452, 2026-11-27): geometry-set synaptic-weight cell; branch `r2-e3` (worktree /home/basil/tt-m3/r2e3, off r2-int e07673e)
- **Feasibility (Sonnet, local):**
  - The strip x 5.0–53.4, y 303.4–317.8 has no other nets' wire.
  - Metal4 stripes run inside it (VGND x 4–6, VDPWR x 50–51.6, VGND x 52.6–54.2), so the cell must be M1–M3 only, like e2gen. The cell top must be ≤ 317.8 (the uio_oe tie row is at 318.4).
  - Nearby nets: VGND 0.5 µm away, en_c0 6.8 µm (Metal3 y 296.3), en_c1 10.2 µm (it starts at x 61.5).
  - Further away: abus 24 µm, probe_rsel[3] 22, probe_sub 23, vbn_prb 41, vreset 43, rt_out[0] 79, rt_out[1] 94, vbp_syn 164.
  - **cfg_out[3] is not routed:** its macro pin is on the south edge at (193.5–194.1, 151.0), a long route with antenna risk (cf. cfg_out[2] ANT.16).
  - **Probe:** SEL 8 / 9 + SUB = 1 → PROBE 0x58 / 0x59 (en_c0 / en_c1 + probe_rsel[3] + probe_sub). F2 / F3 have no SUB = 1 tap, so these are free.
  - **e2gen.py** (r2e2/layout/e2) is a fixed topology; the E3 legs must be added by hand.
- **Risks:** the cfg_out[3] long route (antenna; add a diode or hop layers), and new rt_out[0/1] branches near the array top / E2 (kicks); check at integration.
- **E3 cell v1 (dc57bce, Sonnet sub-agent):**
  - Files: layout/e3/{e3gen.py, build.sh, build.tcl}; sim/tb/e3/{tb_e3.py, run_all.sh}.
  - `e3_syn` is 47.65 × 12.0 µm, M1–M3, 34 devices.
  - Synapse leg copied from cslot_ah: pMOS 2/L on vbp_syn, nMOS 0.5/0.28 pass on sta/stb, pMOS dump; the header is
    gated by gb = NOT grp_en. Unit L stretched 4 → 6.4 µm (about 4 nA at vbp_syn 2.58 V, i.e. ~200 mV in 10 µs).
  - Node A: 1 unit on sta + 3 units on stb. Node B: 1 unit on sta + one 6/6.4 on stb.
  - Reset nMOS 1/0.5 on gb.
  - VM job `r2e3/e3a` (≤ 120 min): build / DRC / LVS / PEX, schematic corners, PEX tt, MC 100; summary in sim/tb/e3/summary.md.
  - **Decisions:** keep the array switch topology (nMOS pass + pMOS dump). **TODO:** rerun the bench with
    vreset = 1.3 / 1.5 V (the chip value; v1 used 1.0 V), because headroom matters.
  - VM-h: e3a 0.06.
- **e3b (c41d6f8, submitted 18:14Z Nov 27, fetched 20:11Z under MIL-467): PASS, rc 0.** Summary in sim/tb/e3/results/summary.md.
  - **Physical checks:** Magic DRC 0; **KLayout DRC 2 × PP.8b (must fix before integration, because TT precheck runs KLayout)**; LVS match; PEX 255 C.
  - **PEX tt/27, vreset 1.3, vbp 2.58:** dV sta 223/215 mV and stb 646/666 mV give a ratio of 2.89/3.10 (na/nb). Iratio is 3.00/3.07 at every corner.
  - **dV ratio holds only in the linear window:**
    - at ff/85 the node saturates (~1.5 V), so the ratio is ~1.0;
    - at ss/0 and vbp ≥ 2.58, dV is ≤ 12 mV;
    - at vbp 2.50 tt it reaches the rail (ratio 1.1–1.3).
  - This is a bias and window issue, not a weight issue. vbp_syn needs per-corner trim, which is a doc item for info.md.
  - **grp_en=0:** leakage ≤ 1.5 pA, node deviation ≤ 14 mV (PEX vreset 1.5). PASS.
  - **MC 100 (0 failed):** ratio sd/mean 10.5% (na) and 11.1% (nb); min 1.43 (outlier); Iratio sd 3.2/3.8%; absolute dV sd ~58%, as expected for subthreshold vbp.
  - **VM-h:** about 0.22. The job ran 18:14:00–18:16:33Z, then the VM self-stopped after 10 idle minutes; the 0.85 in the first note was wrong. Add 0.01 for the fetch resume (stopped at 20:11:38Z).
- **e3c: PP.8b fix (MIL-467).** In e3gen.py the gap after XQA and after PH goes from 0.40 to 0.46 µm. That widens the two Pplus holes from 0.82 × 0.41 to 0.88 × 0.41, i.e. 0.361 µm² (≥ 0.35).
  - Device W/L and nets are unchanged, and the cell is still 47.65 × 12.0.
  - Local EDA is still down (no Docker; /tmp was wiped, so I re-extracted host KLayout from tt-m3/.renderdeps to /tmp/b1r_kl). The generator ran locally (rc 0), and the build ran as VM job `r2e3/e3c` (build.sh only).
  - **Result:** Magic DRC 0, **KLayout DRC 0**, LVS "Circuits match uniquely". Deliverables are in layout/e3/final.
  - VM-h about 0.22 (resumed 23:37:32Z, job about 3 min, then self-stop).
  - The benches were not rerun: the only change is a 0.06 µm x-shift, and the e3b PEX numbers stand. The full PEX re-check is in the gate run.
  - **E3 cell gate: PASS** (DRC/LVS clean; weight ratio 2.89–3.10 at PEX tt in the linear window; grp_en=0 reset rule OK).
  - **Next:** integrate into r2-int: placement in the strip x 5.0–53.4 / y 303.4–317.8, a cfg_out[3] route with an antenna diode, and probe 0x58/0x59.

## E3 integration, 2026-11-28 ~00:15Z (MIL-467): r2-e3 801477d (r2-int 702b523 merged in, 978b928)
- **Placement:** e3_syn at (5.7, 303.9), top 315.9. x 5.7 rather than 5.5: the vss stub at 5.5 was inside the spacing of the probe_sub Metal2 join at x 4.3.
- **Nets:**
  - vreset, abus, vbn_prb, vbp_syn;
  - en_a / en_b = en_c0 / en_c1, rsel = probe_rsel[3], sub = probe_sub (PROBE 0x58 / 0x59);
  - sta / stb = rt_out[0] / [1];
  - grp_en = cfg_out[3] (GRP_EN[3], was spare; regmap updated).
- **Antenna diode `gant2`** on cfg_out[3]: tie row, east of tap0 (x 85.68). It is a routed terminal (landing pad on its I pin). West of gant0 is blocked by the probe_sub diode Metal2 line.
- **Routes:**
  - `extend` order: VGND VDPWR rt_out[0] en_c1 en_c0 rt_out[1] probe_rsel[3] probe_sub vreset abus vbn_prb vbp_syn (ROUTE_MARGIN=120). Routing power first is needed.
  - rt_out[0] used RT0_NA_KO=0.5 (env, default 3.0). The new branch is Metal2 x 3.0, y 141–284 along the array's west edge (4.75 µm off it), then Metal3 y 295.6 over the array top to the sta pin.
  - cfg_out[3] `reroute` ROUTE_MARGIN=250: Metal2 124 / Metal3 169 / Metal4 374 µm, 20 vias.
- **Local checks:** floorplan OK, prep OK, route.py check 0 illegal, conncheck 207 tasks 0 disconnected, assemble.py / plot.py OK. netlist.py needs PDK_ROOT, so it runs on the VM.
- **Pre-gate boot `r2e3/pg1` (submitted 00:17:18Z, VM resumed 00:16:41Z):**
  - vm_r2.sh (top / LVS / KLayout + antenna / magic / precheck);
  - cocotb (test/r2_e3_tests.log);
  - PEX at JOBS=3 for kick / coupling / probe_step / bias_dc_S100 / gndchk, into sim/results/top/vm_e3pg.
  - Fetch: `cd r2e3 && vmwait.sh r2e3 pg1 5`.
  - Compare: `python3 sim/tb/top/r2_compare.py /home/basil/tt-m3/top3/sim/results/top sim/results/top/vm_e3pg sim/results/top/r2_vs_m3_e3pg.txt` (check the arg form against item 3).
  - Watch the rt_out[0] / [1] edges, and S column 0 / 1 victims.
- **pg1 result (fetched 01:15Z): green.**
  - **Top level:** LVS unique, KLayout main 0, **antenna 0**, Magic 0, precheck rc 0, gate ok. cocotb 16 / 16.
  - **PEX (r2_compare vs top3 M3 / vs r2shield c5adf74):**
    - bias DC +0.004 mV;
    - probe 0.10 mV / 1750 ns;
    - **no array victim moved > 0.5 mV on any non-MRESET edge**, including stim A / B (rt_out[0] / [1]).
  - **Kick FAIL flag:** the only edges over tol are D1 vs ← HOLD +16.16 → +10.99 / −24.32 → −19.37. Both kicks got smaller. It is the same extraction net-selection flip as r2shield/top1 (10.99, #43), so it is not a regression.
  - **Coupling:** cfg_out[3] now loads AdEx vm 243 aF (3.44 mV) and vw 188 aF (2.85 mV). It is config-time (GRP_EN), so it falls under #40 and is below cfg_out[0]'s 4.76 mV.
    - Tried the ADEX_W keep-out: the reroute (784 µm) crossed D1 for 104 µm instead, which is worse, so it was reverted.
    - Bias lines: vbp_syn ← rt_out[0] 1.7 → 4.7 fF and vbn_prb ← cfg_out[3] 2.7 fF. Their effect on the membranes is inside the kick bench (no deltas).
  - **VM-h:** 0.63 (resume 00:16:41Z to self-stop 00:54:30Z), plus 0.01 for the fetch resume (the VM was stopped, so vmwait could not reach it).
