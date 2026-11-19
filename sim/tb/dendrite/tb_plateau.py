"""D1 plateau: threshold, duration, amplitude, quasi-steady transfer with/without plateau, star vs chain.

usage: python3 sim/tb/dendrite/tb_plateau.py [corner] [temp] [parts] [seed]
  parts: comma list of  ramp (threshold), pulse (duration/amplitude/burst), xfer (step sweep vs model)
  seed : >0 turns on per-instance mismatch (sw_stat_mismatch, .option seed) -- used by tb_mc.py

Reference: model/reference.py Compartments with C = 200 fF, gL = 2 nS, g_ax = 4 nS, EL = 1.30 V (was 1.20),
Vp = EL + 0.15, wp = 20 mV, Ep = EL + 0.6, plateau_g = 20 nS on both subunits (GP_MODEL).
The reference plateau has no termination (it latches); the circuit ends it with a timer, so the
quasi-steady comparison is taken at the end of a 600 us step, inside the plateau.
"""
import json
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
from reference import Compartments

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
parts = (sys.argv[3] if len(sys.argv) > 3 else "ramp,pulse,xfer").split(",")
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
S = 100.0
GP_MODEL = 20e-9
VSRC_OFF = 1.4          # test mode: AH trip moved above the plateau level (soma passive)
tag = f"{corner}_{temp}" + (f"_mc{seed}" if seed else "")
hdr = dict(corner=corner, temp=temp, mismatch=bool(seed), seed=max(seed, 1))
res = dict(corner=corner, temp=temp, seed=seed)
vsrc_cal = cal_vsrc("typical" if seed else corner, temp, S)
res["vsrc_cal"] = vsrc_cal
SV = ["v(vs)", "v(d1)", "v(d2)", "v(spk)", "v(xd.vep)", "v(xd.xp1.xb)", "v(xd.xp2.xb)",
      "v(xd.xp1.vt)", "v(xd.xp1.xdt.n1)"]


def tran(src, tstop, name, vsrc, pl_en=1, chain=0, step="1u"):
    """vsrc: soma AH rail; the plateau detectors (vsrcp) always get the calibrated rail."""
    body = f"""{cells()}
{bias(S=S, vsrc=vsrc, pl_en=pl_en, chain=chain, vsrcp=vsrc_cal)}
{src}
{DUT}
"""
    return run(deck(body, f"tran {step} {tstop}", SV, **hdr), f"dendrite/{name}_{tag}")


def pwl(node, segs):
    pts = " ".join(f"{t:.6g} {i:.6g}" for t, i in segs)
    return f"I{node} vdd {node} pwl({pts})"


# ------------------------------------------------------------------ threshold (slow ramps)
if "ramp" in parts:
    # d1 ramp 0 -> 700 pA over 7 ms, release, 4 ms pause, same on d2.  Soma spiking normally.
    T = 7e-3
    T0 = 2e-3            # let the DC operating point (may start inside a plateau) settle first
    s1 = pwl("d1", [(0, 0), (T0, 0), (T0 + T, 700e-12), (T0 + T + 1e-6, 0)])
    t2 = T0 + T + 4e-3
    s2 = pwl("d2", [(0, 0), (t2, 0), (t2 + T, 700e-12), (t2 + T + 1e-6, 0)])
    r = tran(s1 + "\n" + s2, t2 + T + 0.5e-3, "ramp", vsrc_cal)
    t = r["_x"]
    for k, (nd, t0) in enumerate((("d1", T0), ("d2", t2))):
        xb = r[f"v(xd.xp{k+1}.xb)"]
        m = t > t0
        tc = crossings(t[m], xb[m], 1.65)
        rest = float(np.interp(t0 - 1e-6, t, r[f"v({nd})"]))
        if len(tc):
            tt = tc[0]
            v = float(np.interp(tt, t, r[f"v({nd})"]))
            i = 700e-12 * (tt - t0) / T
            res[f"thr_{nd}"] = dict(v_el=v - EL, v_rest=v - rest, i=i, rest=rest)
        else:
            res[f"thr_{nd}"] = dict(v_el=float("nan"), v_rest=float("nan"), i=float("nan"), rest=rest)
    # reference: steady-state trigger of the model plateau (continuation in I, soma passive)
    print(f"[{tag}] threshold d1: {res['thr_d1']['v_el']*1e3:.1f} mV above EL "
          f"({res['thr_d1']['v_rest']*1e3:.1f} above rest), I = {res['thr_d1']['i']*1e12:.0f} pA; "
          f"d2: {res['thr_d2']['v_el']*1e3:.1f} mV / {res['thr_d2']['v_rest']*1e3:.1f} / {res['thr_d2']['i']*1e12:.0f} pA")

