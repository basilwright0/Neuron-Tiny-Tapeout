# Timeline to tapeout (status 2026-11-19)

**Shuttle:** TTGF26c closes **2026-12-07**; chips are expected ~2027-05-12.

| Gate | Date | Definition |
|---|---|---|
| G1 | Nov 15 | Core schematics simulated vs the reference model; readout settles | **done** |
| G2 | **Nov 22** | Every block DRC/LVS clean with measured area; final floorplan; 1×2 confirmed | in progress |
| G3 | **Nov 29** | **MVP submittable:** full-chip layout, full LVS, PEX spot checks, local precheck green, `docs/info.md`, GitHub repo + CI green | upcoming |
| G4 | Dec 5 | Final review and fixes; the user submits and pays (~€220 for 1×2 + 2 analog pins) | upcoming |
| — | Dec 6–7 | Buffer before the shuttle closes | |

## Completed

| Area | What | State |
|---|---|---|
| Planning | Conversation summary, reconciliation, research, design plan, frozen plan (`08`), TT Q&A (`07`), hardwiring experiment (`09`), speed limits + 10000× roadmap | docs |
| Simulation infrastructure | Python ↔ ngspice harness, reference models, testbenches | done |
| Control block rev E | Config latches, probe decode, bias codes, digital LIF; 14/14 tests; **166 × 166 µm**, v2 pin order | **verified** (DRC/LVS/antenna/timing clean) |
| Bias generator rev C | Fixed range per DAC (speed via ua[0]), V-to-I voltage path, ESD; **265 × 115 µm** notched frame | **verified** (DRC 0/0, LVS) |
| R1 corner | Pad driver (400 µA), Vreset buffer, `vsrc` buffer, ua[1] strap; 40 × 40 µm | **verified** |
| Neuron core | Starved detector + reset keeper, wider leak OTA, EL 1.30 V, synapse, gap trim, τ trim, probe-tap fix | schematic verified at all corners |
| Slot variants | S, F, AH50, AH800, REF, DUMMY routed on the new cells; τ-trim cell clean | layout verification running |
| D1 dendrite | Schematic on new cells (cold corners fixed, clustered vs distributed works) | layout at 70 × 104 in progress |
| AdEx | Schematic on new cells (adaptation matches the model) | layout at ~38 µm wide in progress |
| Floorplan v2 | Block frames fixed from measured shapes | plan doc §10; `floorplan.py` update pending |
| Characterization | Speed envelope (1000×, ~2000× with firmware), mismatch MCs, corner sweeps | docs |

## Still to do

### By G2 (Nov 22): blocks finished
1. **Slots:** DRC/LVS/PEX on all 9 variants on the fixed cells; route H and CMP; derive P; post-layout f–I. *(slot track)*
2. **D1:** keeper on its plateau detectors; route at 70 × 104 with both trims; DRC/LVS/PEX; post-layout clustered/distributed. *(D1 track)*
3. **AdEx:** route at ~38 × 75 with the keeper; DRC/LVS/PEX; functional checks. *(AdEx track)*
4. **Floorplan:** put the measured boxes into `floorplan.py`, re-check geometry, confirm the bias-line channel (~7 µm at y ~131–138) and the 1×2 margin. *(integrator)*
5. Commit.

### By G3 (Nov 29): MVP submittable
| Days | Work |
|---|---|
| Nov 23–24 | **Neuron array assembly:** 4×4 slots by abutment; connect row Metal3 tracks to the control block's W edge; column lines to the bias channel; τ-trim cells to `aux` (col 0, col 2); `vth_cmp` to col 1 `aux`. |
| Nov 24–25 | **Top-level assembly in magic:** place the control macro, B1, R1, D1, AdEx, the array and the τ cells; Metal4 power stripes as ports (full height, ≥ 0.8 µm); route the channels (bias lines, probe bus, R1 feed-throughs, spikes, D1/AdEx lines, TT pin jogs); tie-high cells on uio_oe; ua[0]/ua[1] connections. |
| Nov 26 | **Full-chip checks:** magic DRC, KLayout gf180mcu deck (as precheck runs it), antenna; **top-level LVS** with netgen (macro + analog blocks against a top-level SPICE netlist). |
| Nov 27 | **PEX spot checks:** one neuron through the probe chain to the pad; bias distribution to the far array column; reset and probe-enable kicks. Fix anything found. |
| Nov 28 | **Local TT precheck** (tt-support-tools, gf180mcuD); `docs/info.md` (pinout, register map, bring-up procedure, firmware rules); final `info.yaml`. |
| Nov 28–29 | **GitHub repo** (user creates it) → push → TT GDS / precheck CI green. **G3.** |

### By G4 (Dec 5)
- Fix anything CI or review finds.
- Optional, only if time allows: the D1 ff/85 plateau outlier, Monte Carlo of the rev C DACs, a bring-up firmware sketch for the RP2350.
- **The user submits and pays.**

## Needs from the user
- **Create the GitHub repo**, by about Nov 27, so CI can run before G3.
- **Approve submission and payment**, at G4.

## Main risks
- **Top-level routing:** the bias channel to the array is tight (~7 µm), and the probe bus and R1 feed-throughs must thread through B1's corridor.
- **Top-level LVS** of the mixed hardened-macro + analog design: the first full-chip run usually turns up naming and connectivity issues. Budget a day.
- **Slot routing:** H and CMP are still converging. If either fails, a placement tweak costs 2–3 h.
- **Agent and tooling interruptions** (Docker stops, session restarts): mitigated by commits and the RESUME HERE notes.
