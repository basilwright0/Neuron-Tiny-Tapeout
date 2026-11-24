"""MIL-319 item 1: full-chip PEX transient at S = 10000 with every neuron firing.

  python3 sim/tb/top/tb_top_s10k.py [corner] [T]          (default typical 27; also ss 0)

Operating point (docs/info.md, S = 10000): ua[0] EXT /1 at 100 uA, IB_X2 = 1, EL / Vth / Vreset 1.50 / 1.58 / 1.50 V,
leak code i0 10 -> 11 (step 5.5 high-speed rule, x 13/12 rounded to the code), other codes = topbench.op_point.
vsrc (AH threshold, v0) = the S = 10000 AH trip calibration of the corner (slotbench.cal_vsrc, as the f-I gate).
Supplies ideal (power = 'ideal'): the static IR drop at S = 10000 comes from tb_top_icur.py + pgrid.py (ICUR_CASES).
Timeline (us):  0-0.5 precond (topbench.chip)   1.3-2.0 baseline (no input)   2.0 every array neuron + AdEx on
  vth_cmp code 27 (r2_b0 = 1):  2.0-5.0 CMP input 0 (false-spike window)   5.0-7.0 CMP at 2 x rheobase
  7.0 r2_b0 -> 0 = code 26 (only bit 0 differs), CMP input 0:  7.5-10.0 false-spike window   10.0-12.0 CMP at 2 x
Drive: neuron i at k = 2 / 3 / 4 (cycled) x its nominal rheobase g * GF * 80 mV, g = 200 fF * S / 10 ms x 1.1 (code 11),
GF = 0.5 for the F cells (half leak). Ideal LIF rate uses tau = C_m / (g GF), t_ref = 2 ms / S (informational).
Reports: per-neuron spikes / rate / rate over ideal LIF; CMP spikes in each window and vm max vs its trip;
supply current; every shared bias line at the B1 driver and at each slot terminal: baseline mean, shift with all
neurons firing (droop), p-p ripple. Writes sim/results/top/s10k_<corner>_<T>.txt
"""
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402
from ngs import crossings     # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CORNER = ARGS[0] if ARGS else "typical"
TEMP = int(ARGS[1]) if len(ARGS) > 1 else 27
S = 10000.0
TEND = float(os.environ.get("S10K_TEND", "12e-6"))
LEAK = 11
G = 200e-15 * S / 10e-3 * LEAK / 10.0
TREF = 2e-3 / S
TON, T27Q, T27D, TSW, T26Q, T26D = 2.0e-6, 2.0e-6, 5.0e-6, 7.0e-6, 7.5e-6, 10.0e-6
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


# vsrc: AH detector trip calibrated to Vth at this corner / S (slotbench, EL / Vth / Vreset + 0.2 V as tb_fi FI_DEL)
sys.path.insert(0, "/work/sim/tb/trim")
import slotbench as sb        # noqa: E402
sb.EL, sb.VTH, sb.VRESET = sb.EL + 0.2, sb.VTH + 0.2, sb.VRESET + 0.2
if B.DECK_ONLY:
    VSRC = 0.6534
else:
    VSRC = sb.cal_vsrc(CORNER, TEMP, S, tag=f"s10k_{CORNER}_{TEMP}")
codes = B.op_point(S)
codes.update(T.vcodes(el=1.50, vreset=1.50, vth_cmp=1.58, vth_ref=VSRC))
codes["i0"] = LEAK
codes["r2"] = 27
log(f"S = 10000 full chip, {CORNER} {TEMP} C: codes {codes}, vsrc {VSRC:.4f} V (v0 {codes['v0']}), ua[0] 100 uA EXT/1, IB_X2 1")

