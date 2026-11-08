# Design plan: TTGF26c analog neuron test bench

**Target:** TTGF26c, gf180mcuD, analog 1×2 (112,780 µm²), 2 analog pins, VDPWR 3.3 V, top cell `tt_um_basilwright0_analog_neurons`.
**Hard deadline:** 2026-12-07. **Internal submit target:** 2026-12-05.
**Primary operating point:** S = 100× (τ_bio 10 ms → τ_hw 100 µs). 10× and 1,000× are characterisation sweeps; 1× is a stretch goal.

## 1. Strategy: protect an MVP, then grow

There are 29 days left, and this is a first analog tapeout. The conversation's full 18-instance matrix is the goal, but it is not the plan of record. Two rules govern the schedule:

1. **The MVP must be precheck-green, LVS-clean and pushed by 2026-11-29.** After that the repo is always submittable.
2. Tier-2 and Tier-3 blocks are inserted only after passing their own schematic, layout, DRC, LVS and PEX checks. Layout tiles are modular, so late additions do not disturb verified blocks.

## 2. Block list and tiers

The ranking follows [02 Reconciliation](02%20Reconciliation%20with%20Prior%20Work.md) §4. Areas are planning estimates for GF180 at 4 fF/µm² MOS caps.

| ID | Block | Tier | Count | Est. area (µm²) |
|---|---|---|---|---|
| R1 | Probe path: in-cell pFET follower → 3.3 V TG mux (≥16:1) → Miller-OTA pad driver → ua[1], plus a calibration node | **MVP** | 1 | 8,000 |
| C1 | Control plane: SPI config chain (~96–128 bits) + shadow latch, decoder, spike selector and stretchers → uo_out, 16-bit spike counter, reset/hold (LibreLane-hardened macro) | **MVP** | 1 | 12,000 |
| B1 | Bias: ua[0] master current → Bult-Geelen splitter + shifted-source branch → per-group bias lines (cell-type domains); 4-bit local gain trim cells | **MVP** | 1 + trims | 10,000 |
| M1 | Membrane primitive: NMOS-cap C (50/200/800 fF) + DPI/subthreshold leak + current-input synapse (pulse- or DAC-driven) + hold gate | **MVP** | reused | — |
| N1 | Regenerative (axon-hillock) LIF on M1, spread across 3 capacitances, interleaved across the tile | **MVP** | 8 | 8,000 |
| N2 | Comparator LIF on M1 (50 and 200 fF) | **MVP** | 2 | 3,000 |
| P1 | Probed/unprobed pairs: in-cell follower present vs absent (folded into N1/N2) | **MVP** | — | — |
| G1 | Parameter-economy groups at 200 fF, each of 4: fixed geometry / shared bias / hybrid (gain trim) / programmable | **MVP** (N1 replicas are counted here) | 4 × 4 | 6,000 |
| D1 | Dendritic neuron: soma + 2–3 subunits in a **star**, diffusor axial coupling, **plateau nonlinearity enabled by a config bit**, reconfigurable as a chain | **MVP** | 1 | 6,000 |
| L1 | Digital LIF, 8–12-bit, scan-readable, same spike-in/spike-out semantics | **MVP** | 1 | 4,000 |
| A1 | AdEx (DPI adaptation + exponential feedback) | Tier 2 | 2 | 5,000 |
| D2 | 2nd continuous-time dendrite (different subunit count) | Tier 2 | 1 | 6,000 |
| S1 | Switched-capacitor dendrite (MoM Cs, local non-overlap clock) | Tier 2 | 1 | 5,000 |
| W1 | Small network: 4 reused LIFs, 4-bit log-ish synapse currents, chain and E/I configurations | Tier 2 | — | 4,000 |
| X* | Extra 50 fF replicas, an alt-leak LIF, preset classes (fast/med/slow), a second layout style, a 2-deep dendrite tree | Tier 3 | — | fill |

- **MVP total:** ~57k µm². With routing and isolation reserve that is ~75–80k µm² of 112.8k.
- **MVP + Tier 2:** ~82k µm². This is tight but plausible. It must be decided against real layouts at gate G2.

## 3. Schedule and gates

