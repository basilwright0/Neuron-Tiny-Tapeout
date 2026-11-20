<!---
This file is used to generate the project datasheet (Tiny Tapeout). Images must be < 512 kB each, < 1 MB total.
-->

## How it works

**Analog Neuron Test Bench** is a 1×2 analog tile (gf180mcuD, 3.3 V) that puts 15 analog spiking neurons, one digital
reference neuron and their shared bias generator on one die, so that silicon-only effects — noise, drift, hold leakage,
mismatch gradients, real capacitance, temperature — can be measured against a software reference model.

What is on the chip:

| Block | What it is |
|---|---|
| Neuron array (4 × 4 slots) | Axon-hillock LIF neurons with a 200 fF membrane, leak OTA, refractory period, two input synapses (stim A / stim B), hold switch, membrane reset and an in-cell probe follower. Groups: **S** (shared bias, ×3), **F** (leak set by geometry, τ_F = 2·τ_S, ×3), **H** (shared bias + 4-bit threshold trim, ×3), **P** (threshold trim + 4-bit leak-τ trim, ×2), plus **CMP** (comparator LIF), **AH50 / AH800** (50 fF / ~740 fF membranes), **REF** (probe of the EL line, for calibration) and one dummy slot. |
| AdEx (channel 3) | Adaptive exponential neuron with its own adaptation current (`vbp_w`). |
| D1 (channel 13) | Dendritic neuron: soma + two subunits with an all-or-none plateau nonlinearity, star or chain topology, clustered or distributed stimulus. |
| Digital LIF | 12-bit bit-serial LIF in the control block, clocked by `clk`, one update per `ui[7]` tick — the exact software model in hardware. |
| B1 bias generator | Reference current from `ua[0]` (or an internal reference), eight 5-bit current/voltage DACs and a 6-bit threshold DAC; speed S = 10…1000× real time is set by the `ua[0]` current. |
| R1 readout | Buffered probe of one selected membrane (or adaptation / dendrite node) on `ua[1]` (400 µA source follower), plus the reset-voltage and detector-rail buffers. |
| Control block | Write-only configuration latches (23 bytes over a 3-wire serial port), probe decoder, digital LIF. |

All 16 spike outputs are plain digital levels on `uo[7:0]` and `uio[7:0]`. Spike timing, counting, stimulus
sequencing and the LIF tick are done by the demo board's RP2040/RP2350 (PIO).

## Pinout

| Pin | Function |
|---|---|
| ui[0] | CFG_SCK: config shift clock (rising edge) |
| ui[1] | CFG_DATA: config serial data, MSB first |
| ui[2] | CFG_LOAD: config latch strobe (high = write) |
| ui[3] | Stimulus A (`rt_out[0]`); digital-LIF event source 0 |
| ui[4] | Stimulus B (`rt_out[1]`); digital-LIF event source 1 |
| ui[5] | Hold (`rt_out[2]`) |
| ui[6] | Membrane reset (`rt_out[3]`) |
| ui[7] | Digital-LIF tick (one update per rising edge) |
| uo[7:0] | Spikes of analog channels 0–7 |
| uio[5:0] | Spikes of analog channels 8–13 (outputs) |
| uio[6] | OUT_MUX = 0: digital-LIF spike; OUT_MUX = 1: channel 14 |
| uio[7] | OUT_MUX = 0: config echo (shift-register MSB); OUT_MUX = 1: channel 15 |
| ua[0] | Bias reference current input (EXT ÷1 / ÷16), stimulus input, or internal-reference monitor |
| ua[1] | Buffered analog probe output |

`uio` are always outputs (`uio_oe` tied high). `uio_in`, `ena` and `ua[2..5]` are not used.

Spike channels: 0/4/8 S1–S3, 1/5/9 F1–F3, 2/6/10 H1–H3, 3 AdEx, 7/11 P2/P3, 12 CMP, 13 D1, 14 AH50, 15 AH800.

## Register map (summary)

Full map, timing and bit packing: [`docs/regmap.md`](regmap.md).