NEUR = [(n, i, c) for n, i, c in T.neurons()]
CMP = T.slot_inst("CMP")
src = {"vstim": "Vstim vstim 0 3.3"}
ideal = {}
ks = [2, 3, 4]
j = 0
for n, i, c in NEUR:
    gf = 0.5 if c.endswith("ah_f") else 1.0
    rheo = G * gf * 0.08
    if i == CMP:
        a = 2 * rheo
        src["Icmp"] = (f"Icmp vstim {T.vnode(i + '.vm')} PWL(0 0 {T27D:g} 0 {T27D + 10e-9:g} {a:g} {TSW:g} {a:g} "
                       f"{TSW + 10e-9:g} 0 {T26D:g} 0 {T26D + 10e-9:g} {a:g})")
        k = 2
    else:
        k = ks[j % 3]
        j += 1
        src[f"I{i}"] = f"I{i} vstim {T.vnode(i + '.vm')} PWL(0 0 {TON:g} 0 {TON + 10e-9:g} {k * rheo:g})"
    tau = T.membrane_cap(c) / (G * gf)
    ideal[i] = (k, 1.0 / (TREF + tau * np.log(k / (k - 1))), tau)
AX = []
try:
    ax_vm, ax_spk = T.vnode("ax.vm"), T.vnode("ax.spk")
    src["Iax"] = f"Iax vstim {ax_vm} PWL(0 0 {TON:g} 0 {TON + 10e-9:g} {3 * G * 0.08:g})"
    AX = [("AdEx", ax_vm, ax_spk)]
except KeyError as e:
    log(f"AdEx node missing ({e}); AdEx not driven")

state = {"r2_b0": f"PWL(0 3.3 {TSW:g} 3.3 {TSW + 1e-9:g} 0)"}
assert (27 & 1) and not (26 & 1) and (27 >> 1) == (26 >> 1)
body = B.chip(S, codes=codes, ib_x2=1, sources=src, state_over=state)

# shared lines: B1 driver end and every slot's own terminal (R-network lines; one node otherwise)
SH = ["vbn_leak", "vbn_ref", "vbp_st", "vbp_syn", "vbn_prb", "el", "vreset", "vsrc", "vth_cmp"]
NET = {"vth_cmp": "aux3"}
par = {}


def f(x):
    while par.get(x, x) != x:
        par[x] = par.get(par[x], par[x])
        x = par[x]
    return x


for l in T.load()["lines"]:
    if l[0] == "R":
        t = l.split()
        a, b = f(t[1]), f(t[2])
        if a != b:
            par[a] = b
term = defaultdict(lambda: defaultdict(set))
for l in T.load()["lines"]:
    if l[0] in "XD":
        t = l.split()
        nn = [q for q in t[1:] if "=" not in q][:-1]
        o = T.owner(nn) or "other"
        for q in nn:
            term[f(q)][o].add(q)
SLOTS = [i for _, i, _ in NEUR]
at = {}
for ln in SH:
    lnet = T.net(NET.get(ln, ln))
    g = f(lnet)
    drv = sorted(term[g].get("r1" if ln in ("vsrc", "vreset") else "b1", set())) or [lnet]
    at[(ln, "drv")] = drv[0]
    for s_ in SLOTS:
        at[(ln, s_)] = (sorted(term[g].get(s_, set())) or [lnet])[0]
sv = {f"v({T.vnode(i + '.vm')})" for _, i, _ in NEUR} | {f"v({T.vnode(i + '.spk')})" for _, i, _ in NEUR}
sv |= {f"v({T.san(x)})" for x in at.values()} | {"i(vvdd)", f"v({T.node('ua[0]')})"}
for _, a_, b_ in AX:
    sv |= {f"v({a_})", f"v({b_})"}
name = f"s10k_{CORNER}_{TEMP}"
r = B.go(B.deck(body, f"tran 1n {TEND:g} 0 1n", sorted(sv), corner=CORNER, temp=TEMP), name,
         timeout=int(os.environ.get("S10K_TIMEOUT", str(125 * 60))))
t = r["_x"]


def V(n):
    return r[n.lower()]


def win(a, b):
    return (t >= a) & (t < b)


UA0 = f"v({T.node('ua[0]')})"
log(f"ua[0] pin {V(UA0)[win(1.3e-6, 2e-6)].mean():.3f} V; "
    f"I(VDD) baseline {-1e6 * V('i(vvdd)')[win(1.3e-6, 2e-6)].mean():.1f} uA, all firing (2.5-7 us) "
    f"{-1e6 * V('i(vvdd)')[win(2.5e-6, 7e-6)].mean():.1f} uA, peak {-1e6 * V('i(vvdd)')[t > 2e-6].min():.1f} uA")
