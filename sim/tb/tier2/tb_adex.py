"""A1 AdEx (cells/adex/adex.spice): step response with and without adaptation, vs model/reference.py AdEx.

usage: python3 sim/tb/tier2/tb_adex.py [corner] [temp] [i_adw_pA]
DC current steps into vm (ideal source, as the array f-I benches), 0.5 ms after start, 6 ms long.
Adaptation on: vbp_adw master carries i_adw (default 8 nA); off: 0 (IDAC off).
Prints ISI sequences, first/last ISI, adaptation index; writes sim/results/tier2/adex_<corner>_<temp>.json
and a plot adex_<corner>_<temp>.png.
"""
import json
import sys

import numpy as np

sys.path.insert(0, "/work/sim/tb/tier2")
from t2common import *  # noqa
from reference import AdEx

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
IADW = float(sys.argv[3]) * 1e-12 if len(sys.argv) > 3 else 8000e-12
S = 100.0
T0, T1, TEND = 0.5e-3, 4.5e-3, 6.5e-3
STEPS = [250e-12, 400e-12, 700e-12]
vsrc = cal_vsrc(corner, temp, S)
DUT = ("XA vm vw spk sel_adex sub0 sub1 sta stb hold mreset vbp_syn el vsrc vreset vbn_leak vbp_st "
       "vbn_ref vbn_prb vbp_w en abus vdd 0 adex_a1")


def sim(istep, iadw, tag):
    body = f"""{cells('adex/adex.spice')}
{bias(S=S, vsrc=vsrc, i_adw=iadw)}
Vsta sta 0 0
Vstb stb 0 0
Iin vdd vm pwl(0 0 {T0} 0 {T0 + 1e-6} {istep} {T1} {istep} {T1 + 1e-6} 0)
{DUT}
"""
    r = run(deck(body, f"tran 200n {TEND}", ["v(vm)", "v(vw)", "v(spk)"], corner=corner, temp=temp),
            f"tier2/adex_{corner}_{temp}_{tag}")
    st = crossings(r["_x"], r["v(spk)"], 1.65)
    return r, st[(st > T0) & (st < T1 + 50e-6)]


def ref_isis(istep, b, tau_w, VT, DT=0.037, t_ref=20e-6):
    """reference.py AdEx in hardware voltages (EL 1.2, Vpeak = AH trip 1.28 V) + the hardware's t_ref."""
    m = AdEx(C=C, gL=g_leak(S), EL=EL, VT=VT, DT=DT, Vpeak=VTH, Vreset=VRESET, a=0.0, b=b, tau_w=tau_w)
    dt = 0.2e-6
    n = int((TEND - T0) / dt)
    I = np.full(n, istep)                     # (reference AdEx has no refractory period)
    V, Wv, spikes = m.simulate(I, dt)
    return np.diff(spikes)


res = {}
for i, istep in enumerate(STEPS):
    for on in (0, 1):
        r, st = sim(istep, IADW if on else 0.0, f"{i}_{on}")
        isi = np.diff(st)
        key = f"{istep*1e12:.0f}pA_{'adapt' if on else 'noadapt'}"
        res[key] = dict(n=len(st), isi_us=(isi * 1e6).round(2).tolist(),
                        vw_end=float(r["v(vw)"][-1]), vw_max=float(r["v(vw)"].max()))
        if on:
            # decay after the step: dVw/dt = -Itau/Cw; tau_w = n*UT/|dVw/dt| (n ~ 1.3 assumed)
            x, vw = r["_x"], r["v(vw)"]
            m = (x > T1 + 0.3e-3) & (x < T1 + 1.3e-3)
            sl = np.polyfit(x[m], vw[m], 1)[0]
            res[key].update(vw_slope_V_per_ms=float(sl * 1e-3), tau_w_est_ms=float(1.3 * 0.02585 / abs(sl) * 1e3))
        if len(isi) >= 3:
            ai = float(np.mean((isi[1:] - isi[:-1]) / (isi[1:] + isi[:-1])))
            res[key].update(first_isi_us=float(isi[0] * 1e6), last_isi_us=float(isi[-1] * 1e6),
                            ratio_last_first=float(isi[-1] / isi[0]), adapt_index=ai)
        print(f"{key:18s} spikes {len(st):3d}  ISI(us) first {isi[0]*1e6 if len(isi) else 0:7.1f} "
              f"last {isi[-1]*1e6 if len(isi) else 0:7.1f}  vw end {r['v(vw)'][-1]:.3f} max {r['v(vw)'].max():.3f}",
              flush=True)
        res[key]["_r"] = r
        res[key]["_st"] = st

# reference: AdEx with b = 20 pA, tau_w = 1 ms (reference.py defaults), a = 0, hardware voltages
for istep in STEPS:
    isi = ref_isis(istep, 20e-12, 1e-3, VT=VTH - 0.03)
    key = f"{istep*1e12:.0f}pA_ref"
    res[key] = dict(n=len(isi) + 1, isi_us=(isi * 1e6).round(2).tolist())
    if len(isi) >= 2:
        res[key].update(first_isi_us=float(isi[0] * 1e6), last_isi_us=float(isi[-1] * 1e6),
                        ratio_last_first=float(isi[-1] / isi[0]))
    print(f"{key:18s} spikes {len(isi)+1:3d}  ISI(us) first {isi[0]*1e6 if len(isi) else 0:7.1f} "
          f"last {isi[-1]*1e6 if len(isi) else 0:7.1f}")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for i, istep in enumerate(STEPS):
        for on, c in ((0, "0.6"), (1, "C0")):
            k = f"{istep*1e12:.0f}pA_{'adapt' if on else 'noadapt'}"
            st = res[k]["_st"]
            ax[0].plot((st[1:]) * 1e3, np.diff(st) * 1e6, "o-" if on else "x--", ms=3,
                       color=f"C{i}" if on else "0.6", label=k)
        kr = f"{istep*1e12:.0f}pA_ref"
        isi = np.array(res[kr]["isi_us"])
        ax[0].plot(T0 * 1e3 + np.cumsum(isi) / 1e3, isi, ":", color=f"C{i}")
    ax[0].set_ylabel("ISI (us)"); ax[0].legend(fontsize=6); ax[0].set_title(f"A1 {corner} {temp}C (dotted: AdEx ref b=20pA tau_w=1ms)")
    r = res[f"{STEPS[1]*1e12:.0f}pA_adapt"]["_r"]
    ax[1].plot(r["_x"] * 1e3, r["v(vm)"]); ax[1].set_ylabel("vm (V)"); ax[1].set_ylim(1.1, 1.5)
    ax[2].plot(r["_x"] * 1e3, r["v(vw)"]); ax[2].set_ylabel("vw (V)"); ax[2].set_xlabel("ms")
    fig.savefig(OUT / f"adex_{corner}_{temp}.png", dpi=110, bbox_inches="tight")
except Exception as e:  # noqa
    print("plot failed:", e)

for v in res.values():
    v.pop("_r", None); v.pop("_st", None)
(OUT / f"adex_{corner}_{temp}.json").write_text(json.dumps(dict(corner=corner, temp=temp, i_adw=IADW, vsrc=vsrc,
                                                                results=res), indent=1))
