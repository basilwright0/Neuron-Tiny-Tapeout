"""Vreset buffer checks (cells/vreset/vreset_buf.spice).

  python3 sim/tb/vreset/tb_vreset.py [quick]

Load: vreset line (Cline lumped, Rline series) + 20 neurons (19 x 200 fF + 1 x 800 fF AH800),
each = mcap + refrac (lif.spice) at S = 1000 (I_ref for t_ref ~ 2 us).  All 20 membranes sit at
VM0 = vreset + 0.2 V and spike simultaneously at t = 0.5 us.
Pass: line back within 5 mV of its pre-reset value in <= 200 ns, every corner x temp, vin 0.9/1.2/1.5.
Also: DC offset over 0.9..1.5 V; loop gain / phase margin with line-only load and with all
20 membranes attached (reset switches on).
"""
import sys, numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, CORNERS, TEMPS

QUICK = "quick" in sys.argv
I_BIAS = 4e-6            # R1 bias input = B1 ib_r1 (4 uA sink) into the receiver diode W0.4/L1
if "ib" in sys.argv:
    I_BIAS = float(sys.argv[sys.argv.index("ib") + 1])
I_REF = 34e-9            # refractory discharge, S = 1000 -> t_ref ~ 2 us
CLINE, RLINE = 250e-15, 300
NN = 20
BUF = sys.argv[sys.argv.index("buf") + 1] if "buf" in sys.argv else "vreset_buf"
PAR = " " + sys.argv[sys.argv.index("par") + 1].replace(",", " ") if "par" in sys.argv else ""
TAG = BUF + ("_" + PAR.strip().replace(" ", "_").replace("=", "") if PAR else "")
if "ib" in sys.argv:
    TAG += f"_ib{I_BIAS:g}"
# "pex": the buffer (and its bias receiver) from the extracted R1 corner layout
# (layout/readout/out/r1_corner_pex.spice); pad driver disabled (en_b = vdd), abus held at 1.2 V.
PEX = "pex" in sys.argv
PEXNET = "/work/layout/readout/out/r1_corner_pex.spice"
CORNER_SEL = sys.argv[sys.argv.index("corners") + 1].split(",") if "corners" in sys.argv else None
if PEX:
    TAG = TAG.replace(BUF, "pex", 1)
    _ports = next(l for l in open(PEXNET) if l.lower().startswith(".subckt r1_corner")).split()[2:]
    _map = {"pad": "padx", "vrin": "vin", "ibias": "vbp", "vreset": "vout", "abus": "abx",
            "en_b": "vdd", "vdd": "vdd", "vss": "0", "vth_ref": "vthx", "vsrc": "vsrcx"}
    BUFINST = (f".include {PEXNET}" + chr(10) + "Xb " + " ".join(_map[q] for q in _ports) + " r1_corner"
               + chr(10) + "Vabx abx 0 1.2" + chr(10) + "Cpadx padx 0 1p"
               + chr(10) + "Vthx vthx 0 0.5" + chr(10) + "Cvsx vsrcx 0 100f")   # vsrc buffer idle
    RCV = ""
else:
    BUFINST = f"Xb vin vout vbp vdd 0 {BUF}{PAR}"
    RCV = "XPD vbp vbp vdd vdd pfet_03v3 W=0.4u L=1u"

def bias():
    return f"""Vdd vdd 0 3.3
Ib vbp 0 {I_BIAS}
{RCV}
Ir vdd vbnr {I_REF}
Xnr vbnr 0 nmaster w=2u l=4u
"""

def neurons(spk, vm0):
    L = []
    for k in range(NN):
        wl = "14.1u" if k == 0 else "7.07u"
        L.append(f"Xm{k} vm{k} 0 mcap wl={wl}\nXr{k} {spk} vm{k} vr{k} vline vbnr vdd 0 refrac")
    L.append(".ic " + " ".join(f"v(vm{k})={vm0}" for k in range(NN)))
    return "\n".join(L)

def body(vin, load):
    s = f"""{include('neuron/membrane.spice', 'neuron/lif.spice', 'vreset/vreset_buf.spice')}
{bias()}
Vin vin 0 {vin}
{BUFINST}
Rl vout vline {RLINE}
Cl vline 0 {CLINE}
"""
    return s + load

