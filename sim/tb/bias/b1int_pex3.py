#!/usr/bin/env python3
"""b1int (MIL-133): top-level PEX DC compare in ONE deck, settled by a supply ramp (transient) instead of .op.

The gen_pex_top.py .op bench is not reliable for a layout-to-layout compare: its .op lands on different
operating points of the *same* schematic copy depending on the rest of the deck (e.g. Xs.vgp5 2.290 V in the
rev C deck vs 2.244 V in the new deck, same stimuli).  Here the schematic (s), the rev C PEX (b) and the new PEX
(p) sit in one deck; vdd ramps 0 -> 3.3 V in 10 us and the outputs are read at 0.5 ms (settling checked at
0.4 ms).  Inputs: out/b1int/{base,new}/top.cir + bias_b1_pex.inc written by gen_pex_top.py.

usage (in the EDA container, from sim/tb/bias): python3 b1int_pex3.py  -> out/b1int/pex3/run.cir
"""
import re
from pathlib import Path

D = Path("out/b1int")
OUTS = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w", "vbp_st", "vbn_prb", "vth_ref", "el",
        "vreset_src", "vth_cmp"]
new = (D / "new/top.cir").read_text().splitlines()
binc = (D / "base/bias_b1_pex.inc").read_text().replace("_pex", "_pexb")
(D / "pex3").mkdir(exist_ok=True)
(D / "pex3/base_pexb.inc").write_text(binc)
head, ctl = new[:new.index(".control")], new[new.index(".control"):]
out = []
for ln in head:
    if ln.startswith("Vdd "):
        ln = "Vdd vdd 0 PWL(0 0 10u 3.3)"
    out.append(ln)
    if ln.startswith(".include") and "bias_b1_pex.inc" in ln:
        out.append(f".include {(D / 'pex3/base_pexb.inc')}")
# copy b: the p block with p -> b and bias_b1_pex -> bias_b1_pexb
blk = []
on = False
for ln in head:
    if ln.startswith("Xp "):
        on = True
    if on and not re.match(r"^(Xp|Iref_p|Vib_p|Rso_p|C\w+_p) ", ln):
        on = False
    if on:
        ln = re.sub(r"_p\b", "_b", ln).replace("bias_b1_pex", "bias_b1_pexb")
        ln = re.sub(r"^(\w+)_p ", r"\1_b ", ln)
        blk.append(ln.replace("Xp ", "Xb ", 1))
# Xb ports: rebuild from the base port order
bports = re.search(r"^\.subckt bias_b1_pexb (.*?)$", binc.replace("\n+", " "), re.M).group(1).split()
pline = [l for l in head if l.startswith("Xp ")][0].split()
pports = re.search(r"^\.subckt bias_b1_pex (.*?)$", (D / "new/bias_b1_pex.inc").read_text().replace("\n+", " "),
                   re.M).group(1).split()
pmap = dict(zip(pports, pline[1:-1]))
blk[0] = "Xb " + " ".join(re.sub(r"_p$", "_b", pmap[q]) for q in bports) + " bias_b1_pexb"
out += [l for l in blk]
L = [".control", "set noaskquit"]
k = 0
for ln in ctl:
    if ln.startswith("alter iref_s"):
        L += [ln, ln.replace("iref_s", "iref_p"), ln.replace("iref_s", "iref_b")]
    elif ln.startswith("alter iref_p"):
        continue
    elif ln.startswith("alter v_"):
        L.append(ln)
    elif ln == "op":
        L.append("tran 0.5u 500u")
        vals = []
        for o in OUTS:
            for t in "sbp":
                for tt, at in (("", "500u"), ("e", "400u")):
                    L.append(f"meas tran m{k}_{o}_{t}{tt} find v({o}_{t}) at={at}")
                vals.append(f"$&m{k}_{o}_{t} $&m{k}_{o}_{t}e")
        for t in "sbp":
            L.append(f"meas tran m{k}_ib_{t} find i(vib_{t}) at=500u")
            vals.append(f"$&m{k}_ib_{t} $&m{k}_ib_{t}")
        tag = [l for l in ctl if l.startswith('echo "T')][k].split('"')[1]
        L.append(f'echo "{tag}" ' + " ".join(vals))
        k += 1
    elif ln.startswith("destroy"):
        L.append(ln)
L += ["quit", ".endc", ".end"]
if __import__("sys").argv[1:] != ["sum"]:
    (D / "pex3/run.cir").write_text("\n".join(out + L) + "\n")
    print("wrote", D / "pex3/run.cir", k, "points")


def summarize():
    """out/b1int/pex3/run.txt -> out/b1int/pex3/summary.txt"""
    res = []
    for ln in (D / "pex3/run.txt").read_text().splitlines():
        if ln.startswith("T "):
            t = ln.split()
            x = list(map(float, t[3:]))
            res.append((t[1], t[2], x))
    names = OUTS + ["ib_r1"]
    W = [0.0] * len(names); WS = [0.0] * len(names); SET = [0.0] * len(names)
    L = ["b1int top-level PEX compare, one deck, vdd ramp, values at 0.5 ms (mV; ib_r1 nA)",
         "columns per output: base-PEX - sch / new-PEX - sch / new - base / settling (|v(0.5ms) - v(0.4ms)|, max of 3)"]
    for iref, st, x in res:
        row = []
        for k, o in enumerate(names):
            sc = 1e9 if o == "ib_r1" else 1e3
            s, se, b, be, p, pe = x[6 * k:6 * k + 6]
            row.append(f"{o}:{(b - s) * sc:+.2f}/{(p - s) * sc:+.2f}/{(p - b) * sc:+.2f}/{max(abs(s - se), abs(b - be), abs(p - pe)) * sc:.2f}")
            W[k] = max(W[k], abs(p - b) * sc); WS[k] = max(WS[k], abs(p - s) * sc)
            SET[k] = max(SET[k], abs(s - se) * sc, abs(b - be) * sc, abs(p - pe) * sc)
        L.append(f"{iref} {st} " + " ".join(row))
    L.append("max |new - base|: " + " ".join(f"{o}={w:.2f}" for o, w in zip(names, W)))
    L.append("max |new - sch|:  " + " ".join(f"{o}={w:.2f}" for o, w in zip(names, WS)))
    L.append("max settling:     " + " ".join(f"{o}={w:.2f}" for o, w in zip(names, SET)))
    (D / "pex3/summary.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__" and __import__("sys").argv[1:] == ["sum"]:
    summarize()
