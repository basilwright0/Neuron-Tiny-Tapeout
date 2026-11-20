import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
import numpy as np
d = np.genfromtxt(f"/work/sim/results/dendrite/doff_{sys.argv[1]}.dat", names=True)
for k in d.dtype.names:
    v = d[k]
    print(f"{k:22s} end {v[-1]:.4g}  at 30us {v[np.searchsorted(d[d.dtype.names[0]], 30e-6)]:.4g}")
