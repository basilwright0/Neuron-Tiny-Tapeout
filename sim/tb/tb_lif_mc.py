"""Mismatch Monte Carlo for the comparator / AH LIF at S=100, 200 fF (and 50 fF).

Per instance (seed) we extract:
  g      leak conductance        from steady-state vm at a sub-rheobase input (vinf-EL = I/g)
  off    leak offset (V)         vm at zero input minus EL
  vthr   effective threshold     max vm before reset at 2x rheobase
  rate   firing rate at 2x and 4x rheobase
Then we ask which single trim knob removes the most rate variance (parameter economy):
  ideal 'gain' trim  (scale input current per neuron)  vs  'threshold' trim  vs  'leak' trim,
estimated by regressing rate on (g, off, vthr) and removing each term's contribution.

usage: python3 sim/tb/tb_lif_mc.py [variant] [N] [cap_um]
"""
import json, sys
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings, rate, RESULTS

variant = sys.argv[1] if len(sys.argv) > 1 else "cmp"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
WL = sys.argv[3] if len(sys.argv) > 3 else "7.07u"
C = 4.0e-3 * float(WL.rstrip("u")) ** 2 * 1e-12 if False else 4.0e-15 * float(WL.rstrip("u")) ** 2
S = 100
g_nom = C * S / 10e-3
G_PER_IB = 0.927e-9 / 150e-12
IB = g_nom / G_PER_IB
EL, VTH, VRST, VSRC = 1.2, 1.28, 1.2, 0.505
rheo = g_nom * (VTH - EL)
I_REF = 50e-15 * 1.35 / (2e-3 / S)

def body(Iin):
    cell = ("Xn vm spk el vth vrst vbl vbs vbr vdd 0 lif_cmp wl=" + WL) if variant == "cmp" else \
           ("Xn vm spk el vsrc vrst vbl vbs vbr vdd 0 lif_ah wl=" + WL)
    return f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vel el 0 {EL}
Vth vth 0 {VTH}
Vrs vrst 0 {VRST}
Vsr vsrc 0 {VSRC}
Ibl vdd vbl {IB}
Xbl vbl 0 nmaster
Ibr vdd vbr {I_REF}
Xbr vbr 0 nmaster
Ibs vbs 0 100n
Xbs vbs vdd pmaster w=1u l=2u
Iin vdd vm {Iin}
{cell}
.ic v(vm)={EL}
"""
# NOTE: bias masters are shared (one per bias line in silicon too), but they also get
# mismatch per seed; that's a global (whole-array) shift, which is what a shared trim fixes.

def one(seed):
    tau = C / g_nom
    out = {"seed": seed}
    # sub-rheobase steady states (two inputs -> g and offset)
    vs = []
    for I in (0.0, 0.5 * rheo):
        d = deck(body(I), f"tran {tau/50} {12*tau} uic", ["v(vm)"], mismatch=True, seed=seed)
        r = run(d, f"mc_{variant}_{WL}_s{seed}_ss{I*1e12:.0f}")
        vs.append(r["v(vm)"][-1])
    out["off"] = vs[0] - EL
    out["g"] = 0.5 * rheo / (vs[1] - vs[0])
    for k in (2, 4):
        d = deck(body(k * rheo), f"tran {tau/200} {30*tau} uic", ["v(vm)", "v(spk)"], mismatch=True, seed=seed)
        r = run(d, f"mc_{variant}_{WL}_s{seed}_r{k}")
        t, vm, spk = r["_x"], r["v(vm)"], r["v(spk)"]
        st = crossings(t, spk, 1.65)
        out[f"rate{k}"] = rate(st, 5 * tau)
        if k == 2:
            out["vthr"] = float(np.percentile(vm[t > 5 * tau], 99.9))
    return out

if __name__ == "__main__":
    with Pool(6) as p:
        res = p.map(one, range(1, N + 1))
    (RESULTS / f"mc_{variant}_{WL}.json").write_text(json.dumps(res, indent=1))
    A = {k: np.array([r[k] for r in res]) for k in res[0]}
    def cv(x): return np.std(x) / np.mean(x)
    print(f"{variant} C={C*1e15:.0f}fF S={S} N={N}: g mean {A['g'].mean()*1e9:.3f} nS cv {cv(A['g'])*100:.1f}%  "
          f"offset sd {A['off'].std()*1e3:.2f} mV  vthr sd {A['vthr'].std()*1e3:.2f} mV (mean {A['vthr'].mean():.4f})")
    for k in (2, 4):
        print(f"  rate@{k}x rheo: mean {A[f'rate{k}'].mean():.0f} Hz  cv {cv(A[f'rate{k}'])*100:.1f}%")
    # regression of log rate@2x on standardized (log g, off, vthr) -> variance explained per knob
    y = np.log(A["rate2"])
    X = np.column_stack([np.log(A["g"]), A["off"], A["vthr"]])
    Xs = (X - X.mean(0)) / X.std(0)
    beta, *_ = np.linalg.lstsq(np.column_stack([np.ones(N), Xs]), y, rcond=None)
    pred = Xs @ beta[1:]
    tot = np.var(y)
    print("  variance of log(rate@2x) explained by each mismatch source (single-knob trim potential):")
    for i, nm in enumerate(["leak g (-> leak/tau trim)", "leak offset (-> EL trim)", "threshold (-> Vth trim)"]):
        print(f"    {nm:28s} {beta[i+1]**2/tot*100:5.1f}%")
    print(f"    residual (unexplained)       {np.var(y-beta[0]-pred)/tot*100:5.1f}%")
    # an ideal per-neuron input-gain trim can null rate error at ONE operating point;
    # how much error remains at the other (4x) point after trimming at 2x?
    # gain trim factor k_i s.t. rate2_i(k_i I) = mean rate2  -> approximate via local slope
    print("  (gain-trim portability is measured in the next step with explicit trimmed reruns)")
