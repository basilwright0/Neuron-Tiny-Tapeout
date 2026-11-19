"""A1 AdEx (cells/adex/adex.spice, rev 2: vbp_w, probe mux, hold-gated exp/adaptation) characterisation.

usage (inside the EDA container, via scripts/eda.sh):
    python3 sim/tb/tier2/tb_adex_char.py nominal          # typical 27 C: I-V/exp fit, steps 250/400/700 pA, model compare
    python3 sim/tb/tier2/tb_adex_char.py sweepw           # typical 27 C: ISI ratio vs adaptation current Iin (vbp_w)
    python3 sim/tb/tier2/tb_adex_char.py corners          # 5 corners x 0/27/85 C: key numbers
    python3 sim/tb/tier2/tb_adex_char.py mc [N] [corner] [temp]   # local mismatch, N seeds (default 24, typical 27)

Bias point S = 100 (t2common.bias): EL 1.30 V, Ib_leak 324 pA, AH trip 1.38 V (vsrc per corner),
adaptation increment Iin = 8 nA on vbp_w (pfet 1/2 master, 1:1). Input = ideal DC step into vm.

Measured per case:
  I-V   vm forced (DC sweep EL-0.15..Vth-0.01 V), adaptation off. A leak-only replica (leak_ota_deg) on the same
        voltage separates I_exp = I_neuron - I_leak. Fits: gL, EL (leak slope / zero), Delta_T (slope of
        ln I_exp), VT (I_exp = gL*Delta_T), rest (zero of I_neuron), rheobase (-min I_neuron below trip).
  step  current step T0..T1, adaptation on/off. Iw read on a replica nfet (0.22/8, gate vw, drain 1.2 V):
        b = mean Iw jump over spikes 2..5, tau_w from ln Iw decay after the step.
  model reference.py AdEx equations (+ the hardware refractory time, fitted on the no-adaptation ISI)
        with the fitted gL, EL, VT, DT and the measured b, tau_w; ISI sequences compared.
Results: sim/results/tier2/adexc_<mode>.json (+ .png for nominal).
"""
import json
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
from ngs import CORNERS, TEMPS  # noqa

MODE = "_".join(sys.argv[1:2] + sys.argv[3:5]) or "nominal"
S = 100.0
IADW = 8e-9
T0, T1, TEND = 0.5e-3, 4.5e-3, 6.5e-3
DUT = ("XA vm vw spk sel_adex sub0 sub1 sta stb hold mreset vbp_syn el vsrc vreset vbn_leak vbp_st "
       "vbn_ref vbn_prb vbp_w en abus vdd 0 adex_a1")
PEX = None                           # set by the 'pex' mode: extracted netlist instead of the schematic


def dut_line():
    if PEX is None:
        return DUT
    import re
    txt = open(PEX).read().replace("\n+", " ")
    ports = re.search(r"^\.subckt adex_a1 (.*)$", txt, re.M).group(1).split()
    want = DUT.split()[1:-1]
    names = dict(zip(want, want)); names["vss"] = "0"
    return "XA " + " ".join(names.get(p, "0" if p == "VSUBS" else p) for p in ports) + " adex_a1"


def lib():
    return f"{cells()}\n.include {PEX}" if PEX else cells("adex/adex.spice")


REP = "Vrw vrw 0 1.2\nXrw vrw vw 0 0 nfet_03v3 W=0.22u L=8u\n"


def hdr(corner, temp, seed):
    return dict(corner=corner, temp=temp, mismatch=seed is not None, seed=seed or 1)


