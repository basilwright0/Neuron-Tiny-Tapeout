"""Print a .dat from sim/results around a time window: python3 sim/tb/vsrc/peek.py <name> t0_us t1_us step_ns"""
import sys, numpy as np
f = f"/work/sim/results/{sys.argv[1]}.dat"
hdr = open(f).readline().split()
d = np.loadtxt(f, skiprows=1)
t0, t1, dt = float(sys.argv[2]) * 1e-6, float(sys.argv[3]) * 1e-6, float(sys.argv[4]) * 1e-9
print("t(us)    " + "  ".join(f"{h:>10s}" for h in hdr[1:]))
for tq in np.arange(t0, t1, dt):
    print(f"{tq*1e6:7.3f}  " + "  ".join(f"{np.interp(tq, d[:,0], d[:,k]):10.4g}" for k in range(1, d.shape[1])))