| Week | Dates | Work | Gate (must pass to proceed) |
|---|---|---|---|
| 1 | Nov 9–15 | Python↔ngspice harness (`model/` + `sim/tb`). R1 schematic signed off at all 5 corners × 0/27/85 °C (**P-09: the #1 chip killer**). M1 + N1 + N2 schematics at 200 fF. B1 splitter schematic. C1 RTL + cocotb tests. Jacobian / Monte Carlo trim-sensitivity study (picks the G1 trim knob). | **G1 (Nov 15):** both LIFs match `model/reference.py` (rate error <10 %, τ within design range) at S = 10/100/1,000; buffer settles within 1 % in <1 µs into 5 pF at every corner. |
| 2 | Nov 16–22 | Layout: N1 cell, R1 follower, mux and pad driver, B1. Harden C1 + L1 with LibreLane (gf180 7-track cells). D1 schematic with plateau. Re-derive EXP-47 laws on GF (MOS-cap and leak mismatch). | **G2 (Nov 22):** each MVP cell is DRC- and LVS-clean. Measured cell areas give a real floorplan, which decides how much of Tier 2 to attempt. |
| 3 | Nov 23–29 | Top-level MVP integration in magic. Full LVS. PEX + post-layout sims on R1, N1, D1. `docs/info.md` written. Create the GitHub repo and push, so CI runs the same precheck. | **G3 (Nov 29): MVP submittable.** CI green, local LVS clean, post-layout LIF still passes G1 criteria. |
| 4 | Nov 30–Dec 5 | Insert Tier-2 blocks that passed their own checks (A1 → D2 → S1 → W1). Re-run full LVS, precheck and key PEX. Order and pay. | **G4 (Dec 5):** submit. If a Tier-2 block is not clean by Dec 3, it is dropped. |

Fallback: if G3 slips beyond Dec 3, submit the MVP as it stands. If the MVP itself is not viable, move to TTGF27a (~Apr 2027) and use the extra time for a fuller matrix.

## 4. Pin and control map (draft)

| Pin | Use |
|---|---|
| ua[0] | Master reference current in (demo-board `analog_current_source` or SMU). Optional config switch to an external stimulus or DAC calibration path. |
| ua[1] | Buffered, muxed analog probe out |
| ui[0..2] | SPI SCK / MOSI / CS |
| ui[3] | Stimulus pulse A (synapse trigger, generated by RP2350 PIO) |
| ui[4] | Stimulus pulse B (second dendritic location) |
| ui[5] | Global hold (freeze) |
| ui[6] | Global membrane reset |
| ui[7] | Spare / digital-LIF step |
| uio[0] | MISO (config readback + digital-LIF scan + counter). Remaining uio pins are spare outputs (`uio_oe` set accordingly). |
| uo[0..7] | Spike outputs: 4 config-selected neurons + selected neuron + digital LIF + OR-of-all + probe-valid (toggle or stretched) |
| clk | Digital LIF clock, SC clock source, counter timebase |

## 5. Verification checklist per analog cell

The common suite from conversation turn 7 runs through `sim/tb`:

- rest/drift, impulse, step, f–I
- speed sweep (S = 10/100/1,000), C sweep, programming sweep (one bias at a time, which gives the Jacobian)
- corners tt/ff/ss/fs/sf × 0/27/85 °C
- mismatch Monte Carlo (N ≥ 100, `.option seed`)
- supply ±10 %
- post-layout repeat of the key tests

Dendrites add attenuation, spatial and temporal summation, a coupling sweep, and plateau threshold and duration.

Acceptance metrics follow the CS vault: distributional, in floor units, where a network applies. Single cells are scored against the reference trajectory (V RMSE, rate error, spike-time error after time rescaling).

## 6. Open decisions (owner: user)

1. **Confirm GF26c over waiting for TTGF27a.** Recommended: GF26c with the MVP-first rules above.
2. **2 or 3 analog pins.** A 3rd pin (+€100) would give the neuron-under-test its own supply for direct energy-per-spike measurement. Without it, energy comes from the supply-current vs firing-rate slope.
3. **VAPWR.** Not needed for the MVP; keep `uses_vapwr: false`.
4. **Ask TT Discord #analog:** whether MIM is usable without Metal5, the GF analog-pin R/C/leakage limits, and the VAPWR voltage.
5. **Create the GitHub repo** (`basilwright0/<name>`) and push. This is needed by G3 for CI and submission.
