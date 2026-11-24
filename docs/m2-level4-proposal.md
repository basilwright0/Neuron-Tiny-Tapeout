# M2 phase 1c: 10000× level 4 (leak OTA) proposal, schematic (2026-11-22)

Status: **schematic verified, not committed, no layout change made.** Base `m2-compact` @ b283ae9. User decision 14:40 UTC: add
level 4 to M2 so the 10000× gate also passes at ss/0 °C. Logs: `sim/results/level4/` (`fi_summary.txt`, `leak4_*.txt`,
`leak4_mc_*.txt`, `d1_run_*.log`). Benches: `sim/tb/speed/tb_leak4.py` (new, OTA DC/AC + mismatch MC), `tb_fi.py` via
`run_l4fi.sh`, `tb_d1.py` via `run_l4d1.sh` (new env `D1_REPL`, `D1_DEL`), `summarize_l4fi.py`.
Pass band (speed-limits / level-3 §6): f/f_ideal normalised to the same cell's S = 100 run, 0.7–1.4 at k = 1.1…8 × rheobase.

## 1. Root cause (reproduced): tail headroom, not bandwidth
`leak_ota_deg` (in 4/1, degeneration diodes 8/1, tail 2/4) needs EL ≥ Vgs(input, with body effect) + Vgs(diode) + Vds,sat(tail).
Ib = 324 pA × S/100, so at S = 10000 every device carries 100× the current and each Vgs grows by ~n·UT·ln 100 ≈ 0.15 V.

| ss/0, vm = EL | S = 100, EL 1.3 | S = 10000, EL 1.3 | S = 10000, EL 1.5 (level 1) |
|---|---|---|---|
| tail node t | 87 mV | **2 mV** (tail nFET in deep triode) | 22 mV |
| real tail current / Ib | 0.97 | **0.08** | 0.65 |
| g/Ib (S/A, nominal 6.3) | 6.50 | 0.52 | 4.11 |
| g vs linear scaling from S = 100 | 1.00 | **0.079** | 0.61 |
| linear range below EL / Isat+ | 81 mV / 98 % | 18 mV / 4 % | 29 mV / 42 % |
| f3dB / (g/2πC) | 1.00 | 1.00 (bandwidth is not a limit) | 1.00 |
| slot_ah f–I, normalised (k = 1.1 … 8) | 1.00 | **2.10** … 1.10, rheobase 0.13× | **1.48** … 1.08, rheobase 0.76× (FAIL) |

The stack would need ~1.6 V at full current against 1.3 V. Same failure, same subckt devices, in every OTA copy:
S/F/H/P/CMP/AH50/AH400 (`leak_ota_degx`), D1 soma + d1/d2 leaks (`leak_ota_deg`/`_dega`) and its 4 axial OTAs (`ax_ota_h`),
AdEx (`leak_ota_deg`). tt/27 and ff/85 pass at 10000 (g 0.90–0.91×). ss/0 base fails at EL 1.5 too for S (1.48), AH400 (1.43)
and AH50 (1.59); H (1.38), F (1.25) and CMP (level-3 tail, 1.09) scrape through. D1 at EL 1.5 ss/0: d1 rest −28 mV, atten 0.50.

## 2. What does not work (DC, `leak4_*.txt`, ss/0, S = 10000)
- **Wider devices** (roadmap level 4, in 16/1 + diodes 32/1, 4× gate area): g 0.28× at EL 1.3; passes only at EL 1.5 (0.92×),
  i.e. no better than the in-footprint fix below, at ~+10 % slot area and a re-search of every compact cell.
- **Any W/L at EL 1.3:** W/L buys n·UT·ln(ratio) ≈ 30 mV per 2× per device; ~0.3 V is missing. Best in-footprint at EL 1.3 is 0.5×.
- **No degeneration:** headroom fine, but g/Ib 14 and linear range 32–58 mV (spec ≥ 75): changes the f–I shape, no.
- **p-input flip** (bodies at vdd): fails at ss/0 (g 0.56×, tail at 3.26 V); only with **source-tied n-wells** does it pass at
  EL 1.3 (g 0.84×, all metrics) — +3 devices and 2 separate wells per OTA, a new topology in 10 cells. Not doable for Dec 1.
- **A fixed bias leg (level-3 style):** not applicable. The tail current *is* the neural conductance and must scale with S.