def settle(c, T, vin):
    load = "Vspk spk 0 PWL(0 0 0.5u 0 0.502u 3.3 0.52u 3.3 0.522u 0)\n" + neurons("spk", vin + 0.2)
    d = deck(body(vin, load), "tran 0.5n 1.5u", ["v(vline)", "i(vdd)"], corner=c, temp=T)
    r = run(d, f"vr_set_{TAG}_{c}_{T}_{vin}")
    t, v = r["_x"], r["v(vline)"]
    v0 = np.interp(0.49e-6, t, v)
    after = t > 0.5e-6
    bad = np.where(after & (np.abs(v - v0) > 5e-3))[0]
    ts = (t[bad[-1]] - 0.5e-6) * 1e9 if len(bad) else 0.0
    iq = -np.interp(0.49e-6, t, r["i(vdd)"])
    return ts, (v[after].max() - v0) * 1e3, v0 - vin, iq

def loop(c, T, vin, attached):
    """Loop gain from the closed-loop follower response H = vout/vin: A = H / (1 - H)
    (unity feedback). No loop break, so the operating point is the real one."""
    load = ""
    if attached:   # 20 membranes hard-connected through on reset switches (vr = 3.3 V)
        load = "\n".join(f"Xm{k} vm{k} 0 mcap wl={'14.1u' if k == 0 else '7.07u'}\n"
                         f"XS{k} vm{k} vdd vline 0 nfet_03v3 W=0.5u L=0.5u" for k in range(NN))
    b = body(vin, load).replace(f"Vin vin 0 {vin}", f"Vin vin 0 dc {vin} ac 1")
    d = deck(b, "ac dec 40 1e3 1e10", ["vr(vout)", "vi(vout)"], corner=c, temp=T)
    r = run(d, f"vr_ac_{TAG}_{c}_{T}_{vin}_{int(attached)}")
    f = r["_x"]
    H = r["vr(vout)"] + 1j * r["vi(vout)"]
    A = H / (1 - H)
    g = 20 * np.log10(np.abs(A))
    ph = np.unwrap(np.angle(A))
    i = np.where(g < 0)[0]
    if not len(i) or i[0] == 0:
        return np.nan, np.nan, g[0]
    i = i[0]
    fu = np.interp(0, [g[i], g[i - 1]], [f[i], f[i - 1]])
    return fu, 180 + np.degrees(np.interp(fu, f, ph)), g[0]

corners = ["typical", "ss"] if QUICK else CORNERS
temps = [27] if QUICK else TEMPS
if CORNER_SEL:          # e.g. corners typical:27,fs:85
    cases = [(c.split(":")[0], int(c.split(":")[1])) for c in CORNER_SEL]
else:
    cases = [(c, T) for c in corners for T in temps]
print(f"buffer {TAG}: 20 membranes (1 x 800 fF) reset from vin+0.2 V, line {CLINE*1e15:.0f} fF")
print("corner  T   vin  t5mV(ns)  peak(mV)  offset(mV)  Iq(uA)   PM_line(deg) f_u(MHz)  PM_att(deg) f_u(MHz)")
worst = 0; worst_pm = 180
for c, T in cases:
    if True:
        for vin in (0.9, 1.2, 1.5):
            ts, pk, off, iq = settle(c, T, vin)
            fu0, pm0, _ = loop(c, T, vin, False)
            fu1, pm1, _ = loop(c, T, vin, True)
            worst = max(worst, ts); worst_pm = min(worst_pm, pm0, pm1)
            print(f"{c:7s} {T:3d} {vin:4.1f}  {ts:7.0f}   {pk:7.1f}   {off*1e3:7.2f}   {iq*1e6:6.1f}"
                  f"   {pm0:8.1f}   {fu0/1e6:7.2f}   {pm1:8.1f}   {fu1/1e6:7.2f}")
print(f"worst recovery to 5 mV: {worst:.0f} ns ({'PASS' if worst <= 200 else 'FAIL'} vs 200 ns); worst PM {worst_pm:.1f} deg")
