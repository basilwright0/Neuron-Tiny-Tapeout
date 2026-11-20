"""Gap trim of the CMP double slot (slot_cmp_h, 2026-11-20): rest shift vs code and rate at codes 0/8/15,
schematic and post-layout (magic PEX), typical 27 C.

usage: python3 sim/tb/trim/tb_trim_cmp.py [S]
rest: DC sweep of the code (behavioural decoder) with zero input (rest = EL_eff) and with 0.5 x rheobase (gives g);
rate: transient spike rate at 2 x rheobase for codes 0, 8, 15. aux = vth_cmp = VTH (1.38 V).
Writes sim/results/trim/trim_cmp_summary.txt.
"""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slotbench as sb                       # noqa: E402
from ngs import deck, run, crossings, rate, RESULTS   # noqa: E402

CELL = "slot_cmp_h"
S = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
CORNER, TEMP = "typical", 27
PEX = Path(f"/work/layout/slot/out/{CELL}_pex.spice")
DEC = "\n".join(f"Bb{k} b{k} 0 V = 3.3*(floor(v(code)/{2**k}+0.01) - 2*floor(v(code)/{2**(k+1)}+0.01))"
                for k in range(4)) + "\nVcode code 0 0"
b = sb.Bias(S)
vsrc = sb.cal_vsrc(CORNER, TEMP, S, tag=f"trimcmp_S{S:g}")


def inst(kind):
    if kind == "sch":
        return True, None
    txt = re.sub(r"\n\+", " ", PEX.read_text())
    ports = re.search(rf"^\.subckt\s+{CELL}\s+(.*)$", txt, re.M | re.I).group(1).split()
    return False, f".include {PEX}\nXn " + " ".join(sb.nets(CELL)[p] for p in ports) + f" {CELL}"


out = {}
for kind in ("sch", "pex"):
    libs, ins = inst(kind)
    res = {}
    for nm, iin in (("rest", 0.0), ("half", 0.5 * b.rheo)):
        body = sb.slot_body(CELL, b, vsrc, iin=iin, code=None, extra=DEC, inst=ins, include_libs=libs)
        r = run(deck(body, "dc Vcode 0 15 1", ["v(vm)"], corner=CORNER, temp=TEMP), f"trim/cmp_{nm}_{kind}_S{S:g}")
        res[nm] = np.array([float(v) for v in r["v(vm)"]])
    res["g_rel"] = (0.5 * b.rheo) / (res["half"] - res["rest"])      # leak conductance per code (A/V)
    rates = {}
    for code in (0, 8, 15):
        body = sb.slot_body(CELL, b, vsrc, iin=2 * b.rheo, code=code, inst=ins, include_libs=libs)
        r = run(deck(body + f".ic v(vm)={sb.EL}\n", f"tran {b.tau / 200} {40 * b.tau} uic", ["v(spk)"],
                     corner=CORNER, temp=TEMP), f"trim/cmp_rate_{kind}_S{S:g}_c{code}")
        st = crossings(r["_x"], r["v(spk)"], 1.65)
        rates[code] = float(rate(st, t_settle=5 * b.tau))
    res["rate"] = rates
    out[kind] = res

L = [f"CMP gap trim (slot_cmp_h double slot), {CORNER} {TEMP} C, S = {S:g}, EL = {sb.EL} V, vth_cmp = {sb.VTH} V",
     "code   rest_sch(mV)  shift_sch(mV)   rest_pex(mV)  shift_pex(mV)"]
for k in range(16):
    L.append(f"{k:4d}   {out['sch']['rest'][k] * 1e3:10.2f}   {(out['sch']['rest'][k] - out['sch']['rest'][8]) * 1e3:+10.2f}"
             f"     {out['pex']['rest'][k] * 1e3:10.2f}   {(out['pex']['rest'][k] - out['pex']['rest'][8]) * 1e3:+10.2f}")
for kind in ("sch", "pex"):
    r = out[kind]["rest"]
    d = np.diff(r) * 1e3
    L.append(f"{kind}: range code 0..15 = {(r[0] - r[8]) * 1e3:+.1f} .. {(r[15] - r[8]) * 1e3:+.1f} mV (vs code 8), "
             f"step {d.min():.2f}..{d.max():.2f} mV (mean {d.mean():.2f}), monotonic {bool(np.all(d > 0))}")
    rt = out[kind]["rate"]
    L.append(f"{kind}: rate at 2 x rheobase, code 0 / 8 / 15 = {rt[0]:.1f} / {rt[8]:.1f} / {rt[15]:.1f} Hz")
txt = "\n".join(L)
print(txt)
(RESULTS / "trim").mkdir(exist_ok=True)
(RESULTS / "trim" / "trim_cmp_summary.txt").write_text(txt + "\n")
