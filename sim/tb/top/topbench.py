"""Shared pieces of the top-level PEX spot-check benches (sim/tb/top/*.py; run inside the EDA container).

Chip = topnet.build() (full-chip flat R+C extraction, control macro replaced by ideal drivers), plus:
  - ua[0]: reference current source (EXT /1: S = 100 x I[uA]);
  - ua[1]: TT analog mux 500 ohm + 2 pF on the chip side, 200 pF pad + board after it (node `pad`);
  - unused TT inputs tied low.
Operating points follow docs/info.md: S = 100 nominal codes (B1 report C.3), EL / Vth / Vreset = 1.30 / 1.38 / 1.30 V,
at S >= 300: 1.50 / 1.58 / 1.50 V.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "lib"))
sys.path.insert(0, str(_HERE))
import numpy as np                      # noqa: E402
import topnet as T                      # noqa: E402
from ngs import header, run             # noqa: E402

OUT = T.ROOT / "sim/results/top"
RUNS = "top"                            # run() writes sim/results/<name>.*; we prefix names with top/

CB = 200e-12                            # pad + board on ua[1]
import os as _os                        # noqa: E402
SUFFIX = "_vsrcfix" if _os.environ.get("TOP_VSRC_FIX") == "1" else ""   # result-name tag (topnet.vsrc_fix)


def op_point(S=100.0):
    """(codes, el, vth, vreset): nominal codes; vth_ref ~ AH trip calibration at that S (typical 27 C)."""
    # vsrc = vth_ref: det_ah (schematic) trip calibrated to Vth at typical 27 C (slotbench.ah_trip iteration)
    if S >= 300:
        el, vr, vth, vsrc = 1.50, 1.50, 1.58, 0.6534
    else:
        el, vr, vth, vsrc = 1.30, 1.30, 1.38, 0.5833
    codes = dict(T.CODES_S100)
    codes.update(T.vcodes(el=el, vreset=vr, vth_cmp=vth, vth_ref=vsrc))
    return codes


PRE_LINES = ["vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_ax", "vbp_w"]
T_REL = 0.5e-6
D1_OFS = 0.038                          # D1 rest - EL (schematic dend_d1, typical 27 C, S = 100: 1.338 V at EL 1.30)


def pre_extra(el):
    """Block-state nodes that the full-chip op leaves away from rest, held through the same switches as PRE_LINES:
    AdEx vw powers up near VDD (MRESET clamps it to VSS, XR1 / XR2; its rest without spikes is ~0 V), so it is held
    at 0 V; D1 vs / d1 / d2 are held at the D1 rest (EL + D1_OFS: the D1 leak OTAs settle ~38 mV above EL, tau
    ~150 us, so holding them at EL or pulsing MRESET early leaves a +0.2..0.3 V/ms drift through the kick window).
    Without this AdEx vm sat at ~0.88 V and D1 vs drifted 1.28 -> 1.09 V (MRESET-on artefacts +364 / +148 mV in
    the 330bf04 run). Block-level schematic check (sub-circuit, same switches, MRESET at 100 us): AdEx vm 1.306 V
    at 59 us, MRESET-on edge -6.8 mV (was +391); D1 vs 1.339 V, slope -0.3 mV/ms, edge -31.7 mV = vs rest ->
    vreset (was +113)."""
    d1 = el + D1_OFS
    return [("ax.vw", 0.0), ("d1.vs", d1), ("d1.d1", d1), ("d1.d2", d1)]


def slot_vl(inst):
    """Raw flat node of a slot's leak-OTA output vl: the source of XHL, the HOLD pfet (W 1u, L 0.28u) between
    <inst>.vm and vl, gate = HOLD (rt_out[2]). vl has no label, so it is an a_x_y# node in the flat netlist."""
    hold = T.net("rt_out[2]")
    vm = f"{inst}.vm"
    for l in T.load()["lines"]:
        if l[0] not in "Xx" or "pfet" not in l or vm not in l:
            continue
        t = l.split()
        nn = [x for x in t[1:] if "=" not in x]
        kv = dict(x.lower().split("=") for x in t[1:] if "=" in x)
        if len(nn) < 4 or nn[1] != hold or kv.get("l") != "0.28u" or kv.get("w") != "1u":
            continue
        d, s = nn[0], nn[2]
        if vm in (d, s):
            return s if d == vm else d
    raise KeyError(f"vl of {inst}")


