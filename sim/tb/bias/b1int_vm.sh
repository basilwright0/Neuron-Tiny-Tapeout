#!/bin/bash
# b1int (MIL-133): full route of bias_b1 with all M3 leaves + pocket NB, then DRC/LVS/KLayout/PEX, frame check, and run the top-level
# PEX check for the new layout and the rev C baseline (sim/tb/bias/b1d_base_pex.spice = HEAD rev C extraction).
set -e
cd /work/layout/bias
export PYTHONHASHSEED=0
PEX=1 CELLS=bias_b1 bash build.sh 2>&1 | tee out/b1int_build.txt
python3 chk_frame.py > out/b1int_chk_frame.txt 2>&1 || true
cd /work/sim/tb/bias
mkdir -p out/b1int/base out/b1int/new
P=/work/layout/bias/out/bias_b1_pex.spice
cp $P out/b1int/new_pex.spice
cp b1d_base_pex.spice $P
python3 gen_pex_top.py out/b1int/base/top.cir
cp out/b1int/new_pex.spice $P
python3 gen_pex_top.py out/b1int/new/top.cir
for v in base new; do ngspice -b out/b1int/$v/top.cir > out/b1int/${v}_ngspice.txt 2>&1 & done
wait
python3 - <<'PY'
OUTS = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w", "vbp_st", "vbn_prb", "vth_ref", "el",
        "vreset_src", "vth_cmp", "ib_r1"]
res = {}
for v in ("base", "new"):
    for ln in open(f"out/b1int/{v}_ngspice.txt"):
        if ln.startswith("T "):
            t = ln.split(); key = (t[1], t[2]); x = list(map(float, t[3:]))
            res.setdefault(key, {})[v] = [(x[2*k], x[2*k+1]) for k in range(len(OUTS))]
with open("out/b1int/pex_top_compare.txt", "w") as f:
    f.write("PEX - schematic, mV (ib_r1: nA); base = rev C 265x115, new = M3 leaves 242x115 + pocket NB\n")
    f.write("iref set " + " ".join(f"{o}:base/new" for o in OUTS) + "\n")
    worst = [0.0] * len(OUTS)
    for key, d in sorted(res.items()):
        row = []
        for k, o in enumerate(OUTS):
            sc = 1e9 if o == "ib_r1" else 1e3
            db = (d["base"][k][1] - d["base"][k][0]) * sc; dn = (d["new"][k][1] - d["new"][k][0]) * sc
            worst[k] = max(worst[k], abs(dn - db))
            row.append(f"{db:+.2f}/{dn:+.2f}")
        f.write(f"{key[0]} {key[1]} " + " ".join(row) + "\n")
    f.write("max |new - base| per output: " + " ".join(f"{o}={w:.2f}" for o, w in zip(OUTS, worst)) + "\n")
print(open("out/b1int/pex_top_compare.txt").read())
PY