# ------------------------------------------------------------------ duration / amplitude (pulse)
if "pulse" in parts:
    src = pwl("d1", [(0, 0), (2e-3, 0), (2.001e-3, 800e-12), (2.1e-3, 800e-12), (2.101e-3, 0)])
    for mode, vsrc in (("spk", vsrc_cal), ("pas", VSRC_OFF)):
        r = tran(src, 6e-3, f"pulse_{mode}", vsrc)
        t = r["_x"]
        xb = r["v(xd.xp1.xb)"]
        m0 = t > 1.9e-3
        up = crossings(t[m0], xb[m0], 1.65)
        dn = crossings(t[m0], xb[m0], 1.65, rising=False)
        if len(up):
            dn = dn[dn > up[0]]
        d1 = r["v(d1)"]
        hi = t[(d1 > EL + 0.25) & m0]
        spk = crossings(t[m0], r["v(spk)"][m0], 1.65)
        res[f"pulse_{mode}"] = dict(
            t_detect=float(dn[0] - up[0]) if len(up) and len(dn) else float("nan"),
            t_above250=float(hi[-1] - hi[0]) if len(hi) else 0.0,
            d1_max=float(d1[m0].max() - EL), vs_max=float(r["v(vs)"][m0].max() - EL),
            d2_max=float(r["v(d2)"][m0].max() - EL), nspk=int(len(spk)),
            burst_hz=float(1 / np.mean(np.diff(spk))) if len(spk) > 2 else 0.0,
            vep=float(r["v(xd.vep)"][-1]))
        p = res[f"pulse_{mode}"]
        print(f"[{tag}] pulse ({mode}): plateau (detector high) {p['t_detect']*1e6:.0f} us, d1 > EL+250mV "
              f"{p['t_above250']*1e6:.0f} us, d1 max +{p['d1_max']*1e3:.0f} mV, soma max +{p['vs_max']*1e3:.0f} mV, "
              f"d2 max +{p['d2_max']*1e3:.0f} mV, spikes {p['nspk']} ({p['burst_hz']:.0f} Hz), vep {p['vep']:.3f}")


# ------------------------------------------------------------------ quasi-steady transfer vs model
def model(topo, gp, inj, amps, tstep=600e-6, dt=1e-6):
    kw = dict(C=C, gL=g_leak(S), g_ax=4e-9, EL=EL, Vp=EL + 0.15, wp=0.02, Ep=EL + 0.6,
              plateau_g=np.array([0, gp, gp]) if gp else None)
    m = Compartments.star(2, **kw) if topo == "star" else Compartments.chain(3, **kw)
    out = []
    for a in amps:
        I = np.zeros((int(tstep / dt), 3))
        I[:, inj] = a
        V = m.simulate(I, dt)
        out.append(V[-1] - EL)
    return np.array(out)


if "xfer" in parts:
    amps = np.arange(0, 701e-12, 50e-12)
    TS, TP = 600e-6, 3.0e-3
    xres = {}
    for topo, inj in (("star", 1), ("chain", 2)):
        nd = ["vs", "d1", "d2"][inj]
        segs = [(0, 0)]
        t0s = []
        for k, a in enumerate(amps):
            t0 = 2e-3 + k * TP
            t0s.append(t0)
            segs += [(t0, 0), (t0 + 1e-6, a), (t0 + TS, a), (t0 + TS + 1e-6, 0)]
        tstop = t0s[-1] + TP
        for pl in (0, 1):
            r = tran(pwl(nd, segs), tstop, f"qss_{topo}_pl{pl}", VSRC_OFF, pl_en=pl,
                     chain=int(topo == "chain"), step="2u")
            t = r["_x"]
            base = {n: float(np.interp(1.99e-3, t, r[f"v({n})"])) for n in ("vs", "d1", "d2")}
            sp = np.array([[np.interp(t0 + TS - 1e-6, t, r[f"v({n})"]) - base[n] for n in ("vs", "d1", "d2")]
                           for t0 in t0s])
            mo = model(topo, GP_MODEL if pl else 0, inj, amps, TS)
            xres[f"{topo}_pl{pl}"] = dict(amps=amps.tolist(), spice=sp.tolist(), model=mo.tolist())
            print(f"[{tag}] quasi-steady ({topo}, input at {nd}, plateau {'on' if pl else 'off'}): "
                  "I(pA)  soma spice/model  input-compartment spice/model (mV above rest)")
            for a, s_, m_ in zip(amps, sp, mo):
                print(f"   {a*1e12:5.0f}  {s_[0]*1e3:7.1f} / {m_[0]*1e3:7.1f}   {s_[inj]*1e3:7.1f} / {m_[inj]*1e3:7.1f}")
    res["qss"] = xres

(OUT / f"plateau_{tag}_{'-'.join(parts)}.json").write_text(json.dumps(res, indent=1))