def sch_bias(S, codes=None, ib_x2=0):
    """Schematic bias_b1 DC outputs (cached): the start values of the slow current-mode lines."""
    import json
    codes = codes or op_point(S)
    key = f"S{S:g}_" + "_".join(f"{k}{codes[k]}" for k in sorted(codes)) + f"_x{ib_x2}"
    f = OUT / "sch_bias_cache.json"
    try:
        cache = json.loads(f.read_text())
    except Exception:
        cache = {}
    if key not in cache:
        r = go(deck(sch_chain(S, codes=codes, ib_x2=ib_x2), "op", [f"v({n})" for n in PRE_LINES]), f"sch_bias_{key}")
        cache[key] = {n: float(r[f"v({n})"][0]) for n in PRE_LINES}
        f.write_text(json.dumps(cache, indent=1))
    return cache[key]


def chip(S=100.0, codes=None, probe=None, rt=(0, 0, 0, 0), ib_x2=0, sources=None, power="ideal", cb=CB,
         state_over=None, precond=True, **kw):
    """precond: the slow current-mode bias lines (PRE_LINES), every membrane and the block-state nodes of
    pre_extra() (AdEx vw = 0, D1 vs / d1 / d2 = D1 rest) are held at their schematic / rest values through switches
    that open at T_REL = 0.5 us (the full-chip op does not converge by Newton, and ngspice's transient-op fallback
    leaves these nA-biased lines and block states unsettled)."""
    codes = codes or op_point(S)
    st = T.config(codes=codes, probe=probe, rt=rt, ib_x2=ib_x2)
    st.update(state_over or {})
    body = T.build(st, sources=sources, power=power, **kw)
    iref = S / 100.0 * 1e-6
    tt = [f"Iref 0 {T.node('ua[0]')} DC {iref:g}",
          f"Cpi {T.node('ua[1]')} 0 2p", f"Rsw {T.node('ua[1]')} pad 500", f"Cpad pad 0 {cb:g}"]
    for p in ("clk", "rst_n", "ena") + tuple(f"ui_in[{i}]" for i in range(8)) + tuple(f"uio_in[{i}]" for i in range(8)):
        tt.append(f"Rtie_{T.san(p)} {T.node(p)} 0 1k")
    el = 1.50 if S >= 300 else 1.30          # help the op: every membrane starts at EL
    vms = [f"s{r}{c}.vm" for r in range(4) for c in range(4) if f"s{r}{c}.vm" in T.names()] + ["ax.vm"]
    vms += [f"{i}.vm" for _, i, _ in T.bay() if f"{i}.vm" in T.names()]     # R2 bay neurons (by0..by2)
    ns = [f".nodeset v({T.vnode(n)})={el}" for n in vms]
    ns += [f".nodeset v({T.vnode(n)})={v:g}" for n, v in pre_extra(el)]
    if precond:
        vb = sch_bias(S, codes=codes, ib_x2=ib_x2)
        tt += [".model swpre sw vt=1.65 vh=0.1 ron=100 roff=1e16",
               f"Vpre_ctl pre_ctl 0 PWL(0 3.3 {T_REL:g} 3.3 {T_REL + 1e-9:g} 0)"]
        for k, (n, v) in enumerate(list(vb.items()) + [(m, el) for m in vms] + pre_extra(el)):
            tt += [f"Vpre{k} pre{k} 0 {v:.5f}", f"Spre{k} pre{k} {T.vnode(n)} pre_ctl 0 swpre"]
    return body + "\n".join(tt + ns) + "\n"


def _save_name(v):
    """`save` form of a wrdata vector: v(n) -> n, i(vx) -> vx#branch."""
    m = re.match(r"^([vi])\((.+)\)$", v.strip(), re.I)
    if not m:
        return v
    return m.group(2) if m.group(1).lower() == "v" else f"{m.group(2)}#branch"


