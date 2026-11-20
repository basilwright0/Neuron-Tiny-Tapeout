"""Leak-tau trim trim_tau4 rev B (cells/trim/trim_tau.spice, referenced to vbn_leak / vss) with the real B1.

usage: python3 sim/tb/trim/tb_trim_tau.py [quick] [nmc=20] [nosettle] [pex]
  B1     the full bias_b1 rev C LVS reference (layout/bias/out/ref_bias_b1.spice: leak IDAC Xi0 + rx_n4 master
         and everything feeding them), EXT /1 mode, Iref into ua0 = S/100 uA, leak code i0; no ideal source
         on vbn_leak.  'pex': one extra typical 27 C case with the extracted bias_b1 (bias_b1_pex.spice).
  slots  one S slot (slot_ah, tail on vbn_leak) and one P slot (slot_ah_p, tail on aux from trim_tau4), both
         schematic, vm forced to EL +- 10 mV (nested DC with the tau code 0..15):
           g = dI/dV(vm) at EL, tau = 200 fF / g;  ratio = g_P / g_S = tau_S / tau_P  (ideal (8 + c)/16).
         Plus tail copies (2/4, drain 0.6 V) on vbn_leak and on aux: I_P / I_S (the leak current ratio).
  cases  typical 27 C, ss 0 C, ff 85 C at S = 100 x leak code 1 / 9 (S = 100 design tau) / 16 / 31;
         ff 85 C S = 10 code 1 (3 pA tails: leakage stress); ss 0 C S = 1000 code 31 (10 nA tails: headroom).
  mc     mismatch MC (typical 27 C, S = 100, code 9), N seeds: every seed is an independent die (B1, S slot,
         P slot and trim cell all with mismatch); ratio vs code per seed.
  settle aux settling for tau code 0 <-> 15 steps at S = 10, leak code 9 (S tails ~30 pA), 27 / 85 C.
Writes sim/results/trim/trim_tau_summary.txt (+ trim_tau.json).
"""
import json
import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slotbench as sb                        # noqa: E402
from ngs import deck, run, include, RESULTS, REPO   # noqa: E402

OUT = RESULTS / "trim"
ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
B1REF = REPO / "layout" / "bias" / "out" / "ref_bias_b1.spice"
B1PEX = REPO / "layout" / "bias" / "out" / "bias_b1_pex.spice"
DEC = "\n".join(f"Bc{k} c{k} 0 V = 3.3*(floor(v(code)/{2**k}+0.01) - 2*floor(v(code)/{2**(k+1)}+0.01))"
                for k in range(4))
DV = 0.01
EL_OF = lambda S: 1.50 if S >= 300 else sb.EL     # firmware rule: EL ~1.5 V above S ~300 (leak OTA headroom)


def ports_of(txt, cell):
    lines = txt.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(f".subckt {cell} "))
    head = lines[i].split()[2:]
    for ln in lines[i + 1:]:
        if not ln.startswith("+"):
            break
        head += ln[1:].split()
    return head


def pex_include():
    """bias_b1_pex.spice with every subckt renamed <name>_pex (leaf names collide with the reference)."""
    txt = B1PEX.read_text()
    for name in sorted(set(re.findall(r"^\.subckt (\S+)", txt, re.M)), key=len, reverse=True):
        txt = re.sub(r"(?<![\w.])" + re.escape(name) + r"(?!\w)", name + "_pex", txt)
    p = OUT / "bias_b1_pex.inc"
    p.write_text(txt)
    return p


def b1(S, i0, pex=False, i0_nodes=False):
    """bias_b1 instance: EXT /1, Iref = S/100 uA into ua0, leak code i0, every other code 0; vbn_leak -> vbl.
    i0_nodes: the leak code bits go to nodes i0b<k> (the caller drives them)."""
    src = pex_include() if pex else B1REF
    cell = "bias_b1_pex" if pex else "bias_b1"
    ports = ports_of(src.read_text(), cell)
    conn, L = {}, []
    for p in ports:
        m = re.fullmatch(r"i0_b(\d)", p)
        if m:
            conn[p] = f"i0b{m.group(1)}" if i0_nodes else ("vdd" if (i0 >> int(m.group(1))) & 1 else "0")
        elif re.fullmatch(r"(i\d|r\d)_b\d|v0_c\d|ua0_s1|ua0_stim|ua0_int|ib_x2", p):
            conn[p] = "0"
        elif p in ("ua0_s0", "bias_en", "vdd", "VDD"):
            conn[p] = "vdd"
        elif p in ("vss", "VSS", "VSUBS"):
            conn[p] = "0"
        elif p == "vbn_leak":
            conn[p] = "vbl"
        else:
            conn[p] = f"b1_{p}"
    L.append(f".include {src}")
    L.append("XB1 " + " ".join(conn[p] for p in ports) + f" {cell}")
    L += [f"Iref 0 b1_ua0 DC {S * 1e-8}", "Vib b1_ib_r1 0 2.5", "Rso b1_ua0_stim_out 0 1e9"]
    return "\n".join(L)


