"""Check 2: bias distribution on the full-chip PEX (B1 -> far array column, AdEx, D1, tau cells, R1 buffers).

  python3 sim/tb/top/tb_top_bias.py dc   [S]        # DC: driver end vs far end of every line (R-network lines)
  python3 sim/tb/top/tb_top_bias.py step [S]        # code step after settling, settling at the far end
  python3 sim/tb/top/tb_top_bias.py spk  [on|off]   # S = 1000, 4 neighbours spiking (on) or not (off) around a
                                                    # victim neuron driven at 2x rheobase: victim rate, line ripple
Lines that have no R network in the extraction (extresist keeps only the nets whose R matters) are one node: their
far end equals the driver end by construction; what can still differ is the local ground / supply of the mirror
devices, which is the IR-drop result of pgrid.py (check 4).
spk also reports the ripple of every shared line at each array slot's own terminal, per neuron row (diagnosis of
the victim rate shift with spiking neighbours).
Writes sim/results/top/bias_<mode>_*.txt.   `--deck`: write the deck to $TOP_DECK_DIR (default /tmp/topdeck), no run.
"""
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402
from ngs import crossings     # noqa: E402

ARGV = [sys.argv[0]] + [a for a in sys.argv[1:] if not a.startswith("--")]
MODE = ARGV[1] if len(ARGV) > 1 else "dc"
LINES = ["vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_prb", "el", "vreset", "vreset_src", "vsrc", "vth_ref",
         "aux0", "aux2", "aux3", "vbn_ax", "vbp_w"]
DRIVER = {"vsrc": "r1", "vreset": "r1"}            # others: b1
FAR = ["s30", "s33", "ax", "d1", "tau0", "tau2"]    # array top row ends (M2 layout B: F2, AH400), AdEx, D1, tau cells
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


# ---- R networks: union-find over R elements; device terminals of each net per block
par = {}


def f(x):
    while par.get(x, x) != x:
        par[x] = par.get(par[x], par[x])
        x = par[x]
    return x


for l in T.load()["lines"]:
    if l[0] == "R":
        t = l.split()
        a, b = f(t[1]), f(t[2])
        if a != b:
            par[a] = b
term = defaultdict(lambda: defaultdict(set))       # group -> block -> {raw node}
for l in T.load()["lines"]:
    if l[0] in "XD":
        t = l.split()
        nn = [q for q in t[1:] if "=" not in q][:-1]
        o = T.owner(nn) or "other"
        for q in nn:
            term[f(q)][o].add(q)


def ends(ln):
    """(driver-end nodes, {far block: nodes}) of a line (raw names)."""
    g = f(T.net(ln))
    drv = term[g].get(DRIVER.get(ln, "b1"), set()) or {T.net(ln)}
    far = {b: term[g][b] for b in FAR if b in term[g]}
    return sorted(drv), {b: sorted(v) for b, v in far.items()}


if MODE == "dc":
    S = float(ARGV[2]) if len(ARGV) > 2 else 100.0
    sv, keys = [], []
    for ln in LINES:
        drv, far = ends(ln)
        for n in drv:
            sv.append(f"v({T.san(n)})"); keys.append((ln, "drv", n))
        for b, ns in far.items():
            for n in ns:
                sv.append(f"v({T.san(n)})"); keys.append((ln, b, n))
    sv = sorted(set(sv))
    body = B.chip(S, ib_x2=1 if S >= 300 else 0)
    r = B.go(B.deck(body, "op", sv), f"bias_dc_S{S:g}")
    log(f"Bias lines, DC at nominal codes, S = {S:g}, typical 27 C, full-chip PEX (ideal supplies: wiring R of the"
        f" line only; ground offsets are in pgrid.py). Far end - driver end, mV (max |.| over the block's terminals)")
    log("line         driver(V)  " + "  ".join(f"{b:>8s}" for b in FAR) + "   R-network?")
    for ln in LINES:
        drv, far = ends(ln)
        vd = np.mean([r[f"v({T.san(n)})".lower()][0] for n in drv])
        row = f"{ln:12s} {vd:8.4f}  "
        for b in FAR:
            if b in far:
                vv = [r[f"v({T.san(n)})".lower()][0] - vd for n in far[b]]
                row += f"  {1e3 * vv[int(np.argmax(np.abs(vv)))]:+8.3f}"
            else:
                row += f"  {'-':>8s}"
        g = f(T.net(ln))
        row += "   yes" if any(f(k) == g for k in par) else "   no (single node)"
        log(row)
    (B.OUT / f"bias_dc_S{S:g}.txt").write_text("\n".join(lines) + "\n")