def deck(body, analysis, save, corner="typical", temp=27, opts="", pre=""):
    """ngspice deck; `pre` = control-block lines before the analysis (alter, etc.).
    Only the written vectors are kept (`save`): without it ngspice stores every node of the full chip at every
    time / sweep point, which is what got the M1 full-chip DC sweeps OOM-killed. TOP_SAVE_ALL=1 keeps all."""
    import os
    vecs = " ".join(save)
    if os.environ.get("TOP_SAVE_ALL") != "1":
        pre = "save " + " ".join(_save_name(v) for v in save) + "\n" + pre
    return f"""* top-level PEX bench
{header(corner=corner, temp=temp)}
.option rshunt=1e14 abstol=1e-14 {opts}
{body}
.control
set wr_singlescale
set wr_vecnames
set num_threads={os.environ.get("TOP_THREADS", "4")}
{pre}
{analysis}
wrdata __OUT__ {vecs}
quit
.endc
.end
"""


DECK_ONLY = "--deck" in sys.argv          # benches: write the deck and stop (no ngspice run)


def go(d, name, timeout=6 * 3600):
    """Run a deck. With --deck on the command line: write it to $TOP_DECK_DIR (default /tmp/topdeck)/<name>.cir
    and exit (deck-generation check, no simulation)."""
    if DECK_ONLY:
        import os
        dd = Path(os.environ.get("TOP_DECK_DIR", "/tmp/topdeck"))
        dd.mkdir(parents=True, exist_ok=True)
        f = dd / f"{name}.cir"
        f.write_text(d.replace("__OUT__", str(dd / f"{name}.dat")))
        print(f"--deck: wrote {f} ({len(d.splitlines())} lines), not run")
        sys.exit(0)
    OUT.mkdir(parents=True, exist_ok=True)
    return run(d, f"top/{name}", timeout=timeout)


# ------------------------------------------------------------------ locating nodes of a block
_dev = {}


def devices():
    if "d" in _dev:
        return _dev["d"]
    L = []
    for l in T.load()["lines"]:
        if l[0] in "XD":
            t = l.split()
            nn = [x for x in t[1:] if "=" not in x]
            L.append((t[0], nn[:-1], nn[-1]))
    _dev["d"] = L
    return L


def block_terms(net, inst, box=None):
    """Sanitised R-network terminals of `net` (e.g. 'd1.vsrc', 'VGND') used by devices of instance `inst`
    (a device belongs to inst if one of its other nodes is named inst.* or lies inside `box`)."""
    out = set()
    for name, nodes, model in devices():
        own = any(n.startswith(inst + ".") and not n.startswith(net) for n in nodes) or \
            (box is not None and any(T._inbox(T._xy(n), box) for n in nodes))
        if not own:
            continue
        for n in nodes:
            if n == net or re.match(re.escape(net) + r"\.[nt]\d+$", n):
                out.add(T.san(n))
    return sorted(out)


def slot_box(inst):
    import config as C
    cell, x, y = C.instances()[inst]
    w, h = C.LIB[cell].get("size", (T.fp.SLOT_W, T.fp.TALL_H))
    return (x, y, x + w, y + h)


def settle_time(t, y, t0, tol=0.01, y_from=None):
    """1 % settling time after t0 (relative to the step y(t0-) -> y(end))."""
    yf = y[-1]
    y0 = np.interp(t0 - 1e-9, t, y) if y_from is None else y_from
    band = tol * abs(yf - y0)
    out = np.where((np.abs(y - yf) > band) & (t > t0))[0]
    return (t[out[-1]] - t0) if len(out) else 0.0, y0, yf


