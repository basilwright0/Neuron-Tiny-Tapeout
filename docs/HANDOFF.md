# Project handoff (2026-11-20)

The **Analog Neuron Test Bench** is a mixed-signal neuromorphic test chip for Tiny Tapeout **TTGF26c**: gf180mcuD,
3.3 V, analog 1 × 2 tile, 2 analog pins. The top module is `tt_um_basilwright0_analog_neurons`. **The shuttle closes
2026-12-07.**

The design is complete and verified at commit `946cd68`:
- full-chip LVS match;
- KLayout, antenna and Magic DRC all 0;
- local TT precheck passes.

It has **not been pushed** since `e301844`.

## 1. Start here

| Read | For |
|---|---|
| `README.md` | What the chip is, architecture, verification status, build commands |
| `docs/10 Timeline.md` | **The plan:** three submittable milestones (M1 baseline, M2 compact + fast, M3 new neurons) |
| `docs/08 Updated Plan.md` | The frozen design and its decisions (§1–12), plus the status log (§13) |
| `docs/info.md`, `docs/regmap.md` | Datasheet, pinout, register map, bring-up procedure, firmware rules |
| `layout/top/README.md` | Top-level assembly flow, block-swap procedure, open items, **PEX "RESUME HERE" note** at the end |
| Each `layout/<block>/README.md` and `cells/<block>/README.md` | Per-block flow, status and design notes |

## 2. Where things stand

**Milestone M1 (Phase 0), in progress:** the PEX spot checks on the full chip, then fixes, then push.

- **PEX batch on Boat VM `bx_pc3b73cf`** (name `pex-batch`, large, 8 vCPU):
  - **Finished, all rc = 0:** kicks; probe settling at typical and ss / 0 °C; bias code step at S = 1000;
    spiking-neighbour off; B1 ground cross-check; IR drop at ss / 0 °C.
  - **Killed (rc = 137):** the two probe DC sweeps. Full-chip DC sweeps don't converge.
  - **Replaced by a ramp batch** (started 21:03 UTC): 8 jobs of `tb_top_probe.py ramp <corner> <T> <tap>`.
  - **Still running then:** the spiking-neighbour on run (`tb_top_bias.py spk on`).
  - **Stopping:** the ramp batch waits for that run, packs everything and runs `boat stop self`. An auto-stop
    backstop is set for 2026-11-21 02:32 UTC.
  - **To get the results:**
    ```
    boat resume bx_pc3b73cf
    boat exec bx_pc3b73cf --timeout 30 -- cat /home/user/neuron/sim/results/top/batch/summary_full.txt
    boat exec bx_pc3b73cf --timeout 30 -- cat /home/user/neuron/sim/results/top/batch/summary_ramp.txt
    ```
    The packed archive is `/home/user/neuron/sim/results/top/batch/results_ramp.tgz`. Copy it back with `boat scp`;
    in Git Bash, set `MSYS_NO_PATHCONV=1` or the remote path is mangled. Stop the VM again afterwards.
  - Bench outputs land in `sim/results/top/*.txt`, with the logs in `sim/results/top/batch/`.
- **Found before the batch** (details in `layout/top/README.md`, PEX section):
  1. **B1 supply drop: FAIL.** B1's power enters only at its east edge; its receivers see about +22 mV ground and
     −14 mV VDD, so bias currents are 1.5–1.9× the DAC setting. **Proposed fix:** via3 drops from the Metal4 stripes
     that already cross B1 (x 121.0 VDPWR, 123.6 VGND) onto B1's Metal3 rails. It modelled at < 1 mV.
     **Needs the user's approval.**
  2. **Stimulus-A coupling: likely FAIL.** Row-band track 0 sits 0.74 µm above the vm wire in H, P, AH50 and CMP,
     an estimated 8–10 mV kick per edge. The kick transient (now finished) confirms or refutes it. **Fix options:**
     a Metal4 hop of track 0 over those slots, or move or shield vm in the slot. **Needs approval.**
  3. **Passing so far:** array, D1 and AdEx IR drop < 0.01 mV; R1 about 6 mV; bias-line DC error < 0.5 mV;
     macro switching noise negligible.
- **Next steps for M1:**
  1. Read all the results and write the tables into `layout/top/README.md`.
  2. Add firmware rules to `docs/info.md`.
  3. Get approval for the fixes, apply them, then run `build.sh`, `drc.sh` and `scripts/precheck.sh`, and re-run
     the affected PEX benches.
  4. Commit; push (with approval); get CI green.
- **Also open:** `sim/tb/tb_readout.py` PEX port map lacks `vth_ref` / `vsrc`.

