"""R2 blocks E1 (bay by2, ce1_fb) and E2 (e2_leak) on the full-chip PEX (MIL-362, final chip r2-int 988c8d8).

  python3 sim/tb/top/tb_top_r2blk.py e1 [corner] [T]          # default typical 27
  python3 sim/tb/top/tb_top_r2blk.py e2 A|B [corner] [T]      # default ff 85; A: probe SEL 11 SUB 1, clamp off;
                                                              #               B: probe SEL 15 SUB 1, clamp on
e1 (docs/r2/e1-fixed-bias.md section 4): S = 100 nominal codes, probe on E1 (SEL 18, PROBE_SUB 0) for the whole run.
  0-60 us GRP_EN = 0 (E1 parked: vm and pad should read ~0 V); 60 us GRP_EN[1] = 1 (vm settles to EL, ~1.40 V);
  120 us sta = rt_out[0] = 1 (weight A, DC; every array neuron gets it too); 820 us + stb = rt_out[1] (A + B) to TEND.
  Reports parked vm / pad, EL, Vth (vm peaks), E1 rate in each window vs the block PEX (tt/27: A 9.2 kHz, A+B 17.0 kHz,
  first spike 116 us after sta), and S1-S3 rates in the same windows.
e2 (docs/r2/e2-leak.md): S = 100 nominal codes, vreset held (nominal R-DAC). 0-20 us GRP_EN[0] = 1 (charge na / nb to
  vreset), probe on the tap from 10 us; 20 us release (t = 0 of the droop); TEND = E2_TEND (default 1 s: the ff/85
  junction floor is ~-9 mV/s, i.e. 0.09 mV in 10 ms). Reports na / nb / pad at 1 ms .. TEND and the droop slope over
  the last 90 % of the run vs the block PEX (ff/85, vreset 1.2-1.5 V: na -9.04, nb clamp off -9.7..-9.9, on -9.03 mV/s).
Writes sim/results/top/r2blk_<mode>_<corner>_<T>.txt.   `--deck`: write the deck and stop.
"""
import os
import sys

import numpy as np

if sys.argv[1:2] == ["e1"] or sys.argv[1:2] == ["e2"]:   # the bay en (g_bay) needs the full glue model
    os.environ.setdefault("TOP_GLUE", "full")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402
from ngs import crossings     # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MODE = ARGS[0] if ARGS else "e1"
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


S = 100.0
codes = B.op_point(S)