## 3. Proposal
**Option 1 (recommended hardware fix, L05): inputs XM1/XM2 4/1 → 4/0.5 and diodes XD1/XD2 8/1 → 8/0.5, same W, drawn in the old
1 µm slots.** Only `leak_ota*` subckts (+ D1's identical `ax_ota_h`). W/L 2× plus short-channel Vt roll-off lowers the stack.
Works **with the level-1 operating point EL/Vth/Vreset = 1.50/1.58/1.50 V at S = 10000** (which the gate benches use); at EL 1.3
nothing in-footprint passes ss/0 at 10000 (§2). Diff (uncommitted, `git diff cells`):

    cells/neuron/membrane.spice  .subckt leak_ota_deg  ... wi=4u li=0.5u ... wd=8u ld=0.5u   (was li=1u ld=1u; + note)
    cells/neuron/slot.spice      .subckt leak_ota_degx ... wi=4u li=0.5u ... wd=8u ld=0.5u   (was li=1u ld=1u)
    cells/dendrite/dtrim.spice   leak_ota_dega XM1/XM2 W=4u L=0.5u, XD1/XD2 W=8u L=0.5u       (was L=1u)
    cells/dendrite/dendrite.spice ax_ota_h     XM1/XM2 W=4u L=0.5u, XD1/XD2 W=8u L=0.5u       (was L=1u)

OTA at ss/0, S = 10000, EL 1.5: g 0.81× (base 0.61×), tail 0.86 Ib, g/Ib 5.6. At EL 1.3 and S = 1000, ss/0 improves too (f–I
max 1.35 → 1.13). Costs: systematic rest offset +4.5 mV (DIBL: XM1 sees ~1 V more Vds than XM2; absorbed by EL/vsrc calibration);
**mismatch σ of the rest offset 7.2 → 9.2 mV** (40-seed MC, tt/27; untrimmed S/F/AH50/AH400 neurons take this as rheobase spread);
linear range below EL 81 → 75 mV at S = 100 ss/0 (at the spec limit). g/Ib +2 % (trim_gap gain unchanged within 2 %).

**Option 0 (ZERO LAYOUT, firmware only): EL 1.5 + τ-based leak-code calibration.** At ss/0 the tail is starved, not saturated,
so raising the vbn_leak code ~1.3× restores g. Simulated as tail W ×1.3 (`code13`, all six slot types, ss/0, S = 10000, EL 1.5):
S 1.07–1.23, H 1.06–1.17, F **0.75**–1.05, AH50 1.10–1.34, AH400 1.04–1.18, CMP 0.79–0.93: **all pass**, no device changes.
Needs a per-die/temperature τ measurement (probe tap) to set the code at 10000× (codes are already recalibrated per S; leak
code ≤ 12 → ≤ 16 of 31). Limits: one global code for all types (F is less starved and gets over-corrected: 0.75 at k = 1.1);
below-EL behaviour (linear range 29 mV, Isat+ 42 %) stays degraded; D1/AdEx not simulated with it.
Option 0 + Option 1 together give the most margin. Other diode-only variants (8/0.28: g 0.91×, but σ 11.4 mV and AH50 1.44 FAIL;
8/0.35: σ 10.0 mV, AH50 1.42 FAIL) are in `fi_summary.txt` / `leak4_mc_*.txt`; reversible choice.

## 4. Verification (schematic, Option 1 = L05; f–I normalised min–max, k = 1.1 … 8)
| Cell | EL | tt/27 S=10000 | ss/0 S=10000 | ff/85 S=10000 | S = 10 / 1000 (EL 1.3, tt/ss/ff) | base ss/0 10000 |
|---|---|---|---|---|---|---|
| slot_ah (S/F/H/P base) | 1.5 | 1.06–1.18 | **1.06–1.26** | 1.07–1.15 | 0.97–1.00 / 1.01–1.13 | 1.08–1.48 FAIL |
| slot_ah | 1.3 | 1.06–1.19 | 1.09–1.92 FAIL | 1.07–1.16 | (gate needs EL 1.5) | 1.10–2.10 FAIL |
| slot_ah_h / slot_ah_f | 1.5 | – | 1.06–1.19 / 1.05–1.19 | – | – | 1.08–1.38 / 1.06–1.25 |
| slot_cmp_h (level-3 tail) | 1.5 | 0.82–0.93 | 0.78–0.95 | 0.86–0.93 | 0.98–1.03 (S=1000) | 0.79–1.09 |
| slot_cmp_h | 1.3 | 0.84–0.93 | 0.83–1.38 (pass, thin) | 0.88–0.93 | 0.98–1.03 | 0.83–1.50 FAIL |
| slot_ah_50 (Cm 50 fF) | 1.5 | 1.09–1.30 | **1.07–1.37** | 1.11–1.27 | 1.03–1.15 (S=1000) | 1.11–1.59 FAIL |
| slot_ah_400 (Cm ~470 fF) | 1.5 | 1.03–1.12 | **1.04–1.21** | 1.04–1.09 | 1.01–1.11 (S=1000) | 1.05–1.43 FAIL |

S = 10/100/1000 at EL 1.3: no regression in any run (S, AH50, AH400, CMP; 0.97–1.15). AH50 is the tightest (1.37 at k = 1.1);
its near-rheobase ratio is ill-conditioned (base tt/27 is already 1.35), so expect it to stay marginal post-layout.
**D1** (`tb_d1.py`, trim code 3, both before/after): EL 1.5, S = 10000, ss/0: d1 rest −27.7 → **−8.8 mV** (tt +0.3), attenuation
0.500 → **0.526** (tt 0.527), plateau present 1267 µs (S = 100: 1194), threshold +79.6 mV unchanged. At EL 1.3 ss/0 stays
collapsed (rest −141 mV, atten 0.38). S = 100: rest moves +11–19 mV (systematic offsets of the 3 leak + 4 axial OTAs), threshold 80.0 mV unchanged. Two
atten values of 0.72–0.73 at S = 100 are a bench start-up artifact (vs starts at 0.8 V and is still settling at the 4.9τ
baseline sample; end values match). **AdEx** uses the same `leak_ota_deg` and bias, so the OTA bench applies (g 0.81×);
rerun `tb_adex.py` at EL 1.5 in its level-3 rebuild.

## 5. Layout cost (Option 1)
No device count, W, or cell-area change. Gate L only (gate area per OTA 24 → 12 µm²). **Drawn inside the existing L = 1 µm
footprints** (keep the 1 µm pitch, narrow the poly), the metal, contacts and pin access stay identical, so placements and
routes can be replayed instead of searched. Needs a "kept-slot L" option in each generator (`dendgen.SLOT_L` already exists).

| Cell (array use) | OTA devices | Work | VM-h (est.) |
|---|---|---|---|
| cslot_ah (S1–S3), cslot_ah_f (F1) | 4 each | compact: kept-slot in `geom.py`, rebuild same seed/params, DRC/LVS/PEX; no search | 0.5–1 each |
| czslot_ah_f (F2/F3), czslot_ah_50, czslot_ah_400 | 4 each | same; AH400 reuses its one clean seed (5) | 0.5–1 each |
| slot_ah_h (H1–H3) → slot_ah_p (P2/P3, `P_FROM_H`) | 6 (diodes as 2 halves) | tall `slotgen.py`: fixed centres; re-route unless kept-slot added | 1–1.5 |
| slot_cmp_h (CMP, 28 × 87) | 6 | tall re-route (level-3 precedent: routed clean) | 1–1.5 |
| dend_d1 | 28 (3 leak + 4 axial OTAs) | add to `SLOT_L`, re-route (level-3 D1 + CMP rebuild: 37 min on the VM) | 1 |
| adex_a1 | 4 | rides on the pending level-3 AdEx rebuild | ~0 extra |
| slot_ref, trims, B1, R1, control | 0 | none | 0 |

Effort: ~0.5 d generator option + ~1 d builds/DRC/LVS/PEX + LVS refs regenerate automatically; **~1.5–2 days, ~8–12 VM-h**,
plus the planned 1c gate (~10–20 VM-h). Top level: no pin, line or footprint change, so only the planned M2 full-chip LVS/DRC.
Option 0: **zero layout**, firmware calibration rule only (~0.5 d to write and bench it on D1/AdEx).

## 6. Schedule and gates
- Option 1 plan: netlists + kept-slot Nov 23; rebuilds Nov 24–25 (parallel with phase-2 B1/AdEx); post-layout f–I ss/0 Nov 26;
  **Nov 28 checkpoint met, M2 Dec 1 holds**, M3 Dec 5 and TTGF26c close Dec 7 unaffected.
- Risk: if a compact cell does not reproduce bit-for-bit with the narrowed poly, it needs a new search. AH400 (1 clean seed in 8)
  is the worst case: +1–2 d, +15–30 VM-h, **M2 slips to ~Dec 2–3**, M3 drops GIF or the minimal neurons per the Timeline.
- **Real gates (user):**
  1. Level 4 only passes ss/0 at 10000× **with EL 1.5 V** (level 1). At EL 1.3 no in-footprint fix passes; the p-input
     source-tied-well redesign would re-lay all 10 OTA cells with new searches (≥ 1 week): M2 would slip past Dec 5.
  2. Option 0 (firmware, zero layout) vs Option 1 (L05, 10 cell rebuilds, offset σ +27 %) vs both.
  3. The speed-limits roadmap estimate for level 4 (16/1 + 32/1, ~10 % larger slots, full re-layout) is superseded.

## Decision record (2026-11-22 15:15 UTC)
- User decision 14:40 UTC: add level 4 to M2, so the 10000× gate includes ss/0 °C.
- Adopted: **Option 1** (leak OTA input and diode L 1 → 0.5 µm, same widths and footprints; cells/ change in this commit) **plus Option 0** (leak-code calibration at EL 1.5) as margin. The 10000× operating point is EL 1.5 V (the level-1 point). Passing at EL 1.3 would need a p-input OTA redesign (> 1 week, past Dec 5) and is not pursued.
- Next: rebuild the 10 affected cells with the same placements/seeds (compact: cslot_ah, cslot_ah_f, czslot_ah_f, czslot_ah_50, czslot_ah_400; tall: H, P, CMP, REF if it uses the OTA; D1; AdEx rides its level-3 rebuild), then the full chip, PEX and the gate.