**Uncommitted in the working tree:**
- `docs/10 Timeline.md` (milestone plan);
- `info.yaml` (pin labels, description, `clock_hz` 10 MHz);
- `layout/top/README.md` (PEX resume note);
- `scripts/eda.sh` (Linux-host support, for the Boat VM);
- `sim/tb/top/` (all full-chip PEX benches, `run_batch.sh`, `tb_top_probe.py` ramp mode);
- this file.

## 3. Milestones after M1 (see `docs/10 Timeline.md`)

- **M2 (~Dec 1):** a compact layout generator with automatic place-and-route search, proven on the S slot first.
  - Compact all slot variants, with the 10000× level-2 changes.
  - Compact array tile, with tile-level PEX.
  - 10000× levels 1–3, with **fixed** non-scaling bias lines (no new DAC codes, so no register-map change).
  - Split B1 into sub-blocks; regenerate D1 and AdEx.
  - Level 4 (10000× at every corner) is not planned.
- **M3 (Dec 5):** minimal neurons (no probe, trim or bias), a GIF neuron, control block rev F with bank-switched spike
  outputs, then final integration.
- **Each milestone ends submittable:** full LVS/DRC, the PEX batch, precheck, push, CI. If time runs out, submit the
  last finished one.

## 4. How to run things

All EDA tools run in `hpretl/iic-osic-tools:2026.08` (digest `sha256:3c371645…`) through `scripts/eda.sh "<cmd>"` from
the repository root:
- **Windows host:** Docker runs in WSL `Ubuntu-24.04`, so Docker Desktop must be running.
- **Linux host:** native Docker.

| Task | Command |
|---|---|
| Full chip: prepare, route, assemble, extract, LVS (~30–45 min) | `scripts/eda.sh "nice -n 15 bash layout/top/build.sh"` (`noroute` to reuse `work/routes.json`) |
| Full-chip DRC | `scripts/eda.sh "nice -n 15 bash layout/top/drc.sh"` |
| TT precheck | `scripts/eda.sh "bash scripts/precheck.sh"` |
| Control-block tests | `scripts/eda.sh "bash test/run_tests.sh"` (14/14) |
| Layout renders | `scripts/eda.sh "klayout -b -r scripts/render_layout.py"` |
| TT docs check | `python3 .tools/tt-support-tools/tt_tool.py --check-docs` (in the container; install `.tools/tt-support-tools/requirements.txt` first) |
| PEX batch | `bash sim/tb/top/run_batch.sh smoke\|full\|ramp`, with env `JOBS`, `STOP_SELF=1`, `WAIT_PATTERN` |

**Block swap:** deliver the block's GDS and LVS netlist, set `final=True` in `layout/top/config.py`, then re-run
`build.sh`, `drc.sh` and the precheck. Pins are read from the GDS labels.

**Boat:** the `boat` CLI is installed and signed in, both locally and inside Boat VMs.
- The $20 plan has about 365 VM-hours left this period; a large VM counts double.
- Push the repo with `boat push <id> . --to /home/user/neuron`. Git-ignored inputs (`layout/top/work`,
  `sim/results/top`) need a tarball and `boat scp`.
- `boat stop self` works from inside a VM (tested).
- A stopped test VM, `bx_h9sbz2jb`, can be deleted.

## 5. Standing rules

- **Commit and push only when the user asks.** Pushing publishes the repository publicly.
- **Spending money and the shuttle submission need the user's explicit approval.** The user submits and pays
  (~€220).
- **Report layout fixes that change the design before applying them,** unless they're trivial routing tweaks that
  keep LVS, DRC and the precheck clean.
- **Agents stop only containers they started.** Never relay or work around a denied permission for another agent.
- **Keep the user's personal details out of anything sent to outside services.**
- **The internal planning notes** (`docs/01–05`, `docs/Analog Neuron Tapeout Plan.md`) reference the user's other
  projects. The user chose to leave them in; they will become public with the repository.
- **Keep text files LF-only** (`.gitattributes` has `* text=auto eol=lf`). Windows checkouts have produced CRLF
  `.sh` files that bash rejects.

## 6. Known gotchas

- **Full-chip operating point doesn't converge by Newton.** PEX benches pre-set the slow bias lines and membranes
  through switches released at 0.5 µs (`topbench.chip(precond=True)`). Use transients and ramps, not `.dc` sweeps,
  on the full chip.
- **Probe select:** SEL 4 shows CMP and SEL 12 shows S2, because they swapped array positions after the macro was
  frozen. This is documented in `docs/info.md` and `docs/regmap.md`.
- **Firmware rules** are in `docs/info.md`: rewrite the config after enable, the three-step probe move, BIAS_EN = 0
  while changing codes, pulse MRESET after BIAS_EN, EL 1.5 V above S ≈ 300, leak current > 30 pA hot/fast, and more.
- **Post-layout neurons run at 0.8–0.9× schematic speed** (wiring capacitance). Per-die calibration absorbs it.
  D1 node capacitance was accepted at 237–272 fF (design 200 fF).
