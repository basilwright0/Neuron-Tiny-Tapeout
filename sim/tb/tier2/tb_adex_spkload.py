"""Spike-edge race check: schematic A1 with extra capacitance on spk (and on vm), 400 pA, typical 27 C.
Counts raw spk crossings vs real spikes (a runt pulse gives two crossings ~ns apart). usage: python3 tb_adex_spkload.py"""
import sys
import numpy as np
sys.argv = ["tb_adex_char.py", "spkload"]
sys.path.insert(0, "/work/sim/tb/tier2")
import tb_adex_char as T  # noqa: E402
vsrc = T.cal_vsrc("typical", 27, T.S)
base = T.dut_line
for cs, cv in ((0, 0), (6e-15, 0), (11e-15, 0), (0, 25e-15), (11e-15, 25e-15)):
    T.dut_line = lambda cs=cs, cv=cv: base() + f"\nCxs spk 0 {cs + 1e-18}\nCxv vm 0 {cv + 1e-18}"
    o = T.step("typical", 27, vsrc, 400e-12, 0.0, tag=f"_cs{cs*1e15:.0f}_cv{cv*1e15:.0f}", t1=1.5e-3, tend=1.6e-3)
    st = o["_st"]
    real = st[np.r_[True, np.diff(st) > 2e-6]]
    print(f"extra spk {cs*1e15:4.0f} fF vm {cv*1e15:4.0f} fF: crossings {len(st)} spikes {len(real)} "
          f"ISI {np.mean(np.diff(real))*1e6:.1f} us", flush=True)
