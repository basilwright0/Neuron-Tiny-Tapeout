# Timeline to tapeout (updated 2026-11-20)

**Shuttle:** TTGF26c closes **2026-12-07**. Chips are expected around 2027-05-12.

**Rule:** the work is split into three milestones. Each one ends with a complete, verified design pushed to GitHub with
green CI, and each is a valid submission on its own. A later milestone replaces the submitted design only once it
passes the same checks. If time runs out, the last finished milestone is submitted.

## Milestone overview

| Milestone | Plan phases | Target date | Result |
|---|---|---|---|
| **M1: baseline** | Phase 0 | ~Nov 23 | The current design, PEX-checked and fixed, pushed, CI green |
| **M2: compact + fast** | Phases 1a, 1b, 1c, 2 | ~Dec 1 | Compact neurons, array and blocks; 10000× support (levels 1–3) |
| **M3: new neurons** | Phases 3, 4, 5 | Dec 5 | Minimal neurons, GIF neuron, control block rev F |
| — | — | Dec 6–7 | Buffer for CI and submission (the user submits and pays) |

Each milestone ends with about 1–1.5 days of integration and verification:
- top-level assembly;
- full-chip LVS and DRC (KLayout, antenna, Magic);
- the PEX batch on a Boat VM (`sim/tb/top/run_batch.sh`, about 3 h of machine time);
- the local TT precheck;
- commit, push and the GitHub CI run.

## M1: Phase 0, baseline (~Nov 21–23)

- **PEX spot checks:**
  - probe chain (settling done; DC transfer re-run as ramps);
  - kicks, bias distribution, spiking-neighbour ripple;
  - IR drop at typical and ss / 0 °C.
- **Fixes:**
  - B1 supply: via3 drops from the Metal4 stripes at x 121.0 / 123.6 onto B1's Metal3 rails;
  - stimulus-A track kick, if the transient confirms it;
  - any firmware rules the results call for.
- **Verify, commit, push, CI green.**

## M2: Phases 1a, 1b, 1c and 2, compact and fast (~Nov 23 – Dec 1)

| Phase | Work |
|---|---|
| Generator (first) | Compact layout generator: shared diffusion, common well strips, row-based placement, and an automatic place-and-route search (placement scored by a trial route). Proven on the S slot first. |
| 1a | All slot variants compacted, with the 10000× level-2 changes (wider reset switch, refractory and synapse bias taps) built in |
| 1b | Compact array tile (row band, column lines, variable row heights), verified with tile-level PEX before the top level |
| 1c | 10000× levels 1–3: firmware rules, level-2 silicon, and level-3 non-scaling bias lines for the comparators, detectors and buffers. Gate: post-layout simulation of every neuron type at 10000× across corners at 27 °C plus ss / 0 °C. |
| 2 | B1 split into sub-blocks (reference/ESD, 5 current DACs, V-to-I + 3 resistor DACs, threshold DAC, buffers), carrying the level-3 lines. D1 and AdEx regenerated on the new generator. |

**Design rule:** the level-3 bias lines are **fixed, with no new DAC codes**. The control block's register map then
stays the same, and at most the macro is re-hardened for a new pin order (about half a day).

**Fallback:** if the compact S slot isn't clean and smaller after about 2 days, the milestone shrinks to B1 and 10000× on
the existing layouts.

Level 4 (wider leak OTA, 10000× at every corner) is not planned; it would make every neuron about 10 % larger.

## M3: Phases 3, 4 and 5, new neurons (~Dec 1–5)

| Phase | Work |
|---|---|
| 3 | Minimal neurons: no probe, no trim, fixed bias (fixed mirror ratios off the master), built on the compact generator |
| 4 | GIF neuron: comparator front end, spike-triggered adaptation current, adaptive threshold. Expected near AdEx size (~2–3k µm²). |
| 5 | Control block rev F (bank-switched spike outputs for the extra neurons, new probe addresses, re-harden, cocotb tests), then final integration |

The schematics for phases 3 and 4 are designed during M2, so M3 is mostly layout and integration. If M2 slips, M3 drops
the GIF or the minimal neurons, and M2 is submitted.

## Completed (as of 2026-11-20)

| Area | State |
|---|---|
| Planning, research, frozen design (`08`), TT Q&A (`07`), hardwiring protocol (`09`), speed study and 10000× roadmap | done |
| Control block rev E (166 × 166 µm), 14/14 cocotb tests | verified |
| B1 rev C (265 × 115 µm), R1 corner (40 × 40 µm) | verified |
| Neuron array: all slot variants on the fixed cells; CMP double slot with its gap trim; τ-trim rev B on `vbn_leak` | verified |
| D1 (70 × 104 µm), AdEx (38 × 73 µm) | verified |
| Full chip: LVS match, DRC 0 (KLayout, antenna, Magic), local precheck pass | commit `946cd68` |
| README, datasheet (`docs/info.md`), `info.yaml` (TT docs check passes), layout renders | done |

## Needs from the user
- Approve each push (pushing publishes the repository).
- Approve layout fixes that change the design (B1 vias, stimulus-A track).
- Submit and pay at the end (~€220 for 1×2 + 2 analog pins).

## Main risks
- **M2 schedule:** the generator rework is on the critical path for every M2 block.
- **M3 has no slack:** the GIF and control rev F are each several days of work.
- **Top-level re-integration** at each milestone: the first full-chip run after big block changes usually turns up
  connectivity issues. A day is budgeted per milestone.
- **Tool interruptions** (Docker, session restarts, usage limits): mitigated by commits at each milestone, RESUME notes
  and unattended batches on Boat.