def iv(corner, temp, vsrc, seed=None, tag=""):
    body = f"""{lib()}
{bias(S=S, vsrc=vsrc, i_adw=0.0)}
Vsta sta 0 0
Vstb stb 0 0
Vvm vm 0 1.2
Vvm2 vm2 vm 0
Xlk vm2 el vbn_leak vdd 0 leak_ota_deg
{dut_line()}
"""
    r = run(deck(body, f"dc Vvm {EL - 0.15:.3f} {VTH - 0.01:.3f} 0.5m", ["i(Vvm)", "i(Vvm2)"], **hdr(corner, temp, seed)),
            f"tier2/adexc_{MODE}_iv_{corner}_{temp}{tag}")
    v = r["_x"]
    irep = r["i(vvm2)"]                  # current the leak replica pushes into its node
    idut = r["i(vvm)"] - irep           # current the neuron pushes into vm (leak + exp + ...)
    iexp = idut - irep
    k = np.argmin(np.abs(irep))
    m = (v > v[k] - 0.01) & (v < v[k] + 0.01)
    gL = float(-np.polyfit(v[m], irep[m], 1)[0])
    EL_ = float(np.interp(0.0, -irep, v))
    sel = (iexp > 2e-12) & (iexp < 1e-9)
    out = dict(gL_nS=gL * 1e9, EL=EL_)
    if sel.sum() > 5:
        p = np.polyfit(v[sel], np.log(iexp[sel]), 1)
        DT = 1.0 / p[0]
        VT = float((np.log(gL * DT) - p[1]) / p[0])
        out.update(DT_mV=DT * 1e3, VT=VT)
    zc = np.where((idut[:-1] > 0) & (idut[1:] <= 0))[0]
    out["rest"] = float(v[zc[0]]) if len(zc) else float("nan")
    below = v < VTH
    # with mismatch the detector can trip below Vth: the refractory switch then sinks uA. Stop the
    # rheobase search at the first point where the neuron current steps by more than 1 nA.
    jump = np.where(np.abs(np.diff(idut)) > 1e-9)[0]
    if len(jump):
        below &= np.arange(len(v)) <= jump[0]
        out["trip_below"] = float(v[jump[0]])
    i_min = float(idut[below].min())
    out["rheobase_pA"] = -i_min * 1e12
    out["rheo_at_trip"] = bool(np.argmin(idut[below]) >= below.sum() - 2)
    out["iexp_at_EL_pA"] = float(np.interp(EL, v, iexp)) * 1e12
    out["_v"], out["_idut"], out["_iexp"], out["_irep"] = v, idut, iexp, irep
    return out


def step(corner, temp, vsrc, istep, iadw, seed=None, tag="", t0=T0, t1=T1, tend=TEND):
    body = f"""{lib()}
{bias(S=S, vsrc=vsrc, i_adw=iadw)}
Vsta sta 0 0
Vstb stb 0 0
Iin vdd vm pwl(0 0 {t0} 0 {t0 + 1e-6} {istep} {t1} {istep} {t1 + 1e-6} 0)
{REP}
{dut_line()}
"""
    r = run(deck(body, f"tran 200n {tend}", ["v(vm)", "v(vw)", "v(spk)", "i(Vrw)"], **hdr(corner, temp, seed)),
            f"tier2/adexc_{MODE}_st_{corner}_{temp}_{istep*1e12:.0f}_{iadw*1e9:.2f}{tag}")
    x = r["_x"]
    st = crossings(x, r["v(spk)"], 1.65)
    nraw = len(st)
    if len(st):                               # a runt on spk would give two crossings ~ns apart: count once
        st = st[np.r_[True, np.diff(st) > 2e-6]]
    pre = st[st < t0]
    st = st[(st > t0) & (st < t1 + 50e-6)]
    iw = np.abs(r["i(vrw)"])
    isi = np.diff(st)
    out = dict(n=len(st), n_pre=len(pre), runts=nraw - len(st) - len(pre) * 0, isi_us=(isi * 1e6).round(2).tolist(),
               vm_rest=float(np.mean(r["v(vm)"][(x > 0.6 * t0) & (x < t0)])),
               vw_max=float(r["v(vw)"].max()), iw_max_pA=float(iw.max() * 1e12))
    if len(isi) >= 3:
        out.update(first_isi_us=float(isi[0] * 1e6), last_isi_us=float(isi[-1] * 1e6),
                   ratio=float(isi[-1] / isi[0]), f0_Hz=float(1 / isi[0]), fss_Hz=float(1 / isi[-1]))
    if iadw > 0 and len(st) >= 6:
        m = (x > t1 + 0.2e-3) & (x < min(t1 + 1.5e-3, tend)) & (iw > 0.5e-12)
        tw = None
        if m.sum() > 20:
            tw = float(-1 / np.polyfit(x[m], np.log(iw[m]), 1)[0])
            out["tau_w_ms"] = tw * 1e3
        # b: increment per spike, Iw just before spike k+1 minus Iw just before spike k decayed over the ISI
        jumps = []
        for k in range(1, 5):
            a = np.interp(st[k] - 2e-6, x, iw)
            b_ = np.interp(st[k + 1] - 2e-6, x, iw)
            jumps.append(b_ - a * (np.exp(-isi[k] / tw) if tw else 1.0))
        out["b_pA"] = float(np.mean(jumps) * 1e12)
        out["iw_ss_pA"] = float(np.interp(st[-1] - 2e-6, x, iw) * 1e12)
    out["_r"] = r
    out["_st"] = st
    return out


