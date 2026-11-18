# neuron_ctrl configuration map (rev C: write-only latches)

RTL: `rtl/neuron_ctrl.v` (top), `rtl/nc_cfg.v` (config port), `rtl/nc_sync.v` (sync, latch, SC divider), `rtl/digital_lif.v`.
Addresses and the `cfg_out` packing live in `rtl/nc_regmap.vh` and are mirrored in `test/regmap.py`.
Rev B (SPI register file with read-back, counter, spike muxes) is preserved in `rtl/revB/` and `test/revB/`.

Rev C keeps only the configuration storage, the probe decoder, the digital LIF and the SC clock on chip. Everything else (spike timestamping and counting, tick generation, sequencing, read-back of state) is done by the demo-board RP2040/RP2350 (PIO).

Every byte resets to **0**, and all-zero means "everything off": bias off, all groups disabled, probe off, rt pass-through off, SC clock stopped, digital LIF disabled, OUT_MUX = 0.

## 1. Pins

| Pin | Dir | Signal |
|---|---|---|
| ui[0] | in | **SCK**: config shift clock (rising edge) |
| ui[1] | in | **DATA**: config serial data, MSB first |
| ui[2] | in | **LOAD**: config latch strobe (high = write) |
| ui[3] | in | stim A: `rt_out[0]`; LIF event source 0 |
| ui[4] | in | stim B: `rt_out[1]`; LIF event source 1 |
| ui[5] | in | hold: `rt_out[2]` |
| ui[6] | in | membrane reset: `rt_out[3]` |
| ui[7] | in | **LIF tick**: one digital-LIF update per rising edge |
| uo[7:0] | out | spikes of analog neurons 0..7 (combinational, buffered) |
| uio[5:0] | out | spikes of analog neurons 8..13 (combinational, buffered) |
| uio[6] | out | OUT_MUX = 0: digital-LIF spike (1-clk pulse); OUT_MUX = 1: neuron 14 |
| uio[7] | out | OUT_MUX = 0: config echo (shift-register MSB); OUT_MUX = 1: neuron 15 |

`uio_oe` = 0xFF (all uio pins are outputs). `uio_in` is unused.
`rt_out` = `ui_in[6:3]` & RT_EN, combinational.

## 2. Write protocol

- **Frame:** 13 bits `{ADDR[4:0], DATA[7:0]}`, MSB first. DATA is sampled on each SCK rising edge into a 13-bit shift register (clocked directly by the pin; no clk needed, no oversampling).
- **Only the last 13 bits before LOAD count.** A PIO can therefore send 16-bit words with 3 leading don't-care bits (tested), or any longer stream.
- **Write:** pulse LOAD high. While LOAD is high, the latch byte `ADDR` is transparent and takes `DATA`; LOAD falling closes it. Exactly one byte changes, once (tested with LOAD widths of 10 ns to 500 ns).
- **SCK with LOAD low never writes** (tested with 200 random bits).
- Writes to unused addresses (0x1A..0x1F, and trim bytes beyond `NTRIM`) are ignored.
- There is no read-back. Link check: with OUT_MUX = 0, uio[7] = shift-register MSB, so every bit shifted in reappears on uio[7] 13 SCK rising edges later (it changes just after each SCK rising edge; sample it before the next one). Before the first 13 SCK edges after power-up the echo is undefined (the shift register has no reset).
- The config port and latches do not use clk; they work with clk stopped (tested).
- **Reset:** `rst_n` low clears every latch asynchronously (directly from the pin, no clk needed). LOAD has no effect while `rst_n` is low.

### Timing contract (host)

```
          ___     ___           ___                                   ___
SCK   ___|   |___|   |__ ... __|   |_________________________________|   |__
      <D12 ><D11 >      ...  <D0  >
DATA  ======X=====X=====...==X=====X==================================X====
                                    |<-t_su->|_____________|<-t_h->|
LOAD  ______________________________________|  t_load      |__________________
                                             latch[ADDR] transparent
```

| Requirement | Min | Notes |
|---|---|---|
| SCK high, SCK low | 20 ns | simulated down to 10 ns |
| DATA setup / hold to SCK rising | 5 ns | |
| t_su: last SCK rising → LOAD rising | 50 ns | decode settles (simulated at 20 ns) |
| t_load: LOAD high | 50 ns | simulated 10 ns..500 ns |
| t_h: LOAD falling → next SCK rising | 50 ns | latch closes before the frame moves |

