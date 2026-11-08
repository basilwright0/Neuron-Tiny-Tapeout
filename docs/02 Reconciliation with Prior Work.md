# Reconciling the TT analog-neuron plan with prior work

Date: 2026-11-08. Inputs:
- [01 Conversation Summary](01%20Conversation%20Summary.md)
- `C:\Projects\Neural Hardware` (NH vault)
- `C:\Projects\Connectomics Simulation` (CS vault)
- `C:\Projects\connectome-vault` (CV vault)
- the WSL repo `~/neural-hardware-ic` (Hermes-built EDA environment)

## 1. How the four efforts fit together

The CS vault's binding note `05 Bridge/Division of Labour.md` splits the programme into three questions:

| Vault | Question | Relevance to this chip |
|---|---|---|
| connectome-vault | *Can we measure it?* Connectome-seq / SynLink-seq wet lab | **Low.** It sits upstream. It produces cell-type-resolved connectivity with no positions; its first targets are the cerebellum and pons. Nothing in it constrains circuits. |
| Connectomics Simulation | *Is the measurement sufficient?* It owns the neuron-model question. | **High.** It sets the acceptance criteria for neuron dynamics. |
| Neural Hardware | *Can we build it?* Silicon, area, trim, PPA | **Very high.** This chip is its Phase 0 silicon. The NH note `EXP-02 TT analog integrator test chip` is its direct predecessor. |

**This project is Neural Hardware Phase 0 silicon.** It should be framed as the extended successor to NH EXP-02, so its results feed the NH gate `Gate — Phase 0 to Phase 1`. That gate's criterion #3 is still unmet: *"analog integrator noise floor measured in fabricated silicon"*.

## 2. Where the conversation plan and the prior work agree

| Conversation plan | Prior-work counterpart | Verdict |
|---|---|---|
| Turn 11: hard-coded vs programmable parameters, fixed physiological presets | NH EXP-46 decision: **etch τ variants per cell-type macro plus a load-time per-neuron gain rescale; a per-neuron τ trim was rejected** (`Q How is the membrane time constant set`) | Strong agreement. The chip directly tests this decision. |
| Turn 10: parameter economy, shared/trim/live classes, sensitivity Jacobian | NH `Trim bits follow from device area`: 3 bits at 5.4 µm², 4 bits at 0.9 µm², 7 bits at 0.035 µm² leak area. Trim *knob count* is still an open "free paper task". | Agreement. The Jacobian study is that paper task. |
| Reproducibility and replication | NH EXP-47 (Monte Carlo of N=200): static mismatch is predictable from the PDK, ρ(τ,R) ≥ 0.973. Laws: σ(lnR) ≈ 9.3 %·µm/√(WL); MIM 0.47 %/√area. | Agreement, with a **change of emphasis** (see §3.3). |
| Dendritic compartments | NH architecture: **only the dendritic subunit is analog**; the soma is time-multiplexed digital. CS finding: a point neuron is *not* sufficient, and a Poirazi-Mel plateau nonlinearity moves network statistics by 14.7 floor units. | Agreement. Dendrites are the most programme-relevant block on the chip. |
| Digital LIF reference | NH Q-INTEGRATOR: digital integration is 19–1022× more power than analog. The CS/NH reference model is Potjans-Diesmann LIF. | Agreement. Use the same equations. |

## 3. Where they conflict, and the resolution

### 3.1 Process and shuttle: GF26c (GF180) vs TTSKY26d (sky130A)

- The conversation targets **TT GF26c / GF180MCU**, deadline **2026-12-07**.
- NH, the vault notes and `~/neural-hardware-ic/AGENTS.md` target **TTSKY26d / sky130A** ("sky130A exactly"). That environment has proven one inverter through DRC, LVS and PEX. All mismatch laws were measured in sky130.
- The area basis differs widely. The conversation budgets ~116,000 µm², but that figure is from GF26b **digital** tile dimensions. The sky130 analog 1×2 tile is ~160×225 µm ≈ 36,000 µm² gross, ~28.8k usable per NH EXP-02. **The 57.5k µm² baseline does not fit a sky130 analog 1×2.**
- Both PDKs (gf180mcuD and sky130A) are installed in the pinned image `hpretl/iic-osic-tools:2026.08`, which was checked today.
- **Resolution:** decided by the TT shuttle research in [03 Research Findings](03%20Research%20Findings.md). Design the neuron primitives to be process-portable at the schematic level, with a common Python test harness, so the first two weeks of work are not lost either way.

### 3.2 Operating speed: 1×–1,000× vs the NH design point S = 50–100×

- The conversation never settled whether biological real time is required.
- The NH architecture fixes **S = 50–100×** (ceiling 3,000–5,000×). For τ_bio = 10 ms that means hardware τ = 100–200 µs.
- The NH smoke cell ran at ns–µs (10⁵–10⁷×), so no prior design has yet run at the programme's real operating point.
- **Resolution:** make **100× the primary design point** for every block. 10× and 1,000× are characterisation sweeps; 1× is a stretch measurement. This answers the open question from turn 3: biological real time is not a hard requirement. At 200 fF and τ = 100 µs, g = 2 nS (≈200 pA at 100 mV), comfortably above leakage. At 50 fF it is 0.5 nS.

### 3.3 What replication is for

- EXP-47 showed that static random mismatch is predictable in simulation, so a large static mismatch array mostly re-measures what Monte Carlo already predicts.
- The NH-ranked **silicon-only** questions are:
  1. 1/f and RTN drift on the integrating node, which the PDK cannot simulate;
  2. leakage and retention under a hold/freeze gate;
  3. **systematic gradients across the array**, the only way to falsify EXP-47;
  4. the real kT/C floor;
  5. trim-actuator monotonicity;
  6. true node capacitance;
  7. temperature coefficient.
