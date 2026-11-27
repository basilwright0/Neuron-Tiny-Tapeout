"""R2 blocks E1 (bay by2, ce1_fb) and E2 (e2_leak) on the full-chip PEX (MIL-362, final chip r2-int 988c8d8).

  python3 sim/tb/top/tb_top_r2blk.py e1 [corner] [T]          # default typical 27
  python3 sim/tb/top/tb_top_r2blk.py e1trip [corner] [T]      # default typical 27
  python3 sim/tb/top/tb_top_r2blk.py e2 A|B [corner] [T]      # default ff 85; A: probe SEL 11 SUB 1, clamp off;
                                                              #               B: probe SEL 15 SUB 1, clamp on
e1 (docs/r2/e1-fixed-bias.md section 4): S = 100 nominal codes, probe on E1 (SEL 18, PROBE_SUB 0) for the whole run.
  0-60 us GRP_EN = 0 (E1 parked: vm and pad should read ~0 V); 60 us GRP_EN[1] = 1 (vm settles to EL, ~1.40 V);
  120 us sta = rt_out[0] = 1 (weight A, DC; every array neuron gets it too); 820 us + stb = rt_out[1] (A + B) to TEND.
  E1 is probe-only (its spk pin is open, spk_in[18] tied low, r2-int c91f33e): spikes are the vm sawtooth resets
  (falling crossings of EL + E1_VDET, default 40 mV), as the user counts them on ua[1].
  Reports parked vm / pad, EL, Vth (vm peaks), E1 rate in each window vs the block PEX (tt/27: A 9.2 kHz, A+B 17.0 kHz,
  first spike 116 us after sta), and S1-S3 rates in the same windows.
e1trip: E1 DC trip as tb_e1.py dc_char (EL = zero-current vm of a vm source, Vth = vm where spk trips), as a slow
  transient ramp (full-chip DC sweeps get OOM-killed): S = 100 nominal codes, GRP_EN[1] = 1 from 0, probe off, no
  input; by2.vm forced through E1T_R (1 kohm) at E1T_RATE (1 mV/us) around E1T_EL (1.407 V): EL - 60 -> EL + 20 ->
  EL - 60 mV (EL from the up/down-averaged current, cancels C dV/dt), then -> EL + 160 mV (Vth: first by2.spk
  crossing of VDD/2). 400 us. Block PEX tt/27: EL 1.407 V, Vth 1.486 V, gap 78.6 mV.
e2 (docs/r2/e2-leak.md): S = 100 nominal codes, vreset held (nominal R-DAC). 0-20 us GRP_EN[0] = 1 (charge na / nb to
  vreset), probe on the tap from 10 us; 20 us release (t = 0 of the droop); TEND = E2_TEND (default 1 s: the ff/85
  junction floor is ~-9 mV/s, i.e. 0.09 mV in 10 ms). Reports na / nb / pad at 1 ms .. TEND and the droop slope over
  the last 90 % of the run vs the block PEX (ff/85, vreset 1.2-1.5 V: na -9.04, nb clamp off -9.7..-9.9, on -9.03 mV/s).
Writes sim/results/top/r2blk_<mode>_<corner>_<T>.txt.   `--deck`: write the deck and stop.
"""
import os
import sys

import numpy as np

