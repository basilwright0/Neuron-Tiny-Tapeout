"""Print spk/vm around the first spikes of a tier2 transient (.dat). usage: python3 peek_spk.py <dat>"""
import sys
import numpy as np
f = sys.argv[1]
a = np.loadtxt(f, skiprows=1); h = open(f).readline().split()
t = a[:, 0]; spk = a[:, h.index('v(spk)')]; vm = a[:, h.index('v(vm)')]
i = np.where((spk[:-1] < 1.65) & (spk[1:] >= 1.65))[0][2:4]
for k in i:
    for j in range(k - 3, k + 30):
        print('%.3f us spk %.3f vm %.3f' % (t[j] * 1e6, spk[j], vm[j]))
    print('--')
