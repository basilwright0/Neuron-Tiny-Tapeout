"""E1 (e1_fb, cells/neuron/e1.spice) benches.

usage (in the EDA container, from /work):
  python3 sim/tb/e1/tb_e1.py corners [S]          tt/27, ss/0, ff/85: DC (EL, Vth, gap, rheobase, g), tau, t_ref, f-I,
                                                  leg currents, grp_en = 0 state     -> sim/results/e1/corners_S<S>.json/.txt
  python3 sim/tb/e1/tb_e1.py mc N [first] [S]     N-die MC (statistical corner: global process + mismatch, one seed
                                                  per die, typical 27 C)              -> sim/results/e1/mc_<first>_<N>.json
  env PEX=<path>: use the extracted e1 netlist instead of the schematic (subckt name from the file).

Bias: the chip's vbp_st line = I_nd/16 into the 1/4 pfet diode (rx_p05); S = 100 <-> I_nd = 1 uA (B1 rev C, EXT /1).
None of e1_fb's other bias column lines feeds it: they are tied to deliberately wrong values (el 1.0 V, vsrc 0.3 V,
vreset 2.0 V, vbn_leak / vbn_ref / vbp_syn / aux from strong sources), so any accidental use would show.
Probe off (en = rsel = 0), abus at 0.6 V, sub_b = 1 (as the bay ties it).
Input: ideal current into vm (Iin, multiples of the DC rheobase), and the fixed synapse weights in DC mode
(sta = 1: weight A; sta = stb = 1: A + B) - the chip's own stimulus path.
Definitions: EL = vm at rest (zero net current, DC sweep of a vm source); Vth = the vm where spk trips in the same
sweep; rheobase = the current the source must supply to hold vm at Vth; g = dI/dV at EL;
tau = 63 % time of a small current step (0.25 x rheobase); t_ref = time from the spk rising edge until vm rises
10 mV above its clamped level at 8 x rheobase.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings, rate, RESULTS   # noqa: E402

OUTD = RESULTS / "e1"
OUTD.mkdir(parents=True, exist_ok=True)
LIBS = ("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice", "neuron/synapse.spice",
        "neuron/slot.spice", "neuron/e1.spice")
PORTS = ("vm spk rsel sub sub_b el vsrc vreset vbn_leak vbp_st vbn_ref vbn_prb en abus vdd vss aux "
         "vbp_syn sta stb hold mreset grp_en").split()
NETS = dict(vm="vm", spk="spk", rsel="0", sub="0", sub_b="vddc", el="xel", vsrc="xvs", vreset="xvr",
            vbn_leak="xbl", vbp_st="vbs", vbn_ref="xbr", vbn_prb="vbp", en="0", abus="abus", vdd="vddc", vss="0",
            aux="xel", vbp_syn="xsy", sta="sta", stb="stb", hold="hold", mreset="mrst", grp_en="gen")
PEX = os.environ.get("PEX")
CM = 200e-15


def inst():
    if not PEX:
        return "Xn " + " ".join(NETS[p] for p in PORTS) + " e1_fb", include(*LIBS)
    txt = re.sub(r"\n\+", " ", Path(PEX).read_text())
    m = re.search(r"^\.subckt\s+(\S+)\s+(.*)$", txt, re.M | re.I)
    ports = m.group(2).split()
    return f".include {PEX}\nXn " + " ".join(NETS.get(p, "0") for p in ports) + f" {m.group(1)}", include(*LIBS[:5])


def body(S=100.0, iin="0", sta="0", stb="0", gen="3.3", vm_src=None, extra=""):
    x, libs = inst()
    vm = f"Vvm vm 0 {vm_src}" if vm_src is not None else ""
    return f"""{libs}
