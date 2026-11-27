"""E3 synaptic-weight test cell (e3_syn) block bench, schematic (LVS reference) or PEX netlist, flattened so the
internal nodes na / nb can be probed and forced.  Adapted from sim/tb/e2/tb_e2.py (r2-e2).

usage (in the EDA container, from /work):
  python3 sim/tb/e3/tb_e3.py sch|pex <corner> <temp> [vbp,...] [vr,...] corner: typical | ss | ff
  python3 sim/tb/e3/tb_e3.py mc N [first] [vbp] [vreset=1.3] schematic MC (statistical corner, global + mismatch), tt/27
  python3 sim/tb/e3/tb_e3.py summary                         -> sim/tb/e3/results/summary.md
Results: sim/tb/e3/results/<tag>.json (+ raw/ decks and ngspice logs).

Per vbp_syn value (ideal source on the gate line):
  tran : grp_en 0 (nodes held at vreset) -> 1 at 5 us; sta 10 us pulse (7-17 us); grp_en 0 18-23 us (reset);
         stb 10 us pulse (25-35 us); grp_en 0 from 36 us, then sta + stb both high 39-49 us (reset-state check).
         dV_sta / dV_stb per node = v(after pulse + 0.5 us) - v(pulse start - 50 ns); ratio = dV_stb / dV_sta
         (3.0 by design: node A 3 parallel units, node B one 3W device); B/A = nb vs na for the same input.
  dc   : na, nb forced to vreset + 0.1 V, grp_en = 1, (sta, stb) = (1, 0) and (0, 1): leg currents and ratios.
  off  : grp_en = 0 with sta = stb = 0 and 1: I(vdd), I(vreset), I(vbp_syn) (reset rule: no static current).
"""
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sim" / "lib"))
import ngs  # noqa: E402
from ngs import header  # noqa: E402

OUTD = REPO / "sim/tb/e3/results"
OUTD.mkdir(parents=True, exist_ok=True)
ngs.RESULTS = OUTD / "raw"
LAY = REPO / "layout/e3"
VBP_DEFAULT = (2.50, 2.58, 2.67)     # chip: 2.67 V (S = 100), 2.58 V (S = 1000), 2.46 V (S = 10000), tt/27 PEX
OPT_TR = ".option gmin=1e-15 abstol=1e-15 reltol=1e-4 method=gear"
T_REL, TA0, TA1, T_RST0, T_RST1, TB0, TB1, T_OFF, TC0, TC1, TEND = (
    5e-6, 7e-6, 17e-6, 18e-6, 23e-6, 25e-6, 35e-6, 36e-6, 39e-6, 49e-6, 50e-6)


def netlist(mode):
    for d in ("out", "final"):
        p = LAY / d / f"e3_syn_{'lvs' if mode == 'sch' else 'pex'}.spice"
        if p.exists():
            return p
    raise FileNotFoundError(f"no e3_syn {mode} netlist in layout/e3/out or final")


def flat(mode):
    """Subckt body as top-level elements (port nets keep their names; VSUBS -> 0)."""
    txt = re.sub(r"\n\+", " ", netlist(mode).read_text())
    m = re.search(r"^\.subckt\s+e3_syn\s+(.*?)$(.*?)^\.ends", txt, re.M | re.S | re.I)
    return re.sub(r"\bVSUBS\b", "0", m.group(2))


def pwl(edges, tr=10e-9):
    """edges: [(t, level)] steps (level 3.3 / 0) -> PWL string starting at 0."""
    pts, v = ["0 0"], 0.0
    for t, lv in edges:
        pts += [f"{t:.4g} {v}", f"{t + tr:.4g} {lv}"]
        v = lv
    return "PWL(" + " ".join(pts) + ")"


