# Research findings (2026-11-08)

Five research streams fed this note: the TT GF26c rules, transistor-level circuits, GF180 device facts with local simulation, test and measurement, and the three prior-work vaults.
Unverified items are marked **(unverified)**.

## 1. Shuttle and submission facts

Sources: tinytapeout.com/chips, `TinyTapeout/ttgf-analog-template`, `tt-support-tools` precheck and DEF source.

| | **TTGF26c (chosen)** | TTSKY26d (fallback) |
|---|---|---|
| Process | gf180mcuD (wafer.space run #3), 5 metal layers, MIM option B | sky130A |
| Closes | **2026-12-07** | 2026-11-30 (the NH note said "Dec"; that is wrong) |
| Chips | ~2027-05-12 | ~2027-05-25 |
| Analog 1×2 usable area | **346.64 × 325.36 µm = 112,780 µm²** (106,950 µm² with the VAPWR template) | 161 × 225.76 µm = 36,350 µm² |
| Analog 2×2 | 711.2 × 325.36 µm = 231,400 µm² | 75,600 µm² |
| Analog pins | ua[0..5], Metal4 pads on the bottom edge, 43.68 µm pitch | ua[0..5] |
| Core supply | VDPWR = **3.3 V**; optional VAPWR (voltage on GF unverified; one project asks for 5 V) | 1.8 V; VAPWR 3.3 V |
| Metal | **Metal1–Metal4 only. Metal5 is forbidden.** | met1–met4 |
| Analog pin R/C limits | **Not published for GF.** sky130 has <500 Ω and <5 pF. | <500 Ω, <5 pF, 4 mA |
| Precheck | KLayout GF180 DRC, antenna, pin/boundary/power/layer/cell-name/analog-pin checks, Verilog syntax. **No LVS: run your own.** | Adds Magic DRC |

- **Cost:** €70 per tile, so €140 for a 1×2. The first two analog pins cost €40 each; more cost €100 each. A devkit is €100 with tiles (individuals), and shipping is €15. GF chips are chip-on-board.
- **Prior art on GF:** GF0p3 had 16 analog projects and GF26c has 4 so far. **No analog neuron has been taped out on GF.** Good layout references:
  - `smunaut/ttgf_analog_factory_test`
  - `mattvenn/gf-r2r-dac`
  - `htfab/ttgf0p3-momcap` (MoM capacitors, relevant to §2)
  - `ktm0228/ttgf26c-opamptrim`
- **Next GF shuttle:** TTGF27a, ~April 2027. It is the fallback if the MVP is not ready by Dec 5.

**Decision: GF26c, 1×2, 2 analog pins.**
- It has 3.1× the sky130 analog area, which makes the conversation's ~57.5k µm² baseline plausible.
- 3.3 V thick-oxide devices give much lower off-leakage, which suits pA-level biasing.
- It keeps the conversation's own target.
- The sky130 work in the NH vault (EXP-47 mismatch laws) stays valid as a cross-process comparison, but those laws must be re-derived for GF.

## 2. Capacitors: the MIM plan changes

- In gf180mcuD, MIM (`cap_mim_2f0_m4m5_noshield`, 2 fF/µm², minimum 5×5 µm ≈ 54 fF) sits between Metal4 and Metal5. Contacting its top plate needs Metal5, which TT forbids.
- **Treat MIM as unavailable.** Asking on the TT Discord #analog channel is the only way to confirm.
- A local ngspice C–V sweep (`sim/pdk_smoke/moscap/cv.cir`, typical corner) gives these densities:

  | Gate voltage | nfet_03v3 gate cap (S/D/B = 0) | pfet_03v3 gate cap (S/D/B = 3.3 V) |
  |---|---|---|
  | 0.0 V | 1.52 fF/µm² | 4.08 |
  | 0.5 V | 1.74 | 4.09 |
  | 0.75 V | 3.46 | 4.10 |
  | 1.0 V | 3.91 | 4.10 |
  | 1.5 V | 4.00 | 4.08 |
  | 2.0 V | 4.01 | 4.01 |
  | 2.5 V | 4.01 | 2.86 |
  | 3.3 V | 3.99 | 1.88 |

- **Design rule:** membrane capacitors are thick-oxide MOS gate caps at about 4 fF/µm², with the membrane kept in the flat region.
  - **NMOS cap (referenced to VGND) for membranes operating between 1.0 and 3.0 V.** This is preferred because the reference is quiet ground.
  - The PMOS cap is flat from 0 to 2.0 V, but its well is tied to VDD, so supply noise couples straight onto the membrane. Use it only with a dedicated clean well bias.
- **Area at 4 fF/µm²:**

  | C | Area |
  |---|---|
  | 50 fF | 12.5 µm² (3.5×3.5 µm) |
  | 200 fF | 50 µm² (7×7 µm) |
  | 800 fF | 200 µm² (14×14 µm) |

  That is half the MIM area. The trade-off is that MOS caps cannot sit over active circuits the way MIM can.
- **Still to check:** MOS-cap mismatch and temperature behaviour, plus MOM finger caps on M1–M4 for linear small caps (switched-capacitor Cs ≈ 2–10 fF).

## 3. GF180 device facts and smoke simulations

The simulations are in [`sim/pdk_smoke/`](../sim/pdk_smoke/README.md) and all run in the pinned image.

| Fact | Value |
|---|---|
| Model include | `.include design.ngspice` + `.lib sm141064.ngspice typical\|ff\|ss\|fs\|sf\|statistical`. MOSFETs are subcircuits, so instances use the `X` prefix. |
| Mismatch Monte Carlo | `.param sw_stat_mismatch=1` after the `design.ngspice` include, plus `.option seed=N`. A_VT ≈ 7.15 mV·µm (nfet_03v3). |
| nfet_03v3 subthreshold slope | 83 mV/dec at 27 °C; 99 mV/dec at 85 °C |
| Vgs for 1 pA / 10 pA / 1 nA / 10 nA (W/L = 1/1) | 0.19 / 0.28 / 0.45 / 0.54 V |
| Off current (Vgs = 0, 1 µm²) | 14 fA at 27 °C; 0.39 pA at 85 °C |
| Corner spread | ~210 mV of Vg for a fixed current (ff→ss). **Use currents from mirrors, never fixed gate voltages.** |
| Hold leakage (200 fF, gate at 0 V) | ~14 fA, so the hold time is seconds |
| Mismatch at 75 pA (W/L = 1/1) | σ/I ≈ 14–15 %. Die-to-die means vary from 17 to 139 pA, which is far larger than the in-die spread. |
| Single-transistor leak behaviour | Acts as a current sink, not a conductance, above ~100 mV swing. A true exponential RC needs an OTA follower-integrator, a degenerated or linearised leak, or a small swing. |
| Poly resistor | ppolyf_u_3k: 3 kΩ/sq. Useless for GΩ, fine for bias references. |

## 4. Circuit topology choices

These come from the circuit brief. Unverified numbers are flagged there.

| Block | Recommended topology | Notes |
|---|---|---|
| Regenerative LIF | **Mead axon-hillock** (~6T + Cfb) + explicit subthreshold leak + current-starved first inverter | ΔV = VDD·Cfb/(Cm+Cfb). The trip point varies with process, which is a known pitfall. |
| Comparator LIF | **van Schaik 5T-OTA comparator** with explicit Vthr → inverter → reset + refractory | Same membrane and leak as the regenerative LIF; only the spike generator is swapped. |
| Leak / τ | DPI or follower-integrator: τ = C·U_T/(κ·I_τ). At 200 fF, τ = 100 µs (S = 100) needs I_τ ≈ 74 pA. | 50 fF at 10 ms needs 0.18 pA, which is at the floor. Treat it as a stretch. 800 fF at 10 µs needs 80 nS. |
| AdEx | **DPI neuron** (Chicca/Indiveri 2014, ~21T, two caps) at bio and 100× speed; BrainScaleS-2 OTA style at 1,000× | Adaptation is a second DPI. Ringing appears at high Vthrahp. |
| Axial coupling | **Single-transistor diffusor** (Mead/Boahen): exactly linear in the current domain, 1 transistor per link, gate-voltage-tunable over ≥5 decades | In a voltage-mode membrane, g depends on the common-mode voltage. Use current-mode (DPI) compartments, or reference the gate to the common mode. Alternative: Aamir 2018 floating bulk-drain pFET resistor (1.7–62 nS, ~7T). |
| Plateau nonlinearity | Local regenerative conductance (positive-feedback pair) gated by a config bit | Matches the NH NMDA-plateau subunit spec. |
| Switched-capacitor dendrite | Cs ≤ Cm/20 (2–10 fF MoM), non-overlapping clocks from local standard cells, dummy half-switches | 5 pS needs 0.5 Hz, which is useless. SC only suits the 100×–1,000× regime. |
| Probe | In-cell pFET source follower in its own n-well (~1–2 fF load), enabled only when selected → 3.3 V TG mux → shared 2-stage Miller OTA pad driver (50–200 µA) | **Never put a mux switch directly on Cm.** Calibrate the follower offset with a reference channel. |
| Bias | Reduced **Delbruck bias generator**: µA master from ua[0] → Bult-Geelen MOS-ladder splitter (factor-2 steps, ~1 µA → 4 pA) + shifted-source branch for sub-pA | Local trim: 3–5-bit binary-weighted mirror, units WL ≥ 4 µm². |
| Digital LIF | 8–12-bit fixed-point, scan-readable state, hardened with LibreLane on `gf180mcu_fd_sc_mcu7t5v0` | Starting points: `rejunity/tt05-lif-neuron` and `tt05-spiking-neural-net`. |

**Novelty check:** there is no silicon-proven open-source analog LIF on any TT shuttle. Closest references:
- `rejunity/tt06-analog-current-comparator`
- `preetopritam/NeuroLIF-SKY130` (not taped out)
- `valrek-sol/analog-perceptron-gf180mcu` (GF180 xschem setup)

## 5. Test and measurement

- **Demo board TTDBv3 (RP2350):** the MicroPython SDK selects the project and sets the clock (Hz to tens of MHz).
  - Analog pins come out on the 100-mil ANALOG header.
  - The RP2350 ADC (12-bit, ~500 kS/s, ~9 ENOB) is on a separate header and is jumpered by hand.
  - **Remove or raise the board's pull-downs on the ua lines.** They are 10 MΩ on new boards, which is ~100 nA at 1 V.
  - The board's `analog_current_source` (≤250 µA) is a ready master reference for ua[0].
- **Lessons from earlier TT analog silicon:**
  - Buffer every analog output: unbuffered pads give 240–360 ns edges.
  - Bias-dependent timing landed 20–40 % off simulation, so τ must be trimmable or measured.
  - Put duplicates on the die.
  - Timestamp spikes as fast as possible.
- **Never pass sub-nA currents through a pad.** Pad leakage and ESD leakage are undocumented (pA–nA). Make the currents on-chip, and convert current to frequency or time on-chip.
- **Control plane (recommended):**
  - SPI on ui[0..2] into a config shift register with a shadow latch and safe all-off defaults, with MISO on uio[0].
  - Real-time stimulus pulses and global reset/hold on ui[3..7].
  - Spikes on uo_out through a selector and pulse stretchers; timestamping is done off-chip by RP2350 PIO (~6.7 ns).
  - Optional shared 16-bit spike counter.
- **Energy per spike:** take the slope of supply current against firing rate, which cancels static current. Alternatively, power the neuron-under-test from a dedicated pin (a 3rd analog pin, +€100).
- **Bench, minimum:** the demo board, an Analog Discovery 3 (TT has a guide for it), and a CurrentRanger or used Keithley 6485 for pA work.
- **Verification flow:**
  - xschem + ngspice for circuits; magic or KLayout for layout; netgen for LVS; magic PEX.
  - cocotb + iverilog for the digital blocks, with the same tests reused on silicon via microcotb.
  - Mixed-signal checks with ngspice `d_cosim` or XSPICE `d_source`.

## 6. Local environment status (verified today)

| Item | Status |
|---|---|
| WSL Ubuntu-24.04, 20 cores, 23 GB, 907 GB free | OK |
| Docker Desktop 4.89 / engine 29.7.2 | OK after a restart. The WSL integration dropped once during the session, which is the known signature: restart Docker Desktop and run `wsl --shutdown`. |
| Image `hpretl/iic-osic-tools:2026.08` (digest-pinned) | gf180mcuD, sky130A, ihp-sg13g2; ngspice 47, xschem, magic, netgen, KLayout, yosys, OpenROAD, **LibreLane**, iverilog, verilator, openvaf, xyce; std cells `gf180mcu_fd_sc_mcu7t5v0` / `9t5v0` |
| gf180mcuD ngspice models + mismatch MC | Run and verified (`sim/pdk_smoke`) |
| TT frame (`mag/`, `gds/`, `lef/`) generated from the official 1×2 DEF | Done |
| **Local TT precheck** (`scripts/precheck.sh`) | **11/12 pass** on the empty frame. The only failure is "ua[0] not connected", which is expected until wiring. |
