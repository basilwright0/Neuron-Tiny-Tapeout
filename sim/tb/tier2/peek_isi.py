"""Print vm (and vw if saved) at fixed delays after a spike, for tier2 transients. usage: peek_isi.py <dat>..."""
import sys
import numpy as np
for f in sys.argv[1:]:
    a = np.loadtxt(f, skiprows=1); h = open(f).readline().split()
    t = a[:, 0]; spk = a[:, h.index('v(spk)')]; vm = a[:, h.index('v(vm)')]
    up = np.where((spk[:-1] < 1.0) & (spk[1:] >= 1.0))[0]
    up = up[np.r_[True, np.diff(t[up]) > 5e-6]]
    k0, k1 = up[5], up[6]
    ds = [0.05e-6, 0.2e-6, 0.5e-6, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 30e-6, 40e-6, 50e-6, 60e-6, 70e-6]
    print(f.split('/')[-1], 'ISI %.1f us' % ((t[k1] - t[k0]) * 1e6))
    print('  vm ', [round(float(np.interp(t[k0] + d, t, vm)), 4) for d in ds])
    print('  spk', [round(float(np.interp(t[k0] + d, t, spk)), 3) for d in ds])
