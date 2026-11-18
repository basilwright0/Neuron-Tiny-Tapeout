# neuron_ctrl register map (rev B: byte-addressed SPI register file)

RTL: `rtl/neuron_ctrl.v`. Addresses live in `rtl/nc_regmap.vh` and are mirrored in `test/regmap.py`.
Every writable register resets to **0**, and all-zero means "everything off": master bias off, all groups disabled, probe and one-hot off, rt pass-through off, SC clock stopped, digital LIF disabled, counter cleared.

## 1. SPI protocol

- **Pins:** SCK = `ui_in[0]`, MOSI = `ui_in[1]`, CS_N = `ui_in[2]`, MISO = `uio_out[0]` (`uio_oe = 0x01`). Mode 0, MSB first.
- **Frame:** one 16-bit frame per CS_N assertion, `{RW, ADDR[6:0], DATA[7:0]}`. RW = 0 writes, RW = 1 reads.
- **Write:** after the 16th bit, one 1-clk enable pulse loads that register's latches. The pulse comes 1 clk after the last shift, so the address and data are already stable. Only the addressed byte changes, exactly once (tested).
  - Frames shorter than 16 bits never write.
  - Bits after the 16th are ignored.
  - Writes to read-only or unused addresses are ignored.
- **Read:** the addressed byte comes back in the **same frame**. MISO is 0 during the 8 address bits, and DATA[7:0] arrives on bits 7..0. The DATA bits the master sends during a read are ignored.
- **16-bit values:** reading `CNT_L` (or `LIFV_L`) copies the matching high byte into a HOLD register. `CNT_H` (or `LIFV_H`) then returns HOLD. Always read L, then H.
- **Storage:** the registers are latches with async reset (latrnq), 138 bits in all. Spare bits read back 0 and drive 0 on `cfg_out`.
- **cfg_out[159:0]:** byte *a* (addresses 0x00..0x13) sits at `cfg_out[8a+7:8a]`. This is the analog-side bus.

### Timing (clk oversamples SCK)

SCK, MOSI and CS_N each pass through a 2-FF synchronizer.

| Requirement | Min |
|---|---|
| f_clk / f_SCK | **6** (tested at 6, 8 and 10 with random phase); **8 recommended** |
| SCK high, SCK low | 2 clk each |
| MISO valid after an SCK rising edge | ≤ 4 clk + pad |
| CS_N fall → first SCK rise | 4 clk |
| CS_N high between frames | 4 clk |

A 16-bit frame at clk 20 MHz and SCK 2.5 MHz takes about 7 µs.

## 2. Writable registers (0x00..0x13)

| Addr | Name | Bits | Meaning |
|---|---|---|---|
| 0x00 | CTRL | [0] SPK_MODE | uo[5:0] output mode: 0 = stretched pulse, 2 clk, synchronous; 1 = raw async toggle flop (timing-exact, for PIO timestamping) |
| | | [2:1] CNT_MODE | 0 = cleared and held; 1 = run; 2 = count while ui7 = 1 (windows accumulate); 3 = like 2, but each ui7 rising edge clears |
| | | [4:3] CNT_SRC | 0 = neuron SEL0; 1 = OR of enabled groups; 2 = digital-LIF spike; 3 = ui3 stim-A rising edges |
| 0x01 | RT | [3:0] RT_EN | `rt_out` = `ui_in[6:3]` & RT_EN. Bit 0 stim A, 1 stim B, 2 hold, 3 membrane reset. Combinational. |
| | | [7:4] TRIM_EN | **Analog, provisional.** Trim enables |
| 0x02..0x05 | SEL0..SEL3 | [4:0] | Neuron on uo[0..3]. SEL0 also feeds counter source 0 and LIF source 3. |
| 0x06 | PROBE | [4:0] PROBE_SEL | **Analog.** Probe-mux target, decoded to `probe_sel_onehot` |
| | | [6:5] PROBE_SUB | **Analog, provisional.** 0 Vmem, 1 adaptation, 2 dendrite, 3 calibration node |
| | | [7] PROBE_EN | **Analog.** Enables the probe buffer and one-hot. Also switches uo[6] to probe-valid. |
| 0x07 | GRP | [7:0] GRP_EN | **Analog.** Group enables; neuron *i* is in group *i*/4. Also masks the uo[4] OR. |
| 0x08 | DAC_LEAK | [7:0] | **Analog, provisional** bias code |
| 0x09 | DAC_VTH | [7:0] | **Analog, provisional** |
| 0x0A | DAC_VRST | [7:0] | **Analog, provisional** |
| 0x0B | DAC_WSYN | [7:0] | **Analog, provisional** |
| 0x0C | SC | [3:0] SC_DIV | `sc_clk` = clk / 2^SC_DIV (1..15); 0 = stopped low |
| | | [7:6] PLATEAU_EN | **Analog.** Bit 0 D1, bit 1 D2 |
| 0x0D | ANA | [0] BIAS_EN | **Analog.** Master bias enable |
| | | [2:1] UA0_MODE | **Analog, provisional.** 0 ref current in, 1 external stimulus, 2 DAC calibration |
| 0x0E | LIF0 | [0] EN | 0 = V held at EL, ref = 0 |
| | | [2:1] SRC | 0 ui3 stim A, 1 ui4 stim B, 2 DC (weight every tick), 3 analog neuron SEL0 |
| | | [3] STEP | 1 = update on ui7 rising edge instead of the prescaler |
| | | [7:4] PRESC | Tick every 2^PRESC clk. **Use ≥ 6**: an update occupies 2W + SHIFT + 7 clk (≤ 46). Ticks during an update are dropped. |
| 0x0F | LIF1 | [3:0] SHIFT | Leak shift *s*: a = 1 − 2^−s |
| | | [7:4] REFR | Refractory ticks (0..15) |
| 0x10 | LIF_EL | [7:0] | EL = code << (W−8) |
| 0x11 | LIF_VTH | [7:0] | Vth = code << (W−8) |
| 0x12 | LIF_VRST | [7:0] | Vreset = code << (W−8) |
| 0x13 | LIF_W | [7:0] | Input weight in LSB units (unscaled) |

