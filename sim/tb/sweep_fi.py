"""Parallel f-I sweep: variants x corners x temps x speeds. Results -> sim/results/fi_*.json + summary."""
import itertools, json, subprocess, sys
from multiprocessing import Pool
from pathlib import Path
R = Path("/work/sim/results")
jobs = list(itertools.product(sys.argv[1:] or ["cmp", "ah"], ["typical", "ff", "ss", "fs", "sf"], [0, 27, 85], [10, 100, 1000]))
def go(j):
    v, c, t, s = j
    p = subprocess.run(["python3", "/work/sim/tb/tb_lif_fi.py", v, c, str(t), str(s)], capture_output=True, text=True)
    return j, p.returncode, p.stdout[-400:] + p.stderr[-400:]
if __name__ == "__main__":
    with Pool(6) as pool:
        for j, rc, out in pool.imap_unordered(go, jobs):
            print(j, "OK" if rc == 0 else "FAIL\n" + out, flush=True)
