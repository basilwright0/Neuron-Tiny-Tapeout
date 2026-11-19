"""A1 sizing exploration: exp-term mirror length (le) and adaptation current (i_adw).

usage: python3 sim/tb/tier2/tune_adex.py
Prints rest vm (no input), ISI at 250 pA without adaptation for several le, then first/last ISI at
400 pA for several i_adw.
"""
import sys

import numpy as np

sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa

S = 100.0
vsrc = cal_vsrc("typical", 27, S)
T0, TEND = 0.3e-3, 3.3e-3


def dut(le):
    return ("XA vm vw spk sel_adex sub0 sub1 sta stb hold mreset vbp_syn el vsrc vreset vbn_leak vbp_st "
            f"vbn_ref vbn_prb vbp_w en abus vdd 0 adex_a1 {le}")


def sim(le, istep, iadw, tag):
    body = f"""{cells('adex/adex.spice')}
{bias(S=S, vsrc=vsrc, i_adw=iadw)}
Vsta sta 0 0
Vstb stb 0 0
Iin vdd vm pwl(0 0 {T0} 0 {T0 + 1e-6} {istep})
{dut(le)}
"""
    r = run(deck(body, f"tran 200n {TEND}", ["v(vm)", "v(vw)", "v(spk)", "v(vbn_leak)"]), f"tier2/tune_{tag}")
    st = crossings(r["_x"], r["v(spk)"], 1.65)
    return r, st[st > T0]


print(f"vsrc {vsrc:.4f}")
for le in sys.argv[1].split(";"):
    for istep in (0.0, 200e-12):
        r, st = sim(le, istep, 0.0, f"le{le.replace(' ','_').replace('=','')}_{istep*1e12:.0f}")
        isi = np.diff(st)
        print(f"{le:12s} I={istep*1e12:4.0f}p vm min/max before T0 {r['v(vm)'][r['_x'] < T0].min():.4f}/{r['v(vm)'][r['_x'] < T0].max():.4f} "
              f"vbn_leak={r['v(vbn_leak)'][-1]:.4f} n={len(st)} ISI={isi[-1]*1e6 if len(isi) else 0:.1f}us", flush=True)
for iadw in ([] if len(sys.argv) < 3 else [float(v) * 1e-12 for v in sys.argv[2].split(",")]):
    r, st = sim(sys.argv[3] if len(sys.argv) > 3 else "", 400e-12, iadw, f"adw{iadw*1e12:.0f}")
    isi = np.diff(st)
    print(f"i_adw={iadw*1e12:5.0f}p n={len(st)} ISI first {isi[0]*1e6:.1f} 2nd {isi[1]*1e6:.1f} last {isi[-1]*1e6:.1f} "
          f"vw max {r['v(vw)'].max():.3f}", (isi*1e6).round(0).tolist()[:14], flush=True)
