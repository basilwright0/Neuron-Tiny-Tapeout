# R2 B1 re-pack: handoff (MIL-344, branch `r2-b1-pack` off main `fdcf2ad`)

`main` is the submission candidate. Nothing here is merged or pushed.

## Step 1: measurement (fdcf2ad)
- **B1:** frame 242 × 114.5 at tile (103, 12), with notches N1 (R1, 40 × 42) and NB (28 × 40, empty).
  - Net area 25,030 µm²; the 19 leaves cover 16,875 µm² (67 %).
  - Column gaps are already tight (2.8–3.6 µm). The slack is in C4 + NB (local 131–159), above the rails
    (local 156–200 × 82–115), and in the east strips.
- **Tile free space** (M1–M3 empty, `area_free.py`; logs in untracked `work_b1r/`): 15,637 µm² (13.9 %), but
  fragmented.
  - Only NB (28 × 51.8, RESERVED RB) can take a 28-wide slot.
  - RW (22.8 × 104.6) is too narrow.
  - If top routing were ignored, CH_ROW (x 120–170, y 213–325) would be the next big area.
- **Neuron add requirements:**
  - All 16 `spk_in` channels and all 16 spike output pins (`uo_out`, `uio_out`) are used.
  - A full-peer neuron therefore needs a macro RTL change plus re-harden (`spk_in` width, output mux, SEL bit 4).
  - S/F/AH need no new B1 output and no config bits. H/P/CMP need trim nibbles: GRP_EN is one latched nibble that
    is currently unused.

## Step 2/3: options (detail in the Paperclip doc `b1-repack`)
- **A (chosen): west trim.**
  - C4 is removed: idac_p Xi0 goes to the top of C1, Xi1 goes over N1 rotated (above the rails), and the receivers
    are re-packed around Xi0 in C1.
  - The frame becomes 214 × 115 at tile (131, 12). B1's east group, R1/N1, the corridor, ua[0], vdd/vss and all
    digital pins keep their tile positions. The 10 analog outputs keep their local x.
  - Freed: one contiguous bay, tile x 80–129 × 12–116, which takes one column of 3 compact slots plus a ~20 µm
    channel.
- **B: in-place pocket.** Same leaf moves, west edge kept. This gives a 28 × ~106 pocket inside B1 with no side
  channel, and RW stays unusable.
- **C: also drop the corridor / compress the east group.** It cannot reach a second slot column with the current
  leaves.
- **D (tile, not B1):** a 5th array column at x 120–148 in rows 2–3 (CH_ROW), giving +2 compact slots. It is
  independent of B1.

## Step 4: implementation status
- `layout/bias/topgen.py`: `B1_R2=1` (the default on this branch) is the option A placement. `place_f` reports no
  overlaps: 214 × 115, net 22,930 µm².
- B1 full route is on the VM: jobs `r2b1s0/route` and `r2b1s1/route` (PYTHONHASHSEED 0 / 1), submitted 18:10 UTC
  2026-11-24. Results come back with `bash /home/basil/tt-m3/vmwait.sh r2b1s0 route` (into `layout/bias/out`,
  `bias_b1*.mag`).
- **Still to do after the route:**
  1. Pick the clean seed. Check magic DRC, KLayout DRC and LVS from the job logs. Adapt `chk_frame.py` (no NB,
     214 frame, pins = shifted `b1_pins_242.json`).
  2. Top level:
     - `floorplan.py`: B1_BOX (131, 12, 345, 126.5), notches = R1 only, RESERVED RW → bay (80, 12, 129, 116),
       drop RB; update `b1_rects()`.
     - `geom.py blocks_power`: the bx = 103 assert; the east vss/vdd hookup local x −28; re-derive the west power
       entry, because the x 121/123.6 stripes are no longer over B1 (use the 185.9/189.2 strap-pair-0 stripes and
       trace B1's Metal3 vdd/vss lines).
     - `route.py reroute` of the 10 analog outputs and any nets that `route.py check` flags.
  3. VM: `layout/top/vm_top3.sh` (LVS, KLayout/antenna, magic, TT precheck) plus B1 PEX DC with
     `sim/tb/bias/b1int_pex3.py` (new vs M3 PEX).
  4. Renders: `tools/render_labeled.py` from branch `renders` on the new GDS (before/after).