def model_isis(p, istep, b, tau_w, t_ref, dur=T1 - T0, dt=0.1e-6):
    """reference.py AdEx equations (a = 0) + a refractory hold at Vreset for t_ref."""
    C_, gL, EL_, VT, DT = C, p["gL_nS"] * 1e-9, p["EL"], p["VT"], p["DT_mV"] * 1e-3
    v, w, t, hold, sp = p.get("rest", EL_), 0.0, 0.0, 0.0, []     # start at the no-input rest, w = 0
    while t < dur:
        if hold > 0:
            hold -= dt
            v = VRESET
        else:
            dv = (-gL * (v - EL_) + gL * DT * np.exp(min((v - VT) / DT, 50.0)) - w + istep) / C_
            v += dv * dt
            if v >= VTH:                     # Vpeak = the AH trip
                sp.append(t)
                v = VRESET
                w += b
                hold = t_ref
        w -= w / tau_w * dt
        t += dt
    return np.diff(sp)


def case(arg):
    """Key numbers for one corner/temperature (or MC seed)."""
    corner, temp, seed = arg
    vsrc = cal_vsrc(corner, temp, S)
    tag = f"_s{seed}" if seed is not None else ""
    res = dict(corner=corner, temp=temp, seed=seed, vsrc=vsrc)
    try:
        p = iv(corner, temp, vsrc, seed, tag)
        res.update({k: v for k, v in p.items() if not k.startswith("_")})
    except Exception as e:  # noqa
        res["iv_error"] = str(e)[:200]
    for on in (0, 1):
        o = step(corner, temp, vsrc, 400e-12, IADW if on else 0.0, seed, tag)
        res["adapt" if on else "noadapt"] = {k: v for k, v in o.items() if not k.startswith("_")}
    return res


