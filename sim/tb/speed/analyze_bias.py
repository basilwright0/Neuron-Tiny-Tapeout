"""Speed track: summarize B1 IDAC vs master current (sim/results/speed/bias/idac_*_m*.log)."""
import glob, re, sys
O = "sim/results/speed/bias" if len(sys.argv) < 2 else sys.argv[1]
names = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w", "vbp_st"]
L = ["B1 rev C: line current at code 16 (and 31) normalized per uA of I_nd, relative to I_nd = 1 uA (tt 27, /1 mode);",
     "<1 = ladder/tap compression (absorbed by the 5-bit code while code_nom/ratio <= 31). N: pad, nd, in_n, in_p, vsp",
     ]
ref = None
for f in sorted(glob.glob(f"{O}/idac_*_m*.log")):
    m = re.search(r"idac_(\w+)_(\d+)_m(\d)", f); c, t, mode = m.group(1), m.group(2), int(m.group(3))
    D, N = {}, {}
    for l in open(f):
        p = l.split()
        if l.startswith("D "): D[(float(p[1]), int(p[2]))] = [abs(float(x)) for x in p[3:9]]
        if l.startswith("N "): N[float(p[1])] = [float(x) for x in p[2:]]
    irefs = sorted(N)
    if not irefs: L.append(f"{c} {t} m{mode}: NO DATA"); continue
    ind = lambda i: i / 16 if mode == 1 else i
    base = [k for k in irefs if abs(ind(k) - 1e-6) < 1e-9]
    b16 = [x / 1e-6 for x in D[(base[0], 16)]] if base else None
    if c == "tt" and t == "27" and mode == 0: ref = b16
    b = ref if ref is not None else b16
    L.append(f"--- {c} {t}C mode {'/16' if mode else '/1'}")
    L.append("  Iref(uA) I_nd(uA)  S    " + " ".join(f"{n:>8s}" for n in names) + "   pad   nd    in_n  in_p  vsp   | code31/code16 (leak, syn)")
    for i in irefs:
        r = [x / ind(i) / y for x, y in zip(D[(i, 16)], b)]
        lin = [D[(i, 31)][j] / D[(i, 16)][j] / (31 / 16) for j in (0, 2)] if (i, 31) in D else [float("nan")] * 2
        n = N[i]
        L.append(f"  {i*1e6:8.1f} {ind(i)*1e6:7.2f} {ind(i)*1e8:6.0f} " + " ".join(f"{x:8.3f}" for x in r)
                 + f"  {n[1]:.2f} {n[0]:.2f} {n[2]:.2f} {n[3]:.2f} {n[10]:.2f} | {lin[0]:.3f} {lin[1]:.3f}")
print("\n".join(L)); open("sim/results/speed/bias_summary.txt", "w").write("\n".join(L) + "\n")