if sys.argv[1:2] in (["e1"], ["e1trip"], ["e2"]):   # the bay en (g_bay) needs the full glue model
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
    TAG = f"e1_{CORNER}_{TEMP}" + os.environ.get("E1_TAG", "")
    E1 = [i for n, i, c in T.bay() if c == "ce1_fb"]
    assert E1, "no ce1_fb in the bay (E1 not integrated)"
    E1 = E1[0]
    K = int(E1[2:])
    T_EN, T_A = 60e-6, 120e-6
    T_AB, TEND = float(os.environ.get("E1_TAB", "820e-6")), float(os.environ.get("E1_TEND", "1.5e-3"))
    pr = dict(blk="bay", k=K, sub=0)
    ev = [(0.0, T.config(codes=codes, probe=pr, grp_en=0)),
          (T_EN, T.config(codes=codes, probe=pr, grp_en=2)),
          (T_A, T.config(codes=codes, probe=pr, grp_en=2, rt=(1, 0, 0, 0))),
          (T_AB, T.config(codes=codes, probe=pr, grp_en=2, rt=(1, 1, 0, 0)))]
    body = B.chip(S, codes=codes, state_over=B.timeline(ev))
    ARR = [(n, i) for n, i, c in T.neurons() if n in ("S1", "S2", "S3")]
    sv = ["v(pad)", f"v({T.vnode(E1 + '.vm')})"]                     # E1 spk pin is open (probe-only)
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

    e1sp = crossings(t, vm, el + float(os.environ.get("E1_VDET", "0.04")), rising=False)   # vm resets (no spk)
    e1sp = e1sp[e1sp > T_A]
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
elif MODE == "e1trip":
    CORNER = ARGS[1] if len(ARGS) > 1 else "typical"
    TEMP = int(ARGS[2]) if len(ARGS) > 2 else 27
    TAG = f"e1trip_{CORNER}_{TEMP}" + os.environ.get("E1_TAG", "")
    E1 = [i for n, i, c in T.bay() if c == "ce1_fb"]
    assert E1, "no ce1_fb in the bay (E1 not integrated)"
    E1 = E1[0]
    EL0 = float(os.environ.get("E1T_EL", "1.407"))       # ramp anchor: block PEX EL (tt/27, S = 100)
    RATE = float(os.environ.get("E1T_RATE", "1e3"))      # V/s (1 mV/us)
    RF = float(os.environ.get("E1T_R", "1e3"))           # source -> by2.vm
    LO, MID, HI, T0 = EL0 - 0.060, EL0 + 0.020, EL0 + 0.160, 20e-6
    # 0-T0 hold at LO; up LO -> MID, down MID -> LO (trip-free pair: averaging the two currents at the same vm
    # cancels the C dV/dt current, ~tau x rate = 100 mV of offset at 1 mV/us); up LO -> HI (Vth: spk first crossing)
    t1 = T0 + (MID - LO) / RATE
    t2 = t1 + (MID - LO) / RATE
    TEND = t2 + (HI - LO) / RATE
    ramp = B.pwl([(0, LO), (T0, LO), (t1, MID), (t2, LO), (TEND, HI)])
    src = {"Fe1": f"Vfe1 fe1 0 {ramp}", "Rfe1": f"Rfe1 fe1 {T.vnode(E1 + '.vm')} {RF:g}"}
    st = T.config(codes=codes, grp_en=2)                   # GRP_EN[1] = 1 from t = 0, probe off (as the block bench)
    body = B.chip(S, codes=codes, sources=src, state_over=st)
    vmn, spn = T.vnode(E1 + ".vm"), T.vnode(E1 + ".spk")   # spk: internal node (the cell's spk pin is open)
    sv = [f"v({vmn})", f"v({spn})", "i(vfe1)", "v(fe1)"]
    d = B.deck(body, f"tran 10n {TEND:g} 0 50n", sv, corner=CORNER, temp=TEMP)
    r = B.go(d, f"r2blk_{TAG}{B.SUFFIX}", timeout=int(os.environ.get("R2BLK_TIMEOUT", "7200")))
    t = r["_x"]
    vm, spk, ii = r[f"v({vmn})".lower()], r[f"v({spn})".lower()], -r["i(vfe1)"]   # ii > 0: cell sinks (vm > EL)
    log(f"E1 ({E1}, ce1_fb) DC trip on the full-chip PEX by a slow vm ramp, {CORNER} {TEMP} C, S = {S:g}, codes "
        f"{codes}, glue {T.GLUE_MODE}; GRP_EN[1] = 1 from 0, probe off, no input; vm forced through {RF:g} ohm, "
        f"{RATE * 1e-3:g} mV/us: hold {LO:.3f} V to {T0 * 1e6:g} us, up to {MID:.3f} V, down to {LO:.3f} V, "
        f"up to {HI:.3f} V at {TEND * 1e6:g} us")
    up, dn = (t >= T0) & (t <= t1), (t > t1) & (t <= t2)
    xs = np.arange(LO + 0.002, MID - 0.002, 0.0005)
    o = np.argsort(vm[up])
    iu = np.interp(xs, vm[up][o], ii[up][o])
    o = np.argsort(vm[dn])
    idn = np.interp(xs, vm[dn][o], ii[dn][o])
    iav, ic = (iu + idn) / 2, (iu - idn) / 2

    def zc(x, y):
        k = np.where((y[:-1] < 0) & (y[1:] >= 0))[0]
        return float(x[k[0]] - y[k[0]] * (x[k[0] + 1] - x[k[0]]) / (y[k[0] + 1] - y[k[0]])) if len(k) else float("nan")

    el = zc(xs, iav)
    m = np.abs(xs - el) <= 0.005
    g = np.polyfit(xs[m], iav[m], 1)[0] if m.sum() > 3 else float("nan")
    up2 = t > t2
    tr = crossings(t[up2], spk[up2], 1.65)
    # Vth = the forced source voltage at the trip. vm itself is no good there: through RF the cell's regenerative
    # upstroke runs vm ~13 mV past the ramp before spk reaches VDD/2 (the source then sinks ~ -12 uA), so vm at the
    # spk crossing overstates Vth, and interpolating the current at Vth - 1 mV against vm lands in the upstroke
    # (the -11844043 pA printout). On the ramp below the takeoff vm = v(fe1) within < 1 uV (I x 1 kohm).
    fe = r["v(fe1)"]
    vth = float(np.interp(tr[0], t, fe)) if len(tr) else float("nan")
    vm_tr = float(np.interp(tr[0], t, vm)) if len(tr) else float("nan")
    tr1 = crossings(t[t <= t2], spk[t <= t2], 1.65)
    log(f"EL (zero of the up/down-averaged source current) {el:.4f} V (block PEX 1.407 V, {1e3 * (el - 1.407):+.1f} mV); "
        f"g at EL {g * 1e9:.2f} nS (block 2.1); C dV/dt current {np.mean(ic) * 1e12:.0f} pA = C_eff "
        f"{np.mean(ic) / RATE * 1e15:.0f} fF; zero of the raw up / down current {zc(xs, iu):.4f} / {zc(xs, idn):.4f} V")
    log(f"Vth (forced vm = v(fe1) at the first rising spk crossing of 1.65 V, final up ramp; vm there {vm_tr:.4f} V, "
        f"past the ramp by the upstroke) {vth:.4f} V (block PEX 1.486 V, "
        f"{1e3 * (vth - 1.486):+.1f} mV) at {tr[0] * 1e6 if len(tr) else float('nan'):.1f} us; "
        f"{len(tr)} spk crossings on that ramp" + (f"; WARNING: spk tripped {len(tr1)}x in the trip-free pair" if len(tr1) else ""))
    mm = up2 & (t < (tr[0] if len(tr) else TEND)) & (np.abs(vm - fe) < 1e-4)   # final ramp, vm still on the source
    rh = np.interp(vth - 1e-3, fe[mm], ii[mm]) - np.mean(ic) if len(tr) else float("nan")
    # At 1 mV/us the detector's first stage couples ~2.5 fC back onto vm in the last ~30 mV before the trip (a hump
    # that a DC sweep doesn't have), so the raw value overstates the rheobase. The DC estimate extrapolates the
    # straight leak line fitted between EL and Vth - 20 mV.
    lf = mm & (fe >= el) & (fe <= vth - 0.02)
    rh_dc = (np.polyval(np.polyfit(fe[lf], ii[lf], 1), vth - 1e-3) - np.mean(ic)) if len(tr) and lf.sum() > 3 else float("nan")
    log(f"gap Vth - EL {1e3 * (vth - el):.1f} mV (block PEX 78.6 mV); rheobase DC estimate (leak line EL..Vth - 20 mV "
        f"at Vth - 1 mV, minus C dV/dt) {rh_dc * 1e12:.0f} pA (block 156); raw at Vth - 1 mV incl. the detector "
        f"feedback hump {rh * 1e12:.0f} pA")
    log("after the trip the reset fights the forced source (vm held by the source); only the first crossing is used")
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
