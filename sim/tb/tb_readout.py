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

I_PRB, I_PAD = 1e-6, 200e-6
NCH_PAR = 15      # other (deselected) channels hanging on the bus

def common(vm_src):
    par = "\n".join(f"Xo{k} vx{k} abus 0 0 vbn vdd 0 prb_nsf\nVx{k} vx{k} 0 1.2" for k in range(NCH_PAR))
    return f"""{include('neuron/membrane.spice', 'readout/readout.spice')}
Vdd vdd 0 3.3
Ibn vdd vbn {I_PRB}
Xbn vbn 0 nmaster w=2u l=2u
Ibp vbp 0 {I_PAD}
Xbp vbp vdd pmaster w=20u l=1u
Ven en 0 3.3
Vsl sel 0 3.3
Venb enb 0 0
{vm_src}
Xp vm abus en sel vbn vdd 0 prb_nsf
{par}
Cbus abus 0 50f
Xd abus padi enb vbp vdd 0 pad_psf
Rsw padi pad 500
Cpi padi 0 2p
Cpad pad 0 23p
"""

print("corner  T   gain   Vpad@1.2  lin(1.0-1.6)  t_settle1%(ns)  slew-dir(ns,fall)")
worst = 0
for c in CORNERS:
    for T in TEMPS:
        d = deck(common("Vm vm 0 1.2"), "dc Vm 0.9 2.1 5m", ["v(pad)"], corner=c, temp=T)
        r = run(d, f"ro_dc_{c}_{T}")
        vm, vp = r["_x"], r["v(pad)"]
        m = (vm >= 1.0) & (vm <= 1.6)
        p = np.polyfit(vm[m], vp[m], 1)
        resid = np.max(np.abs(np.polyval(p, vm[m]) - vp[m]))
        v12 = np.interp(1.2, vm, vp)
        ts = []
        for v0, v1 in ((1.2, 1.3), (1.3, 1.2)):
            src = f"Vm vm 0 PWL(0 {v0} 1u {v0} 1.01u {v1})"
            d = deck(common(src), "tran 1n 4u", ["v(pad)"], corner=c, temp=T)
            r = run(d, f"ro_step_{c}_{T}_{v0}")
            t, y = r["_x"], r["v(pad)"]
            yf = y[-1]; y0 = np.interp(0.99e-6, t, y)
            tol = 0.01 * abs(yf - y0)
            out = np.where(np.abs(y - yf) > tol)[0]
            ts.append((t[out[-1]] - 1.0e-6) * 1e9 if len(out) else 0)
        worst = max(worst, max(ts))
        print(f"{c:7s} {T:3d}  {p[0]:.3f}  {v12:.3f}     {resid*1e3:5.1f}mV      {ts[0]:8.0f}        {ts[1]:8.0f}")
print(f"worst-case 1% settling: {worst:.0f} ns  -> G1 {'PASS' if worst < 1000 else 'FAIL'}")

# probe loading / kick on a 50 fF floating membrane at typical
body = common("") + "XC vm 0 mcap wl=3.54u\n.ic v(vm)=1.2\n"
body = body.replace("Ven en 0 3.3", "Ven en 0 PWL(0 0 2u 0 2.01u 3.3)").replace("Vsl sel 0 3.3", "Vsl sel 0 PWL(0 0 4u 0 4.01u 3.3)")
d = deck(body, "tran 2n 6u uic", ["v(vm)", "v(pad)"], temp=27)
r = run(d, "ro_kick")
t, v = r["_x"], r["v(vm)"]
print(f"membrane (50 fF, floating) kick: en toggle {1e3*(np.interp(3.9e-6,t,v)-np.interp(1.9e-6,t,v)):+.2f} mV, "
      f"sel toggle {1e3*(np.interp(5.9e-6,t,v)-np.interp(3.9e-6,t,v)):+.2f} mV")
