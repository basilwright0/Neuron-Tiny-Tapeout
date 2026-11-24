#!/usr/bin/env python3
"""MIL-319 item 2b: Monte Carlo of the CMP vth_cmp code window at S = 10000 (slot_cmp_h PEX, EL 1.50 V).

One die = one seed s: per-instance mismatch of the slot (tb_fi FI_SEED = s; comparator, leak OTA, detector, ...) and
the vth_cmp DAC offset of DAC seed s (mc_vdac_vc.py, vdac_vc_mc_*.json: v_s(c) - v_0(c), schematic, same corner). Per code c:
  vth_cmp = PEX code-26 output of the corner (m3_codes.sh) + (c - 26) x 13.68 mV + DAC offset_s(c)
  f-I gate as vdac_gate_sum.py: per k, (f/f_ideal at S = 10000) / (f/f_ideal at S = 100), same die and code;
  pass = all six k in 0.7-1.4 and >= 3 spikes at every k. S = 10000 uses the step 5.5 leak calibration (x 13/12).
Codes 27 and 26 always; 25 and 28 when both fail, and for seeds <= MC_FULL (window shape). Seed 0 = no mismatch.
Biases are ideal (per-die bias / leak-code calibration is the firmware's job), as in the corner gate.

  python3 sim/tb/speed/mc_cmp.py <corners, e.g. ss or tt,ff>
  env: MC_NMIN (default 20) / MC_NMAX (60) seeds per corner, MC_TMAX (s, default 5400), MC_STOP (file: stop once it
  exists and every corner has MC_NMIN seeds), MC_FULL (5)
  -> sim/results/m3mc/mc_cmp_<corner>.jsonl (one line per die and code)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OUT = Path("/work/sim/results/m3mc")
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
PEXNOM = {"tt": ("typical", 27, 1.57961), "ss": ("ss", 0, 1.58145), "ff": ("ff", 85, 1.57512)}
STEP = 0.01368
CORNERS = sys.argv[1].split(",")
NMIN, NMAX = int(os.environ.get("MC_NMIN", "20")), int(os.environ.get("MC_NMAX", "60"))
NMIN_C = {"ss": NMIN, "tt": min(NMIN, 12), "ff": min(NMIN, 8)}   # dies per corner (ss = worst corner)
TMAX, STOP, FULL = float(os.environ.get("MC_TMAX", "5400")), os.environ.get("MC_STOP"), int(os.environ.get("MC_FULL", "3"))
DAC = {}
for _f in OUT.glob("vdac_vc_mc_*.json"):          # mc_vdac_vc.py output(s), one per job
    DAC.update(json.loads(_f.read_text()))
T0 = time.time()


def fi(corner, seed, code, S):
    cn, temp, v26 = PEXNOM[corner]
    d = DAC[corner]
    off = (d[str(seed)][str(code)] - d["0"][str(code)]) if seed and str(seed) in d else 0.0
    vthc = f"{v26 + (code - 26) * STEP + off:.5f}"
    env = dict(os.environ, FI_RESULTS=str(RAW), FI_DEL="0.2", FI_PEX="/work/layout/slot/out/slot_cmp_h_pex.spice",
               FI_VTHC=vthc, FI_TAG=f"_c{code}", FI_SEED=str(seed), FI_IBSCALE="1.083333" if S > 1000 else "1")
    tag = f"slot_cmp_h_{cn}_{temp}_S{S:g}_EL1.50_vthc{vthc}_c{code}" + (f"_mc{seed}" if seed else "")
    npr = "2" if STOP and Path(STOP).exists() else "1"     # 2 cores once this job's chip transient is done
    r = subprocess.run(["python3", "sim/tb/speed/tb_fi.py", "slot_cmp_h", cn, str(temp), f"{S:g}", npr], env=env,
                       cwd="/work", capture_output=True, text=True, timeout=900)
    f = RAW / f"fi_{tag}.json"
    if not f.exists():
        print(f"{tag}: no result\n{r.stdout[-400:]}{r.stderr[-600:]}", flush=True)
        return None, off
    out = json.loads(f.read_text())
    if seed:                                     # keep the json, drop the bulky per-k decks / waveforms
        for p in RAW.glob(f"fi*_{tag}*"):
            if p.suffix in (".dat", ".cir"):
                p.unlink()
    return out, off


def gate(a, b):
    if a is None or b is None:
        return None, []
    r = [(y["rate"] / y["ideal"]) / (x["rate"] / x["ideal"]) if x["rate"] > 0 and x["ideal"] > 0 else float("nan")
         for x, y in zip(a["res"], b["res"])]
    ok = all(0.7 <= v <= 1.4 for v in r) and all(y["nspk"] >= 3 for y in b["res"])
    return ok, r


def die(corner, seed):
    rows = {}

    def one(c):
        a, off = fi(corner, seed, c, 100)
        b, _ = fi(corner, seed, c, 10000)
        ok, r = gate(a, b)
        row = dict(corner=corner, seed=seed, code=c, dac_off=off, ok=ok, ratios=r,
                   vtrip100=a and a["vtrip"], vtrip10k=b and b["vtrip"], stuck=b and sum(y["stuck"] for y in b["res"]))
        rows[c] = row
        with open(OUT / f"mc_cmp_{corner}.jsonl", "a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{corner} seed {seed:3d} code {c}: {'PASS' if ok else 'FAIL' if ok is False else 'ERR '} "
              f"dac {1e3 * off:+6.2f} mV trip10k {row['vtrip10k']} [{' '.join(f'{v:.2f}' for v in r)}] "
              f"t {time.time() - T0:.0f}s", flush=True)

    for c in (27, 26):
        one(c)
    if seed == 0 or seed <= FULL or not (rows[27]["ok"] or rows[26]["ok"]):
        for c in (25, 28):
            one(c)


n = {c: 0 for c in CORNERS}
for c in CORNERS:                                # seed 0 (no mismatch) baseline at codes 25-28
    die(c, 0)
while True:
    el = time.time() - T0
    done_min = all(v >= NMIN_C.get(k, NMIN) for k, v in n.items())
    if el > TMAX or all(v >= NMAX for v in n.values()) or (done_min and STOP and Path(STOP).exists()):
        break
    c = min(CORNERS, key=lambda k: n[k] / NMIN_C.get(k, NMIN))
    n[c] += 1
    die(c, n[c])
print(f"MC_DONE seeds {n} in {time.time() - T0:.0f} s", flush=True)
