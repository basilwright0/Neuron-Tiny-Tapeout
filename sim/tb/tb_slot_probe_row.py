"""Probe select check: does a same-row, other-column tap (rsel = sb = 1, en = 0) disturb abus?

usage: python3 sim/tb/tb_slot_probe_row.py [cell_tap]   cell_tap = prb_tap (default) | prb_tap_old
Selected tap: vm_sel = 1.20 V, en = sel = sb = 1. Three same-row taps (en = 0, sel = sb = 1) with their
vm swept 1.0 .. 2.0 V. abus loaded by the pad follower model (pad_psf) as in tb_readout.py is not needed
for the DC question: abus only sees a 1 pF bus cap and the weak pull-down.
Reports abus vs the other taps' vm, against abus with the other taps deselected (sel = 0).
"""
import sys
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include   # noqa: E402

tap = sys.argv[1] if len(sys.argv) > 1 else "prb_tap"
old = """.subckt prb_tap_old vm abus en sel sb vbn_prb vdd vss wf=1u lf=0.5u
XMF vdd vm  prb vss nfet_03v3 W={wf} L={lf}
XME prb en  s   vss nfet_03v3 W=1u L=0.28u
XMB s   vbn_prb vss vss nfet_03v3 W=2u L=2u
XSW prb sel m   vss nfet_03v3 W=1u L=0.28u
XSB m   sb  abus vss nfet_03v3 W=1u L=0.28u
.ends prb_tap_old"""
out = {}
for osel in (0, 3.3):
    body = f"""{include('neuron/membrane.spice', 'readout/readout.spice', 'neuron/lif.spice', 'neuron/synapse.spice', 'trim/trim_gap.spice', 'neuron/slot.spice')}
{old}
Vdd vdd 0 3.3
Ibp vdd vbp 1u
Xbp vbp 0 nmaster w=2u l=2u
Vs vs 0 1.2
Vo vo 0 1.2
Von on 0 {osel}
Xsel vs abus vdd vdd vdd vbp vdd 0 {tap} wf=4u lf=2u
Xo1 vo abus 0 on on vbp vdd 0 {tap} wf=4u lf=2u
Xo2 vo abus 0 on on vbp vdd 0 {tap} wf=4u lf=2u
Xo3 vo abus 0 on on vbp vdd 0 {tap} wf=4u lf=2u
XPD abus vdd 0 0 nfet_03v3 W=0.22u L=20u
"""
    r = run(deck(body, "dc Vo 1.0 2.0 0.1", ["v(abus)"]), f"probe_row_{tap}_{osel:g}")
    out[osel] = (r["_x"], r["v(abus)"])
print(f"{tap}: abus with the selected tap at vm = 1.20 V; 3 same-row taps (en = 0) at vm_other")
print(" vm_other   abus(others sel=sb=1)   abus(others sel=0)   error (mV)")
for x, a, b in zip(out[3.3][0], out[3.3][1], out[0][1]):
    print(f"  {x:5.2f}     {a:8.4f}               {b:8.4f}          {1e3 * (a - b):8.1f}")
