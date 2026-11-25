"""R2 bay column (by0 = S4 cslot_ah, by1 = F4 cslot_ah_f, by2 = E1 slot, a cslot_ah until e1_fb lands) on the
full-chip PEX (MIL-362).

  python3 sim/tb/top/tb_top_bay.py fire  [corner] [T]   # bay S4 / F4 / by2 and the array S1-S3 / F1 fire together
  python3 sim/tb/top/tb_top_bay.py probe [corner] [T]   # ua[1] probe steps onto SEL 16 / 17 / 18 (bay)

fire: S = 1000, IB_X2 = 1, EL / Vth / Vreset 1.50 / 1.58 / 1.50 V (topbench.op_point, as tb_top_bias.py spk); every
  driven neuron gets the same DC input from 3.3 V, K x its nominal rheobase g * GF * 80 mV (g = 200 fF * S / 10 ms,
  GF = 0.5 for the F cells, as tb_top_s10k.py). Same cell type in the array is the reference: by0 / by2 vs the mean
  of S1-S3 (cslot_ah), by1 vs F1 (cslot_ah_f). Rate from the spk rising edges after T_SKIP. PASS: |rate / ref - 1|
  <= TOL. Also every column line at the bay top (by2) vs the array (s30) while firing.
probe: S = 100 (as tb_top_probe.py step); taps forced by ideal sources: near H1 1.6 V, far (3,0) 1.0 V, by0 1.0 V,
  by1 1.6 V, by2 1.0 V. Sequence near -> by0 -> by1 -> by2 -> near -> far, each move the firmware 3-step (EN 0 with
  the old SEL, then the new SEL, then EN 1; bay: probe_sel_bay[k] = EN & SEL == 16 + k, rsel / en_c all 0;
  en_b via g_bay -> NOR4). Reports pad level, 1 % settling (PASS <= 2 us as the array bench) and the pad level of
  each bay tap minus the array tap forced to the same voltage (far for 1.0 V, near for 1.6 V).
Writes sim/results/top/bay_<mode>_<corner>_<T>.txt.   `--deck`: write the deck and stop.
"""
import os
import sys

import numpy as np

if "probe" in sys.argv[1:2]:              # the bay en (g_bay) comes from the bay glue or3: needs the full glue model
    os.environ.setdefault("TOP_GLUE", "full")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402
from ngs import crossings     # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MODE = ARGS[0] if ARGS else "fire"
CORNER = ARGS[1] if len(ARGS) > 1 else "typical"
TEMP = int(ARGS[2]) if len(ARGS) > 2 else 27
TAG = f"{CORNER}_{TEMP}"
BAY = T.bay()
assert BAY, "no bay column in this floorplan (pre-R2 netlist)"
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


