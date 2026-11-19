# r1_corner: R1 pad driver + bias receiver + Vreset buffer + vsrc buffer (gf180mcuD, 3.3 V devices)

Schematic: `cells/readout/r1_corner.spice`. It instantiates `pad_psf` from `cells/readout/readout.spice`, `vreset_buf` from `cells/vreset/vreset_buf.spice` and `vsrc_buf` from `cells/vsrc/vsrc_buf.spice`.
The in-cell probe followers (`prb_nsf`) live in the array slots, not here.

Layouts:
- `r1_corner.mag` and `out/r1_corner.gds`: the 40 × 40 µm box at tile (262, 14)–(302, 54).
- `out/r1_ua1.gds`: the same box placed at tile y 14, plus the ua[1] strap through CH_BOT (origin = tile (262, 0)).

Everything here is generated. Do not hand-edit the `.mag` files.

## Flow (from the repo root, Git Bash)

    scripts/eda.sh "bash layout/readout/build.sh"          # devices -> generate -> DRC -> LVS -> PEX
    scripts/eda.sh "bash layout/readout/build.sh nogen"    # re-verify only
    # SKIPDEV=1 keeps devices/*.mag

| Step | File |
|---|---|
| Transistors: one PDK cell per size, `gf180mcu::{n,p}fet_03v3_draw`, multi-finger, guard 0, no gate contacts | `gen_devices.tcl`, `devices/devlist.tcl` -> `devices/*.mag` |
| Placement, gate bars, tap rings, straps, routing (hand-placed in code, no router: 18 devices) | `r1gen.py` -> `r1_corner_base.mag`, `r1_corner_paint.tcl`, `r1_ua1_paint.tcl`, `preview.png` |
| Magic: draw, DRC `drc(full)`, GDS, LVS netlist, PEX (`ext2spice cthresh 0`); then the r1_ua1 wrapper | `build.tcl` -> `out/` |
| netgen LVS against the flat reference | `r1_corner_lvs.spice` -> `out/r1_corner_lvs_report.txt` |
| KLayout `gf180mcu.drc`, `variant=D`, `run_mode=flat`, `decks=all,-density`, both cells | `out/*_klayout_drc.lyrdb` |

## Status

| Check | r1_corner | r1_ua1 |
|---|---|---|
| Magic DRC, `drc(full)` | 0 | 0 |
| KLayout gf180mcu DRC (variant D, flat, all decks except density) | 0 | 0 |
| netgen LVS | Circuits match uniquely, no property errors | (wire only) |

## Floorplan (µm, origin at the box lower-left)

- **Box:** 40 × 40, now filled edge to edge (the vsrc buffer took the free corners). A p-tap (vss) ring 0.6 wide runs on all four edges.
- **Bottom band, pad n-well (body = pad):** XPF (W40/L0.5, 8 × 5/0.5), the PMOS pad follower.
  - Its sources go to a 1.0 µm Metal2 bar with two via1 per stripe, then through a via2 array to the ua[1] Metal3 strap.
  - The strap is 6 µm wide at x 18.64–24.64 (tile 280.64–286.64) and leaves the bottom edge.
  - The n-tap ring is tied to the pad bar.
  - Its drains go to a 1.0 µm Metal2 vss bar that runs east to the vss rail.
- **Middle band, vdd n-well:**
  - XPT, the Vreset tail (W3/L1, 3 × 1/1).
  - XPR, the receiver diode (W0.4/L1).
  - XPB, the pad bias (W40/L1, 10 × 4/1).
  - XPE, the enable switch (W10/L0.28, 2 × 5/0.28).
  - XPB's drains (pad) reach the strap through a 2 µm Metal3 vertical at x 22.5–24.5.
- **Upper band:**
  - Left: the input pair XM1/XM2 (each W20/L0.5, 4 × 5/0.5) in an n-well tied to the tail t.
  - Right: the NMOS mirror XN1/XN2 (each W4/L2, 2 × 2/2) in a p-tap ring.