Vdd vdd 0 3.3
Vddc vddc 0 3.3
Ist vbs 0 {62.5e-9 * S / 100}
XD0 vbs vbs vdd vdd pfet_03v3 W=1u L=4u
Ibp vdd vbp 1u
Xbp vbp 0 nmaster w=2u l=2u
Vxel xel 0 1.0
Vxvs xvs 0 0.3
Vxvr xvr 0 2.0
Vxbl xbl 0 0.9
Vxbr xbr 0 0.9
Vxsy xsy 0 1.5
Vab abus 0 0.6
Vsa sta 0 {sta}
Vsb stb 0 {stb}
Vho hold 0 0
Vmr mrst 0 0
Vgen gen 0 {gen}
Iin vdd vm {iin}
{vm}
{x}
{extra}
"""


def dc_char(tag, hdr, S=100.0):
    """EL, Vth, gap, rheobase, g from one DC sweep of a vm source."""
    r = run(deck(body(S, vm_src="1.0"), "dc Vvm 0.6 2.4 0.5m", ["v(spk)", "i(Vvm)"], **hdr), f"e1/{tag}_dc")
    v, i = r["_x"], -r["i(vvm)"]         # i > 0: the cell sinks current from the source (vm above EL)
    trip = crossings(v, r["v(spk)"], 1.65)
    vth = float(trip[0]) if len(trip) else float("nan")
    k = np.where((i[:-1] < 0) & (i[1:] >= 0))[0]
    el = float(v[k[0]] - i[k[0]] * (v[k[0] + 1] - v[k[0]]) / (i[k[0] + 1] - i[k[0]])) if len(k) else float("nan")
    m = (v >= el - 0.005) & (v <= el + 0.005)
    g = float(np.polyfit(v[m], i[m], 1)[0]) if m.sum() > 3 else float("nan")
    rheo = float(np.interp(vth - 0.001, v, i))
    return dict(EL=el, Vth=vth, gap=vth - el, rheo=rheo, g=g)


def tau_step(tag, hdr, d, S=100.0):
    tau0 = CM / max(d["g"], 1e-12)
    istep = 0.25 * d["rheo"]
    t1, tstop = 2e-6, 2e-6 + 10 * tau0
    r = run(deck(body(S, iin=f"PULSE(0 {istep} {t1} 1n 1n 1 2)"), f"tran {tau0 / 400} {tstop}", ["v(vm)"], **hdr),
            f"e1/{tag}_tau")
    t, vm = r["_x"], r["v(vm)"]
    v0, v1 = np.interp(t1, t, vm), vm[-1]
    t63 = crossings(t, vm, v0 + 0.632 * (v1 - v0))
    return dict(tau=float(t63[0] - t1) if len(t63) else float("nan"), dv_step=float(v1 - v0), istep=istep)


def fi_run(tag, hdr, iin=0.0, sta="0", stb="0", S=100.0, tstop=4e-3, tref=False):
    r = run(deck(body(S, iin=f"PULSE(0 {iin} 2u 1n 1n 1 2)" if iin else "0", sta=sta, stb=stb),
                 f"tran {1e-6 * 100 / S / 2} {tstop * 100 / S}", ["v(vm)", "v(spk)"], **hdr), f"e1/{tag}")
    t, vm, spk = r["_x"], r["v(vm)"], r["v(spk)"]
    st = crossings(t, spk, 1.65)
    out = dict(rate=float(rate(st, t_settle=0.0)), nspk=int(len(st)),
               vm_min=float(vm[t > 2e-4 * 100 / S].min()), vm_max=float(vm[t > 2e-4 * 100 / S].max()))
    if tref and len(st) >= 2:
        trs = []
        for a, b in zip(st[:-1], st[1:]):
            m = (t > a) & (t < b)
            tt, vv = t[m], vm[m]
            j = int(np.argmin(vv[: max(1, len(vv) // 2)]))
            up = np.where(vv[j:] > vv[j] + 0.010)[0]
            if len(up):
                trs.append(float(tt[j + up[0]] - a))
        out["t_ref"] = float(np.median(trs)) if trs else float("nan")
    return out


LEGS = """{libs}
Vdd vdd 0 3.3
Ist vbs 0 {ist}
XD0 vbs vbs vdd vdd pfet_03v3 W=1u L=4u
XP1 el_l vbs vdd vdd pfet_03v3 W=1u L=2u
XE1 el_l el_l mid 0 nfet_03v3 W={we1} L=0.5u
XE2 mid mid 0 0 nfet_03v3 W={we2} L=0.5u
XP2 vsl vbs vdd vdd pfet_03v3 W=1u L=2u
XV  vsl vsl 0 0 nfet_03v3 W=1u L=0.5u
XNW vbw mid 0 0 nfet_03v3 W=0.22u L={lnw}
XPW vbw vbw vdd vdd pfet_03v3 W=2u L=1u
Vt  tn 0 0.45
XT  tn mid 0 0 nfet_03v3 W=0.22u L={lt}
Vr  rn 0 2.0
XR  rn mid 0 0 nfet_03v3 W={wnr} L={lnr}
Vw  wn 0 1.5
XW  wn vbw vdd vdd pfet_03v3 W=2u L=4u
Vs  sn 0 1.5
XS  sn vbs vdd vdd pfet_03v3 W=1u L=2u
Vdum dum 0 0
"""
SIZES = dict(we1="0.7u", we2="4u", lt="11u", wnr="0.5u", lnr="2.6u", lnw="2.4u")


def legs(tag, hdr, S=100.0):
    r = run(deck(LEGS.format(libs=include("neuron/membrane.spice"), ist=62.5e-9 * S / 100, **SIZES), "dc Vdum 0 0 1",
                 ["i(Vt)", "i(Vr)", "i(Vw)", "i(Vs)", "v(el_l)", "v(mid)", "v(vsl)"], **hdr), f"e1/{tag}_legs")
    g = lambda k: float(r[k][0])
    return dict(I_leak=g("i(vt)"), I_ref=g("i(vr)"), I_w=-g("i(vw)"), I_st=-g("i(vs)"),
                V_el=g("v(el_l)"), V_mid=g("v(mid)"), V_vsrc=g("v(vsl)"))


def off_state(tag, hdr, S=100.0):
    """grp_en = 0: supply current of the cell (op), vm parking from 1.4 V, then grp_en 0 -> 1 at 300 us (sta = 1)."""
    r = run(deck(body(S, gen="0"), "op", ["i(Vddc)", "v(vm)", "v(xn.vbpl)", "v(xn.el_l)", "v(spk)"], **hdr),
            f"e1/{tag}_off_op") if not PEX else None
    out = {}
    if r is not None:
        out.update(I_vdd_off=-float(r["i(vddc)"][0]), vm_off=float(r["v(vm)"][0]), vbpl_off=float(r["v(xn.vbpl)"][0]),
                   el_off=float(r["v(xn.el_l)"][0]), spk_off=float(r["v(spk)"][0]))
    r2 = run(deck(body(S, gen="0"), "op", ["i(Vddc)"], **hdr).replace("Vgen gen 0 0", "Vgen gen 0 3.3"),
             f"e1/{tag}_on_op")
    out["I_vdd_on_rest"] = -float(r2["i(vddc)"][0])
    t_on = 300e-6
    r3 = run(deck(body(S, gen=f"PULSE(0 3.3 {t_on} 1u 1u 1 2)", sta="3.3", extra=".ic v(vm)=1.4"),
                  "tran 0.5u 1.2m uic", ["v(vm)", "v(spk)", "i(Vddc)"], **hdr), f"e1/{tag}_off_tran")
    t, vm, spk = r3["_x"], r3["v(vm)"], r3["v(spk)"]
    st = crossings(t, spk, 1.65)
    out.update(vm_at_100us=float(np.interp(100e-6, t, vm)), vm_at_290us=float(np.interp(290e-6, t, vm)),
               spikes_before_on=int((st < t_on).sum()), first_spike_after_on=float(st[st > t_on][0] - t_on)
               if (st > t_on).any() else float("nan"), I_vdd_off_tran=float(-np.mean(r3["i(vddc)"][(t > 200e-6) & (t < t_on)])))
    return out


def corners(S=100.0):
    res = {}
    txt = [f"e1_fb {'PEX ' + PEX if PEX else 'schematic'}  S = {S:g} (I_nd = {S / 100:g} uA, vbp_st = I_nd/16)"]
    for corner, T in (("typical", 27), ("ss", 0), ("ff", 85)):
        hdr = dict(corner=corner, temp=T)
        tag = f"{'pex_' if PEX else ''}{corner}{T}_S{S:g}"
        d = dc_char(tag, hdr, S)
        d.update(tau_step(tag, hdr, d, S))
        if not PEX:
            d.update(legs(tag, hdr, S))
        fi = []
        for k in (0.9, 1.5, 2, 3, 5, 8):
            f = fi_run(f"{tag}_fi{k}", hdr, iin=k * d["rheo"], S=S, tref=(k == 8))
            f["k"] = k
            fi.append(f)
            if k == 8:
                d["t_ref"] = f.get("t_ref", float("nan"))
        syn = {nm: fi_run(f"{tag}_syn{nm}", hdr, sta="3.3", stb=b, S=S) for nm, b in (("A", "0"), ("AB", "3.3"))}
        d["fi"], d["syn"] = fi, syn
        d.update(off_state(tag, hdr, S))
        res[f"{corner}/{T}"] = d
        txt.append(f"\n{corner}/{T}C: EL {d['EL']:.3f} V  Vth {d['Vth']:.3f} V  gap {1e3 * d['gap']:.1f} mV  "
                   f"rheobase {1e12 * d['rheo']:.0f} pA  g {1e9 * d['g']:.2f} nS  tau {1e6 * d['tau']:.1f} us  "
                   f"t_ref {1e6 * d['t_ref']:.1f} us")
        if "I_leak" in d:
            txt.append(f"   legs: I_leak {1e12 * d['I_leak']:.0f} pA  I_ref {1e9 * d['I_ref']:.2f} nA  I_w {1e12 * d['I_w']:.0f} pA"
                       f"  I_starve {1e9 * d['I_st']:.0f} nA  el_l {d['V_el']:.3f}  mid {d['V_mid']:.3f}  vsrc_l {d['V_vsrc']:.3f}")
        txt.append("   f-I (ideal Iin): " + "  ".join(f"{f['k']}x {f['rate']:.0f} Hz" for f in fi))
        txt.append(f"   fixed weights (DC): A {syn['A']['rate']:.0f} Hz, A+B {syn['AB']['rate']:.0f} Hz")
        txt.append("   grp_en: " + "  ".join(f"{k} {v:.4g}" for k, v in d.items() if k in (
            "I_vdd_off", "vm_off", "vbpl_off", "el_off", "spk_off", "I_vdd_on_rest", "vm_at_100us", "vm_at_290us",
            "spikes_before_on", "first_spike_after_on", "I_vdd_off_tran")))
        print("\n".join(txt[-5:]), flush=True)
    name = f"{'pex_' if PEX else ''}corners_S{S:g}"
    (OUTD / f"{name}.json").write_text(json.dumps(res, indent=1))
    (OUTD / f"{name}.txt").write_text("\n".join(txt) + "\n")


def mc(n, first=1, S=100.0):
    res = []
    for seed in range(first, first + n):
        t0 = time.time()
        hdr = dict(corner="statistical", temp=27, mismatch=True, global_var=True, seed=seed)
        tag = f"mc{seed}"
        try:
            d = dc_char(tag, hdr, S)
            d.update(tau_step(tag, hdr, d, S))
            f = fi_run(f"{tag}_fi8", hdr, iin=8 * d["rheo"], S=S, tstop=1e-3, tref=True)
            d["t_ref"], d["rate8"] = f.get("t_ref", float("nan")), f["rate"]
            f = fi_run(f"{tag}_synA", hdr, sta="3.3", S=S, tstop=2e-3)
            d["rateA"] = f["rate"]
        except Exception as e:      # keep going; a failed die is reported
            d = dict(error=str(e)[:200])
        d["seed"] = seed
        res.append(d)
        print(seed, {k: (round(v, 12) if isinstance(v, float) else v) for k, v in d.items()}, f"{time.time() - t0:.0f}s",
              flush=True)
        (OUTD / f"mc_{first}_{n}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "corners":
        corners(float(a[1]) if len(a) > 1 else 100.0)
    elif a[0] == "diag":
        diag()
    elif a[0] == "mc":
        mc(int(a[1]), int(a[2]) if len(a) > 2 else 1, float(a[3]) if len(a) > 3 else 100.0)


def diag(S=100.0):
    """Short f-I run (2 x the DC rheobase, 0.4 ms) saving internal nodes, to find what forces small time steps."""
    hdr = dict(corner="typical", temp=27)
    d = dc_char("diag", hdr, S)
    print("dc", d, flush=True)
    print("legs", legs("diag", hdr, S), flush=True)
    t0 = time.time()
    nodes = ["v(vm)", "v(spk)", "v(xn.vsl)", "v(xn.el_l)", "v(xn.mid)", "v(xn.vr)", "v(xn.vbw)", "v(xn.xd.n1)", "v(xn.xd.p)",
             "v(xn.xd.pb)", "v(xn.vl)"]
    r = run(deck(body(S, iin=f"PULSE(0 {2 * d['rheo']} 2u 1n 1n 1 2)"), "tran 0.5u 0.4m", nodes, **hdr), "e1/diag_fi2")
    t = r["_x"]
    print(f"{len(t)} points in {time.time() - t0:.0f} s; spikes {len(crossings(t, r['v(spk)'], 1.65))}")
    m = (t > 0.1e-3)
    for n in nodes:
        v = r[n][m]
        print(f"  {n:14s} min {v.min():.4f} max {v.max():.4f}  mean |dv| per step {np.mean(np.abs(np.diff(v))):.2e}")
    h, e = np.histogram(t, bins=40)
    print("points per 10 us:", h.tolist())