The latch enable is `le[a] = LOAD & (sr[12:8] == a)`. Because SCK has no edge from t_su before LOAD rises until t_h after LOAD falls, the address decode and the latch D inputs are static whenever LOAD can be 1; each `le` is then an AND of a static level with one pin, which cannot glitch. The 50 ns figures leave margin for pad/TT-mux delay and the ss corner (the decode is ~3 gate levels). At 10 MHz SCK one write takes ≈ 1.5 µs.

### Clock-domain crossing rules (firmware)

- **LIF_EN** is 2-FF synchronized into clk (latency 1–3 clk).
- **All other digital-LIF fields** (LIF_SRC, LIF_SR, LIF_EL/VTH/VRST/W) are used without synchronization: change them **only while LIF_EN = 0**. Sequence: write CLKD with LIF_EN = 0, wait ≥ 3 clk, write parameters, write CLKD with LIF_EN = 1. (While disabled the LIF holds V = EL, ref = 0 and clears its pending input, so mux-switch glitches are discarded.)
- **SC_DIV** is used asynchronously by the divider; a change may produce one irregular sc_clk period. If that matters, write SC_DIV = 0 first.
- Rewriting a byte with an unchanged field does not disturb that field (a transparent latch fed the same value).
- **Probe:** no on-chip break-before-make. To move the probe: write PROBE with EN = 0 and the *old* SEL, then EN = 0 with the new SEL, then EN = 1 with the new SEL. (Changing EN and SEL in one write could briefly enable the new tap before the old one is off.)

## 3. Map (5-bit address, 26 bytes)

| Addr | Name | Bits | Meaning |
|---|---|---|---|
| 0x00..0x05 | IDAC0..5 | [4:0] FINE, [7:5] RANGE | **Analog.** Current DAC k: 3-bit range code + 5-bit fine code |
| 0x06..0x08 | VDAC0..2 | [5:0] | **Analog.** Voltage DAC k (6 bit); [7:6] no storage |
| 0x09 | ANA | [3:0] GRP_EN | **Analog.** Group enables |
| | | [5:4] PLATEAU_EN | **Analog.** Bit 0 D1, bit 1 D2 |
| | | [6] BIAS_EN | **Analog.** Master bias enable |
| 0x0A | PROBE | [3:0] PROBE_SEL | Neuron 0..15 → `probe_sel_onehot` |
| | | [5:4] PROBE_SUB | **Analog.** 0 membrane, 1 adaptation, 2 dendrite, 3 reference |
| | | [6] PROBE_EN | **Analog.** Probe buffer enable; `probe_sel_onehot` = PROBE_EN ? 1 << SEL : 0 |
| 0x0B | MODE | [1:0] UA0_MODE | **Analog.** ua[0] mode (0 ref current in, 1 external stimulus, 2 DAC calibration) |
| | | [2] OUT_MUX | 0: uio[6] = LIF spike, uio[7] = echo; 1: uio[7:6] = neurons 15:14 |
| | | [7:4] RT_EN | `rt_out` = `ui_in[6:3]` & RT_EN (bit 0 stim A, 1 stim B, 2 hold, 3 mem reset) |
| 0x0C | CLKD | [3:0] SC_DIV | `sc_clk` = clk / 2^SC_DIV (1..15), 50 % duty; 0 = stopped low |
| | | [4] LIF_EN | Digital LIF enable (2-FF synchronized) |
| | | [6:5] LIF_SRC | LIF input event: 0 ui3 stim A, 1 ui4 stim B, 2 DC (weight added every tick), 3 analog neuron 0 spike |
| 0x0D | LIF_SR | [3:0] SHIFT, [7:4] REFR | Leak shift *s* (a = 1 − 2^−s); refractory ticks 0..15 |
| 0x0E | LIF_EL | [7:0] | EL = code << (W − 8) |
| 0x0F | LIF_VTH | [7:0] | Vth = code << (W − 8) |
| 0x10 | LIF_VRST | [7:0] | Vreset = code << (W − 8) |
| 0x11 | LIF_W | [7:0] | Input weight in LSB units (unscaled) |
| 0x12..0x19 | TRIM0..7 | [3:0] neuron 2k, [7:4] neuron 2k+1 | **Analog.** 4-bit threshold trim of neuron n at byte 0x12 + n/2, nibble n%2. Only the first `NTRIM` neurons have storage. |

