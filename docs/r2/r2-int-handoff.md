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