if MODE == "fire":
    S = 1000.0
    K = float(os.environ.get("BAY_K", "3"))
    TEND = float(os.environ.get("BAY_TEND", "100e-6"))
    T_SKIP = 20e-6
    TOL = 0.05
    g = 200e-15 * S / 10e-3
    ARR = [(n, i, c) for n, i, c in T.neurons() if n in ("S1", "S2", "S3", "F1")]
    DRV = ARR + BAY
    REF = {}
    for n, i, c in BAY:
        same = [i2 for n2, i2, c2 in ARR if c2 == c]
        assert same, f"no array neuron of cell {c} for {n}"
        REF[i] = same
    src = {"vstim": "Vstim vstim 0 3.3"}
    for n, i, c in DRV:
        gf = 0.5 if c.endswith("ah_f") else 1.0
        src[f"I{i}"] = f"I{i} vstim {T.vnode(i + '.vm')} DC {K * g * gf * 0.08:g}"
    codes = B.op_point(S)
    body = B.chip(S, codes=codes, ib_x2=1, sources=src)
    sh = ["vbn_leak", "vbn_ref", "vbp_st", "vbp_syn", "vbn_prb", "el", "vreset", "vsrc"]
    sv = [f"v({T.vnode(i + '.' + p)})" for _, i, _ in DRV for p in ("vm", "spk")]
    sv += [f"v({T.vnode(ln)})" for ln in sh]
    r = B.go(B.deck(body, f"tran 5n {TEND:g} 0 5n", sorted(set(sv)), corner=CORNER, temp=TEMP), f"bay_fire_{TAG}")
    t = r["_x"]
    rate = {}
    log(f"Bay firing, full-chip PEX, {CORNER} {TEMP} C, S = {S:g}, IB_X2 = 1, codes {codes}; every neuron at "
        f"{K:g} x rheobase (g = {g * 1e9:.1f} nS x GF, GF 0.5 for F cells); rate from spikes after {T_SKIP * 1e6:g} us")
    log("neuron  inst  cell          I(nA)  spikes  rate(kHz)  ISI std(ns)  vm min-max (V)")
    for n, i, c in DRV:
        sp = crossings(t, r[f"v({T.vnode(i + '.spk')})".lower()], 1.65)
        sp = sp[sp > T_SKIP]
        rate[i] = (len(sp) - 1) / (sp[-1] - sp[0]) if len(sp) > 2 else 0.0
        vm = r[f"v({T.vnode(i + '.vm')})".lower()][t > T_SKIP]
        gf = 0.5 if c.endswith("ah_f") else 1.0
        log(f"{n:6s}  {i:4s}  {c:12s} {K * g * gf * 0.08 * 1e9:6.2f}  {len(sp):5d}   {rate[i] / 1e3:8.3f}   "
            f"{np.std(np.diff(sp)) * 1e9 if len(sp) > 2 else 0:8.1f}     {vm.min():.3f}-{vm.max():.3f}")
    log("")
    log(f"bay vs the array neurons of the same cell (PASS: |ratio - 1| <= {TOL * 100:g} %)")
    bad = 0
    for n, i, c in BAY:
        ref = np.mean([rate[x] for x in REF[i]])
        ratio = rate[i] / ref if ref > 0 else 0.0
        ok = rate[i] > 0 and abs(ratio - 1) <= TOL
        bad += not ok
        log(f"  {n:3s} {i}: {rate[i] / 1e3:8.3f} kHz vs {'/'.join(REF[i])} {ref / 1e3:8.3f} kHz -> ratio {ratio:.4f} "
            f"({100 * (ratio - 1):+.2f} %)  {'PASS' if ok else 'FAIL'}")
    log(f"bay firing: {'PASS' if not bad else f'FAIL ({bad})'}")
    log("")
    log(f"column lines while firing (after {T_SKIP * 1e6:g} us): mean (V) / p-p (mV) at the saved node")
    m = t > T_SKIP
    for ln in sh:
        y = r[f"v({T.vnode(ln)})".lower()][m]
        log(f"  {ln:9s} {y.mean():.4f}  {1e3 * (y.max() - y.min()):7.2f}")