elif MODE == "step":
    S = float(ARGV[2]) if len(ARGV) > 2 else 100.0
    c0 = B.op_point(S)
    c1 = {k: v - 4 for k, v in c0.items()}          # every DAC -4 codes (no wrap at the S >= 300 codes)
    TS, TEND = 40e-6 * 100 / S + 5e-6, 40e-6 * 100 / S + 5e-6 + 800e-6 * 100 / S
    st = B.timeline([(0.0, T.config(codes=c0, ib_x2=1 if S >= 300 else 0)),
                     (TS, T.config(codes=c1, ib_x2=1 if S >= 300 else 0))])
    body = B.chip(S, state_over=st)
    probes = {}
    for ln in LINES:
        drv, far = ends(ln)
        probes[(ln, "drv")] = drv[0]
        for b in ("s30", "ax", "d1", "tau0"):
            if b in far:
                probes[(ln, b)] = far[b][0]
    sv = sorted(set(f"v({T.san(n)})" for n in probes.values()))
    r = B.go(B.deck(body, f"tran 20n {TEND:g} 0 {TEND / 2000:g}", sv), f"bias_step_S{S:g}")
    t = r["_x"]
    log(f"Code step at {TS * 1e6:g} us (every DAC -4 codes at once), S = {S:g}, typical 27 C, full-chip PEX: "
        f"time from the step to within 1 % of the final change (and 0.5 LSB = 1/8 of the step), us")
    log("line          driver: 1% / LSB/2     s30 (far col.)    AdEx            D1              tau0")
    for ln in LINES:
        row = f"{ln:12s}"
        for b in ("drv", "s30", "ax", "d1", "tau0"):
            if (ln, b) not in probes:
                row += f"  {'-':>15s}"
                continue
            y = r[f"v({T.san(probes[(ln, b)])})".lower()]
            y0, yf = np.interp(TS - 1e-7, t, y), y[-1]
            dv = abs(yf - y0)
            res = []
            for tol in (0.01 * dv, dv / 8):
                late = np.where((np.abs(y - yf) > tol) & (t > TS))[0]
                res.append((t[late[-1]] - TS) * 1e6 if len(late) else 0.0)
            row += f"  {res[0]:6.1f} / {res[1]:6.1f}"
        log(row + f"   (step {1e3 * (yf - y0):+.1f} mV at the last column)")
    (B.OUT / f"bias_step_S{S:g}.txt").write_text("\n".join(lines) + "\n")

