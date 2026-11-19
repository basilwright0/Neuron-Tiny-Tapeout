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
       python3 sim/tb/tb_lif_mc.py trim [N]     gap-trim validation on slot_ah_h (see trim_mc below)
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

# ------------------------------------------------------------------------------------------------
# Gap-trim validation (slot_ah_h schematic: lif_ah + leak_ota_degx + trim_gap4 + synapse + probes).
# Per mismatch instance: rate at 2x / 4x rheobase untrimmed (code 8, the nominal mid code), the trim
# code found by a rate-based binary search at S = 100, 2x rheobase (what bring-up does: count spikes,
# step the code), then the trimmed rates at 4x (S = 100) and at 2x / 4x with the SAME code at S = 10 and
# S = 1000 (portability). Input: ideal current source into vm (the synapse is off). Shared bias lines
# are ideal voltages from mismatch-free masters; vsrc is the per-die/temperature global calibration.
TRIM_S = (100.0, 10.0, 1000.0)


def _trim_setup():
    import importlib.util
    spec = importlib.util.spec_from_file_location("slotbench", "/work/sim/tb/trim/slotbench.py")
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    return sb


def trim_rate(sb, b, vsrc, vb, k, code, seed, tag):
    body = sb.slot_body("slot_ah_h", b, vsrc, iin=k * b.rheo, code=int(code), vbias=vb) + f".ic v(vm)={sb.EL}\n"
    d = deck(body, f"tran {b.tau / 200} {30 * b.tau} uic", ["v(spk)"], mismatch=seed is not None, seed=seed or 1)
    r = run(d, f"mctrim/{tag}")
    return rate(crossings(r["_x"], r["v(spk)"], 1.65), 5 * b.tau)


def trim_u8(arg):
    """Phase 1: untrimmed (code 8) rate at S = 100, 2x rheobase."""
    seed, env = arg
    sb = _trim_setup()
    return trim_rate(sb, sb.Bias(100.0), env[100.0]["vsrc"], env[100.0]["vb"], 2, 8, seed, f"s{seed}_S100_k2_c8")


def trim_one(arg):
    """Phase 2: trim search toward the die's target rate, then trimmed / untrimmed rates everywhere."""
    seed, env, target, r8 = arg
    sb = _trim_setup()
    out = {"seed": seed}
    b100 = sb.Bias(100.0)
    vb100, vs100 = env[100.0]["vb"], env[100.0]["vsrc"]
    cache = {8: r8}

    def r2(c):
        if c not in cache:
            cache[c] = trim_rate(sb, b100, vs100, vb100, 2, c, seed, f"s{seed}_S100_k2_c{c}")
        return cache[c]
    # binary search on the monotonic rate(code); keep the best visited code
    c, step = 8, 4
    while True:
        r = r2(c)
        if step == 0:
            break
        c = c + step if r < target else c - step
        step //= 2
    best = min(cache, key=lambda q: abs(np.log(cache[q] / target)) if cache[q] > 0 else 1e9)
    for q in (best - 1, best + 1):        # DNL guard: also try the neighbours of the best code
        if 0 <= q <= 15:
            r2(q)
    best = min(cache, key=lambda q: abs(np.log(cache[q] / target)) if cache[q] > 0 else 1e9)
    out["code"] = int(best)
    out["n_search"] = len(cache)
    for S in TRIM_S:
        b = sb.Bias(S)
        for k in (2, 4):
            for nm, cc in (("u", 8), ("t", best)):
                if S == 100.0 and k == 2:
                    out[f"{nm}_S{S:g}_k{k}"] = r2(cc)
                    continue
                out[f"{nm}_S{S:g}_k{k}"] = trim_rate(sb, b, env[S]["vsrc"], env[S]["vb"], k, cc, seed,
                                                     f"s{seed}_S{S:g}_k{k}_c{cc}")
    return out


def trim_env(S):
    sb = _trim_setup()
    b = sb.Bias(S)
    vsrc = sb.cal_vsrc("typical", 27, S, tag=f"mctrim_S{S:g}")
    vb = sb.bias_voltages(b, tag=f"mctrim_S{S:g}")
    # nominal (mismatch-free) target: mean of codes 7 and 8 (offsets -/+1.5 mV around zero)
    tgt = {k: float(np.mean([trim_rate(sb, b, vsrc, vb, k, c, None, f"nom_S{S:g}_k{k}_c{c}") for c in (7, 8)]))
           for k in (2, 4)}
    return S, dict(vsrc=vsrc, vb=vb, target=tgt)


def main_trim(N):
    (RESULTS / "mctrim").mkdir(parents=True, exist_ok=True)
    import os
    with Pool(int(os.environ.get("MC_POOL", "3"))) as p:
        env = dict(p.map(trim_env, TRIM_S))
        r8 = p.map(trim_u8, [(s, env) for s in range(1, N + 1)])
        # per-die target: the population median of the untrimmed rate (bring-up trims every neuron of a
        # die to that die's median; the die-level offset is the global vsrc / bias calibration's job)
        target = float(np.median(r8))
        res = p.map(trim_one, [(s, env, target, r) for s, r in zip(range(1, N + 1), r8)])
    (RESULTS / "mc_trim.json").write_text(json.dumps(dict(env=env, target=target, res=res), indent=1))
    A = {k: np.array([r[k] for r in res], dtype=float) for k in res[0]}
    def cv(x): return np.std(x) / np.mean(x) * 100
    def err(x, t): return np.sqrt(np.mean(np.log(x / t) ** 2)) * 100
    L = [f"gap-trim MC: slot_ah_h schematic, typical 27 C, N={N}, trim found at S=100 / 2x rheobase "
         f"(binary search, mean {A['n_search'].mean():.1f} rate measurements per neuron)",
         f"codes used: {np.bincount(A['code'].astype(int), minlength=16).tolist()} (count per code 0..15)",
         f"population median untrimmed rate at S=100 2x = {target:.0f} Hz = {target / env[100.0]['target'][2]:.3f} x "
         f"the mismatch-free neuron; rms log-err columns are vs the population median at each S / k",
         " S     k   median(Hz)  cv untrimmed  cv trimmed   rms log-err untrimmed  trimmed   max |err| trimmed"]
    for S in TRIM_S:
        for k in (2, 4):
            u, t = A[f"u_S{S:g}_k{k}"], A[f"t_S{S:g}_k{k}"]
            tg = float(np.median(u))
            L.append(f" {S:<5g} {k}x {tg:10.1f}   {cv(u):8.1f} %   {cv(t):8.1f} %       {err(u, tg):8.1f} %       "
                     f"{err(t, tg):6.1f} %   {np.max(np.abs(np.log(t / tg))) * 100:6.1f} %")
    txt = "\n".join(L)
    print(txt)
    (RESULTS / "mc_trim_summary.txt").write_text(txt + "\n")


if __name__ == "__main__" and variant == "trim":
    main_trim(N)
    sys.exit(0)

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