if MODE == "e1":
    CORNER = ARGS[1] if len(ARGS) > 1 else "typical"
    TEMP = int(ARGS[2]) if len(ARGS) > 2 else 27
    TAG = f"e1_{CORNER}_{TEMP}"
    E1 = [i for n, i, c in T.bay() if c == "ce1_fb"]
    assert E1, "no ce1_fb in the bay (E1 not integrated)"
    E1 = E1[0]
    K = int(E1[2:])
    T_EN, T_A, T_AB, TEND = 60e-6, 120e-6, 820e-6, float(os.environ.get("E1_TEND", "1.5e-3"))
    pr = dict(blk="bay", k=K, sub=0)
    ev = [(0.0, T.config(codes=codes, probe=pr, grp_en=0)),
          (T_EN, T.config(codes=codes, probe=pr, grp_en=2)),
          (T_A, T.config(codes=codes, probe=pr, grp_en=2, rt=(1, 0, 0, 0))),
          (T_AB, T.config(codes=codes, probe=pr, grp_en=2, rt=(1, 1, 0, 0)))]
    body = B.chip(S, codes=codes, state_over=B.timeline(ev))
    ARR = [(n, i) for n, i, c in T.neurons() if n in ("S1", "S2", "S3")]
    sv = ["v(pad)", f"v({T.vnode(E1 + '.vm')})", f"v({T.vnode(E1 + '.spk')})"]
    sv += [f"v({T.vnode(i + '.spk')})" for _, i in ARR]
    d = B.deck(body, f"tran 10n {TEND:g} 0 50n", sv, corner=CORNER, temp=TEMP)
    r = B.go(d, f"r2blk_{TAG}{B.SUFFIX}", timeout=int(os.environ.get("R2BLK_TIMEOUT", "7200")))
    t = r["_x"]
    vm, pad = r[f"v({T.vnode(E1 + '.vm')})".lower()], r["v(pad)"]
    w = lambda a, b: (t >= a) & (t < b)
    log(f"E1 ({E1}, ce1_fb) on the full-chip PEX, {CORNER} {TEMP} C, S = {S:g}, codes {codes}, glue {T.GLUE_MODE}; "
        f"probe SEL {16 + K} (PROBE_SUB 0) throughout")
    log(f"parked (GRP_EN[1] = 0, 20-60 us): vm {vm[w(20e-6, T_EN)].mean() * 1e3:.3f} mV (max |vm| "
        f"{np.abs(vm[w(20e-6, T_EN)]).max() * 1e3:.3f} mV), pad {pad[w(20e-6, T_EN)].mean():.4f} V")
    el = vm[w(T_A - 20e-6, T_A)].mean()
    log(f"GRP_EN[1] = 1 at {T_EN * 1e6:g} us: EL (vm, {T_A * 1e6 - 20:g}-{T_A * 1e6:g} us) {el:.4f} V "
        f"(block PEX 1.407 V), pad {pad[w(T_A - 20e-6, T_A)].mean():.4f} V; vm within 5 mV of EL after "
        f"{(t[np.where((np.abs(vm - el) > 5e-3) & (t > T_EN) & (t < T_A))[0][-1]] - T_EN) * 1e6 if np.any((np.abs(vm - el) > 5e-3) & (t > T_EN) & (t < T_A)) else 0:.1f} us")
    ref = {"A": (9.2e3, T_A, T_AB), "A+B": (17.0e3, T_AB, TEND)}

    def rate(sp, a, b):
        s_ = sp[(sp >= a) & (sp < b)]
        return ((len(s_) - 1) / (s_[-1] - s_[0]) if len(s_) > 2 else 0.0), s_

    e1sp = crossings(t, r[f"v({T.vnode(E1 + '.spk')})".lower()], 1.65)
    for nm, (fr, a, b) in ref.items():
        f_, s_ = rate(e1sp, a, b)
        sub = s_[1:] if nm == "A" else s_        # A: skip the first spike (start from EL, block: 116 us)
        f2 = (len(sub) - 1) / (sub[-1] - sub[0]) if len(sub) > 2 else 0.0
        pk = [vm[w(x - 2e-6, x + 0.2e-6)].max() for x in s_]
        log(f"E1 input {nm:3s} ({a * 1e6:g}-{b * 1e6:g} us): {len(s_)} spikes, rate {f2 / 1e3:.2f} kHz "
            f"(block PEX {fr / 1e3:.1f} kHz, {100 * (f2 / fr - 1):+.1f} %)"
            + (f", first spike {(s_[0] - a) * 1e6:.1f} us after sta (block 116 us)" if nm == "A" and len(s_) else "")
            + (f", vm peak (Vth) {np.mean(pk):.4f} V, Vth - EL {1e3 * (np.mean(pk) - el):.1f} mV (block 78.6)" if pk else ""))
        rows = []
        for n, i in ARR:
            fa, _ = rate(crossings(t, r[f"v({T.vnode(i + '.spk')})".lower()], 1.65), a, b)
            rows.append(f"{n} {fa / 1e3:.2f}")
        log(f"   array S1-S3 in the same window (kHz): " + ", ".join(rows))
    log(f"pad (SEL {16 + K}) follows vm: pad - vm at EL {1e3 * (pad[w(T_A - 20e-6, T_A)].mean() - el):+.1f} mV")