def slot_inst(cell, tag, vm, aux=None):
    n = dict(sb.nets(cell), vm=vm, spk=f"spk{tag}", vbn_leak="vbl")
    if aux:
        n["aux"] = aux
    return f"X{tag} " + " ".join(n[p] for p in sb.PORTS[cell]) + f" {cell}"


def body(S, i0, pex=False, code_src="Vcode code 0 0", vbias=None, el=None):
    b = sb.Bias(S)
    el = el or EL_OF(S)
    masters = (sb.MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=1e-15) if vbias is None else
               "\n".join(f"V{n} {n} 0 {v}" for n, v in vbias.items() if n != "vbl"))
    masters = "\n".join(ln for ln in masters.splitlines() if "vbl" not in ln)    # vbn_leak comes from B1
    return f"""{include(*sb.LIBS, 'trim/trim_tau.spice')}
{b1(S, i0, pex)}
Vdd vdd 0 3.3
Vel el 0 {el}
Vrs vrst 0 {el}
Vsr vsrc 0 1.6
Vab abus 0 0.6
{masters}
Vsa sta 0 0
Vsb stb 0 0
Vho hold 0 0
Vmr mrst 0 0
* P slot gap trim at its mid code 8
Vb0 b0 0 0
Vb1 b1 0 0
Vb2 b2 0 0
Vb3 b3 0 3.3
{code_src}
{DEC if code_src.startswith('Vcode') else ''}
XC auxp vbl c0 c1 c2 c3 vdd 0 trim_tau4
* tail copies (slot XMT 2/4, drain at 0.6 V): S on vbn_leak, P on aux
XTS dts vbl 0 0 nfet_03v3 W=2u L=4u
XTP dtp auxp 0 0 nfet_03v3 W=2u L=4u
Vdts dts 0 0.6
Vdtp dtp 0 0.6
Vs vms 0 {el}
Ep vmp0 0 vms 0 1
Vp vmp0 vmp 0
Es vms0 0 vms 0 1
Vss vms0 vmsl 0
{slot_inst("slot_ah", "s", "vmsl")}
{slot_inst("slot_ah_p", "p", "vmp", aux="auxp")}
"""


SAVE = ["i(Vss)", "i(Vp)", "i(Vdts)", "i(Vdtp)", "v(vbl)", "v(auxp)"]


def analyse(r):
    """Nested DC: inner Vs (3 points: EL - DV, EL, EL + DV), outer code 0..15."""
    a = {k: r[k.lower()].reshape(16, 3) for k in SAVE}
    gS = (a["i(Vss)"][:, 2] - a["i(Vss)"][:, 0]) / (2 * DV)
    gP = (a["i(Vp)"][:, 2] - a["i(Vp)"][:, 0]) / (2 * DV)
    iS = -a["i(Vdts)"][:, 1]
    iP = -a["i(Vdtp)"][:, 1]
    return dict(gS=gS.tolist(), gP=gP.tolist(), ratio=(gP / gS).tolist(), iS=iS.tolist(), iP=iP.tolist(),
                iratio=(iP / iS).tolist(), vbl=float(a["v(vbl)"][8, 1]), aux=a["v(auxp)"][:, 1].tolist(),
                tauS=float(sb.C / np.mean(gS)), tauP8=float(sb.C / gP[8]))


def an_dc(S=100.0):
    el = EL_OF(S)
    return f"dc Vs {el - DV} {el + DV} {DV} Vcode 0 15 1"


def case(arg):
    corner, temp, S, i0, pex = arg
    tag = f"trim/tau_{corner}_{temp}_S{S:g}_i{i0}{'_pex' if pex else ''}"
    r = run(deck(body(S, i0, pex), an_dc(S), SAVE, corner=corner, temp=temp), tag)
    return dict(corner=corner, temp=temp, S=S, i0=i0, pex=pex, **analyse(r))


def mc(seed):
    r = run(deck(body(100.0, 9), an_dc(), SAVE, mismatch=True, seed=seed), f"trim/tau_mc_s{seed}")
    return dict(seed=seed, **analyse(r))


