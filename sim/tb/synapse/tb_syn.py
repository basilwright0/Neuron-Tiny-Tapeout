"""Input synapse syn_in (cells/neuron/synapse.spice): weight, linearity, compliance, off-leakage,
charge injection, mismatch; plus slot-level hold / mreset / DC-mode f-I checks.

usage: python3 sim/tb/synapse/tb_syn.py [quick]
Corners typical/ff/ss/fs/sf x 0/27/85 C at S = 100. Results: sim/results/syn/syn_summary.txt (+ json).

Bench (standalone syn_in): vm held by a voltage source (current measured through it), vl (the leak
OTA side of the hold switch) at the vm voltage, or at EL for the hold-leakage test, vr held at 0, vbp_syn from an ideal current I_set into a
2/4 pmaster (stand-in for the bias block's p-IDAC + master).
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trim"))
import slotbench as sb                                  # noqa: E402
from ngs import deck, run, include, crossings, rate, RESULTS   # noqa: E402

OUT = RESULTS / "syn"
LOGI = np.arange(0, 5.01, 0.25)            # I_set = 1 pA * 10^x, x = 0..5  (1 pA .. 100 nA)


def bench(vm="1.2", sta="0", stb="0", hold="0", mrst="0", iset="Bsy vsyn 0 I = 1e-12*pow(10, v(x))\nVx x 0 0", vl=None):
    return f"""{include('neuron/membrane.spice', 'neuron/lif.spice', 'neuron/synapse.spice')}