- **Top:** XPD (W0.22/L20), the always-on abus pull-down. Its gate is on vdd.
- **vsrc buffer** (`vsrc_buf`, 8 devices, all inside the box):
  - Region A, bottom left (x 1.2–13.8, y 1.4–13.4): input pair XVB (gate vth_ref) / XVA (gate vsrc), each W10/L2 (2 × 5/2), tail XVT (W0.22/L2) and pull-up XVU (W1.6/L1). Their n-well is merged into the band-2 vdd well, whose ring is their n-tap (pair bodies on vdd). XVT's drain drops straight onto XVB's right source stripe.
  - Mirror/shunt row inside the Vreset-mirror p-tap ring, above XN1/XN2 (y 31–34.5): XVNA (diode) / XVNB, W1/L4, and the shunt XVS (W10/L0.5, 4 × 2.5/0.5). The ring now spans x 16.2–34.8, y 25.6–35.9.
  - Region B, bottom right (n-well x 29.1–37.8, y 1.1–10.9): the Miller cap XVC, a pfet W8/L7 in accumulation (gate = o; S/D, n-well and an n-tap strip at y 1.55 = vsrc). It sits under the vss rail and the XPF vss Metal2 bar (no shared layers).
  - Long nets in Metal3: a2 at x 13.70 (y 4–35), o at x 32.31 (y 11–34), vsrc at x 34.00 (y 1.5 → top-edge pin), vth_ref at x 2.00 (y 7.4 → top-edge pin). Region A reaches them over Metal2 runs at y 11.2 (o) and 12.0 (vsrc). The ibias Metal3 line is extended down to XVU's gate (y 10.85).
- **Layers:** Metal1–3 only. r1_corner has no Metal4. The only Metal4 is in r1_ua1, at the pin footprint y 0–1, outside the box.

Pins:

| Pin | Layer | x (box) | Notes |
|---|---|---|---|
| pad | Metal3, bottom edge | 18.64–24.64 | → ua[1] (r1_ua1 continues it to tile y 0) |
| vrin | Metal3, top edge | 4.60 | B1 `vreset_src` (VDAC tap) |
| ibias | Metal3, top edge | 12.30 | B1 `ib_r1`. B1 sinks 4 µA out of this pin. Pad bias is 100× (400 µA); the Vreset tail is 7.5× (30 µA); the vsrc buffer takes ~1.1 µA (tail) + 16 µA (pull-up). |
| vreset | Metal3, top edge | 15.20 | buffered Vreset → CH_MID → array column line + D1 |
| abus | Metal3, top edge | 18.10 | probe bus from the array |
| en_b | Metal3, top edge | 29.02 | pad-driver enable, active low |
| vth_ref | Metal3, top edge | 2.00 | B1 `vth_ref` (VDAC2 tap, 0.35–0.75 V, high-Z; gate input only) |
| vsrc | Metal3, top edge | 34.00 | buffered AH detector source rail → 13 array slots + D1 (`vsrc` and `vsrcp`) |
| vdd | Metal3 rail, full height | 35.0–36.5 | |
| vss | Metal3 rail, full height | 37.3–38.8 | also the edge p-tap ring |

## Current density and robustness

- **Pad current, 400 µA:**
  - XPF has 5 source stripes × 2 via1 (40 µA per cut). The pad bar is 1.0 µm Metal2, with 18 via2 into a 6 µm Metal3 strap.
  - XPB has 5 drain stripes × 2 via1, a 1.0 µm Metal2 bar, and 6 via2 into a 2 µm Metal3 vertical.
  - The narrowest metal carrying the full 400 µA is 1.0 µm. I have not checked this against the PDK current-density table.
- **No gate on the pad node.** The pad sees only diffusion: XPF source and well, and XPB drain. Its n-well/p-sub junction is a large diode to vss.
- **Tap rings:** every device group has a tap ring, and every NMOS is within 2 µm of a p-tap.

## Measured

PEX is in `out/r1_corner_pex.spice` (C only, all coupling).

**Pad bias is 400 µA** (receiver W0.4/L1, XPB 100×) since 2026-11-18. TT GF dies are chip-on-board, so a whole breakout board is always on ua[1].

**Pad-load sweep** (`python3 sim/tb/tb_readout.py slot pex cb <pF> nokick`, 15 corner/temperature cases each):

| board C (after 500 Ω) | 1 % settling, 200 µA (old) | 1 % settling, 400 µA (now) |
|---|---|---|
| 20 pF | 173–208 ns | ≤ 174 ns |
| 50 pF | 384–464 ns | (not re-run) |
| 100 pF | 737–892 ns | ≤ 743 ns |
| 200 pF | 1.44–1.75 µs | ≤ 1.45 µs |

- Outputs are in `out/readout_slot_pex_cb*.txt` (200 µA) and `out/readout_slot_pex400_cb*.txt` (400 µA).
- **Stability:** 0.00 % step overshoot and 0 dB AC peaking everywhere. The response is overdamped.
- **Gain and range:** gain is 0.670–0.709. The transfer stays linear up to vm = 2.1 V; the highest pad voltage is 2.28 V at fs.
- **The 500 Ω mux sets a floor.** Its RC alone gives about 0.47 µs per 100 pF to reach 1 %, so no amount of pad current gets 200 pF under 1 µs.