def settle(temp):
    T = 40e-3
    src = "\n".join(f"Vc{k} c{k} 0 PWL(0 0 {T} 0 {T + 1e-6} 3.3 {2 * T} 3.3 {2 * T + 1e-6} 0)" for k in range(4))
    r = run(deck(body(10.0, 9, code_src=src), f"tran 20u {3 * T}", ["i(Vdtp)", "i(Vdts)"], temp=temp),
            f"trim/tau_settle_{temp}")
    t, i = r["_x"], -r["i(vdtp)"]
    out = {}
    for nm, t0, t1 in (("up", T, 2 * T), ("down", 2 * T, 3 * T)):
        m = (t > t0) & (t < t1)
        fin = i[m][-1]
        bad = np.where(np.abs(i[m] / fin - 1) > 0.01)[0]
        out[nm] = float(t[m][bad[-1]] - t0) if len(bad) else 0.0
    out["iS"] = float(-r["i(vdts)"][-1])
    return temp, out


# approximate rest of the vbn_leak load (gates only): 9 slot tails 2/4 (S x3, H x3, CMP, AH50, AH800), 3 F tails 1/4,
# 4 gap-trim ladders (H x3, CMP: 0.5/4 x2, 0.5/3 x4, 0.5/1.5 x3), ~5 tails 2/4 for D1 / AdEx, 100 fF of line
VBL_LOAD = "\n".join([f"XLt{i} 0 vbl 0 0 nfet_03v3 W=2u L=4u" for i in range(14)] +
                     [f"XLf{i} 0 vbl 0 0 nfet_03v3 W=1u L=4u" for i in range(3)] +
                     [f"XLa{i} 0 vbl 0 0 nfet_03v3 W=0.5u L=4u m=2\nXLb{i} 0 vbl 0 0 nfet_03v3 W=0.5u L=3u m=4\n"
                      f"XLc{i} 0 vbl 0 0 nfet_03v3 W=0.5u L=1.5u m=3" for i in range(4)] + ["Cvbl vbl 0 100f"])


def vbl_settle(arg):
    """vbn_leak settling after a leak-code step 1 -> 9 -> 1 (S = 10), with and without the two trim cells."""
    temp, ncell = arg
    T = 20e-3
    pw = f"PWL(0 0 {T} 0 {T + 1e-6} 3.3 {2 * T} 3.3 {2 * T + 1e-6} 0)"
    srcs = "\n".join(f"Vi0{k} i0b{k} 0 " + ("3.3" if k == 0 else pw if k == 3 else "0") for k in range(5))
    cells = "\n".join(f"XC{j} aux{j} vbl c0 c1 c2 c3 vdd 0 trim_tau4\nXTP{j} 0 aux{j} 0 0 nfet_03v3 W=2u L=4u"
                      for j in range(ncell))
    bod = f"""{include('trim/trim_tau.spice')}
{b1(10.0, 0, i0_nodes=True)}
Vdd vdd 0 3.3
{srcs}
Vc0 c0 0 0
Vc1 c1 0 0
Vc2 c2 0 0
Vc3 c3 0 3.3
{VBL_LOAD}
XTS dts vbl 0 0 nfet_03v3 W=2u L=4u
Vdts dts 0 0.6
{cells}
"""
    r = run(deck(bod, f"tran 10u {3 * T}", ["i(Vdts)"], temp=temp), f"trim/tau_vblsettle_{temp}_{ncell}")
    t, i = r["_x"], -r["i(vdts)"]
    out = {}
    for nm, t0, t1 in (("up", T, 2 * T), ("down", 2 * T, 3 * T)):
        m = (t > t0) & (t < t1)
        fin = i[m][-1]
        bad = np.where(np.abs(i[m] / fin - 1) > 0.01)[0]
        out[nm] = float(t[m][bad[-1]] - t0) if len(bad) else 0.0
    return (temp, ncell), out


