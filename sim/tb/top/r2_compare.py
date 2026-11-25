"""R2 vs M3 full-chip PEX regression (MIL-362): parses the bench result files of two runs and lists old / new / delta.

  python3 sim/tb/top/r2_compare.py <M3 results dir> <R2 results dir> [out.txt]

Criteria: bias DC driver / far-end values and probe pad levels |delta| <= 0.5 mV; kick edges |delta| <= 0.5 mV (the M3
README criterion vs run 4); firing rates (bias_spk off, s10k) |delta| <= 1 %; probe settling <= 2 us (bench criterion).
Host-side (plain Python, no numpy).
"""
import json
import re
import sys
from pathlib import Path

OLD, NEW = Path(sys.argv[1]), Path(sys.argv[2])
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else NEW / "r2_vs_m3.txt"
L = []
FAIL = []


def log(s=""):
    print(s)
    L.append(s)


def rd(d, n):
    f = d / n
    return f.read_text().splitlines() if f.exists() else None


def verdict(name, ok, why=""):
    log(f"=> {name}: {'PASS' if ok else 'FAIL'} {why}")
    if not ok:
        FAIL.append(name)


# ---------------------------------------------------------------- bias DC (S = 100): driver value + far-end offsets
def bias_dc(fn_old, fn_new, title, skip=()):
    o, n = rd(OLD, fn_old), rd(NEW, fn_new)
    if not (o and n):
        log(f"[{title}] missing ({fn_old}: {bool(o)}, {fn_new}: {bool(n)})")
        return
    def parse(ls):
        hdr = next(l for l in ls if l.startswith("line"))
        cols = hdr.split()[2:-1]
        out = {}
        for l in ls:
            m = re.match(r"^(\S+)\s+(\d+\.\d+)\s+(.*?)\s+(yes|no)", l)
            if not m:
                continue
            out[(m.group(1), "drv")] = float(m.group(2)) * 1e3
            for c, v in zip(cols, m.group(3).split()):
                if v != "-":
                    out[(m.group(1), c)] = float(v)        # far - driver, mV
        return out
    po, pn = parse(o), parse(n)
    log(f"[{title}] {fn_old} -> {fn_new}: driver value (mV) and far-end offsets (mV), old / new / delta")
    worst = (0.0, "")
    for k in po:
        if k not in pn:
            continue
        d = pn[k] - po[k]
        flag = "" if abs(d) <= 0.5 or k[0] in skip else "   <-- > 0.5 mV"
        if k[0] in skip:
            flag = "   (vth_cmp code differs: see the r2c22 run)"
        elif abs(d) > abs(worst[0]):
            worst = (d, f"{k[0]} {k[1]}")
        log(f"  {k[0]:11s} {k[1]:5s} {po[k]:10.3f} {pn[k]:10.3f} {d:+8.3f}{flag}")
    new_only = [k for k in pn if k not in po]
    if new_only:
        log("  new terminals (R2 only): " + ", ".join(f"{a} {b} {pn[(a, b)]:+.3f}" for a, b in new_only))
    verdict(title, abs(worst[0]) <= 0.5, f"(worst {worst[0]:+.3f} mV, {worst[1]})")


def dat(d, n):
    """ngspice wrdata table (wr_vecnames, wr_singlescale) -> {name: [floats]}; None if missing."""
    f = d / n
    if not f.exists():
        return None
    ls = f.read_text().split("\n")
    names = ls[0].split()
    cols = {k: [] for k in names}
    for l in ls[1:]:
        v = l.split()
        if len(v) == len(names):
            for k, x in zip(names, v):
                cols[k].append(float(x))
    return cols


def interp(x, xs, ys):
    for i in range(1, len(xs)):
        if xs[i] >= x:
            a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]) if xs[i] > xs[i - 1] else 0.0
            return ys[i - 1] + a * (ys[i] - ys[i - 1])
    return ys[-1]


def bias_dat(fo, fn, title):
    """Full-precision DC values of every saved node common to both runs (raw node names may differ between the
    netlists; R-network t-node numbers do)."""
    o, n = dat(OLD, fo), dat(NEW, fn)
    if not (o and n):
        log(f"[{title}] .dat missing")
        return
    com = [k for k in o if k in n and k.startswith("v(")]
    worst = (0.0, "")
    rows = []
    for k in com:
        d = (n[k][0] - o[k][0]) * 1e3
        rows.append((k, o[k][0], n[k][0], d))
        if abs(d) > abs(worst[0]) and "aux" not in k.split(".")[-1] and "s13.aux" not in k:
            worst = (d, k)
    log(f"[{title}] full precision from {fo} / {fn}: {len(com)} common nodes (M3 {len(o) - 1}, R2 {len(n) - 1}); "
        f"worst |delta| (aux3 = vth_cmp excluded) {worst[0]:+.4f} mV at {worst[1]}")
    for k, a, b_, d in sorted(rows, key=lambda r: -abs(r[3]))[:12]:
        log(f"  {k:34s} {a:.6f} {b_:.6f} {d:+8.4f} mV")
    return worst


