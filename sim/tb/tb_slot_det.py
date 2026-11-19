"""AH detector (det_ah, cells/neuron/lif.spice) after the 2026-11-19 st3 change vs the old third stage.

usage: python3 sim/tb/tb_slot_det.py          -> sim/results/det/det_summary.txt
Per corner x temp (S = 1000, the worst case for the vsrc line, and S = 100 typical):
  * vsrc load per spike: one lif_ah (200 fF, EL/Vreset 1.30, vsrc calibrated so it trips at 1.38 V) driven by
    8 x rheobase; vsrc is an ideal source; i(Vsrc) peak and charge over one spike (+-1 us around spk rising);
  * idle: supply current of the detector with vm held at EL (between spikes) and its vsrc current.
Both for det_ah (new: XS3 starve, XN3 on vsrc) and det_ah_old (XP3 from vdd, XN3 to vsrc, defined here).
"""
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/lib")
sys.path.insert(0, "/work/sim/tb/trim")
from ngs import deck, run, include, crossings, RESULTS, CORNERS, TEMPS   # noqa: E402
import slotbench as sb                                                   # noqa: E402

OUT = RESULTS / "det"
OLD = """.subckt det_ah_old vm spk vsrc vbp_st vdd vss cfb=8f
XPS s   vbp_st vdd vdd pfet_03v3 W=1u L=2u
XPI n1  vm  s   vdd pfet_03v3 W=1u L=0.5u
XNI n1  vm  vsrc vss nfet_03v3 W=1u L=0.5u
XS2 s2  vbp_st vdd vdd pfet_03v3 W=1u L=2u
XP2 p   n1  s2  vdd pfet_03v3 W=1u L=0.28u
XN2 p   n1  vsrc vss nfet_03v3 W=0.22u L=2u
XP3 pb  p   vdd vdd pfet_03v3 W=1u L=0.28u
XN3 pb  p   vsrc vss nfet_03v3 W=0.5u L=0.28u
Xi4 pb  spk vdd vss inv3
CFB spk vm {cfb}
.ends det_ah_old
.subckt lif_ah_old vm spk el vsrc vreset vbn_leak vbp_st vbn_ref vdd vss wl=7.07u cfb=8f
XC  vm vss mcap wl={wl}
XL  vm el vbn_leak vdd vss leak_ota_deg
XD  vm spk vsrc vbp_st vdd vss det_ah_old cfb={cfb}
XR  spk vm vr vreset vbn_ref vdd vss refrac
.ends lif_ah_old"""


def case(arg):
    c, t, S = arg
    b = sb.Bias(S)
    vsrc = sb.cal_vsrc(c, t, S, tag=f"det_{c}_{t}_S{S:g}")
    out = dict(corner=c, temp=t, S=S, vsrc=vsrc)
    for kind, lif, det in (("new", "lif_ah", "det_ah"), ("old", "lif_ah_old", "det_ah_old")):
        body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
{OLD}
Vdd vdd 0 3.3
Vel el 0 {sb.EL}
Vrs vrst 0 {sb.VRESET}
Vsr vsrc 0 {vsrc}
{sb.MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=1e-15)}
Iin vdd vm {8 * b.rheo}
Xn vm spk el vsrc vrst vbl vbs vbr vdd 0 {lif}
.ic v(vm)={sb.VTH - 0.01}
"""
        tst = min(3 * b.tau, 60e-6)
        r = run(deck(body, f"tran {min(b.tau / 2000, 2e-9)} {tst} uic", ["i(Vsr)", "v(spk)"], corner=c, temp=t),
                f"det/spk_{kind}_{c}_{t}_S{S:g}")
        tt, isr = r["_x"], -r["i(vsr)"]          # current INTO the vsrc source from the detector = load on the line
        st = crossings(tt, r["v(spk)"], 1.65)
        if len(st):
            m = (tt > st[0] - 1e-6) & (tt < st[0] + 1e-6)
            q = float(np.trapezoid(isr[m], tt[m]))
            pk = float(np.max(np.abs(isr[m])))
        else:
            q = pk = float("nan")
        # idle: vm at EL
        body2 = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
{OLD}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
{sb.MASTERS.format(ib=b.ib, i_ref=b.i_ref, i_st=b.i_st, i_syn=1e-15)}
Vdi vddd 0 3.3
Vm vm 0 {sb.EL}
Xd vm spk vsrc vbs vddd 0 {det}
"""
        r2 = run(deck(body2, f"dc Vm {sb.EL} {sb.EL + 0.01} 0.01", ["i(Vdi)", "i(Vsr)"], corner=c, temp=t),
                 f"det/idle_{kind}_{c}_{t}_S{S:g}")
        out[kind] = dict(nspk=int(len(st)), q_fC=q * 1e15, ipk_uA=pk * 1e6, idle_vdd_nA=float(-r2["i(vdi)"][0]) * 1e9,
                         idle_vsrc_nA=float(-r2["i(vsr)"][0]) * 1e9)
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [(c, t, 1000.0) for c in CORNERS for t in TEMPS] + [("typical", 27, 100.0)]
    with Pool(6) as p:
        res = p.map(case, cases)
    L = ["det_ah new (st3: XS3 starve, XN3 on vsrc) vs old; one spike of a lif_ah at 8 x rheobase; vsrc ideal",
         " corner   T     S   vsrc(V) | vsrc Q/spike (fC) new/old | vsrc |I|pk (uA) new/old | idle Idd (nA) new/old | idle Ivsrc (nA) new/old"]
    for r in res:
        n, o = r["new"], r["old"]
        L.append(f" {r['corner']:7s} {r['temp']:3d} {r['S']:5g}  {r['vsrc']:.3f}  |  {n['q_fC']:8.1f} / {o['q_fC']:8.1f}       |"
                 f"  {n['ipk_uA']:6.2f} / {o['ipk_uA']:6.2f}          |  {n['idle_vdd_nA']:7.1f} / {o['idle_vdd_nA']:7.1f}     |"
                 f"  {n['idle_vsrc_nA']:7.2f} / {o['idle_vsrc_nA']:7.2f}")
    txt = "\n".join(L)
    print(txt)
    (OUT / "det_summary.txt").write_text(txt + "\n")