def fmt_case(r):
    g = np.array(r["ratio"])
    ideal = (8 + np.arange(16)) / 16
    ir = np.array(r["iratio"])
    return (f" {r['corner']:7s} {r['temp']:3d} {r['S']:5g} {r['i0']:3d}{'p' if r['pex'] else ' '} "
            f"{np.mean(r['iS']) * 1e12:8.1f} {r['vbl']:6.3f} {r['tauS'] * 1e6:8.1f}  "
            f"{g[0]:.3f}  {g[8]:.3f}  {g[15]:.3f}   {g[15] / g[0]:.2f}  {np.max(np.abs(g / ideal - 1)) * 100:5.1f} %"
            f"   {np.min(np.diff(g)) / np.mean(np.diff(g)):5.2f}   {bool(np.all(np.diff(g) > 0))}"
            f"   {ir[0]:.3f} {ir[8]:.3f} {ir[15]:.3f}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quick = "quick" in sys.argv
    nmc = int(ARGS.get("nmc", "20"))
    cases = [("typical", 27, 100.0, 9, False)] if quick else \
        [(c, t, 100.0, i0, False) for c, t in (("typical", 27), ("ss", 0), ("ff", 85)) for i0 in (1, 9, 16, 31)] + \
        [("ff", 85, 10.0, 1, False), ("ss", 0, 1000.0, 31, False)]
    if "pex" in sys.argv:
        cases.append(("typical", 27, 100.0, 9, True))
    with Pool(int(os.environ.get("POOL", "8"))) as p:
        res = p.map(case, cases)
        mcr = [] if quick else p.map(mc, range(1, nmc + 1))
        st = {} if (quick or "nosettle" in sys.argv) else dict(p.map(settle, (27, 85)))
        vs = {} if (quick or "nosettle" in sys.argv) else \
            dict(p.map(vbl_settle, [(t, n) for t in (27, 85) for n in (0, 2)]))
    (OUT / "trim_tau.json").write_text(json.dumps(dict(cases=res, mc=mcr, settle=st, vbl_settle={f"{k[0]}_{k[1]}": v for k, v in vs.items()}), indent=1))
    L = [f"tau trim trim_tau4 rev B (vbn_leak / vss reference) with the full bias_b1 rev C"
         " (LVS reference; 'p' = extracted) on vbn_leak",
         "ratio = g_P / g_S = tau_S / tau_P of a schematic P slot (aux from trim_tau4) vs an S slot, vm = EL;"
         " ideal (8 + c)/16 = 0.500 / 1.000 / 1.4375",
         "I_S = slot tail current (2/4 copy on vbn_leak); minstep = smallest step / mean step; Iratio = tail-copy"
         " current ratio P/S at codes 0/8/15",
         " corner   T     S  i0   I_S(pA)  vbl(V) tauS(us)  c=0    c=8    c=15   span  max|err|  minstep  mono"
         "   Iratio 0/8/15"]
    L += [fmt_case(r) for r in res]
    if mcr:
        R = np.array([m["ratio"] for m in mcr])
        d = np.diff(R, axis=1)
        L += [f"mismatch MC (typical 27 C, S = 100, leak code 9, N = {len(mcr)} dies: B1 + S slot + P slot + trim cell):",
              "  code:     " + " ".join(f"{c:6d}" for c in (0, 4, 8, 12, 15)),
              "  mean:     " + " ".join(f"{R[:, c].mean():6.3f}" for c in (0, 4, 8, 12, 15)),
              "  sigma:    " + " ".join(f"{R[:, c].std():6.3f}" for c in (0, 4, 8, 12, 15)),
              "  sigma %:  " + " ".join(f"{R[:, c].std() / R[:, c].mean() * 100:6.1f}" for c in (0, 4, 8, 12, 15)),
              f"  code-8 ratio min/max {R[:, 8].min():.3f}/{R[:, 8].max():.3f};  monotonic in {int(np.sum(np.all(d > 0, axis=1)))}"
              f"/{len(mcr)} dies;  smallest step over all dies {d.min():.4f} (mean step {d.mean():.4f});"
              f"  span c15/c0 {np.min(R[:, 15] / R[:, 0]):.2f}-{np.max(R[:, 15] / R[:, 0]):.2f}"]
    for t, s in st.items():
        L.append(f"aux settling at S = 10, leak code 9 (S tail {s['iS'] * 1e12:.1f} pA), {t} C: code 0->15 {s['up'] * 1e3:.2f} ms,"
                 f" 15->0 {s['down'] * 1e3:.2f} ms (to 1 %)")
    for t in (27, 85):
        if (t, 0) in vs:
            a, b = vs[(t, 0)], vs[(t, 2)]
            L.append(f"vbn_leak settling, leak code 1 -> 9 / 9 -> 1 at S = 10, {t} C (approx. array load): without the trim"
                     f" cells {a['up'] * 1e3:.2f} / {a['down'] * 1e3:.2f} ms, with both {b['up'] * 1e3:.2f} /"
                     f" {b['down'] * 1e3:.2f} ms (to 1 %)")
    txt = "\n".join(L)
    print(txt)
    (OUT / "trim_tau_summary.txt").write_text(txt + "\n")