def timeline(events, base=None, tr=None):
    """events: [(t, macro-pin state dict)], sorted; returns {pin: 'PWL(...)'} for pins that change, else values.
    Each change is a linear edge of `tr` starting at t."""
    tr = tr or T.TR
    pins = set()
    for _, st in events:
        pins |= set(st)
    out = {}
    for p in pins:
        vals = [(t, st[p]) for t, st in events if p in st]
        if all(abs(v - vals[0][1]) < 1e-12 for _, v in vals):
            out[p] = vals[0][1]
            continue
        pts = [(0.0, vals[0][1])]
        cur = vals[0][1]
        for t, v in vals[1:]:
            if abs(v - cur) > 1e-12:
                pts += [(t, cur), (t + tr, v)]
                cur = v
        out[p] = "PWL(" + " ".join(f"{a:.6g} {b:.6g}" for a, b in pts) + ")"
    return out


def pwl(pts):
    return "PWL(" + " ".join(f"{a:.6g} {b:.6g}" for a, b in pts) + ")"


# ------------------------------------------------------------------ schematic reference (no layout at all)
SCH_LIBS = ("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice", "neuron/synapse.spice",
            "trim/trim_gap.spice", "neuron/slot.spice", "vreset/vreset_buf.spice", "vsrc/vsrc_buf.spice",
            "readout/r1_corner.spice")


def sch_chain(S=100.0, codes=None, tap="slot", vin="1.2", ib_x2=0, cb=CB, ndesel=31):
    """Schematic probe chain: bias_b1 (schematic, same codes / ua[0] current) -> selected tap (slot: prb_tap
    4/2 three switches; d1: prb_nsf 4/2 one switch; adex: prb_tap 4/2) + ndesel deselected prb_taps -> r1_corner
    schematic -> 500 ohm / 2 pF / cb. Node of the probed voltage: `vin` (source spec)."""
    from ngs import include
    codes = codes or op_point(S)
    st = T.config(codes=codes, ib_x2=ib_x2)
    b1p = ("i0_b0 i0_b1 i0_b2 i0_b3 i0_b4 i1_b0 i1_b1 i1_b2 i1_b3 i1_b4 i2_b0 i2_b1 i2_b2 i2_b3 i2_b4 i3_b0 i3_b1 "
           "i3_b2 i3_b3 i3_b4 i4_b0 i4_b1 i4_b2 i4_b3 i4_b4 r0_b0 r0_b1 r0_b2 r0_b3 r0_b4 r1_b0 r1_b1 r1_b2 r1_b3 "
           "r1_b4 r2_b0 r2_b1 r2_b2 r2_b3 r2_b4 v0_c0 v0_c1 v0_c2 v0_c3 v0_c4 v0_c5 ua0_s0 ua0_s1 ua0_stim ua0_int "
           "bias_en ib_x2").split()
    L = [include(*SCH_LIBS), ".include /work/cells/bias/bias_all.spice", "Vdd vdd 0 3.3"]
    for p in b1p:
        L.append(f"V_{p} b_{p} 0 {st[p]:g}")
    L.append("Xb1 " + " ".join(f"b_{p}" for p in b1p) +
             " vbn_leak vbn_ref vbp_syn vbn_ax vbp_w vbp_st vbn_prb vth_ref el vrin vthc ibr so ua0 vdd 0 bias_b1")
    L.append(f"Iref 0 ua0 DC {S / 100 * 1e-6:g}")
    L.append("Rso so 0 1e9")
    L.append(f"Vin vin 0 {vin}")
    if tap == "d1":
        L.append("Xt vin abus vdd vdd vbn_prb vdd 0 prb_nsf wf=4u lf=2u")
    else:
        L.append("Xt vin abus vdd vdd vdd vbn_prb vdd 0 prb_tap wf=4u lf=2u")
    for k in range(ndesel):
        L.append(f"Xo{k} vx abus 0 0 0 vbn_prb vdd 0 prb_tap wf=4u lf=2u")
    L += ["Vx vx 0 1.2", "Xr abus padi enb ibr vrin vrst vth_ref vsrc vdd 0 r1_corner", "Venb enb 0 0",
          "Crst vrst 0 2p", "Csrc vsrc 0 2p", f"Cpi padi 0 2p", "Rsw padi pad 500", f"Cpad pad 0 {cb:g}"]
    return "\n".join(L) + "\n"