def nominal():
    corner, temp = "typical", 27
    vsrc = cal_vsrc(corner, temp, S)
    p = iv(corner, temp, vsrc)
    print("I-V:", {k: round(v, 4) if isinstance(v, float) else v for k, v in p.items() if not k.startswith("_")})
    steps = [250e-12, 400e-12, 700e-12]
    with Pool(6) as pool:
        outs = pool.starmap(step, [(corner, temp, vsrc, i, a) for i in steps for a in (0.0, IADW)])
    res = dict(vsrc=vsrc, iv={k: v for k, v in p.items() if not k.startswith("_")}, steps={})
    k = 0
    for i in steps:
        for a in (0.0, IADW):
            o = outs[k]; k += 1
            res["steps"][f"{i*1e12:.0f}pA_{'adapt' if a else 'noadapt'}"] = o
    # model: refractory time fitted on the 400 pA no-adaptation ISI
    hw = res["steps"]["400pA_noadapt"]["first_isi_us"] * 1e-6
    mi = model_isis(p, 400e-12, 0.0, 1e-3, 0.0, dur=1e-3)
    t_ref = max(0.0, hw - float(mi[0]))
    ad = res["steps"]["400pA_adapt"]
    b, tau_w = ad["b_pA"] * 1e-12, ad["tau_w_ms"] * 1e-3
    # effective b: the model b that reproduces the hardware adapted (last) ISI at 400 pA
    lo, hi = 1e-12, 200e-12
    for _ in range(16):
        mid = (lo + hi) / 2
        if model_isis(p, 400e-12, mid, tau_w, t_ref)[-1] < ad["last_isi_us"] * 1e-6:
            lo = mid
        else:
            hi = mid
    b_eff = (lo + hi) / 2
    res["model"] = dict(t_ref_us=t_ref * 1e6, b_meas_pA=b * 1e12, b_eff_pA=b_eff * 1e12, tau_w_ms=tau_w * 1e3,
                        cases={})
    b = b_eff
    for i in steps:
        for a in (0, 1):
            isi = model_isis(p, i, b if a else 0.0, tau_w, t_ref)
            key = f"{i*1e12:.0f}pA_{'adapt' if a else 'noadapt'}"
            res["model"]["cases"][key] = dict(n=len(isi) + 1, first_isi_us=float(isi[0] * 1e6),
                                              last_isi_us=float(isi[-1] * 1e6), ratio=float(isi[-1] / isi[0]),
                                              isi_us=(isi * 1e6).round(2).tolist())
    for key, o in res["steps"].items():
        mo = res["model"]["cases"][key]
        print(f"{key:16s} HW n={o['n']:3d} ISI {o.get('first_isi_us', 0):7.1f} -> {o.get('last_isi_us', 0):7.1f} us "
              f"ratio {o.get('ratio', 0):.2f} b={o.get('b_pA', 0):.1f}pA tau_w={o.get('tau_w_ms', 0):.2f}ms | "
              f"model n={mo['n']:3d} {mo['first_isi_us']:7.1f} -> {mo['last_isi_us']:7.1f} ratio {mo['ratio']:.2f}",
              flush=True)
    print("model t_ref %.1f us, b measured %.1f pA, b_eff (fits 400 pA last ISI) %.1f pA, tau_w %.3f ms"
          % (t_ref * 1e6, res["model"]["b_meas_pA"], b * 1e12, tau_w * 1e3))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(12, 8))
        a0 = ax[0, 0]
        for j, i in enumerate(steps):
            o = res["steps"][f"{i*1e12:.0f}pA_adapt"]
            st = o["_st"]
            a0.plot((st[1:] - T0) * 1e3, np.diff(st) * 1e6, "o-", ms=3, color=f"C{j}", label=f"HW {i*1e12:.0f} pA")
            mo = res["model"]["cases"][f"{i*1e12:.0f}pA_adapt"]
            isi = np.array(mo["isi_us"])
            a0.plot(np.cumsum(isi) / 1e3, isi, "x:", ms=3, color=f"C{j}", label=f"model {i*1e12:.0f} pA")
        a0.set_xlabel("ms after step"); a0.set_ylabel("ISI (us)"); a0.legend(fontsize=7)
        a0.set_title("spike-frequency adaptation, HW vs reference AdEx (fitted)")
        a1 = ax[0, 1]
        v = p["_v"]
        a1.semilogy(v, np.maximum(p["_iexp"], 1e-15) * 1e12, label="I_exp (HW)")
        mv = p["gL_nS"] * 1e-9 * p["DT_mV"] * 1e-3 * np.exp((v - p["VT"]) / (p["DT_mV"] * 1e-3))
        a1.semilogy(v, mv * 1e12, "--", label=f"gL DT exp((V-VT)/DT), DT={p['DT_mV']:.1f} mV VT={p['VT']:.3f}")
        a1.axvline(VTH, color="0.5", ls=":"); a1.set_ylim(1e-2, 1e4); a1.set_xlabel("vm (V)"); a1.set_ylabel("pA")
        a1.legend(fontsize=7); a1.set_title("exponential term")
        a2 = ax[1, 0]
        r = res["steps"]["400pA_adapt"]["_r"]
        a2.plot(r["_x"] * 1e3, r["v(vm)"]); a2.set_ylim(1.15, 1.45); a2.set_ylabel("vm (V)"); a2.set_xlabel("ms")
        a3 = ax[1, 1]
        a3.plot(r["_x"] * 1e3, np.abs(r["i(vrw)"]) * 1e12); a3.set_ylabel("Iw (pA)"); a3.set_xlabel("ms")
        a3.set_title("adaptation current (replica)")
        fig.tight_layout()
        fig.savefig(OUT / "adexc_nominal.png", dpi=110)
    except Exception as e:  # noqa
        print("plot failed:", e)
    for o in res["steps"].values():
        o.pop("_r", None); o.pop("_st", None)
    (OUT / "adexc_nominal.json").write_text(json.dumps(res, indent=1))


def sweepw():
    vsrc = cal_vsrc("typical", 27, S)
    iws = [0.25e-9, 0.5e-9, 1e-9, 2e-9, 4e-9, 8e-9, 16e-9, 32e-9, 64e-9]
    with Pool(9) as pool:
        outs = pool.starmap(step, [("typical", 27, vsrc, 400e-12, a) for a in iws])
    res = {}
    for a, o in zip(iws, outs):
        o.pop("_r"); o.pop("_st")
        res[f"{a*1e9:g}"] = o
        print(f"Iin {a*1e9:6.2f} nA: n={o['n']:3d} ISI {o.get('first_isi_us', 0):6.1f} -> {o.get('last_isi_us', 0):7.1f} us "
              f"ratio {o.get('ratio', 0):.2f} b={o.get('b_pA', float('nan')):.1f} pA tau_w={o.get('tau_w_ms', float('nan')):.2f} ms "
              f"vw_max {o['vw_max']:.3f}", flush=True)
    (OUT / "adexc_sweepw.json").write_text(json.dumps(res, indent=1))


