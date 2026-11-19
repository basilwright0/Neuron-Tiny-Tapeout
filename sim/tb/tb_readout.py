"""Readout path checks (gate G1: settle to 1% in < 1 us into the pad load at every corner).

For each corner x temp:
  - DC transfer vm 0.9..2.1 V -> pad: gain, offset, linear range
  - step response: vm 1.20 -> 1.30 V (10 ns edge), 16-channel bus parasitics, pad load
    (500 ohm + 5 pF on-chip/pad + 20 pF board/probe): 1% settling time
  - probe loading on the membrane: charge kick on a 50 fF node when en/sel toggle,
    and effective input capacitance (en=1 vs en=0)
"""
import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, CORNERS, TEMPS, crossings

I_PRB, I_RCV = 1e-6, 4e-6    # I_RCV = B1 ib_r1 into the R1 receiver diode (W0.4/L1) -> 100x = 400 uA pad bias
NCH_PAR = 15      # other (deselected) channels hanging on the bus
# Variant flag "slot" (layout/slot, cells/neuron/slot.spice): follower upsized to wf=4u lf=2u in every
# channel, and each slot has two taps (vm and vr) on abus -> 32 switches, 31 of them deselected.
#   python3 sim/tb/tb_readout.py slot
SLOT = "slot" in sys.argv[1:]
FPAR = " wf=4u lf=2u" if SLOT else ""
TAG = "_slot" if SLOT else ""
if SLOT:
    NCH_PAR = 31
# Flag "pex": pad driver + bias receiver (+ Vreset buffer, idle) from the extracted R1 corner layout
# (layout/readout/out/r1_corner_pex.spice, all coupling caps) instead of the pad_psf schematic.
#   python3 sim/tb/tb_readout.py slot pex
PEX = "pex" in sys.argv[1:]
PEXNET = "/work/layout/readout/out/r1_corner_pex.spice"
if PEX:
    TAG += "_pex"
    _ports = next(l for l in open(PEXNET) if l.lower().startswith(".subckt r1_corner")).split()[2:]
    _map = {"pad": "padi", "vrin": "vrin", "ibias": "vbp", "vreset": "vrst", "abus": "abus",
            "en_b": "enb", "vdd": "vdd", "vss": "0"}
    PAD_DRV = (f".include {PEXNET}\nXr " + " ".join(_map[p] for p in _ports) + " r1_corner\n"
               "Vrin vrin 0 1.2\nCrst vrst 0 250f")
    BIAS_RCV = ""                      # the receiver diode is inside the layout
else:
    PAD_DRV = "Xd abus padi enb vbp vdd 0 pad_psf"
    BIAS_RCV = "Xbp vbp vdd pmaster w=0.4u l=1u"

# Pad load: 500 ohm TT mux + 2 pF on its chip side; pad node = 3 pF (pad/bond) + CB board capacitance.
#   cb <pF>  board capacitance after the 500 ohm (default 20; GF COB: whole breakout board attached)
#   ib <A>   R1 bias input ib_r1 (default 4e-6 -> 400 uA pad bias)
#   nokick   skip the membrane kick test
CB = float(sys.argv[sys.argv.index("cb") + 1]) if "cb" in sys.argv else 20.0
if "ib" in sys.argv:
    I_RCV = float(sys.argv[sys.argv.index("ib") + 1])
    TAG += f"_ib{I_RCV:g}"
if CB != 20.0:
    TAG += f"_cb{CB:g}"
TSTOP = 4e-6 if CB <= 50 else 10e-6

def common(vm_src):
    par = "\n".join(f"Xo{k} vx{k} abus 0 0 vbn vdd 0 prb_nsf{FPAR}\nVx{k} vx{k} 0 1.2" for k in range(NCH_PAR))
    return f"""{include('neuron/membrane.spice', 'readout/readout.spice')}
Vdd vdd 0 3.3
Ibn vdd vbn {I_PRB}
Xbn vbn 0 nmaster w=2u l=2u
Ibp vbp 0 {I_RCV}
{BIAS_RCV}
Ven en 0 3.3
Vsl sel 0 3.3
Venb enb 0 0
{vm_src}
Xp vm abus en sel vbn vdd 0 prb_nsf{FPAR}
{par}
Cbus abus 0 50f
{PAD_DRV}
Rsw padi pad 500
Cpi padi 0 2p
Cpad pad 0 {3 + CB}p
"""