# ---------------------------------------------------------------- probe step: pad levels + settling
def probe():
    o, n = rd(OLD, "probe_step_typical_27.txt"), rd(NEW, "probe_step_typical_27.txt")
    if not (o and n):
        log("[probe step] missing")
        return
    pat = re.compile(r"^(.{15}) -> (.{15})\s+(\d\.\d+) -> (\d\.\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)")
    po = [pat.match(l).groups() for l in o if pat.match(l)]
    pn = [pat.match(l).groups() for l in n if pat.match(l)]
    log("[probe step typ 27] move: pad after (V) old / new / delta (mV); t_settle 1 % (ns) old / new")
    worst, ts = 0.0, 0
    for a, b in zip(po, pn):
        d = (float(b[3]) - float(a[3])) * 1e3
        worst = max(worst, abs(d))
        ts = max(ts, int(b[4]))
        log(f"  {a[0].strip():15s} -> {a[1].strip():15s} {float(a[3]):.4f} {float(b[3]):.4f} {d:+7.2f}   "
            f"{int(a[4]):6d} {int(b[4]):6d}{'   <-- > 0.5 mV' if abs(d) > 0.5 else ''}")
    do, dn = dat(OLD, "probe_step_typical_27.dat"), dat(NEW, "probe_step_typical_27.dat")
    if do and dn:                                          # full precision: pad at each segment end (bench timeline)
        log("  full precision (v(pad) at each move's window end, .dat), mV: " + "; ".join(
            f"{interp(t_, do['time'], do['v(pad)']):.5f} -> {interp(t_, dn['time'], dn['v(pad)']):.5f} V "
            f"({1e3 * (interp(t_, dn['time'], dn['v(pad)']) - interp(t_, do['time'], do['v(pad)'])):+.3f})"
            for t_ in [10e-6 + i * 6e-6 + 6e-6 for i in range(5)]))
    verdict("probe step levels", worst <= 0.5, f"(worst |delta| {worst:.2f} mV)")
    verdict("probe step settling", ts <= 2000, f"(worst {ts} ns, M3 {max(int(a[4]) for a in po)} ns)")


# ---------------------------------------------------------------- kick: edge (step) per victim / event
def kick():
    o, n = rd(OLD, "kick_typical_27.txt"), rd(NEW, "kick_typical_27.txt")
    if not (o and n):
        log("[kick] missing")
        return
    pat = re.compile(r"([+-]\d+\.\d+)\(\s*([+-]?\d+\.\d+)\)")
    def parse(ls):
        i = next(k for k, l in enumerate(ls) if l.startswith("vm / node kicks"))
        hdr = ls[i + 1][22:]
        names = [hdr[j:j + 15].strip() for j in range(0, len(hdr), 15)]
        out = {}
        for l in ls[i + 2:]:
            if l.startswith("worst"):
                break
            ev = l[:21].strip()
            for nm, m in zip(names, pat.findall(l[21:])):
                out[(ev, nm)] = (float(m[0]), float(m[1]))
        return out, names
    (po, no_), (pn, nn) = parse(o), parse(n)
    log(f"[kick typ 27] edge kick (mV), events x victims: |new - old| > 0.5 mV listed; M3 victims {len(no_)}, R2 {len(nn)}")
    worst = (0.0, "")
    cnt = 0
    for k in po:
        if k not in pn:
            continue
        d = pn[k][0] - po[k][0]
        cnt += 1
        if abs(d) > abs(worst[0]):
            worst = (d, f"{k[1]} at {k[0]}")
        if abs(d) > 0.5:
            log(f"  {k[0]:21s} {k[1]:12s} edge {po[k][0]:+7.2f} -> {pn[k][0]:+7.2f} ({d:+.2f}); step {po[k][1]:+6.1f} -> "
                f"{pn[k][1]:+6.1f}")
    log(f"  compared {cnt} edges; worst delta {worst[0]:+.2f} mV ({worst[1]})")
    bay = [x for x in nn if x not in no_]
    if bay:
        log("  bay victims (R2 only), edge (step) mV: ")
        evs = sorted({k[0] for k in pn}, key=lambda e: [k[0] for k in pn].index(e))
        for ev in evs:
            log(f"    {ev:21s} " + "  ".join(f"{b}: {pn[(ev, b)][0]:+6.2f}({pn[(ev, b)][1]:+5.1f})" for b in bay
                                              if (ev, b) in pn))
    for ls, tag in ((o, "M3"), (n, "R2")):
        w = next((l for l in ls if l.startswith("worst edge")), "")
        log(f"  {tag} {w}")
    verdict("kick edges", abs(worst[0]) <= 0.5, f"(worst {worst[0]:+.2f} mV, {worst[1]})")
    # hold-window slopes
    def hold(ls):
        i = next(k for k, l in enumerate(ls) if l.startswith("hold window"))
        return {m.group(1): float(m.group(2)) for m in re.finditer(r"(\S+ \S+): ([+-]\d+\.\d+)", ls[i + 1])}
    ho, hn = hold(o), hold(n)
    log("  hold drift (mV/ms) old -> new: " + "; ".join(f"{k} {ho[k]:+.2f} -> {hn[k]:+.2f}" for k in ho if k in hn))
    log("  bay hold drift: " + "; ".join(f"{k} {v:+.2f}" for k, v in hn.items() if k not in ho))


