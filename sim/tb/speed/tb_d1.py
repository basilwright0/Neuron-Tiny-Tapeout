"""Speed track: D1 dendrite (cells/dendrite) plateau threshold / duration / burst and attenuation at speed S.

usage: python3 sim/tb/speed/tb_d1.py <S> [corner:temp,...] [nproc]
Bench = sim/tb/dendrite/dcommon.py bias(S) (read-only; every bias current x S/100, vsrc calibrated at the
S-scaled I_st) and the tb_plateau.py 'ramp' and 'pulse' stimuli time-scaled by 100/S, currents by S/100:
  ramp   d1: 0 -> 700 pA * S/100 over 7 ms * 100/S, soma spiking: plateau threshold (mV above EL, current)
  pulse  d1: 800 pA * S/100 for 100 us * 100/S: plateau duration (detector high), d1 > EL + 250 mV time,
         soma spikes / burst rate; durations reported in S = 100 units (x S/100)
  atten  d1: 300 pA * S/100 step for 6 tau, plateau off, soma passive (vsrc 1.4 V): soma/d1 at the end
-> sim/results/speed/d1_S<S>.json
"""
import json
import sys
from multiprocessing import Pool

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa: E402,F403

S = float(sys.argv[1])
CASES = [(c.split(":")[0], int(c.split(":")[1])) for c in
         (sys.argv[2] if len(sys.argv) > 2 else "typical:27,ss:0,ff:85,sf:0").split(",")]
NP = int(sys.argv[3]) if len(sys.argv) > 3 else 2
k = 100.0 / S          # time scale
SV = ["v(vs)", "v(d1)", "v(d2)", "v(spk)", "v(xd.xp1.xb)"]


def pwl(node, segs):
    return f"I{node} vdd {node} pwl(" + " ".join(f"{t:.6g} {i:.6g}" for t, i in segs) + ")"


def tran(corner, temp, src, tstop, name, vsrc, vsrc_cal, pl_en=1):
    body = f"""{cells()}
{bias(S=S, gax=4e-9 * S / 100, vsrc=vsrc, pl_en=pl_en, vsrcp=vsrc_cal)}
{src}
{DUT}
"""
    return run(deck(body, f"tran {1e-6 * k} {tstop}", SV, corner=corner, temp=temp), f"d1_{name}_{corner}_{temp}_S{S:g}")


def case(arg):
    corner, temp = arg
    vc = cal_vsrc(corner, temp, S)
    res = dict(corner=corner, temp=temp, S=S, vsrc=vc)
    # ramp
    T, T0 = 7e-3 * k, 2e-3 * k
    r = tran(corner, temp, pwl("d1", [(0, 0), (T0, 0), (T0 + T, 700e-12 / k), (T0 + T + 1e-6 * k, 0)]),
             T0 + T + 0.5e-3 * k, "ramp", vc, vc)
    t, xb = r["_x"], r["v(xd.xp1.xb)"]
    m = t > T0
    tc = crossings(t[m], xb[m], 1.65)
    rest = float(np.interp(T0 - 1e-6 * k, t, r["v(d1)"]))
    if len(tc):
        res["thr_mV_el"] = (float(np.interp(tc[0], t, r["v(d1)"])) - EL) * 1e3
        res["thr_mV_rest"] = (float(np.interp(tc[0], t, r["v(d1)"])) - rest) * 1e3
        res["thr_pA_norm"] = 700 * (tc[0] - T0) / T
    # pulse
    t0 = 2e-3 * k
    src = pwl("d1", [(0, 0), (t0, 0), (t0 + 1e-6 * k, 800e-12 / k), (t0 + 100e-6 * k, 800e-12 / k), (t0 + 101e-6 * k, 0)])
    r = tran(corner, temp, src, 6e-3 * k, "pulse", vc, vc)
    t, xb, d1 = r["_x"], r["v(xd.xp1.xb)"], r["v(d1)"]
    m0 = t > 0.95 * t0
    up = crossings(t[m0], xb[m0], 1.65)
    dn = crossings(t[m0], xb[m0], 1.65, rising=False)
    if len(up):
        dn = dn[dn > up[0]]
    hi = t[(d1 > EL + 0.25) & m0]
    spk = crossings(t[m0], r["v(spk)"][m0], 1.65)
    res.update(t_plat_us_norm=float(dn[0] - up[0]) / k * 1e6 if len(up) and len(dn) else float("nan"),
               t_above250_us_norm=float(hi[-1] - hi[0]) / k * 1e6 if len(hi) else 0.0,
               d1_max_mV=float(d1[m0].max() - EL) * 1e3, vs_max_mV=float(r["v(vs)"][m0].max() - EL) * 1e3,
               nspk=int(len(spk)), burst_hz_norm=float(1 / np.mean(np.diff(spk))) * k if len(spk) > 2 else 0.0)
    # attenuation (plateau off, soma passive)
    tau = C / g_leak(S)
    src = pwl("d1", [(0, 0), (5 * tau, 0), (5 * tau + 1e-9, 300e-12 / k)])
    r = tran(corner, temp, src, 11 * tau, "atten", 1.4, vc, pl_en=0)
    t = r["_x"]
    b = {n: float(np.interp(4.9 * tau, t, r[f"v({n})"])) for n in ("vs", "d1")}
    e = {n: float(np.interp(11 * tau, t, r[f"v({n})"])) - b[n] for n in ("vs", "d1")}
    res.update(atten=e["vs"] / e["d1"], d1_step_mV=e["d1"] * 1e3)
    return res


if __name__ == "__main__":
    with Pool(NP) as p:
        res = p.map(case, CASES)
    for r in res:
        print(f"D1 S={S:g} {r['corner']:7s} {r['temp']:3d}: thr {r.get('thr_mV_el', float('nan')):.1f} mV>EL "
              f"({r.get('thr_pA_norm', float('nan')):.0f} pA@S100) plateau {r['t_plat_us_norm']:.0f} us d1>+250mV "
              f"{r['t_above250_us_norm']:.0f} us d1max +{r['d1_max_mV']:.0f} soma max +{r['vs_max_mV']:.0f} mV spikes {r['nspk']} "
              f"burst {r['burst_hz_norm']:.0f} Hz | atten soma/d1 {r['atten']:.3f} (d1 +{r['d1_step_mV']:.1f} mV)", flush=True)
    (RESULTS / f"d1_S{S:g}.json").write_text(json.dumps(res, indent=1))