def deck(body, mode, hdr, vbp, vr, sources, analysis, save):
    return f"""* e3_syn bench
{header(**hdr)}
{OPT_TR}
.subckt nmaster vb vss w=2u l=4u
XM vb vb vss vss nfet_03v3 W={{w}} L={{l}}
.ends nmaster
{body}
Vss vss 0 0
Vdd vdd 0 3.3
Vhi hi 0 3.3
Ibp vbb vbn_prb 1u
Vbb vbb 0 3.3
Xbp vbn_prb 0 nmaster w=2u l=2u
Vvr vreset 0 {vr}
Vvbp vbp_syn 0 {vbp}
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
Cab abus 0 5p
XPD abus hi 0 0 nfet_03v3 W=0.22u L=20u
Vdum dum 0 0
{sources}
.control
set wr_singlescale
set wr_vecnames
{analysis}
wrdata __OUT__ {' '.join(save)}
quit
.endc
.end
"""


def bench(mode, hdr, vbp, vr, tag, body=None, parts=("tran", "dc", "off")):
    body = body or flat(mode)
    res = dict(vbp=vbp, vreset=vr)
    if "tran" in parts:
        src = f"""Vg grp_en 0 {pwl([(T_REL, 3.3), (T_RST0, 0), (T_RST1, 3.3), (T_OFF, 0)])}
Vsta_src sta 0 {pwl([(TA0, 3.3), (TA1, 0), (TC0, 3.3), (TC1, 0)])}
Vstb_src stb 0 {pwl([(TB0, 3.3), (TB1, 0), (TC0, 3.3), (TC1, 0)])}
.ic v(na)={vr} v(nb)={vr}
"""
        r = ngs.run(deck(body, mode, hdr, vbp, vr, src, f"tran 5n {TEND} 0 5n uic",
                         ["v(na)", "v(nb)", "i(Vdd)", "i(Vvbp)", "i(Vvr)"]), f"{tag}_tran")
        t = r["_x"]
        g = lambda k, tt: float(np.interp(tt, t, r[k]))  # noqa: E731
        for n in ("na", "nb"):
            k = f"v({n})"
            res[f"kick_{n}"] = g(k, TA0 - 50e-9) - vr
            res[f"dV_sta_{n}"] = g(k, TA1 + 0.5e-6) - g(k, TA0 - 50e-9)
            res[f"dV_stb_{n}"] = g(k, TB1 + 0.5e-6) - g(k, TB0 - 50e-9)
            res[f"vmax_{n}"] = float(np.max(r[k]))
            res[f"ratio_{n}"] = res[f"dV_stb_{n}"] / res[f"dV_sta_{n}"] if res[f"dV_sta_{n}"] else None
            off = (t > TC0 - 2e-6) & (t < TEND)
            res[f"off_maxdev_{n}"] = float(np.max(np.abs(r[k][off] - vr)))
        res["BA_sta"] = res["dV_sta_nb"] / res["dV_sta_na"] if res["dV_sta_na"] else None
        res["BA_stb"] = res["dV_stb_nb"] / res["dV_stb_na"] if res["dV_stb_na"] else None
        off = (t > TC0 + 1e-6) & (t < TC1)
        res["off_idd_tran"] = float(np.mean(-r["i(vdd)"][off]))
        res["ivbp_max"] = float(np.max(np.abs(r["i(vvbp)"][t > 1e-6])))
    if "dc" in parts:
        for name, a, b in (("sta", 3.3, 0), ("stb", 0, 3.3)):
            src = f"""Vg grp_en 0 3.3
Vsta_src sta 0 {a}
Vstb_src stb 0 {b}
Vna na 0 {vr + 0.1}
Vnb nb 0 {vr + 0.1}
"""
            r = ngs.run(deck(body, mode, hdr, vbp, vr, src, "dc Vdum 0 0 1", ["i(Vna)", "i(Vnb)", "i(Vdd)", "i(Vvbp)"]),
                        f"{tag}_dc_{name}")
            for n in ("na", "nb"):
                res[f"I_{name}_{n}"] = float(-r[f"i(v{n})"][0])     # current delivered into the node
            res[f"idd_dc_{name}"] = float(-r["i(vdd)"][0])
        for n in ("na", "nb"):
            res[f"Iratio_{n}"] = res[f"I_stb_{n}"] / res[f"I_sta_{n}"] if res[f"I_sta_{n}"] else None
    if "off" in parts:
        for st in (0, 3.3):
            src = f"Vg grp_en 0 0\nVsta_src sta 0 {st}\nVstb_src stb 0 {st}\n"
            r = ngs.run(deck(body, mode, hdr, vbp, vr, src, "dc Vdum 0 0 1",
                             ["i(Vdd)", "i(Vvr)", "i(Vvbp)", "v(na)", "v(nb)"]), f"{tag}_off_{int(st > 0)}")
            k = f"st{int(st > 0)}"
            res[f"off_{k}"] = dict(idd=float(-r["i(vdd)"][0]), ivreset=float(-r["i(vvr)"][0]),
                                   ivbp=float(-r["i(vvbp)"][0]), na=float(r["v(na)"][0]), nb=float(r["v(nb)"][0]))
    return res