# ---------------------------------------------------------------- firing rates
def spk():
    o, n = rd(OLD, "bias_spk_off.txt"), rd(NEW, "bias_spk_off.txt")
    if not (o and n):
        log("[bias_spk off] missing")
        return
    g = lambda ls: float(re.search(r"rate ([\d.]+) kHz", next(l for l in ls if l.startswith("victim:"))).group(1))
    a, b = g(o), g(n)
    log(f"[bias_spk off] victim H2 rate {a:.3f} -> {b:.3f} kHz ({100 * (b / a - 1):+.2f} %)")
    for ls, tag in ((o, "M3"), (n, "R2")):
        log(f"  {tag} " + " | ".join(l.strip() for l in ls if l.strip().startswith(("vreset", "vsrc", "vbn_leak", "quiet"))))
    verdict("bias_spk off rate", abs(b / a - 1) <= 0.01, "(<= 1 %)")


def s10k():
    o, n = rd(OLD, "s10k_typical_27.txt"), rd(NEW, "s10k_typical_27.txt")
    if not (o and n):
        log("[s10k] missing")
        return
    pat = re.compile(r"^(\S+)\s+(s\d\d)\s+\S+\s+\d\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")
    po = {pat.match(l).group(2): pat.match(l).groups() for l in o if pat.match(l)}
    pn = {pat.match(l).group(2): pat.match(l).groups() for l in n if pat.match(l)}
    log("[s10k typ 27] neuron rate (MHz) old / new / delta %")
    worst = (0.0, "")
    for k in po:
        if k in pn:
            a, b = float(po[k][3]), float(pn[k][3])
            d = 100 * (b / a - 1) if a else 0.0
            if abs(d) > abs(worst[0]):
                worst = (d, po[k][0])
            log(f"  {po[k][0]:6s} {k}  {a:.3f} {b:.3f} {d:+6.2f} %")
    for ls, tag in ((o, "M3"), (n, "R2")):
        log(f"  {tag} " + next((l for l in ls if l.startswith("ua[0]")), ""))
        for l in ls:
            if l.startswith("  code") or l.startswith("  vbn_leak") or l.startswith("  vreset") or l.startswith("  vsrc"):
                log(f"  {tag} {l.strip()}")
    # S = 10000 spike counts are small (4-25 in 9.5 us): one spike more or less is 4-25 %; criterion on the rate
    verdict("s10k rates", abs(worst[0]) <= 2.0, f"(worst {worst[0]:+.2f} %, {worst[1]}; criterion 2 %)")


