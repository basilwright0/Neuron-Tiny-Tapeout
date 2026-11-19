"""Gap trim (trim_gap4 in slot_ah_h): rest-voltage shift vs code, across corners / temperatures / speeds.

usage: python3 sim/tb/trim/tb_trim.py [quick]
For each case: one transient with the trim code stepped 0..15 every 8 tau (bits from a behavioural
decoder; rest = vm averaged over the last tau of each step), once with zero input (rest = EL_eff) and
once with 0.25 x rheobase (gives g). Reference: slot_ah (no trim) rest and g. (A DC sweep is not used:
the regenerative detector gives spurious DC solutions near threshold.)
Writes sim/results/trim/trim_summary.txt and trim_cases.json.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slotbench as sb                       # noqa: E402
from ngs import deck, run, RESULTS          # noqa: E402

OUT = RESULTS / "trim"
DEC = "\n".join(f"Bb{k} b{k} 0 V = 3.3*(floor(v(code)/{2**k}+0.01) - 2*floor(v(code)/{2**(k+1)}+0.01))"
                for k in range(4)) + "\nVcode code 0 0"


def case(arg):
    corner, temp, S = arg
    b = sb.Bias(S)
    tag = f"{corner}_{temp}_S{S:g}"
    vsrc = sb.cal_vsrc(corner, temp, S, tag="trim_" + tag)
    res = {"corner": corner, "temp": temp, "S": S, "vsrc": vsrc}
    for nm, iin in (("rest", 0.0), ("half", 0.5 * b.rheo)):
        body = sb.slot_body("slot_ah_h", b, vsrc, iin=iin, code=None, extra=DEC)
        r = run(deck(body, "dc Vcode 0 15 1", ["v(vm)"], corner=corner, temp=temp), f"trim/trim_{nm}_{tag}")
        res[nm] = [float(v) for v in r["v(vm)"]]
        body = sb.slot_body("slot_ah", b, vsrc, iin=iin)
        r = run(deck(body + "Vdum dum 0 0\n", "dc Vdum 0 0 1", ["v(vm)"], corner=corner, temp=temp),
                f"trim/ref_{nm}_{tag}")
        res[nm + "_ref"] = float(r["v(vm)"][0])
    rest = np.array(res["rest"])
    g = 0.5 * b.rheo / (np.array(res["half"]) - rest)
    gref = 0.5 * b.rheo / (res["half_ref"] - res["rest_ref"])
    st = np.diff(rest) * 1e3
    res.update(step_mean=float(st.mean()), step_min=float(st.min()), step_max=float(st.max()),
               lo=float((rest[0] - res["rest_ref"]) * 1e3), hi=float((rest[-1] - res["rest_ref"]) * 1e3),
               mid=float(((rest[7] + rest[8]) / 2 - res["rest_ref"]) * 1e3),
               g_ratio=float(np.mean(g) / gref), g_spread=float((g.max() - g.min()) / gref))
    return res


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quick = "quick" in sys.argv
    cases = [("typical", 27, 100.0)] if quick else \
        [(c, t, 100.0) for c in ("typical", "ff", "ss", "fs", "sf") for t in (0, 27, 85)] + \
        [("typical", 27, 10.0), ("typical", 27, 1000.0), ("ss", 85, 10.0), ("ff", 0, 1000.0)]
    with Pool(3) as p:
        res = p.map(case, cases)
    (OUT / "trim_cases.json").write_text(json.dumps(res, indent=1))
    L = ["gap trim (trim_gap4 in slot_ah_h): rest shift vs code; ref = slot_ah rest (no trim)",
         " corner   T    S   vsrc   code0(mV) code15(mV) mid(mV)  step mean[min,max] (mV)   g/g_ref  g spread"]
    for r in res:
        L.append(f" {r['corner']:7s} {r['temp']:3d} {r['S']:5g} {r['vsrc']:.3f} {r['lo']:9.2f} {r['hi']:10.2f} "
                 f"{r['mid']:7.2f}   {r['step_mean']:5.2f} [{r['step_min']:5.2f},{r['step_max']:5.2f}]"
                 f"        {r['g_ratio']:.3f}   {r['g_spread'] * 100:4.1f}%")
    txt = "\n".join(L)
    print(txt)
    (OUT / "trim_summary.txt").write_text(txt + "\n")