Spare (no storage): VDAC*[7:6], ANA[7], PROBE[7], MODE[3], CLKD[7].
Stored bits: 48 IDAC + 18 VDAC + 7 ANA + 7 PROBE + 7 MODE + 7 CLKD + 40 LIF + 4·NTRIM trim = **134 + 4·NTRIM** (198 latches at NTRIM = 16, 150 at NTRIM = 4).

### cfg_out (analog bus)

`cfg_out[78+4·NTRIM−1:0]` carries only the analog bits, packed without gaps (142 bits at NTRIM = 16):

| cfg_out bits | Field |
|---|---|
| [8k+7 : 8k], k = 0..5 | IDAC k ({RANGE, FINE}) |
| [48+6k+5 : 48+6k], k = 0..2 | VDAC k |
| [67:66] | PROBE_SUB |
| [68] | PROBE_EN |
| [72:69] | GRP_EN |
| [74:73] | PLATEAU_EN |
| [75] | BIAS_EN |
| [77:76] | UA0_MODE |
| [78+4n+3 : 78+4n], n = 0..NTRIM−1 | TRIM n |

Other analog-side outputs: `probe_sel_onehot[15:0]`, `rt_out[3:0]`, `sc_clk`.

## 4. Digital LIF (bit-serial)

Update rule, per accepted tick (same order as `model/reference.py` `LIF.simulate`):

```
if ref > 0:  V = VRST; ref -= 1
else:        Vn = clamp(V + ((EL - V) >>> SHIFT) + (input ? W : 0), 0, 2^W - 1)
             if Vn >= VTH: spike; V = VRST; ref = REFR   else V = Vn
```

- **Tick:** `ui_in[7]` → 2-FF sync → rising-edge detect → 1-clk tick, 2–3 clk after the pin edge. Keep ui7 high ≥ 2 clk and low ≥ 2 clk. An update occupies 2W + SHIFT + 7 clk (≤ 46 clk at W = 12); **ticks during an update are dropped**, so space ticks ≥ 48 clk (64 used in the tests). There is no on-chip prescaler: the PIO generates ticks (fixed rate, or single-step).
- **Input event:** the LIF_SRC-selected line clocks a toggle flop (captures any pulse ≳ 1–2 ns, e.g. a short analog spike), which is 2-FF synchronized; one 1-clk event per rising edge. Events must be ≥ 3 clk apart (two edges inside 2 clk cancel). At most one weight is added per tick (pending flag), as in rev B.
- **Datapath:** W + 2 bits, LSB first (P1: D = EL − V; arithmetic shift; P2: Vn = D + V + W with bit-serial compare). Overflow forces a spike (equals saturation).
- **Output:** the spike (1-clk pulse, a flop output) is on uio[6] when OUT_MUX = 0. There is no read-back of V; the tests check V against the bit-exact model through the hierarchy.
- **Mapping to the analog model:** a = 1 − 2^−s = exp(−dt/τ), V∞ = EL + W·2^s, dt = one tick.

## 5. Clock domains

| Domain | Contents |
|---|---|
| SCK (ui[0]) | 13-bit shift register only (dffq, no reset) |
| none | 198 config latches (latrnq), enable = LOAD & decode, reset = rst_n pin |
| event | LIF event toggle flop, clocked by the LIF_SRC mux output |
| clk | reset bridge (async assert, 2-FF deassert), tick sync, event sync, LIF_EN sync, digital LIF, SC divider |

`sc_clk`: synchronous 15-bit counter (cleared while SC_DIV = 0), output = re-registered counter bit SC_DIV − 1. Ripple-free, glitch-free, 50 % duty.

## 6. Parameters

| Parameter | Default | Effect (yosys, flattened, tt 3.3 V) |
|---|---|---|
| `LIF_W` | 12 | digital LIF state width 8..12; W = 8: −0.78k µm² |
| `NTRIM` | 16 | neurons with a 4-bit trim (even, 2..16); NTRIM = 4: −2.54k µm² (48 latches fewer) |

Flattened cell area (yosys, tt 3.3 V): W=12/NTRIM=16 **21.74k µm²**, W=8/16 20.96k, W=12/4 19.20k, W=8/4 18.53k. Rev B was 37.4k.

Hardened (LibreLane, `rtl/librelane/config.json`, Metal4 max, W=12/NTRIM=16): die **182 × 182 µm** (33.1k µm²), stdcell area 25.8k µm², 92.8 % utilization, DRC/LVS/antenna clean, worst setup slack +2.59 ns at ss 125 °C 3.0 V (25 ns clock), hold +0.25 ns (ff). 180 × 180 is routable but misses 25 ns at ss by 2.1 ns.