elif MODE == "probe":
    S = 100.0
    _FAR, _NEAR = (3, 0), T.slot_pos("H1")
    TAP_FAR = f"far {T.fp.slot_map()[_FAR]} ({_FAR[0]},{_FAR[1]})"
    TAP_NEAR = f"near H1 ({_NEAR[0]},{_NEAR[1]})"
    TAPS = {TAP_FAR: (f"s{_FAR[0]}{_FAR[1]}.vm", dict(row=_FAR[0], col=_FAR[1], sub=0), 1.0),
            TAP_NEAR: (f"s{_NEAR[0]}{_NEAR[1]}.vm", dict(row=_NEAR[0], col=_NEAR[1], sub=0), 1.6)}
    BV = [1.0, 1.6, 1.0]
    for k, (n, i, c) in enumerate(BAY):
        TAPS[f"SEL {16 + k} {n} {i}"] = (f"{i}.vm", dict(blk="bay", k=k, sub=0), BV[k])
    BT = list(TAPS)[2:]
    seq = [TAP_NEAR] + BT + [TAP_NEAR, TAP_FAR]
    SEG, T0 = 6e-6, 10e-6
    codes = B.op_point(S)
    ev = [(0.0, T.config(codes=codes, probe=TAPS[seq[0]][1]))]
    t_on = []
    for i, nm in enumerate(seq[1:]):
        t0 = T0 + i * SEG
        ev.append((t0, T.config(codes=codes, probe=dict(TAPS[seq[i]][1], en=0))))
        ev.append((t0 + 0.5e-6, T.config(codes=codes, probe=dict(TAPS[nm][1], en=0))))
        ev.append((t0 + 1.0e-6, T.config(codes=codes, probe=TAPS[nm][1])))
        t_on.append(t0 + 1.0e-6)
    tend = T0 + (len(seq) - 1) * SEG
    srcs = {f"F{k}": f"Vf{k} {T.vnode(nd)} 0 {v}" for k, (nd, pc, v) in enumerate(TAPS.values())}
    body = B.chip(S, sources=srcs, state_over=B.timeline(ev))
    sv = ["v(pad)", f"v({T.vnode('ua[1]')})", f"v({T.vnode('abus')})", f"v({T.vnode('en_b')})"]
    try:
        sv.append(f"v({T.vnode('g_bay')})")
    except KeyError:
        pass
    r = B.go(B.deck(body, f"tran 2n {tend:g}", sv, corner=CORNER, temp=TEMP), f"bay_probe_{TAG}")
    t, y = r["_x"], r["v(pad)"]
    enb = r[f"v({T.vnode('en_b')})".lower()]
    log(f"Bay probe steps (SEL 16-18), {CORNER} {TEMP} C, glue model {T.GLUE_MODE}, S = {S:g}, 200 pF board after 500 ohm; firmware 3-step "
        f"move; forced taps " + ", ".join(f"{k} {v[2]:g} V" for k, v in TAPS.items()))
    log("move                                   pad before -> after (V)   t_settle 1 % (ns)   overshoot (%)   "
        "ripple last 1 us (mV)   en_b (V)")
    worst, lvl = 0, {}
    for i, ton in enumerate(t_on):
        tend_i = ton + SEG - 1.0e-6
        m = (t >= ton - 1e-6) & (t <= tend_i)
        tt, yy = t[m], y[m]
        yf = np.interp(tend_i, t, y)
        y0 = np.interp(T0 + i * SEG - 1e-9, t, y)
        band = 0.01 * abs(yf - y0)
        late = np.where((np.abs(yy - yf) > band) & (tt > ton))[0]
        ts = (tt[late[-1]] - ton) if len(late) else 0.0
        a = yy[tt > ton]
        ov = 100 * max(0.0, np.max((a - yf) * np.sign(yf - y0))) / abs(yf - y0)
        last = yy[tt > tend_i - 1e-6]
        worst = max(worst, ts)
        lvl.setdefault(seq[i + 1], yf)
        log(f"{seq[i]:20s} -> {seq[i + 1]:20s}   {y0:.4f} -> {yf:.4f}          {ts * 1e9:7.0f}            "
            f"{ov:6.2f}          {1e3 * (last.max() - last.min()):5.2f}          {np.interp(tend_i, t, enb):.2f}")
    log(f"worst 1 % settling {worst * 1e9:.0f} ns -> {'PASS' if worst <= 2e-6 else 'FAIL'} (<= 2 us)")
    log("")
    log("bay pad level vs the array tap forced to the same voltage (mV)")
    for k in BT:
        ref = TAP_FAR if TAPS[k][2] == 1.0 else TAP_NEAR
        log(f"  {k:20s} forced {TAPS[k][2]:.2f} V: pad {lvl[k]:.4f} V, {ref} {lvl[ref]:.4f} V -> "
            f"{1e3 * (lvl[k] - lvl[ref]):+.2f} mV")
else:
    sys.exit(f"unknown mode {MODE}")
(B.OUT / f"bay_{MODE}_{TAG}.txt").write_text("\n".join(lines) + "\n")