def show(r):
    a, n = r["adapt"], r["noadapt"]
    return (f"{r['corner']:8s} {r['temp']:3d} {str(r['seed']):>4s} vsrc {r['vsrc']:.3f} gL {r.get('gL_nS', 0):.2f}nS "
            f"EL {r.get('EL', 0):.3f} rest {r.get('rest', 0):.3f} DT {r.get('DT_mV', 0):5.1f}mV VT {r.get('VT', 0):.3f} "
            f"rheo {r.get('rheobase_pA', 0):5.0f}pA pre-spikes {n['n_pre']}/{a['n_pre']} | noadapt f {n.get('f0_Hz', 0):6.0f}Hz | "
            f"adapt f0 {a.get('f0_Hz', 0):6.0f} fss {a.get('fss_Hz', 0):6.0f} ratio {a.get('ratio', 0):.2f} "
            f"b {a.get('b_pA', 0):5.1f}pA tau_w {a.get('tau_w_ms', 0):.2f}ms")


def corners():
    args = [(c, t, None) for c in CORNERS for t in TEMPS]
    with Pool(8) as pool:
        res = pool.map(case, args)
    for r in res:
        print(show(r), flush=True)
    (OUT / "adexc_corners.json").write_text(json.dumps(res, indent=1))


def mc(n, corner="typical", temp=27):
    cal_vsrc(corner, temp, S)
    args = [(corner, temp, s) for s in range(1, n + 1)]
    with Pool(8) as pool:
        res = pool.map(case, args)
    for r in res:
        print(show(r), flush=True)
    keys = [("rest", lambda r: r.get("rest")), ("DT_mV", lambda r: r.get("DT_mV")),
            ("rheobase_pA", lambda r: r.get("rheobase_pA")),
            ("f0_noadapt_Hz", lambda r: r["noadapt"].get("f0_Hz")), ("ratio", lambda r: r["adapt"].get("ratio")),
            ("b_pA", lambda r: r["adapt"].get("b_pA")), ("tau_w_ms", lambda r: r["adapt"].get("tau_w_ms"))]
    summ = {}
    for k, f in keys:
        v = np.array([f(r) for r in res if f(r) is not None], float)
        summ[k] = dict(mean=float(np.mean(v)), sd=float(np.std(v)), min=float(v.min()), max=float(v.max()), n=len(v))
        print(f"{k:14s} mean {np.mean(v):9.3f} sd {np.std(v):8.3f} min {v.min():9.3f} max {v.max():9.3f} (n={len(v)})")
    summ["self_firing_seeds"] = [r["seed"] for r in res if r["noadapt"]["n_pre"] > 0 or r["adapt"]["n_pre"] > 0]
    print("seeds firing with no input:", summ["self_firing_seeds"])
    (OUT / f"adexc_mc_{corner}_{temp}.json").write_text(json.dumps(dict(summary=summ, cases=res), indent=1))


def pex():
    """Post-layout spot check: 400 pA step, adaptation on/off, schematic vs extracted (typical 27 C)."""
    global PEX
    vsrc = cal_vsrc("typical", 27, S)
    res = {}
    for name, net in (("schematic", None), ("pex", "/work/layout/tier2/out/adex_a1_pex.spice")):
        PEX = net
        for a in (0.0, IADW):
            o = step("typical", 27, vsrc, 400e-12, a, tag=f"_{name}")
            o.pop("_r"); o.pop("_st")
            res[f"{name}_{'adapt' if a else 'noadapt'}"] = o
            print(f"{name:9s} {'adapt' if a else 'noadapt':8s} n={o['n']:3d} ISI {o.get('first_isi_us', 0):6.1f} -> "
                  f"{o.get('last_isi_us', 0):6.1f} us ratio {o.get('ratio', 0):.3f} b={o.get('b_pA', float('nan')):.1f} pA "
                  f"tau_w={o.get('tau_w_ms', float('nan')):.3f} ms", flush=True)
    PEX = None
    (OUT / "adexc_pex.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "nominal"
    if mode == "nominal":
        nominal()
    elif mode == "sweepw":
        sweepw()
    elif mode == "corners":
        corners()
    elif mode == "pex":
        pex()
    elif mode == "mc":
        mc(int(sys.argv[2]) if len(sys.argv) > 2 else 24, *(sys.argv[3:4] or ["typical"]),
           *([int(sys.argv[4])] if len(sys.argv) > 4 else []))
