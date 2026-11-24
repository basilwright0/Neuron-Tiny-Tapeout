"""Check 1: probe chain on the full-chip PEX (sim/tb/top/topnet.py), loaded by 200 pF (TT pad + board).

  python3 sim/tb/top/tb_top_probe.py dc   [corner] [T]   # DC transfer of each tap, PEX vs schematic chain
  python3 sim/tb/top/tb_top_probe.py step [corner] [T]   # probe-select changes (firmware 3-step), 1 % settling

Taps (from floorplan MAP): far = slot (3,0) (s30, row 3 / column 0: the longest abus path to R1; M2 layout B: F2),
near = H1 (M2 layout B: s01, row 0 / column 1),
D1 soma tap (sel0, PROBE_SUB 0), AdEx vm tap. The probed node is forced by an ideal source (the neuron's own
circuit stays connected). Pad = the board node after the 500 ohm mux (what a scope sees); 200 pF.
Results: sim/results/top/probe_<mode>_<corner>_<T>.txt
"""
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "dc"
CORNER = sys.argv[2] if len(sys.argv) > 2 else "typical"
TEMP = int(sys.argv[3]) if len(sys.argv) > 3 else 27
S = 100.0
_FAR, _NEAR = (3, 0), T.slot_pos("H1")
TAP_FAR = f"far {T.fp.slot_map()[_FAR]} ({_FAR[0]},{_FAR[1]})"
TAP_NEAR = f"near H1 ({_NEAR[0]},{_NEAR[1]})"
TAPS = {  # name: (forced node, probe config, schematic tap kind)
    TAP_FAR: (f"s{_FAR[0]}{_FAR[1]}.vm", dict(row=_FAR[0], col=_FAR[1], sub=0), "slot"),
    TAP_NEAR: (f"s{_NEAR[0]}{_NEAR[1]}.vm", dict(row=_NEAR[0], col=_NEAR[1], sub=0), "slot"),
    "D1 soma": ("d1.vs", dict(blk="d1", sub=0), "d1"),
    "AdEx vm": ("ax.vm", dict(blk="adex", sub=0), "adex"),
}
TAG = f"{CORNER}_{TEMP}"
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


def forced(values):
    """Ideal sources on every tap node (values: name -> source spec)."""
    return {f"F{k}": f"Vf{k} {T.vnode(TAPS[n][0])} 0 {v}" for k, (n, v) in enumerate(values.items())}


if MODE == "dc":
    log(f"Probe chain DC transfer, {CORNER} {TEMP} C, S = {S:g}, pad after 500 ohm / 200 pF (DC: no load current)")
    log("tap              src   gain(1.0-1.6)  Vpad@1.2   lin.resid  PEX-SCH @1.0/1.2/1.6/2.0 (mV)")
    for k, (name, (nd, pc, kind)) in enumerate(TAPS.items()):
        res = {}
        others = {n: "1.2" for n in TAPS if n != name}
        for src in ("pex", "sch"):
            if src == "pex":
                srcs = forced(dict(others, **{name: "1.2"}))
                body = B.chip(S, probe=pc, sources=srcs)
                vname = f"vf{list(TAPS).index(name)}"
                d = B.deck(body, f"dc {vname} 0.9 2.1 0.05", ["v(pad)", f"v({T.vnode('abus')})"],
                           corner=CORNER, temp=TEMP)
            else:
                body = B.sch_chain(S, tap=kind, vin="1.2")
                vname = "vin"
                d = B.deck(body, "dc vin 0.9 2.1 0.05", ["v(pad)", "v(abus)"], corner=CORNER, temp=TEMP)
            r = B.go(d, f"probe_dc_{src}_{k}_{TAG}")
            x, y = r["_x"], r["v(pad)"]
            m = (x >= 0.999) & (x <= 1.601)
            p = np.polyfit(x[m], y[m], 1)
            res[src] = (x, y, p, np.max(np.abs(np.polyval(p, x[m]) - y[m])))
        for src in ("pex", "sch"):
            x, y, p, rr = res[src]
            dif = ""
            if src == "pex":
                xs, ys = res["sch"][0], res["sch"][1]
                dif = " ".join(f"{1e3 * (np.interp(v, x, y) - np.interp(v, xs, ys)):+6.2f}" for v in (1.0, 1.2, 1.6, 2.0))
            log(f"{name:15s}  {src}   {p[0]:.4f}        {np.interp(1.2, x, y):.4f}    {rr * 1e3:5.2f} mV   {dif}")