**Vreset buffer** (`python3 sim/tb/vreset/tb_vreset.py pex corners typical:27,fs:85,ss:85,ff:0`, `sim/tb/vreset/out/vreset_pex.txt`):
- After 20 membranes reset (19 × 200 fF + 1 × 800 fF, from vreset + 0.2 V), the line is back within 5 mV in 110–140 ns.
- Phase margin is ≥ 78°. Quiescent current is 32 µA with the pad driver off.
- **Offset Monte Carlo** (`sim/tb/vreset/mc_offset.py`, 40 seeds, typical, 27 °C, `sim/tb/vreset/out/vreset_mc.txt`): σ = 2.8 mV. The mean is +0.4, −1.3 and −2.7 mV at vin 0.9, 1.2 and 1.5 V, and the worst seed is −7.3 / +8.1 mV.

**vsrc buffer** (`cells/vsrc/vsrc_buf.spice`; testbench `sim/tb/vsrc/tb_vsrc.py {dc|ac|spk} [pex]`, results in `sim/tb/vsrc/out/`):
- **Topology:** two-stage. PMOS-input 5T OTA (pair W10/L2, bodies on vdd; nfet mirror W1/L4; tail ~1.1 µA from vbp) drives an nfet shunt XVS (W10/L0.5) on vsrc; a pfet pull-up XVU (~16 µA from vbp) keeps the shunt biased. Miller cap XVC (pfet accumulation, W8/L7, ~120 fF) from o to vsrc. The detectors only ever sink into vsrc, so the output only needs a strong pull-down.
- **Static current:** 16.5 µA (plus the shared 4 µA receiver). R1 total with the pad driver off is now 48.5 µA.
- **DC** (15 corner × temperature cases, vth_ref 0.35/0.55/0.75 V; schematic and PEX): offset −0.07 to −0.15 mV. A 32 µA DC sink load (16 detectors × 2·I_st at S = 1000) moves vsrc by ≤ 0.2 mV. Full 0.35–0.75 V range at every corner.
- **Offset Monte Carlo** (`sim/tb/vsrc/mc_offset.py`, 40 seeds, typical, `out/vsrc_mc.txt`): σ = 2.4 mV (worst −7.3 / +4.6 mV), the same at 0.35, 0.55 and 0.75 V. Per-seed drift from 0 to 85 °C: σ 0.06 mV, max 0.10 mV. So the per-die threshold calibration removes the offset, and it does not come back with temperature.
- **Loop** (A = H/(1−H); line = 3 × 33 Ω / 20 fF, plus 14 idle lif_ah and 2 pdet): PEX phase margin ≥ 56° (line only ≥ 60°), f_u 5–15 MHz, A0 ≥ 54 dB, over 15 corner × temperature cases × vth_ref 0.35/0.75 V (`out/vsrc_pex_ac.txt`). Schematic: ≥ 59°.
- **Spike pulses** (`spk`; S = 1000, vth_ref calibrated per corner so the AH trips at 1.28 V, spikers on the far tap). The line does **not** stay within 2 mV. The cause is `det_ah` itself, not the buffer:
  - With an ideal vsrc source, each detector draws ~40 µA for ~0.3 µs while vm crosses threshold. This is crowbar current in its third stage (XP3/XN3), which is not starved; ~3.8 pC per neuron.
  - 1 neuron spiking: +64 to +89 mV peak, −23 to −40 mV undershoot, back within 2 mV in 54–68 ns.
  - 4 neurons together (15 corners): +171 to +229 mV peak (PEX +178 to +240 mV), −53 to −88 mV, back within 2 mV in 63–98 ns.
  - 13 neurons together: at typical/27, ff/85 and sf/85 it falls into a relaxation oscillation (vsrc swings 0.18–0.65 V with a ~1.1 µs period). The undershoot puts the trip below vreset, so neurons that are being reset re-trip. A smaller or larger shunt (W2.5–W20) and a 32 µA pull-up did not fix it.
  - What-if detector (testbench only): starving XP3 from vbp_st (`st3`), and also moving XN3's source to vss (`st3v`). With 4 neurons: +47 / +28 mV. With 13 neurons: +79 / +58 mV, recovered in ~70 ns, no oscillation. This is the slot track's call.