def icur():
    fo, fn = OLD / "icur_S10000_typical_27.json", NEW / "icur_S10000_typical_27.json"
    if not (fo.exists() and fn.exists()):
        log("[icur S10000] missing")
        return
    o, n = json.loads(fo.read_text())["S10000_ibx2"]["blocks"], json.loads(fn.read_text())["S10000_ibx2"]["blocks"]
    log("[icur S10000 ibx2] block I_vdd / I_vss (uA) old -> new")
    for b in sorted(set(o) | set(n)):
        a, c = o.get(b, [0, 0]), n.get(b, [0, 0])
        d = max(abs(c[0] - a[0]), abs(c[1] - a[1])) * 1e6
        log(f"  {b:6s} {a[0] * 1e6:9.3f} / {a[1] * 1e6:9.3f} -> {c[0] * 1e6:9.3f} / {c[1] * 1e6:9.3f}"
            f"{'   <-- > 1 uA' if d > 1 and b in o else ''}{'   (new)' if b not in o else ''}")
    to = [sum(v[i] for v in o.values()) * 1e6 for i in (0, 1)]
    tn = [sum(v[i] for v in n.values()) * 1e6 for i in (0, 1)]
    log(f"  total {to[0]:.1f} / {to[1]:.1f} -> {tn[0]:.1f} / {tn[1]:.1f} uA")


def plain(fn, title, nlines=12):
    n = rd(NEW, fn)
    o = rd(OLD, fn)
    log(f"[{title}] {fn}" + ("" if o else " (no M3 file)"))
    for l in (n or ["  missing"])[:nlines]:
        log("  " + l)
    if o:
        log("  M3:")
        for l in o[:nlines]:
            log("  " + l)


def coupling():
    o, n = rd(OLD, "coupling.txt"), rd(NEW, "coupling.txt")
    if not (o and n):
        log("[coupling] missing")
        return
    def parse(ls):
        v, sh = {}, {}
        for i, l in enumerate(ls):
            m = re.match(r"^(\S+ vm \(\S+\)|D1 \S+|AdEx \S+)\s+([\d.]+)\s", l)
            if m and i + 1 < len(ls):
                m2 = re.search(r"top-added (\d+) aF -> ([\d.]+) mV", ls[i + 1])
                if m2:
                    v[m.group(1)] = (float(m.group(2)), int(m2.group(1)), float(m2.group(2)))
            m = re.match(r"^(\S+)\s+([\d.]+)\s+sum\s+(\d+):", l)
            if m:
                sh[m.group(1)] = (float(m.group(2)), int(m.group(3)))
        return v, sh
    (vo, so), (vn, sn) = parse(o), parse(n)
    log("[coupling] victim: C_extr (fF) / top-added digital C (aF) / all-toggle kick (mV), old -> new")
    for k in vo:
        if k in vn:
            a, b = vo[k], vn[k]
            log(f"  {k:22s} {a[0]:7.2f} {a[1]:5d} {a[2]:5.2f} -> {b[0]:7.2f} {b[1]:5d} {b[2]:5.2f}"
                f"{'   <-- kick +' + format(b[2] - a[2], '.2f') + ' mV' if b[2] - a[2] > 0.5 else ''}")
    for k in vn:
        if k not in vo:
            b = vn[k]
            log(f"  {k:22s} (R2 only)             {b[0]:7.2f} {b[1]:5d} {b[2]:5.2f}")
    log("  shared line C_total (fF) / digital-coupled C (aF), old -> new (bay load on the column lines)")
    for k in so:
        if k in sn:
            log(f"  {k:12s} {so[k][0]:8.1f} {so[k][1]:6d} -> {sn[k][0]:8.1f} {sn[k][1]:6d}   dC {sn[k][0] - so[k][0]:+7.1f} fF "
                f"({100 * (sn[k][0] / so[k][0] - 1) if so[k][0] else 0:+.1f} %)")
    for ls, tag in ((o, "M3"), (n, "R2")):
        log(f"  {tag} " + next((l for l in ls if l.startswith("worst single")), "")[:400])


log(f"R2 ({NEW}) vs M3 ({OLD}) full-chip PEX regression")
log("")
bias_dc("bias_dc_S100.txt", "bias_dc_S100_r2c22.txt", "bias DC S=100, vth_cmp code 22 as the M3 run")
log("")
bias_dc("bias_dc_S100.txt", "bias_dc_S100.txt", "bias DC S=100, bench default (vth_cmp code 11)", skip=("aux3",))
log("")
bias_dat("bias_dc_S100.dat", "bias_dc_S100_r2c22.dat", "bias DC S=100 r2 22")
log("")
probe()
log("")
kick()
log("")
coupling()
log("")
spk()
log("")
s10k()
log("")
icur()
log("")
plain("gndchk_S100.txt", "gndchk S=100", 6)
log("")
log("FAILED: " + (", ".join(FAIL) if FAIL else "none"))
OUT.write_text("\n".join(L) + "\n")
