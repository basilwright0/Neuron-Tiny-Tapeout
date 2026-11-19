"""Speed-track shared setup: results go to sim/results/speed/ (ngs.RESULTS patched), biases scale with S.

All existing benches are read-only; this module only re-points the harness output directory.
Bias convention (as slotbench.Bias / tb_lif_fi.py): tau_bio = 10 ms, 200 fF membrane, g = C*S/10 ms,
Ib_leak = g / 6.33, I_st = 100 nA * S/100, I_ref = 50 fF * 1.35 V / (2 ms / S).
"""
import sys
from pathlib import Path

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/sim/tb/trim")
import ngs  # noqa: E402

ngs.RESULTS = Path("/work/sim/results/speed")
ngs.RESULTS.mkdir(parents=True, exist_ok=True)
RESULTS = ngs.RESULTS
import slotbench as sb  # noqa: E402,F401

WORST = [("typical", 27), ("ss", 0), ("ff", 85), ("sf", 0)]
