"""Speed track: AdEx (cells/adex) adaptation ratio and tau_w at speed S.

usage: python3 sim/tb/speed/tb_adex.py <S> [corner:temp,...] [nproc]
Runs sim/tb/tier2/tb_adex_char.py's case() (read-only; source patched in memory, like tb_slot_readout.py)
with every time constant scaled by 100/S and every current by S/100: S, the adaptation increment Iin
(8 nA on vbp_w at S = 100), the 400 pA step, the step window T0..TEND, the time step, the runt window, the
tau_w fit window and the b sampling offset. Results normalised back to S = 100 units:
tau_w * S/100 (ms, should equal the S = 100 value), b * 100/S (pA), ISI ratio last/first (S-independent).
-> sim/results/speed/adex_S<S>.json
"""
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402,F401

S = float(sys.argv[1])
CASES = [(c.split(":")[0], int(c.split(":")[1]), None) for c in
         (sys.argv[2] if len(sys.argv) > 2 else "typical:27,ss:0,ff:85,sf:0").split(",")]
NP = int(sys.argv[3]) if len(sys.argv) > 3 else 2
k = 100.0 / S
src = Path("/work/sim/tb/tier2/tb_adex_char.py").read_text()
rep = [
    ("S = 100.0\nIADW = 8e-9\nT0, T1, TEND = 0.5e-3, 4.5e-3, 6.5e-3",
     f"S = {S}\nIADW = 8e-9 / {k}\nT0, T1, TEND = 0.5e-3 * {k}, 4.5e-3 * {k}, 6.5e-3 * {k}"),
    ('f"tran 200n {tend}"', f'f"tran {{200e-9 * {k}}} {{tend}}"'),
    ("np.diff(st) > 2e-6", f"np.diff(st) > 2e-6 * {k}"),
    ("st < t1 + 50e-6", f"st < t1 + 50e-6 * {k}"),
    ("(x > t1 + 0.2e-3) & (x < min(t1 + 1.5e-3, tend))", f"(x > t1 + 0.2e-3 * {k}) & (x < min(t1 + 1.5e-3 * {k}, tend))"),
    ("np.interp(st[k] - 2e-6, x, iw)", f"np.interp(st[k] - 2e-6 * {k}, x, iw)"),
    ("np.interp(st[k + 1] - 2e-6, x, iw)", f"np.interp(st[k + 1] - 2e-6 * {k}, x, iw)"),
    ("np.interp(st[-1] - 2e-6, x, iw)", f"np.interp(st[-1] - 2e-6 * {k}, x, iw)"),
    ("o = step(corner, temp, vsrc, 400e-12, IADW", f"o = step(corner, temp, vsrc, 400e-12 / {k}, IADW"),
    ('MODE = "_".join(sys.argv[1:2] + sys.argv[3:5]) or "nominal"', f'MODE = "spd{S:g}"'),
]
for a, b in rep:
    assert a in src, a
    src = src.replace(a, b)
src = src.split("\nif __name__")[0]
os.makedirs("/work/sim/results/speed/tier2", exist_ok=True)
g = {"__name__": "tb_adex_char_speed"}
sys.argv = ["tb_adex_char.py"]
exec(compile(src, "tb_adex_char.py(speed)", "exec"), g)


def run_case(a):
    return g["case"](a)


if __name__ == "__main__":
    with Pool(NP) as p:
        res = p.map(run_case, CASES)
    out = []
    for r in res:
        a, n = r["adapt"], r["noadapt"]
        row = dict(corner=r["corner"], temp=r["temp"], S=S, rheo_pA_norm=r.get("rheobase_pA", float("nan")) * k,
                   DT_mV=r.get("DT_mV"), VT=r.get("VT"), ratio=a.get("ratio"), tau_w_ms_norm=a.get("tau_w_ms", float("nan")) / k,
                   b_pA_norm=a.get("b_pA", float("nan")) * k, f0_Hz_norm=a.get("f0_Hz", float("nan")) * k,
                   fss_Hz_norm=a.get("fss_Hz", float("nan")) * k, noadapt_f_norm=n.get("f0_Hz", float("nan")) * k,
                   n_pre=(n["n_pre"], a["n_pre"]), nspk=a["n"])
        out.append(row)
        print(f"AdEx S={S:g} {r['corner']:7s} {r['temp']:3d}: ratio {row['ratio'] or 0:.2f} tau_w(S100 units) "
              f"{row['tau_w_ms_norm']:.3f} ms b {row['b_pA_norm']:.1f} pA f0 {row['f0_Hz_norm']:.0f} fss {row['fss_Hz_norm']:.0f} "
              f"(no-adapt f {row['noadapt_f_norm']:.0f}) rheo {row['rheo_pA_norm']:.0f} pA DT {row['DT_mV'] or 0:.1f} mV pre {row['n_pre']}",
              flush=True)
    (RESULTS / f"adex_S{S:g}.json").write_text(json.dumps(out, indent=1, default=str))