- **Write protocol:** shift a 13-bit frame `{ADDR[4:0], DATA[7:0]}` MSB first on SCK/DATA, then pulse LOAD high
  (≥ 50 ns). Only the last 13 bits before LOAD count. No read-back; with OUT_MUX = 0, `uio[7]` echoes the shift register
  13 SCK edges later (link check). The port works with `clk` stopped. `rst_n` low clears every byte to 0 (all off).
- **0x00–0x04** IDAC: eight 5-bit current-DAC codes (leak, refractory, synapse, D1 axial, AdEx adaptation, EL, V_reset, CMP threshold), 40-bit word LSB first.
- **0x05** VDAC: 6-bit threshold reference `vth_ref`.
- **0x06** ANA: group enables, D1 plateau / chain / stim-B steering, **BIAS_EN**.
- **0x07** PROBE: SEL (spike channel to probe), SUB (membrane / secondary node / REF), PROBE_EN.
- **0x08** MODE: ua[0] mode, OUT_MUX, IB_X2 (readout bias ×2), RT_EN (enables of the four `ui[6:3]` pass-throughs).
- **0x09–0x0E** digital LIF: enable/source, leak shift + refractory, EL, Vth, Vreset, weight.
- **0x0F–0x16** TRIM: 4-bit trims (H/P/CMP thresholds, D1 plateau thresholds, P leak-τ).

## How to test

Bring-up (demo board, RP2040/RP2350 driving `ui[2:0]`, a 0.1–10 µA current source or SMU on `ua[0]`, a scope / ADC on `ua[1]`):

1. Select the project, hold `rst_n` low, release it. Everything is off (all codes 0, BIAS_EN = 0, probe off).
2. **Link check:** with OUT_MUX = 0, shift a known pattern and watch it come back on `uio[7]` 13 SCK edges later.
3. Apply the reference current into `ua[0]`: S = 100 × I(µA) in EXT ÷1 mode (0.1 / 1 / 10 µA for S = 10 / 100 / 1000);
   EXT ÷16 takes 16× the current for the same S. The internal reference (UA0_MODE 2/3) gives S ≈ 100 without a source.
4. With BIAS_EN = 0, write the DAC codes (IDAC, VDAC); then set BIAS_EN = 1.
5. **Calibrate per die and per speed setting:** probe REF (PROBE_SUB = 3) to measure EL; set the threshold code
   via the REF channel and firing-rate checks; then EL; then the H/P/CMP/D1 trims.
6. Enable RT_EN, drive stimulus A/B on `ui[3]/ui[4]` and count spikes on `uo`/`uio`; move the probe to look at membranes on `ua[1]`.
7. Digital LIF: write the LIF parameters with LIF_EN = 0, then LIF_EN = 1; drive `clk` and tick `ui[7]` (≥ 48 clk apart).

**Firmware rules**

- Rewrite the whole configuration after every project enable: the design is unpowered while deselected.
- Before changing the probe select, disable the probe (PROBE_EN = 0 with the old SEL/SUB), change SEL/SUB, then re-enable.
- Set BIAS_EN = 0 while changing bias codes (a 5-bit code can straddle two bytes).
- Change digital-LIF parameters only while LIF_EN = 0 (wait ≥ 3 clk after clearing it).
- Stop `clk` during analog measurements (the config latches, spike outputs and stimulus pass-through work without it).
- Calibrate per die and per speed setting: threshold code (REF channel + firing rate), then EL, then the trims.
- Speed: S = 10–1000 is supported. At S ≥ ~300 use EL / Vth / Vreset ≈ 1.50 / 1.58 / 1.50 V so the leak OTA passes
  every corner. Above S = 1000 (up to ~2000): stimulate at most ~4 array neurons at once, set IB_X2, use the ÷1 `ua[0]` mode.
  S = 10000 is not supported.

## External hardware

- Precision current source (or SMU) driving current into `ua[0]` (pad sits at ~0.5–0.75 V): 0.1–10 µA (÷1 mode) or 1.6–160 µA (÷16 mode).
- Oscilloscope or ADC on `ua[1]` (0.5–2.3 V; ~1 µs settling into 200 pF).
- The TT demo board's RP2040/RP2350 for configuration, stimulus timing and spike capture (PIO).