def fmt(res):
    s = [f"vbp {res['vbp']:.2f}:"]
    if "dV_sta_na" in res:
        s.append("dV(mV) na sta/stb {:.1f}/{:.1f} r {:.3f} | nb {:.1f}/{:.1f} r {:.3f} | B/A sta {:.3f} stb {:.3f} | "
                 "vmax {:.2f}/{:.2f} | off dev {:.2g}/{:.2g} V".format(
                     1e3 * res["dV_sta_na"], 1e3 * res["dV_stb_na"], res["ratio_na"] or 0, 1e3 * res["dV_sta_nb"],
                     1e3 * res["dV_stb_nb"], res["ratio_nb"] or 0, res["BA_sta"] or 0, res["BA_stb"] or 0,
                     res["vmax_na"], res["vmax_nb"], res["off_maxdev_na"], res["off_maxdev_nb"]))
    if "I_sta_na" in res:
        s.append("I(nA) na {:.3f}/{:.3f} r {:.3f} | nb {:.3f}/{:.3f} r {:.3f}".format(
            1e9 * res["I_sta_na"], 1e9 * res["I_stb_na"], res["Iratio_na"], 1e9 * res["I_sta_nb"],
            1e9 * res["I_stb_nb"], res["Iratio_nb"]))
    if "off_st1" in res:
        s.append("grp_en=0 idd {:.3g}/{:.3g} A, ivbp {:.2g} A, nodes {:.4f}/{:.4f} V".format(
            res["off_st0"]["idd"], res["off_st1"]["idd"], res["off_st1"]["ivbp"], res["off_st1"]["na"],
            res["off_st1"]["nb"]))
    return "  ".join(s)


def corners(mode, corner, temp, vbps, vr):
    hdr = dict(corner=corner, temp=temp)
    tag = f"e3_{mode}_{corner}_{temp}_{vr:.2f}"
    out = dict(mode=mode, corner=corner, temp=temp, vreset=vr, netlist=str(netlist(mode).relative_to(REPO)), runs=[])
    for v in vbps:
        r = bench(mode, hdr, v, vr, f"{tag}_{v:.2f}")
        out["runs"].append(r)
        print(fmt(r), flush=True)
        (OUTD / f"{tag}.json").write_text(json.dumps(out, indent=1))


def _mc_one(a):
    seed, vbp, vr, body = a
    hdr = dict(corner="statistical", temp=27, mismatch=True, global_var=True, seed=seed)
    try:
        r = bench("sch", hdr, vbp, vr, f"e3mc{seed}", body=body, parts=("tran", "dc"))
    except Exception as e:     # keep going; a failed die is reported
        r = dict(error=str(e)[:200])
    r["seed"] = seed
    return r