elif MODE == "ramp":
    # DC transfer without a full-chip DC sweep (each sweep point is a full-chip op, which does not converge by
    # Newton): one transient per tap from the preconditioned start, the forced tap node ramped 0.9 -> 2.1 -> 0.9 V.
    # Averaging the up and down ramps at the same input cancels the first-order lag of the chain (pad RC, follower);
    # half their difference is reported as the residual lag. The schematic reference keeps its (cheap) DC sweep.
    #   python3 tb_top_probe.py ramp [corner] [T] [tap index 0-3, default all]
    TR, T0 = 12e-6, 8e-6
    sel = [int(sys.argv[4])] if len(sys.argv) > 4 else range(len(TAPS))
    log(f"Probe chain DC transfer (PEX: up/down ramp 0.9-2.1 V, {TR * 1e6:g} us each way; SCH: DC sweep), "
        f"{CORNER} {TEMP} C, S = {S:g}, pad after 500 ohm / 200 pF")
    log("tap              src   gain(1.0-1.6)  Vpad@1.2   lin.resid  PEX-SCH @1.0/1.2/1.6/2.0 (mV)   lag@1.2 (mV)")
    xs = np.arange(0.95, 2.051, 0.01)
    for k in sel:
        name = list(TAPS)[k]
        nd, pc, kind = TAPS[name]
        others = {n: "1.2" for n in TAPS if n != name}
        ramp = B.pwl([(0, 0.9), (T0, 0.9), (T0 + TR, 2.1), (T0 + 2 * TR, 0.9)])
        body = B.chip(S, probe=pc, sources=forced(dict(others, **{name: ramp})))
        d = B.deck(body, f"tran 5n {T0 + 2 * TR:g}", ["v(pad)"], corner=CORNER, temp=TEMP)
        r = B.go(d, f"probe_ramp_pex_{k}_{TAG}")
        t, y = r["_x"], r["v(pad)"]
        up = (t >= T0) & (t <= T0 + TR)
        dn = t > T0 + TR
        xu = 0.9 + 1.2 * (t[up] - T0) / TR
        xd = 2.1 - 1.2 * (t[dn] - T0 - TR) / TR
        yu = np.interp(xs, xu, y[up])
        yd = np.interp(xs, xd[::-1], y[dn][::-1])
        ypex, lag = (yu + yd) / 2, (yu - yd) / 2
        body = B.sch_chain(S, tap=kind, vin="1.2")
        rs = B.go(B.deck(body, "dc vin 0.9 2.1 0.01", ["v(pad)"], corner=CORNER, temp=TEMP),
                  f"probe_ramp_sch_{k}_{TAG}")
        ysch = np.interp(xs, rs["_x"], rs["v(pad)"])
        m = (xs >= 0.999) & (xs <= 1.601)
        for src, yy in (("pex", ypex), ("sch", ysch)):
            p = np.polyfit(xs[m], yy[m], 1)
            rr = np.max(np.abs(np.polyval(p, xs[m]) - yy[m]))
            dif = lg = ""
            if src == "pex":
                dif = " ".join(f"{1e3 * (np.interp(v, xs, ypex) - np.interp(v, xs, ysch)):+6.2f}"
                               for v in (1.0, 1.2, 1.6, 2.0))
                lg = f"   {1e3 * np.interp(1.2, xs, lag):+6.2f}"
            log(f"{name:15s}  {src}   {p[0]:.4f}        {np.interp(1.2, xs, yy):.4f}    {rr * 1e3:5.2f} mV   {dif}{lg}")
    if len(sel) == 1:
        TAG = f"{TAG}_tap{sel[0]}"
