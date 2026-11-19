# Tiny Tapeout answers for TTGF26c (Discord, 2026-11-18)

These are the TT team's answers to our GF-specific questions, plus what each one changes in the design. Precheck facts we found ourselves (full-height power ports at least 0.8 µm wide on Metal4, metal fill added by TT, no LVS in precheck) are in the earlier research notes; they aren't repeated here.

| # | Question | Answer | Impact |
|---|---|---|---|
| 1 | Hardened standard-cell macro inside an analog tile? | **Yes.** | Rev C macro plan stands. |
| 2 | How to drive `uio_oe` high | **Tie-high cells are preferred.** Tying to `ena` also works, since `ena` is always 1 from the project's point of view. | Place 8 gf180 tie-high cells next to the uio_oe pins at top level (floorplan §5). |
| 3 | GF analog-pin R / C / current | **Similar to sky130 on-chip.** But GF chips are chip-on-board, wire-bonded straight to the breakout PCB, so a whole board is always attached and the real pin capacitance is much higher than the sky130 chip-only numbers. | **Re-check readout settling with a larger load.** It was verified into 25 pF + 500 Ω (173–208 ns). Sweep up to ~100 pF and confirm stability and 1 % settling. The pad follower may need more current or a slower spec. |
| 4 | ESD on ua pins | **Primary ESD only.** Add secondary ESD if a pin connects to a transistor gate. | **ua[0] needs secondary ESD.** It feeds B1's master, a diode-connected mirror, so gates are on it: add a series resistor plus clamp diodes to VDPWR/VGND. ua[1] touches diffusion only (the pad follower source/n-well), so it is fine as is. |
| 5 | Powered when not selected? `ena`? | **Not powered when not enabled.** `ena` doesn't need to be used. | Config latches lose their state whenever the project is deselected or power-cycled. Firmware must reset and rewrite the whole config after every enable. Nothing on chip uses `ena` apart from the optional uio_oe tie. |
| 6 | Measuring just our supply current | **Not directly.** Toggle `ctrl_ena` and take a differential measurement. All other projects are disabled, so what remains is whole-chip leakage plus the TT mux, which switches with our I/O activity. **Or use the VAPWR rail:** it powers analog projects only and is quieter. | Energy-per-spike measurements will be differential and need static I/O and a stopped clock. VAPWR is a real option for the analog section: see below. |
| 7 | Demo board; stopping the clock | **RP2350.** Stopping the clock is fine and actually recommended, because it avoids noise from the clock distribution network. | Confirms the clock-off protocol for analog measurements (floorplan §3). Bring-up firmware targets the RP2350 (PIO for spike timestamps). |

## Decision raised: VAPWR for the analog section

Today everything runs from VDPWR. The pgvaa template (`tt_analog_1x2_pgvaa.def`) adds a VAPWR stripe.

**What VAPWR would give us:**
- the neurons, bias generator and readout on a quieter supply that only analog projects share;
- a cleaner differential current measurement for the energy-per-spike comparison;
- the digital macro left alone on VDPWR.

**Costs and unknowns:**
- The VAPWR voltage on GF is unconfirmed. If it is 3.3 V, the domains are the same voltage and no level shifting is needed.
- It needs another full-height stripe set, and the power plan changes, which redraws floorplan §3.
- The digital→analog control lines (static) and the analog→digital spike lines then cross supply domains.
- It needs `uses_3v3`/VAPWR settings in `info.yaml`.

### VAPWR investigation (2026-11-18)

Sources: local `tt-support-tools/tech/gf180mcuD/def/analog/`, the precheck code and the template `info.yaml`.

- **The pgvaa template is narrower.** `tt_analog_1x2_pgvaa.def` is **328.72 × 325.36 µm**, against 346.64 × 325.36 for the plain template. That is −17.92 µm of width, **−5.8k µm² (−5.2 %)**, and every top and bottom pin moves (for example ua[0] is at x 309.4 instead of 327.3).
- **The voltage isn't stated.** The template's `info.yaml` describes VAPWR only as the "second analog power supply", in addition to VDPWR (3.3 V). No GF page or file gives its voltage, and TT's answer didn't either.
- **What it would take:** set `uses_vapwr: true`, which needs at least one analog pin (we have two). Precheck then requires a VAPWR Metal4 port with the same rules as the others: full height and at least 0.8 µm wide. The magic init script adds a VAPWR stripe.

**Recommendation: stay on VDPWR.**
- **Area:** the 5.8k µm² cost is larger than the current Tier-2 margin. T2 has +1 %, and B1+R1 has +10 % of its 13.6k.
- **Voltage:** it is unknown. If it weren't 3.3 V, every digital→analog line would need level shifting.
- **Isolation:** most of what VAPWR offers is already covered. Analog measurements run with the clock stopped, which TT also recommends. The neurons and B1 have their own guard rings and substrate taps.
- **Energy:** the differential `ctrl_ena` method still gives energy per spike.

Reconsider only if silicon noise turns out to matter more than Tier-2 area. Before switching, ask TT for the VAPWR voltage on GF.

### Readout into the board load: result (2026-11-18)

The R1 track swept the extracted pad driver into 20–200 pF of board capacitance behind the 500 Ω mux, at 5 corners × 0/27/85 °C.

- **No ringing anywhere:** 0 % overshoot and 0 dB peaking. The response is overdamped.
- **Fix applied:** the pad-follower bias is doubled to **400 µA**. This only costs current while the probe is enabled. DRC and LVS are still clean.
- **1 % settling after the fix:** ≤ 174 ns at 20 pF, **≤ 743 ns at 100 pF** and 1.45 µs at 200 pF.
- **200 pF can't be fixed with current:** the 500 Ω mux alone takes about 0.95 µs to settle there.

**Spec change: 1 % settling is now ≤ 1 µs at ≤ 100 pF and ≤ 2 µs at 200 pF.**
- Bandwidth at 200 pF is still about 0.5 MHz.
- That is far above what the probe has to follow. Membrane τ is 100 µs at S = 100 and 10 µs at S = 1000.
- Spike edges were never meant to go through the analog probe. Spikes go out on digital pins.
- Measure the real board capacitance at bring-up.
