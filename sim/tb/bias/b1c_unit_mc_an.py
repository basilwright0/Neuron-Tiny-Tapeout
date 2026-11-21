"""b1c: analyse b1c_unit_mc.py output: sigma(I)/I per geometry, and the MSB-step DNL sigma/yield
(code 15->16 of a 31-unit binary DAC: sigma_DNL = sigma_u*sqrt(31) LSB) plus a direct DAC-draw MC."""
import re, sys
import numpy as np
from math import erf, sqrt
d = {}
for ln in open(sys.argv[1]):
    m = re.match(r"i\(v([np])(\d)(\d)x(\d+)\) = (\S+)", ln)
    if m:
        d.setdefault((m[1], int(m[2]), int(m[3])), []).append(abs(float(m[5])))
rng = np.random.default_rng(1)
print("pol W/L  N   mean I     sigma/I   sigma_DNL(MSB)  P(DNL<-1)/DAC   DAC-draw MC (31 units drawn from the instances, 20000 DACs): worst-step DNL<-1 rate, median minDNL")
for k in sorted(d):
    a = np.array(d[k]); s = a.std(ddof=1) / a.mean()
    sd = s * sqrt(31); p = 0.5 * (1 + erf(-1 / sd / sqrt(2)))
    # resample DACs from the normalised instance currents
    u = a / a.mean()
    dacs = rng.choice(u, size=(20000, 31))
    w = [dacs[:, 0:1].sum(1), dacs[:, 1:3].sum(1), dacs[:, 3:7].sum(1), dacs[:, 7:15].sum(1), dacs[:, 15:31].sum(1)]
    codes = np.arange(32)
    I = sum(((codes >> b) & 1)[None, :] * w[b][:, None] for b in range(5))
    lsb = I[:, 31] / 31
    dnl = np.diff(I, axis=1) / lsb[:, None] - 1
    mn = dnl.min(1)
    print(f"{k[0]}   {k[1]}/{k[2]}  {len(a)}  {a.mean():.3e}  {100*s:5.2f} %   {sd:.2f} LSB        {100*p:5.2f} %         {100*np.mean(mn < -1):5.2f} %  {np.median(mn):+.2f}")
