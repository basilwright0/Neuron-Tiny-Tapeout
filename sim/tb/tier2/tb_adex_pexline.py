"""PEX spike-edge / rate check with and without realistic bias-line capacitance (the bias lines are chip-global:
B1 receivers + array + routing, >> 1 pF; the testbench masters alone leave them as tiny high-impedance nodes that
the cell's coupling capacitors can kick). 400 pA, adaptation off/on, typical 27 C. usage: python3 tb_adex_pexline.py"""
import sys
import numpy as np
sys.argv = ["tb_adex_char.py", "pexline"]
sys.path.insert(0, "/work/sim/tb/tier2")
import tb_adex_char as T  # noqa: E402
vsrc = T.cal_vsrc("typical", 27, T.S)
LINES = ["vbn_leak", "vbn_ref", "vbp_st", "vbp_syn", "vbp_w", "vbn_prb"]
for net in (None, "/work/layout/tier2/out/adex_a1_pex.spice"):
    T.PEX = net
    base = T.dut_line
    for cl in (0.0, 1e-12):
        T.dut_line = lambda cl=cl, base=base: base() + "".join(f"\nCl{k} {k} 0 {cl + 1e-18}" for k in LINES)
        for a in (0.0, T.IADW):
            o = T.step("typical", 27, vsrc, 400e-12, a, tag=f"_{'pex' if net else 'sch'}_cl{cl*1e12:.0f}")
            st = o["_st"]
            real = st[np.r_[True, np.diff(st) > 2e-6]]
            isi = np.diff(real)
            print(f"{'pex' if net else 'sch'} Cline {cl*1e12:.0f} pF {'adapt' if a else 'noadapt':8s}: crossings {len(st)} "
                  f"spikes {len(real)} ISI {isi[0]*1e6:.1f} -> {isi[-1]*1e6:.1f} us ratio {isi[-1]/isi[0]:.3f} "
                  f"b {o.get('b_pA', float('nan')):.1f} pA tau_w {o.get('tau_w_ms', float('nan')):.3f} ms", flush=True)
        T.dut_line = base