- **Resolution:**
  - Keep the replicas, but **interleave them across the whole tile** to test gradients, which the conversation also suggested.
  - Add a **hold (freeze) mode** to the shared membrane primitive.
  - Make sure at least two cells can be recorded unloaded through the buffer for hours, for drift and RTN. That needs a long-recording-capable probe path, not just a fast one.

### 3.4 Trim target: τ vs gain

- The conversation's trim candidates were leak, threshold, reset and input gain.
- NH EXP-46 found **R/excitability (gain) is the sensitive parameter, not τ**. A 3.6% systematic offset gives 33% rate error, whereas ±53% random τ scatter gives only 3.1%. Gain error is exactly correctable at load time, and the correction survives 4-bit weights.
- **Resolution:** the hybrid group's single local trim should be an **input-gain (synaptic-current scale) trim**, with τ fixed by geometry. A threshold trim is the alternative arm. The Jacobian study (P0 simulation) confirms the choice before layout.

### 3.5 Active dendrites: Tier 3 vs programme-critical

- The conversation left active dendrites at Tier 3.
- CS EXP-08 found that a dendritic nonlinearity is required, and that it must be given to **all cells or none**.
- NH's subunit spec already includes an **NMDA-like plateau nonlinearity**, with 7 excitatory and 4 inhibitory subunits in a depth-1 star.
- **Resolution:** promote **one passive-plus-plateau-nonlinearity dendritic subunit** (a switchable regenerative conductance) to **Tier 1.5**. It should be designed into the continuous-time dendrite from the start, enabled by a config bit.
- Prefer the **depth-1 star** (soma plus 2–3 subunits) over a linear chain, to match the NH architecture. A 2-deep chain can be configured with the same switches to probe the open star-vs-tree question (D-3).

### 3.6 Synapses and weights

- CS weight-precision results: dynamic range matters more than bit depth; 4.4–9.6 bits, or 4-bit log if the range covers about 2 decades. NH chose 4-bit log weights.
- **Resolution:** give the on-chip stimulus/synapse current DAC **≥2 decades of range**, with log or coarse+fine steps, rather than many linear bits. The small network, if built, uses 4-bit log-ish weights.

### 3.7 Lessons the environment has already paid for

These come from NH `RISK First-silicon design pitfalls` (P-01…P-36) and the `~/neural-hardware-ic` audit. All carry over:

- Never route an integrating node to a pad unbuffered: pads are ~5 pF against a 50–800 fF node.
- **Readout buffer failing to bias at a slow corner is the most likely cause of a dead chip (P-09).** Sign it off across all corners first.
- Leak-device parasitics can dominate small MIMs: 18 fF parasitic against a 10 fF MIM in EXP-47. The nominal 50 fF point is really 50 fF + parasitic, so report it as C_total.
- `.option seed=N` for Monte Carlo; aborted transients exit 0; scale `abstol` to the array size; grep-only pass checks lie (the iverilog false PASS).
- The PDK lacks 1/f/RTN models: sky130 has them stripped, and gf180 needs checking.
- No metal 5 on sky130 TT; check the GF equivalent. Tie unused digital outputs to GND. Template DEF pins are fixed. The `info.yaml` field is `uses_vapwr`.

## 4. What matters most to design and build

Ranked by (programme value × chance of a dead chip if it's wrong):

| Rank | Block | Why it is first |
|---|---|---|
| 1 | **Readout path:** source-follower or unity buffer → analog mux → ua1 pad driver, plus a calibration node | Every analog measurement depends on it. P-09 is the most likely chip killer. It must also support long, low-drift recordings. |
| 2 | **Digital control plane:** shift-register/SPI config, neuron select, spike-out mux/counters on `uo_out`, reset/hold | Without it nothing can be selected or observed. It is also the only path for spike data, independent of the analog path. |
| 3 | **Shared membrane primitive:** C (50/200/800 fF) + subthreshold leak with mirrored bias + input current injection + hold gate, at 100× | Every neuron reuses it. It answers drift, retention, gradient and kT/C questions (NH Gate #3). |
| 4 | **Bias distribution:** one external reference through ua0 → on-chip mirror tree with binary ratios; per-group (cell-type) bias domains; local gain trim on the hybrid group | It implements the shared/trim/live hierarchy, and is the parameter-economy experiment itself. |
| 5 | **Two spike generators on the same membrane:** regenerative (axon-hillock) and comparator, with reset and refractory | Threshold-architecture comparison, and the area claim versus the digital LIF. |
| 6 | **Dendritic subunit:** passive compartment + bidirectional MOS axial coupling + switchable plateau nonlinearity; soma + 2–3 subunits in a star | The most programme-relevant block (CS EXP-08, NH subunit spec). |
| 7 | **Fixed / shared-bias / hybrid / programmable LIF groups**, interleaved across the tile | The P0 experiment from turn 11, aligned with the NH EXP-46 decision. |
| 8 | **Digital LIF reference** (8–12-bit, same I/O semantics) | Area baseline; needs to be synthesised into the tile. Check mixed-signal rules. |
| 9 | AdEx (adaptation + exponential) | Tier 2. Adds the adaptation state, reusing the membrane primitive. |
| 10 | Switched-capacitor dendrite, small network, extra replicas | Tier 2–3, only if area remains. |

The **numerical reference** (Python: the CS/NH LIF equations plus a compartment model) and the **SPICE harness** are not silicon, but they are needed before block 3 can be judged. Build them in week 1.