def mc(n, first, vbp, vr):
    body = flat("sch")
    with Pool(2) as p:
        res = p.map(_mc_one, [(s, vbp, vr, body) for s in range(first, first + n)])
    ok = [r for r in res if "error" not in r]
    st = {}
    for k in ("ratio_na", "ratio_nb", "BA_sta", "BA_stb", "Iratio_na", "Iratio_nb", "dV_sta_na", "dV_sta_nb",
              "I_sta_na", "I_sta_nb"):
        v = np.array([r[k] for r in ok if r.get(k) is not None], float)
        if len(v):
            st[k] = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                         min=float(v.min()), max=float(v.max()), n=len(v))
    out = dict(n=n, first=first, vbp=vbp, vreset=vr, failed=len(res) - len(ok), stats=st, runs=res)
    (OUTD / f"e3_mc_{first}_{n}_{vbp:.2f}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(failed=out["failed"], stats=st), indent=1))


def summary():
    L = ["# e3_syn block bench (sim/tb/e3/tb_e3.py)", "",
         "dV in mV over a 10 us pulse; ratio = dV(stb) / dV(sta) (design 3.0); B/A = nb / na for the same input; "
         "I = DC leg current into the node held at vreset + 0.1 V.", "",
         "| netlist | corner | vreset | vbp | dV sta na / nb | dV stb na / nb | ratio na / nb | B/A sta / stb | I sta na / nb (nA) "
         "| I ratio na / nb | vmax na / nb | grp_en=0: idd (sta=stb=1), node dev |", "|" + "---|" * 12]
    for f in sorted(OUTD.glob("e3_sch_*.json")) + sorted(OUTD.glob("e3_pex_*.json")):
        d = json.loads(f.read_text())
        for r in d["runs"]:
            try:
                L.append(f"| {d['mode']} | {d['corner']}/{d['temp']} | {d['vreset']:.2f} | {r['vbp']:.2f} | {1e3 * r['dV_sta_na']:.1f} / "
                         f"{1e3 * r['dV_sta_nb']:.1f} | {1e3 * r['dV_stb_na']:.1f} / {1e3 * r['dV_stb_nb']:.1f} | "
                         f"{r['ratio_na']:.3f} / {r['ratio_nb']:.3f} | {r['BA_sta']:.3f} / {r['BA_stb']:.3f} | "
                         f"{1e9 * r['I_sta_na']:.2f} / {1e9 * r['I_sta_nb']:.2f} | {r['Iratio_na']:.3f} / "
                         f"{r['Iratio_nb']:.3f} | {r['vmax_na']:.2f} / {r['vmax_nb']:.2f} | "
                         f"{r['off_st1']['idd']:.2g} A, {max(r['off_maxdev_na'], r['off_maxdev_nb']) * 1e3:.2g} mV |")
            except (KeyError, TypeError):
                L.append(f"| {d['mode']} | {d['corner']}/{d['temp']} | {r.get('vbp')} | incomplete |")
    for f in sorted(OUTD.glob("e3_mc_*.json")):
        d = json.loads(f.read_text())
        L += ["", f"## MC {f.name}: N = {d['n']}, failed {d['failed']}, vbp {d['vbp']:.2f}, tt/27 statistical + mismatch",
              "", "| quantity | mean | sd | sd/mean | min | max |", "|---|---|---|---|---|---|"]
        for k, s in d["stats"].items():
            L.append(f"| {k} | {s['mean']:.4g} | {s['sd']:.3g} | {s['sd'] / abs(s['mean']):.2%} | {s['min']:.4g} | "
                     f"{s['max']:.4g} |")
    (OUTD / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "summary":
        summary()
    elif a[0] == "mc":
        mc(int(a[1]), int(a[2]) if len(a) > 2 else 1, float(a[3]) if len(a) > 3 else 2.58,
           float(a[4]) if len(a) > 4 else 1.3)
    else:
        vb = tuple(float(v) for v in a[3].split(",")) if len(a) > 3 else VBP_DEFAULT
        for vr in (a[4].split(",") if len(a) > 4 else ("1.3", "1.5")):
            corners(a[0], a[1], int(a[2]), vb, float(vr))