print(f"pad load: 500 ohm + 2 pF | 3 pF + {CB:g} pF board; ib_r1 = {I_RCV*1e6:g} uA")
print("corner  T   gain   Vpad@1.2  lin(1.0-1.6)  t_settle1%(ns)  slew-dir(ns,fall)  ovs_rise/fall(%)  ac_peak(dB) f3dB(MHz)")
worst = 0; worst_ovs = 0; worst_pk = -99
for c in CORNERS:
    for T in TEMPS:
        d = deck(common("Vm vm 0 1.2"), "dc Vm 0.9 2.1 5m", ["v(pad)"], corner=c, temp=T)
        r = run(d, f"ro_dc{TAG}_{c}_{T}")
        vm, vp = r["_x"], r["v(pad)"]
        m = (vm >= 1.0) & (vm <= 1.6)
        p = np.polyfit(vm[m], vp[m], 1)
        resid = np.max(np.abs(np.polyval(p, vm[m]) - vp[m]))
        v12 = np.interp(1.2, vm, vp)
        ts, ovs = [], []
        for v0, v1 in ((1.2, 1.3), (1.3, 1.2)):
            src = f"Vm vm 0 PWL(0 {v0} 1u {v0} 1.01u {v1})"
            d = deck(common(src), f"tran 1n {TSTOP}", ["v(pad)"], corner=c, temp=T)
            r = run(d, f"ro_step{TAG}_{c}_{T}_{v0}")
            t, y = r["_x"], r["v(pad)"]
            yf = y[-1]; y0 = np.interp(0.99e-6, t, y)
            tol = 0.01 * abs(yf - y0)
            out = np.where(np.abs(y - yf) > tol)[0]
            ts.append((t[out[-1]] - 1.0e-6) * 1e9 if len(out) else 0)
            after = y[t > 1.0e-6]
            ovs.append(100 * max(0.0, (np.max((after - yf) * np.sign(yf - y0)))) / abs(yf - y0))
        # small-signal vm -> pad transfer: peaking above the DC gain, -3 dB bandwidth
        d = deck(common("Vm vm 0 dc 1.25 ac 1"), "ac dec 40 1e3 1e9", ["vm(pad)"], corner=c, temp=T)
        r = run(d, f"ro_ac{TAG}_{c}_{T}")
        f, g = r["_x"], r["vm(pad)"]
        pk = 20 * np.log10(g.max() / g[0])
        f3 = f[np.where(g < g[0] / np.sqrt(2))[0][0]] / 1e6
        worst = max(worst, max(ts)); worst_ovs = max(worst_ovs, max(ovs)); worst_pk = max(worst_pk, pk)
        print(f"{c:7s} {T:3d}  {p[0]:.3f}  {v12:.3f}     {resid*1e3:5.1f}mV      {ts[0]:8.0f}        {ts[1]:8.0f}"
              f"        {ovs[0]:5.2f} / {ovs[1]:5.2f}      {pk:5.2f}    {f3:6.2f}")
print(f"worst-case 1% settling: {worst:.0f} ns  -> G1 {'PASS' if worst < 1000 else 'FAIL'}; "
      f"worst overshoot {worst_ovs:.2f} %, worst AC peaking {worst_pk:.2f} dB")
if "nokick" in sys.argv:
    sys.exit(0)

# probe loading / kick on a 50 fF floating membrane at typical
body = common("") + "XC vm 0 mcap wl=3.54u\n.ic v(vm)=1.2\n"
body = body.replace("Ven en 0 3.3", "Ven en 0 PWL(0 0 2u 0 2.01u 3.3)").replace("Vsl sel 0 3.3", "Vsl sel 0 PWL(0 0 4u 0 4.01u 3.3)")
d = deck(body, "tran 2n 6u uic", ["v(vm)", "v(pad)"], temp=27)
r = run(d, f"ro_kick{TAG}")
t, v = r["_x"], r["v(vm)"]
print(f"membrane (50 fF, floating) kick: en toggle {1e3*(np.interp(3.9e-6,t,v)-np.interp(1.9e-6,t,v)):+.2f} mV, "
      f"sel toggle {1e3*(np.interp(5.9e-6,t,v)-np.interp(3.9e-6,t,v)):+.2f} mV")
