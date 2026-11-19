import numpy as np, sys
a = np.loadtxt(sys.argv[1], skiprows=1)
for t in (0.15e-3, 0.21e-3, 0.3e-3, 0.5e-3, 1e-3, 1.5e-3, 2e-3, 3e-3, 3.9e-3):
    print(f"{t*1e3:5.2f} ms {np.interp(t, a[:,0], a[:,1]):.4e}")