Vdd vdd 0 3.3
{iset}
Xsy vsyn vdd pmaster w=2u l=4u
Vvm vm 0 {vm}
Vvl vl 0 {vm if vl is None else vl}
Vvr vr 0 0
Vsa sta 0 {sta}
Vsb stb 0 {stb}
Vho hold 0 {hold}
Vmr mrst 0 {mrst}
XS vm vl vr sta stb hold mrst vsyn vdd 0 syn_in
"""


def dc_sweep(tag, corner, temp, **kw):
    r = run(deck(bench(**kw), "dc Vx 0 5 0.25", ["i(Vvm)"], corner=corner, temp=temp), f"syn/{tag}")
    return r["i(vvm)"]           # current INTO vm from the cell (flows into the source's + node)


def tran_charge(tag, corner, temp, tw, iset, edge=2e-9, src="sta"):
    """Charge delivered into vm (held at 1.2 V) by one pulse of width tw on src."""
    t0, tstop = 2e-6, 2e-6 + tw + 100e-6
    pulse = f"PULSE(0 3.3 {t0} {edge} {edge} {tw} 1)"
    kw = dict(sta=pulse if src == "sta" else "0", hold=pulse if src == "hold" else "0",
              iset=f"Isy vsyn 0 {iset}")
    r = run(deck(bench(**kw), f"tran {min(tw, 1e-6) / 200} {tstop}", ["i(Vvm)"], corner=corner, temp=temp),
            f"syn/{tag}")
    t, i = r["_x"], r["i(vvm)"]
    base = np.median(i[t < t0 * 0.9])
    m = t > t0 * 0.9
    return float(np.trapezoid(i[m] - base, t[m]))


def case(arg):
    corner, temp = arg
    tag = f"{corner}_{temp}"
    iset = 1e-12 * 10 ** LOGI
    res = dict(corner=corner, temp=temp)
    on = {v: dc_sweep(f"on_{v}_{tag}", corner, temp, vm=v, sta="3.3") for v in ("1.0", "1.2", "1.6", "2.0")}
    both = dc_sweep(f"ab_{tag}", corner, temp, vm="1.2", sta="3.3", stb="3.3")
    off = {v: dc_sweep(f"off_{v}_{tag}", corner, temp, vm=v) for v in ("1.0", "1.2", "2.0")}
    held = {v: dc_sweep(f"hold_{v}_{tag}", corner, temp, vm=v, sta="3.3", stb="3.3", hold="3.3", vl=sb.EL)
            for v in ("1.0", "1.2", "2.0")}
    gain = on["1.2"] / iset
    res["gain"] = gain.tolist()
    res["iset"] = iset.tolist()
    res["ab_over_a"] = (both / on["1.2"]).tolist()
    # compliance: I(vm)/I(1.2 V) at 1.0 and 2.0 V (I_set >= 10 pA)
    k = iset >= 10e-12
    res["compl_1v0"] = [float((on["1.0"] / on["1.2"])[k].min()), float((on["1.0"] / on["1.2"])[k].max())]
    res["compl_2v0"] = [float((on["2.0"] / on["1.2"])[k].min()), float((on["2.0"] / on["1.2"])[k].max())]
    res["off_max"] = float(max(np.abs(v).max() for v in off.values()))
    res["hold_max"] = float(max(np.abs(v).max() for v in held.values()))
    # charge injection (pure: I_set = 1 fA) and pulse-width linearity at I_set = 1 nA
    res["qinj_stim"] = tran_charge(f"qi_{tag}", corner, temp, 1e-6, 1e-15)
    res["qinj_hold"] = tran_charge(f"qh_{tag}", corner, temp, 5e-6, 1e-15, src="hold")
    tws = np.array([0.1e-6, 1e-6, 10e-6, 50e-6])
    q = np.array([tran_charge(f"ql_{tw * 1e9:.0f}n_{tag}", corner, temp, tw, 1e-9) for tw in tws])
    a, b0 = np.polyfit(tws, q, 1)
    res.update(q_lin_slope=float(a), q_lin_offset=float(b0), q_lin=q.tolist(),
               q_lin_resid=float(np.max(np.abs(q - (a * tws + b0)))))
    return res


def mismatch(seed):
    """Weight mismatch: I_w at I_set = 160 pA (rheobase at S = 100) and 16 nA, typical 27 C."""
    out = []
    for iset in (160e-12, 16e-9):
        body = bench(sta="3.3", iset=f"Isy vsyn 0 {iset}") + "Vdum dum 0 0\n"
        r = run(deck(body, "dc Vdum 0 0 1", ["i(Vvm)"], mismatch=True, seed=seed), f"syn/mc_{iset * 1e12:.0f}p_s{seed}")
        out.append(float(r["i(vvm)"][0] / iset))
    return out


def slot_functional(arg):
    """slot_ah schematic: DC-mode f-I via the synapse vs an ideal current source; hold freeze; mreset."""
    corner, temp = arg
    b = sb.Bias(100.0)
    vsrc = sb.cal_vsrc(corner, temp, 100.0, tag=f"syn_{corner}_{temp}")
    res = dict(corner=corner, temp=temp, fi=[])
    for k in (1.5, 2, 4, 8):
        rr = {}
        for mode in ("syn", "ideal"):
            body = sb.slot_body("slot_ah", b, vsrc, iin=(k * b.rheo if mode == "ideal" else 0.0),
                                i_syn=(k * b.rheo if mode == "syn" else 1e-15), sta=("3.3" if mode == "syn" else "0"))
            r = run(deck(body + f".ic v(vm)={sb.EL}\n", f"tran {b.tau / 200} {30 * b.tau} uic", ["v(spk)"],
                         corner=corner, temp=temp), f"syn/fi_{mode}_{k}_{corner}_{temp}")
            rr[mode] = rate(crossings(r["_x"], r["v(spk)"], 1.65), 5 * b.tau)
        res["fi"].append(dict(k=k, syn=rr["syn"], ideal=rr["ideal"]))
    # hold: rest at t = 0 (normal operating point); hold rises at 0.5 tau, stim A (DC, 2x rheobase via
    # the synapse) at 0.6 tau, and a 10 fC kick (ideal 1 nA x 10 us) at 1 tau lifts vm by ~50 mV. vm must
    # then stay frozen (no leak, no input) until hold falls at 10 tau; the neuron then fires; a mreset
    # pulse (2 us) at 13 tau must clamp vm to vreset.
    t2, t3 = 10 * b.tau, 13 * b.tau
    th, ts, tk = 0.5 * b.tau, 0.6 * b.tau, 1.0 * b.tau
    body = sb.slot_body("slot_ah", b, vsrc, i_syn=2 * b.rheo, sta=f"PWL(0 0 {ts} 0 {ts + 10e-9} 3.3)",
                        hold=f"PWL(0 0 {th} 0 {th + 10e-9} 3.3 {t2} 3.3 {t2 + 10e-9} 0)",
                        mrst=f"PULSE(0 3.3 {t3} 10n 10n 2u 1)",
                        extra=f"Ikick vdd vm PULSE(0 1n {tk} 10n 10n 10u 1)")
    r = run(deck(body, f"tran {b.tau / 400} {15 * b.tau}", ["v(vm)", "v(spk)"],
                 corner=corner, temp=temp), f"syn/hold_{corner}_{temp}")
    t, vm = r["_x"], r["v(vm)"]
    m = (t > tk + 0.2 * b.tau) & (t < t2 - 0.1 * b.tau)
    res["hold_drift_mV_per_ms"] = float(np.polyfit(t[m], vm[m], 1)[0] * 1e3 * 1e-3)
    res["hold_vm"] = float(np.mean(vm[m]))
    sp = crossings(t, r["v(spk)"], 1.65)
    res["spikes_in_hold"] = int(np.sum(sp < t2))
    res["spikes_after"] = int(np.sum((sp > t2) & (sp < t3)))
    m2 = (t > t3 + 1.5e-6) & (t < t3 + 2e-6)
    res["mreset_vm"] = float(np.mean(vm[m2]))
    return res


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quick = "quick" in sys.argv
    cases = [("typical", 27)] if quick else [(c, t) for c in ("typical", "ff", "ss", "fs", "sf") for t in (0, 27, 85)]
    with Pool(int(__import__("os").environ.get("SYN_POOL", "3"))) as p:
        res = p.map(case, cases)
        mc = p.map(mismatch, range(1, 41 if not quick else 6))
        fun = p.map(slot_functional, [("typical", 27), ("typical", 85), ("ss", 0), ("ff", 85)] if not quick
                    else [("typical", 27)])
    (OUT / "syn_cases.json").write_text(json.dumps(dict(cases=res, mc=mc, fun=fun), indent=1))
    L = ["syn_in (2/4 pfet weight, drain-steered), S = 100 bench; I_set into a 2/4 pmaster; vm held",
         "gain = I_w/I_set at vm = 1.2 V: min..max over I_set = 1 pA..100 nA [at 10 pA, 160 pA, 10 nA]",
         " corner   T   gain range       [10p   160p   10n ]  A+B/A  compl 1.0V    compl 2.0V    "
         "off max(fA) hold max(fA)  Qinj stim(fC) Qinj hold(fC)  Q(t) slope/1nA  offset(fC)"]
    for r in res:
        g = np.array(r["gain"])
        iset = np.array(r["iset"])
        pick = [float(np.interp(np.log10(v), np.log10(iset), g)) for v in (10e-12, 160e-12, 10e-9)]
        ab = np.array(r["ab_over_a"])[iset >= 10e-12]
        L.append(f" {r['corner']:7s} {r['temp']:3d} {g.min():.3f}..{g.max():.3f}  [{pick[0]:.3f} {pick[1]:.3f} {pick[2]:.3f}]"
                 f"  {ab.min():.2f}-{ab.max():.2f} {r['compl_1v0'][0]:.3f}-{r['compl_1v0'][1]:.3f}  "
                 f"{r['compl_2v0'][0]:.3f}-{r['compl_2v0'][1]:.3f}  {r['off_max'] * 1e15:9.1f}  {r['hold_max'] * 1e15:9.1f}"
                 f"   {r['qinj_stim'] * 1e15:9.3f}   {r['qinj_hold'] * 1e15:9.3f}      {r['q_lin_slope'] / 1e-9:.3f}"
                 f"        {r['q_lin_offset'] * 1e15:7.3f}")
    mc = np.array(mc)
    L.append(f"weight mismatch (typical 27 C, {len(mc)} seeds): sigma(I_w)/I_w = {mc[:, 0].std() / mc[:, 0].mean() * 100:.1f} % "
             f"at 160 pA, {mc[:, 1].std() / mc[:, 1].mean() * 100:.1f} % at 16 nA")
    L.append("slot_ah functional (schematic): DC-mode f-I through the synapse (I_set = k x rheobase) vs ideal source")
    for f in fun:
        fi = " ".join(f"{x['k']:g}x:{x['syn'] / x['ideal'] if x['ideal'] else float('nan'):.3f}" for x in f["fi"])
        L.append(f" {f['corner']:7s} {f['temp']:3d}  rate_syn/rate_ideal {fi} | hold: vm {f['hold_vm']:.3f} V, drift "
                 f"{f['hold_drift_mV_per_ms']:.3f} mV/ms, spikes {f['spikes_in_hold']} (after release "
                 f"{f['spikes_after']}) | mreset: vm {f['mreset_vm']:.3f} V")
    txt = "\n".join(L)
    print(txt)
    (OUT / "syn_summary.txt").write_text(txt + "\n")