elif MODE == "spk":
    ON = (ARGV[2] if len(ARGV) > 2 else "on") == "on"
    S = 1000.0
    g = 200e-15 * S / 10e-3
    rheo = g * 0.08
    # victim H2 (1,1) and its 4 neighbours H1 (0,1), P2 (1,0), H3 (1,2), S2 (2,1); quiet S1 (2,0) (M2 layout B)
    VICTIM, QUIET = T.slot_inst("H2"), T.slot_inst("S1")
    SPIKERS = [T.slot_inst(n) for n in ("H1", "P2", "H3", "S2")]
    src = {"vstim": "Vstim vstim 0 3.3", "Ivic": f"Ivic vstim {T.vnode(VICTIM + '.vm')} DC {2 * rheo:g}"}
    if ON:
        for k, s in enumerate(SPIKERS):
            src[f"Isp{k}"] = f"Isp{k} vstim {T.vnode(s + '.vm')} DC {4 * rheo:g}"
    # SPK_R2: override the vth_cmp code (CMP slot state A/B, MIL-298); SPK_TEND: shorter run (the ISI is steady from
    # the first spike). Either one adds a suffix to the result names.
    import os
    codes = B.op_point(S)
    tag = ""
    if os.environ.get("SPK_R2"):
        codes["r2"] = int(os.environ["SPK_R2"])
        tag += f"_r2c{codes['r2']}"
    TEND = float(os.environ.get("SPK_TEND", "160e-6"))
    if "SPK_TEND" in os.environ:
        tag += f"_t{TEND * 1e6:g}"
    body = B.chip(S, codes=codes, ib_x2=1, sources=src)
    sh = ["vbn_leak", "vbn_ref", "vbp_st", "vbp_syn", "vbn_prb", "el", "vreset", "vsrc"]
    sv = [f"v({T.vnode(VICTIM + '.spk')})", f"v({T.vnode(VICTIM + '.vm')})", f"v({T.vnode(QUIET + '.vm')})"]
    near = {}
    for ln in sh:
        drv, far = ends(ln)
        gq = f(T.net(ln))
        nn = sorted(term[gq].get(VICTIM, set())) or [T.net(ln)]
        near[ln] = nn[0]
        sv.append(f"v({T.san(nn[0])})")
    # per-neuron ripple: each shared line at every array slot's own terminal (R-network lines; single-node lines
    # give one node for all slots), to see whether the victim row / column sees more ripple than the others
    SLOTS = [i for _, i, _ in T.neurons()]
    at_slot = {}
    for ln in sh:
        gq = f(T.net(ln))
        for s_ in SLOTS:
            nn = sorted(term[gq].get(s_, set())) or [T.net(ln)]
            at_slot[(ln, s_)] = nn[0]
            sv.append(f"v({T.san(nn[0])})")
    sv += [f"v({T.vnode(s + '.vm')})" for s in SLOTS]
    CMP = T.slot_inst("CMP")
    sv += [f"v({T.vnode(s + '.spk')})" for s in SPIKERS + [CMP]]
    name = f"bias_spk_{'on' if ON else 'off'}{tag}"
    r = B.go(B.deck(body, f"tran 5n {TEND:g} 0 5n", sorted(set(sv))), name)
    t = r["_x"]
    sp = crossings(t, r[f"v({T.vnode(VICTIM + '.spk')})".lower()], 1.65)
    sp = sp[sp > 30e-6]
    rate = (len(sp) - 1) / (sp[-1] - sp[0]) if len(sp) > 2 else 0.0
    log(f"S = 1000, IB_X2 = 1, EL/Vth/Vreset 1.50/1.58/1.50 V, typical 27 C; victim {VICTIM} at 2x rheobase "
        f"({2 * rheo * 1e9:.2f} nA); neighbours {SPIKERS} at 4x: {'ON' if ON else 'OFF'}")
    log(f"victim: {len(sp)} spikes after 30 us, rate {rate / 1e3:.3f} kHz, ISI "
        f"{np.mean(np.diff(sp)) * 1e6 if len(sp) > 2 else 0:.4f} us +- {np.std(np.diff(sp)) * 1e9 if len(sp) > 2 else 0:.1f} ns")
    for s in SPIKERS:
        n = len(crossings(t, r[f"v({T.vnode(s + '.spk')})".lower()], 1.65))
        log(f"  neighbour {s}: {n} spikes")
    cs = r[f"v({T.vnode(CMP + '.spk')})".lower()]
    log(f"  CMP {CMP} (vth_cmp code r2 = {codes['r2']}): {len(crossings(t, cs, 1.65))} spike edges, spk mean "
        f"{cs[t > 30e-6].mean():.3f} V")
    m = t > 30e-6
    q = r[f"v({T.vnode(QUIET + '.vm')})".lower()][m]
    log(f"quiet neuron {QUIET} vm: mean {q.mean():.4f} V, p-p {1e3 * (q.max() - q.min()):.2f} mV")
    log("shared lines at the victim (after 30 us): mean (V), p-p (mV), rms dev (mV)")
    for ln in sh:
        y = r[f"v({T.san(near[ln])})".lower()][m]
        log(f"  {ln:10s} {y.mean():.4f}  {1e3 * (y.max() - y.min()):8.2f}  {1e3 * y.std():7.3f}")
    log("")
    log("shared-line ripple per neuron, at each slot's own terminal of the line (after 30 us): p-p (mV) / mean - "
        "mean at the victim (mV); rows = array rows (r0 bottom); * = victim, + = spiking neighbour")
    log("slot   name    " + " ".join(f"{ln:>14s}" for ln in sh) + "   vm p-p (mV)")
    names = {i: n for n, i, _ in T.neurons()}
    for row_ in range(4):
        rs = [s_ for s_ in SLOTS if s_[1] == str(row_)]
        pp_row = {ln: 0.0 for ln in sh}
        for s_ in rs:
            tag = "*" if s_ == VICTIM else "+" if s_ in SPIKERS else " "
            cells = ""
            for ln in sh:
                y = r[f"v({T.san(at_slot[(ln, s_)])})".lower()][m]
                y0 = r[f"v({T.san(near[ln])})".lower()][m].mean()
                pp = 1e3 * (y.max() - y.min())
                pp_row[ln] = max(pp_row[ln], pp)
                cells += f" {pp:6.2f}/{1e3 * (y.mean() - y0):+6.2f}"
            v_ = r[f"v({T.vnode(s_ + '.vm')})".lower()][m]
            log(f"{s_}{tag}  {names[s_]:6s} {cells}   {1e3 * (v_.max() - v_.min()):8.1f}")
        log(f"row {row_} max p-p " + " ".join(f"{pp_row[ln]:14.2f}" for ln in sh))
    (B.OUT / f"{name}.txt").write_text("\n".join(lines) + "\n")
