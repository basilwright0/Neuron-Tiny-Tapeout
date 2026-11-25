"""Summarize sim/tb/e2/results/e2_*.json into sim/tb/e2/results/summary.md (host or container python)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parent / "results"
ORDER = [("typical", 27), ("ss", 0), ("ff", 85)]


def ft(t):
    if t is None or t == float("inf"):
        return "never"
    for u, s in ((86400, "d"), (3600, "h"), (60, "min"), (1, "s"), (1e-3, "ms")):
        if t >= u:
            return f"{t / u:.3g} {s}"
    return f"{t:.3g} s"


rows = []
for vr in (1.0, 1.5):
    for c, T in ORDER:
        f = D / f"e2_{c}_{T}_{vr:.2f}.json"
        if f.exists():
            rows.append(json.loads(f.read_text()))
L = ["# e2_leak PEX benches (sim/tb/e2/tb_e2.py)", "",
     "Droop from the DC leakage I(V) of each node (forced) and C from AC; start = post-release voltage (transient).", "",
     "| corner | vreset | C na / nb (fF) | release kick na / nb (mV) | dV/dt na / nb (mV/s) | t(-10 mV) na / nb | t(-100 mV) na / nb | 10 s transient na / nb (mV) |",
     "|---|---|---|---|---|---|---|---|"]
for r in rows:
    tr = [1e3 * (r.get(f"tr_v_{n}_10s", 0) - r.get(f"tr_v0_{n}", 0)) for n in ("na", "nb")]
    L.append(f"| {r['corner']}/{r['temp']} | {r['vreset']:.1f} | {r['C_na'] * 1e15:.0f} / {r['C_nb'] * 1e15:.0f} | "
             f"{1e3 * r['tr_kick_na']:+.1f} / {1e3 * r['tr_kick_nb']:+.1f} | "
             f"{1e3 * r['dvdt_na_at_v0']:.3g} / {1e3 * r['dvdt_nb_at_v0']:.3g} | {ft(r['t10mV_na'])} / {ft(r['t10mV_nb'])} | "
             f"{ft(r['t100mV_na'])} / {ft(r['t100mV_nb'])} | {tr[0]:+.3f} / {tr[1]:+.3f} |")
L += ["", "| corner | vreset | reset to 1 mV na / nb | I(vdd) bias off / on (pA) | I(vreset) (pA) | tap offset A / B / array ref (mV) | abus settle (us) | na step at tap on (mV) | na drift while probed 100 us (mV) |",
      "|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    p = r["probe"]
    L.append(f"| {r['corner']}/{r['temp']} | {r['vreset']:.1f} | {r['tset_na'] * 1e9:.0f} / {r['tset_nb'] * 1e9:.0f} ns | "
             f"{r.get('idd_bias_off', float('nan')) * 1e12:.3g} / {r['idd_held'] * 1e12:.3g} | {r.get('ivreset_bias_off', float('nan')) * 1e12:.3g} | "
             f"{1e3 * p['off_a']:.1f} / {1e3 * p['off_b']:.1f} / {1e3 * p['off_ref']:.1f} | {p['tsettle_a'] * 1e6:.2f} | "
             f"{1e3 * p['dna_tap']:+.2f} | {1e3 * p['drift_na_probing_100us']:+.3f} |")
(D / "summary.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

# rev B: vreset step after release, clamp_en = 0 / 1 (V1 = 1.5 V)
S = ["", "## rev B: vreset stepped to V1 - dV after release (V1 = 1.5 V); dV = 0 is the junction-leakage floor", "",
     "| corner | dV | na dV/dt (mV/s) | nb clamp off | nb clamp on | t -10 mV na / nb off / nb on | t -100 mV na / nb off / nb on |",
     "|---|---|---|---|---|---|---|"]
for c, T in ORDER:
    f = D / f"e2_{c}_{T}_1.50.json"
    if not f.exists():
        continue
    st = json.loads(f.read_text()).get("step", {})
    for dv in (0, 300, 600, 1200, 1500):
        a, b0, b1 = st[f"c1_d{dv}"]["na"], st[f"c0_d{dv}"]["nb"], st[f"c1_d{dv}"]["nb"]
        S.append(f"| {c}/{T} | {dv / 1e3:.1f} | {1e3 * a['dvdt']:.3g} | {1e3 * b0['dvdt']:.3g} | {1e3 * b1['dvdt']:.3g} | "
                 f"{ft(a['t10'])} / {ft(b0['t10'])} / {ft(b1['t10'])} | {ft(a['t100'])} / {ft(b0['t100'])} / {ft(b1['t100'])} |")
    for k in ("c0_d300", "c0_d600", "c1_d300", "c1_d600", "c0_d1500", "c1_d1500"):
        tr = st.get(k, {}).get("tran")
        if tr:
            S.append(f"| {c}/{T} tran {k} | | na 10 s: {1e3 * (tr['na']['v10s'] - tr['na']['v2ms']):+.2f} mV | "
                     f"nb 10 s: {1e3 * (tr['nb']['v10s'] - tr['nb']['v2ms']):+.2f} mV | | | |")
with open(D / "summary.md", "a") as fh:
    fh.write("\n".join(S) + "\n")
print("\n".join(S))