elif MODE == "e2":
    WHICH = ARGS[1] if len(ARGS) > 1 else "A"
    CORNER = ARGS[2] if len(ARGS) > 2 else "ff"
    TEMP = int(ARGS[3]) if len(ARGS) > 3 else 85
    TAG = f"e2{WHICH}_{CORNER}_{TEMP}" + os.environ.get("E2_TAG", "")
    OPTS = os.environ.get("E2_OPTS", "reltol=1e-4")      # block bench (sim/tb/e2): gmin=1e-18 abstol=1e-18 method=gear
    NOPROBE = os.environ.get("E2_NOPROBE") == "1"
    TEND = float(os.environ.get("E2_TEND", "1.0"))
    T_PR, T_REL = 10e-6, 20e-6
    col = 2 if WHICH == "A" else 3                       # SEL 11 = (3,2) AH50, SEL 15 = (3,3) AH400, PROBE_SUB 1
    clamp = 0 if WHICH == "A" else 1
    pr = dict(row=3, col=col, sub=1, en=0 if NOPROBE else 1)
    g0 = 1 | (clamp << 2)
    ev = [(0.0, T.config(codes=codes, probe=dict(pr, en=0), grp_en=g0)),
          (T_PR, T.config(codes=codes, probe=pr, grp_en=g0)),
          (T_REL, T.config(codes=codes, probe=pr, grp_en=clamp << 2))]
    body = B.chip(S, codes=codes, state_over=B.timeline(ev))
    na, nb = T.vnode("e2.na"), T.vnode("e2.nb")
    sv = ["v(pad)", f"v({na})", f"v({nb})", f"v({T.vnode('vreset')})", f"v({T.vnode('abus')})"]
    EXTRA = []
    if os.environ.get("E2_SAVEALL") == "1":            # every node coupled to na / nb + every e2.* node
        for l in body.splitlines():
            if l[:1] == "C":
                t_ = l.split()
                if na in t_[1:3] or nb in t_[1:3]:
                    EXTRA += [x for x in t_[1:3] if x not in (na, nb, "0", "VGND", "VDPWR")]
        EXTRA += [T.san(x) for x in T.names() if x.startswith("e2.")]
        EXTRA = sorted(set(EXTRA) - {na, nb})
        sv += [f"v({x})" for x in EXTRA]
    d = B.deck(body, f"tran 10n {TEND:g} 0 {float(os.environ.get('E2_TMAX', min(2e-3, TEND / 200))):g}", sv, corner=CORNER, temp=TEMP,
               opts=OPTS)
    r = B.go(d, f"r2blk_{TAG}{B.SUFFIX}", timeout=int(os.environ.get("R2BLK_TIMEOUT", "7200")))
    t = r["_x"]
    log(f"E2 droop on the full-chip PEX, {CORNER} {TEMP} C, S = {S:g}, vreset held (nominal); GRP_EN[0] 1 -> 0 at "
        f"{T_REL * 1e6:g} us, clamp (GRP_EN[2]) {clamp}; probe SEL {11 if col == 2 else 15} PROBE_SUB 1 "
        f"(node {WHICH}) from {T_PR * 1e6:g} us{' (probe EN 0)' if NOPROBE else ''}; glue {T.GLUE_MODE}; options {OPTS}")
    ys = {"na": r[f"v({na})".lower()], "nb": r[f"v({nb})".lower()], "pad": r["v(pad)"],
          "vreset": r[f"v({T.vnode('vreset')})".lower()]}
    pts = [x for x in (T_REL - 1e-6, T_REL + 1e-6, 1e-3, 10e-3, 100e-3, 0.5, 1.0, TEND) if x <= TEND]
    log("node        " + " ".join(f"{('%g ms' % (x * 1e3)):>11s}" for x in pts) + "   slope over the last 90 % (mV/s)")
    m = t > T_REL + 0.1 * (TEND - T_REL)
    for k, y in ys.items():
        sl = np.polyfit(t[m], y[m], 1)[0] * 1e3 if m.sum() > 3 else float("nan")
        log(f"{k:10s} " + " ".join(f"{np.interp(x, t, y):11.6f}" for x in pts) + f"   {sl:+9.3f}")
    for x in EXTRA:
        y = r[f"v({x})".lower()]
        log(f"  {x:28s} {np.interp(T_REL + 1e-6, t, y):10.6f} -> {y[-1]:10.6f} V, slope {np.polyfit(t[m], y[m], 1)[0] * 1e3:+10.3f} mV/s")
    blk = {"A": "na -9.04 mV/s (vreset 1.2-1.5 V)", "B": "nb clamp on -9.03 mV/s, clamp off -9.7..-9.9 mV/s"}[WHICH]
    log(f"block PEX (docs/r2/e2-leak.md, ff/85, vreset held): {blk}; release step na / nb -5.2 / -10.6..-12.8 mV")
    rel = {k: 1e3 * (np.interp(T_REL + 1e-6, t, ys[k]) - np.interp(T_REL - 1e-6, t, ys[k])) for k in ("na", "nb")}
    log(f"release step (1 us after - before): na {rel['na']:+.2f} mV, nb {rel['nb']:+.2f} mV")
else:
    sys.exit(f"unknown mode {MODE}")
(B.OUT / f"r2blk_{TAG}{B.SUFFIX}.txt").write_text("\n".join(lines) + "\n")