log("")
log("neuron  slot  cell            k   spikes(2.5-12us)  rate(MHz)  ideal(MHz)  ratio  stuck  tau(us)")
bad = 0
for n, i, c in NEUR:
    if i == CMP:
        continue
    sp = crossings(t, V(f"v({T.vnode(i + '.spk')})"), 1.65)
    sp = sp[sp > 2.5e-6]
    rate = (len(sp) - 1) / (sp[-1] - sp[0]) if len(sp) > 2 else 0.0
    stuck = V(f"v({T.vnode(i + '.spk')})")[-20:].mean() > 1.65 and len(sp) < 3
    k, fi, tau = ideal[i]
    ok = len(sp) >= 4 and not stuck
    bad += not ok
    log(f"{n:6s}  {i:4s}  {c:14s} {k:2d}   {len(sp):5d}            {rate / 1e6:7.3f}    {fi / 1e6:7.3f}   "
        f"{rate / fi:5.2f}  {str(stuck):5s}  {tau * 1e6:.2f}{'' if ok else '   <-- NOT FIRING'}")
for nm, a_, b_ in AX:
    sp = crossings(t, V(f"v({b_})"), 1.65)
    sp = sp[sp > 2.5e-6]
    log(f"{nm:6s}  ax    adex           3   {len(sp):5d}            "
        f"{(len(sp) - 1) / (sp[-1] - sp[0]) / 1e6 if len(sp) > 2 else 0:7.3f}    (informational; vm "
        f"{V(f'v({a_})')[t > 2.5e-6].min():.3f}-{V(f'v({a_})')[t > 2.5e-6].max():.3f} V)")
log(f"array neurons not firing: {bad}")
log("")
cs, cv = V(f"v({T.vnode(CMP + '.spk')})"), V(f"v({T.vnode(CMP + '.vm')})")
allsp = crossings(t, cs, 1.65)
log(f"CMP {CMP}: vth_cmp at its terminal and CMP spikes per window (input 0 = false-spike check)")
for lab, a, b, code in (("code 27, input 0  ", T27Q, T27D, 27), ("code 27, 2 x rheo ", T27D, TSW, 27),
                        ("code 26, input 0  ", T26Q, T26D, 26), ("code 26, 2 x rheo ", T26D, TEND, 26)):
    m = win(a, b)
    nsp = int(((allsp >= a) & (allsp < b)).sum())
    vthc = V(f"v({T.san(at[('vth_cmp', CMP)])})")[m]
    log(f"  {lab} {a * 1e6:4.1f}-{b * 1e6:4.1f} us: {nsp:3d} spikes, vth_cmp {vthc.mean():.4f} V (p-p "
        f"{1e3 * (vthc.max() - vthc.min()):.2f} mV), vm {cv[m].min():.4f}-{cv[m].max():.4f} V")
log("")
log("shared lines: baseline mean at the B1 / R1 driver (1.3-2.0 us); with all neurons firing (2.5-7.0 us): worst "
    "mean shift over the slot terminals (droop, mV), worst p-p (mV), and the slot")
for ln in SH:
    y0 = V(f"v({T.san(at[(ln, 'drv')])})")
    base = y0[win(1.3e-6, 2e-6)].mean()
    worst = (0.0, 0.0, "-", "-")
    for s_ in SLOTS:
        y = V(f"v({T.san(at[(ln, s_)])})")
        sh = 1e3 * (y[win(2.5e-6, 7e-6)].mean() - y[win(1.3e-6, 2e-6)].mean())
        pp = 1e3 * (y[win(2.5e-6, 7e-6)].max() - y[win(2.5e-6, 7e-6)].min())
        worst = (sh if abs(sh) > abs(worst[0]) else worst[0], max(pp, worst[1]),
                 s_ if abs(sh) >= abs(worst[0]) else worst[2], s_ if pp >= worst[1] else worst[3])
    log(f"  {ln:9s} {base:.4f} V   shift {worst[0]:+7.2f} mV ({worst[2]})   p-p {worst[1]:7.2f} mV ({worst[3]})")
(B.OUT / f"{name}.txt").write_text("\n".join(lines) + "\n")