elif MODE == "step":
    # far(1.0) -> near(1.6) -> far(1.0) -> D1(1.3) -> AdEx(1.8) -> near(1.6); firmware 3-step move each time:
    # t0: PROBE_EN = 0 (old SEL), t0+0.5 us: new SEL/SUB, t0+1 us: PROBE_EN = 1; settle window 5 us.
    seq = [TAP_FAR, TAP_NEAR, TAP_FAR, "D1 soma", "AdEx vm", TAP_NEAR]
    val = {TAP_FAR: 1.0, TAP_NEAR: 1.6, "D1 soma": 1.3, "AdEx vm": 1.8}
    SEG, T0 = 6e-6, 10e-6
    codes = B.op_point(S)
    ev = [(0.0, T.config(codes=codes, probe=TAPS[seq[0]][1]))]
    t_on = []
    for i, nm in enumerate(seq[1:]):
        t0 = T0 + i * SEG
        prev = TAPS[seq[i]][1]
        ev.append((t0, T.config(codes=codes, probe=dict(prev, en=0))))
        new = TAPS[nm][1]
        ev.append((t0 + 0.5e-6, T.config(codes=codes, probe=dict(new, en=0))))
        ev.append((t0 + 1.0e-6, T.config(codes=codes, probe=new)))
        t_on.append(t0 + 1.0e-6)
    tend = T0 + (len(seq) - 1) * SEG
    st = B.timeline(ev)
    srcs = forced({n: f"{v}" for n, v in val.items()})
    body = B.chip(S, sources=srcs, state_over=st)
    sv = ["v(pad)", f"v({T.vnode('ua[1]')})", f"v({T.vnode('abus')})", f"v({T.vnode('en_b')})"]
    d = B.deck(body, f"tran 2n {tend:g}", sv, corner=CORNER, temp=TEMP)
    r = B.go(d, f"probe_step_{TAG}")
    t, y = r["_x"], r["v(pad)"]
    log(f"Probe-select steps, {CORNER} {TEMP} C, S = {S:g}, 200 pF board after 500 ohm; firmware 3-step move "
        f"(EN off, SEL, EN on); settling from EN-on to 1 % of the pad step")
    log("move                              pad before -> after (V)   t_settle 1 % (ns)   overshoot (%)   ripple last 1 us (mV)")
    worst = 0
    for i, ton in enumerate(t_on):
        tend_i = ton + SEG - 1.0e-6
        m = (t >= ton - 1e-6) & (t <= tend_i)
        tt, yy = t[m], y[m]
        yf = np.interp(tend_i, t, y)
        y0 = np.interp(T0 + i * SEG - 1e-9, t, y)          # before the move (old tap, enabled)
        band = 0.01 * abs(yf - y0)
        late = np.where((np.abs(yy - yf) > band) & (tt > ton))[0]
        ts = (tt[late[-1]] - ton) if len(late) else 0.0
        a = yy[tt > ton]
        ov = 100 * max(0.0, np.max((a - yf) * np.sign(yf - y0))) / abs(yf - y0)
        last = yy[tt > tend_i - 1e-6]
        worst = max(worst, ts)
        log(f"{seq[i]:15s} -> {seq[i + 1]:15s}   {y0:.4f} -> {yf:.4f}          {ts * 1e9:7.0f}            "
            f"{ov:5.2f}          {1e3 * (last.max() - last.min()):5.2f}")
    log(f"worst 1 % settling {worst * 1e9:.0f} ns -> {'PASS' if worst <= 2e-6 else 'FAIL'} (<= 2 us)")
(B.OUT / f"probe_{MODE}_{TAG}.txt").write_text("\n".join(lines) + "\n")