Spare: 20 bits in the used bytes (CTRL[7:5], SEL*[7:5], SC[5:4], ANA[7:3]), plus addresses 0x1A..0x7F.

## 3. Read-only registers

| Addr | Name | Content |
|---|---|---|
| 0x14 | CNT_L | counter[7:0]; also captures counter[15:8] into HOLD |
| 0x15 | CNT_H | HOLD |
| 0x16 | LIFV_L | V[7:0]; also captures `{REF[3:0], V[11:8]}` into HOLD |
| 0x17 | LIFV_H | HOLD |
| 0x18 | STATUS | `{cnt_gate, cnt_saturated, probe_valid, lif_en, lif_input_pending, lif_busy, 0, 0}` |
| 0x19 | ID | 0xA2 |

## 4. Digital LIF (bit-serial)

Update rule, per accepted tick (same order as `model/reference.py` `LIF.simulate`):

```
if ref > 0:  V = VRST; ref -= 1
else:        Vn = clamp(V + ((EL - V) >>> SHIFT) + (input ? W : 0), 0, 2^W - 1)
             if Vn >= VTH: spike; V = VRST; ref = REFR   else V = Vn
```

- **Datapath:** W + 2 bits, LSB first.
  - P1 computes D = EL − V with one serial subtractor, while V rotates.
  - D is then shifted right arithmetically *s* times, in place.
  - P2 computes Vn = D + V + W with two serial adders. Vn shifts into V, and the comparison with Vth runs bit-serially.
  - An overflow beyond W bits forces a spike; this equals saturating, since the maximum is ≥ Vth.
- **Logic depth:** there is no barrel shifter and no wide adder, so the LIF is off the critical path.
- **Mapping to the analog model:** a = 1 − 2^−s = exp(−dt/τ), V∞ = EL + W·2^s, dt = one tick.
- **Floor bias:** `>>>` floors, so the fixed-point rheobase sits slightly above the ideal one.
- **Outputs:** the spike goes to uo[5] and to counter source 2. V and REF are readable at 0x16/0x17.

## 5. Outputs

| Pin | Signal |
|---|---|
| uo[3:0] | Spikes of SEL0..3 |
| uo[4] | OR of `spk_in` & GRP_EN mask |
| uo[5] | Digital LIF spike |
| uo[6] | PROBE_EN ? probe_valid : counter window (gate) active |
| uo[7] | Heartbeat = free_cnt[15]: clk/65536, i.e. 153 Hz at 10 MHz |
| uio[0] | MISO; uio[7:1] = 0, oe = 0 |

- **probe_sel_onehot:** break-before-make. When PROBE_SEL changes, all outputs go 0 for 2 clk, then the new bit rises. The outputs are AND(registered enable, decode(registered select)), so they are glitch-free.
- **probe_valid:** rises 128–256 clk (`SETTLE_BIT` = 6) after the last PROBE write or select change, i.e. 6.4–12.8 µs at 20 MHz.

### Spike capture and metastability

Each selected asynchronous line (and the OR) clocks its own toggle flop, so any pulse above about 1 ns is captured; a 20 ns pulse at 10 MHz is tested at random phase.

- **Synchronization:** the toggle passes a 2-FF synchronizer and a 2-deep delay line.
  - The clk-domain event (for the counter and LIF) is `tog_s ^ dl[0]`.
  - The stretched output is `tog_s ^ dl[1]`, a 2-clk pulse.
  - Only the first synchronizer flop can go metastable; a late resolution delays the event by 1 clk.
- **Latency and rate:** latency is 2–3 clk, with 1 clk of jitter. The countable rate is ≤ f_clk/3.
- **Exact timing:** mode 1 outputs the raw toggle flop, with no clk latency.
- **Write blanking:** counter and LIF events are blanked for 5 clk after every write, which absorbs mux-reselection glitches. The stretched *output* is not blanked, so a SEL write can show one spurious 2-clk pulse.

## 6. Parameters

| Parameter | Default | Area effect (yosys, flattened, tt 3.3 V) |
|---|---|---|
| `LIF_W` | 12 | 8: −1.0k µm² |
| `CNT_W` | 16 | 12: −0.7k µm² |
| `RB_REGS` | 1 | 0 (writable registers not readable; read-only registers still work): −2.2k µm² |
| `STRETCH` | 2 | +1 flop per channel per extra clk |
| `HB_BIT` | 15 | > 15 adds free-counter bits |
| `SETTLE_BIT` | 6 | — |
