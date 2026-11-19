"""vsrc buffer checks (cells/vsrc/vsrc_buf.spice).

  python3 sim/tb/vsrc/tb_vsrc.py <test> [options]

tests
  dc      offset at vin 0.35/0.55/0.75 V with no load and with a 32 uA DC sink (16 detectors each
          drawing 2 x I_st near threshold at S = 1000), plus quiescent current; 15 corner x temp.
  ac      loop gain / phase margin (unity follower, A = H/(1-H)) with the line + 16 idle detectors,
          and with the line alone; 15 corner x temp, vin 0.35/0.75.
  spk     N neurons (lif_ah, S = 1000) spike at once at the far end of the line; reports the
          vsrc excursion at the buffer and at the far end, the time back within 2 mV, and the
          spike time vs. an ideal vsrc source. options: n <N> (default 4)
options
  corners typical:27,ss:0     restrict cases      buf <subckt>     par k=v,k=v   (buffer params)
  pex                         buffer from layout/readout/out/r1_corner_pex.spice (R1 corner)
  ideal                       (spk) ideal vsrc source instead of the buffer

Line model: ~300 um Metal2 (0.28 um) -> 3 x (33 Ohm, 20 fF) RC ladder; the buffer at one end,
detectors spread along it (spikers on the far tap). Bias: R1 receiver W0.4/L1 fed ib_r1 = 4 uA.
vth_ref source impedance: 100 kOhm (resistor-string tap through the DAC mux) + 50 fF.
"""
import sys
import numpy as np
sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, crossings, CORNERS, TEMPS

A = sys.argv
TEST = A[1] if len(A) > 1 else "dc"
def opt(k, d=None):
    return A[A.index(k) + 1] if k in A else d
BUF = opt("buf", "vsrc_buf")
PAR = " " + opt("par").replace(",", " ") if opt("par") else ""
NSPK = int(opt("n", "4"))
PEX = "pex" in A
IDEAL = "ideal" in A
# st3: what-if detector with its third stage (XP3) starved from vbp_st like stages 1-2 (NOT the
# current cells/neuron/lif.spice det_ah; defined here only to quantify the vsrc load).
ST3 = "st3" in A or "st3v" in A
XN3SRC = "vss" if "st3v" in A else "vsrc"     # st3v: also XN3 source on vss (only stages 1-2 on vsrc)
LIF = "lif_ah3" if ST3 else "lif_ah"
ST3NET = f"""
.subckt det_ah3 vm spk vsrc vbp_st vdd vss cfb=8f
XPS s   vbp_st vdd vdd pfet_03v3 W=1u L=2u
XPI n1  vm  s   vdd pfet_03v3 W=1u L=0.5u
XNI n1  vm  vsrc vss nfet_03v3 W=1u L=0.5u
XS2 s2  vbp_st vdd vdd pfet_03v3 W=1u L=2u
XP2 p   n1  s2  vdd pfet_03v3 W=1u L=0.28u
XN2 p   n1  vsrc vss nfet_03v3 W=0.22u L=2u
XS3 s3  vbp_st vdd vdd pfet_03v3 W=1u L=2u
XP3 pb  p   s3  vdd pfet_03v3 W=1u L=0.28u
XN3 pb  p   {XN3SRC} vss nfet_03v3 W=0.5u L=0.28u
Xi4 pb  spk vdd vss inv3
CFB spk vm {{cfb}}
.ends det_ah3
.subckt lif_ah3 vm spk el vsrc vreset vbn_leak vbp_st vbn_ref vdd vss wl=7.07u cfb=8f
XC  vm vss mcap wl={{wl}}
XL  vm el vbn_leak vdd vss leak_ota_deg
XD  vm spk vsrc vbp_st vdd vss det_ah3 cfb={{cfb}}
XR  spk vm vr vreset vbn_ref vdd vss refrac
.ends lif_ah3
""" if ST3 else ""
TAG = (("pex" if PEX else BUF) + ("_" + PAR.strip().replace(" ", "_").replace("=", "") if PAR else ""))
CASES = ([(c.split(":")[0], int(c.split(":")[1])) for c in opt("corners").split(",")] if opt("corners")
         else [(c, T) for c in CORNERS for T in TEMPS])

S = 1000.0
C = 200e-15
G = C * S / 10e-3
IB_LEAK = G / (0.927e-9 / 150e-12)
I_REF = 50e-15 * 1.35 / (2e-3 / S)
I_ST = 100e-9 * max(1, S / 100)
RSEG, CSEG = 33, 20e-15
NDET = 16          # 13 slots + D1 soma (lif_ah) and 2 pdet

PEXNET = "/work/layout/readout/out/r1_corner_pex.spice"


def buffer_inst():
    """Buffer between vref (after the source impedance) and node vsrc; own supply vddb (Iq)."""
    if PEX:
        ports = next(l for l in open(PEXNET) if l.lower().startswith(".subckt r1_corner")).split()[2:]
        m = {"pad": "padx", "vrin": "vrx", "ibias": "vbp", "vreset": "vrstx", "abus": "abx", "en_b": "vddb",
             "vth_ref": "vref", "vsrc": "vsrc", "vdd": "vddb", "vss": "0"}
        return (f".include {PEXNET}\nXb " + " ".join(m[q] for q in ports) + " r1_corner\n"
                "Vabx abx 0 1.2\nCpadx padx 0 1p\nVrx vrx 0 1.2\nCrst vrstx 0 300f\n")
    return f"Xb vref vsrc vbp vddb 0 {BUF}{PAR}\n"


def common(vin, src=True):
    s = f"""{include('neuron/membrane.spice', 'neuron/lif.spice', 'readout/readout.spice',
                   'dendrite/dendrite.spice', 'vsrc/vsrc_buf.spice')}
{ST3NET}
Vdd vdd 0 3.3
Vddb vddb 0 3.3
Ib vbp 0 4u
{'' if PEX else 'XPR vbp vbp vddb vddb pfet_03v3 W=0.4u L=1u'}
Ibl vdd vbl {IB_LEAK}
Xbl vbl 0 nmaster
Ibr vdd vbr {I_REF}
Xbr vbr 0 nmaster
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Vel el 0 1.2
Vrs vrst 0 1.2
Rl1 vsrc l1 {RSEG}
Rl2 l1 l2 {RSEG}
Rl3 l2 l3 {RSEG}
Cl1 l1 0 {CSEG}
Cl2 l2 0 {CSEG}
Cl3 l3 0 {CSEG}
"""
    if src:
        s += f"Vin vin 0 {vin}\nRin vin vref 100k\nCin vref 0 50f\n" + buffer_inst()
    return s


def idle_dets(nspk, taps=("l1", "l2", "l3")):
    """Idle detectors: lif_ah neurons resting at EL (no input) + D1's two pdet (vd at EL)."""
    L = []
    nlif = NDET - 2 - nspk
    for k in range(nlif):
        L.append(f"Xi{k} vi{k} spi{k} el {taps[k % 3]} vrst vbl vbs vbr vdd 0 {LIF}")
    L.append(f".ic " + " ".join(f"v(vi{k})=1.2" for k in range(nlif)) if nlif else "")
    L.append("Xpd1 el xb1 l2 vbs vdd 0 pdet\nXpd2 el xb2 l3 vbs vdd 0 pdet")
    return "\n".join(L) + "\n"


def cases_loop(fn):
    for c, T in CASES:
        fn(c, T)


# ---------------------------------------------------------------------------------- dc ---
def t_dc():
    print(f"[dc] {TAG}: offset = vsrc - vth_ref (mV); Iq = buffer supply (uA, incl. 4 uA receiver; pex: + Vreset buffer 30 uA)")
    print("corner  T  | off@.35  off@.55  off@.75 | +32uA load: .35   .55   .75 | Iq(uA) @.55")
    VS = (0.35, 0.55, 0.75)
    for c, T in CASES:
        res = []
        for il in (0.0, 32e-6):
            b = common(0.55) + f"Ild 0 l3 {il}\n"
            d = deck(b, "dc Vin 0.30 0.80 0.01", ["v(vsrc)", "i(vddb)"], corner=c, temp=T)
            r = run(d, f"vsrc_dc_{TAG}_{c}_{T}_{il*1e6:.0f}")
            x = r["_x"]
            res.append([1e3 * (np.interp(v, x, r["v(vsrc)"]) - v) for v in VS])
            if il == 0:
                iq = -np.interp(0.55, x, r["i(vddb)"])
        print(f"{c:7s} {T:3d} | " + "  ".join(f"{o:+7.2f}" for o in res[0]) + " | "
              + "  ".join(f"{o:+6.2f}" for o in res[1]) + f" | {iq*1e6:6.1f}", flush=True)


# ---------------------------------------------------------------------------------- ac ---
def loop(c, T, vin, dets):
    b = common(vin) + (idle_dets(0) if dets else "")
    b = b.replace(f"Vin vin 0 {vin}", f"Vin vin 0 dc {vin} ac 1").replace("Rin vin vref 100k", "Rin vin vref 1")
    d = deck(b, "ac dec 40 1e3 1e10", ["vr(vsrc)", "vi(vsrc)"], corner=c, temp=T)
    r = run(d, f"vsrc_ac_{TAG}_{c}_{T}_{vin}_{int(dets)}")
    f = r["_x"]
    H = r["vr(vsrc)"] + 1j * r["vi(vsrc)"]
    Al = H / (1 - H)
    g = 20 * np.log10(np.abs(Al))
    ph = np.unwrap(np.angle(Al))
    i = np.where(g < 0)[0]
    if not len(i) or i[0] == 0:
        return np.nan, np.nan, g[0]
    i = i[0]
    fu = np.interp(0, [g[i], g[i - 1]], [f[i], f[i - 1]])
    return fu, 180 + np.degrees(np.interp(fu, f, ph)), g[0]


def t_ac():
    print(f"[ac] {TAG}: loop gain from the closed-loop follower (A = H/(1-H))")
    print("corner  T  vin  | A0(dB)  f_u(MHz) PM(deg) [line+16 det] | f_u(MHz) PM(deg) [line only]")
    worst = 180
    for c, T in CASES:
        for vin in (0.35, 0.75):
            fu1, pm1, a0 = loop(c, T, vin, "nodet" not in A)
            fu0, pm0, _ = loop(c, T, vin, False)
            worst = min(worst, pm0, pm1)
            print(f"{c:7s} {T:3d} {vin:4.2f} | {a0:6.1f}  {fu1/1e6:7.2f}  {pm1:6.1f}  | {fu0/1e6:7.2f}  {pm0:6.1f}",
                  flush=True)
    print(f"worst PM {worst:.1f} deg")


# --------------------------------------------------------------------------------- spk ---
def ah_trip(vsrc, c, T):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=c, temp=T), f"vsrc_trip_{c}_{T}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


def cal_vin(c, T):
    """Per-die/temperature calibration (as at bring-up): vth_ref so the AH trips at 1.28 V (S = 1000)."""
    v = 0.42
    for _ in range(4):
        v = float(np.clip(v + (1.28 - ah_trip(v, c, T)) / 1.27, 0.2, 0.9))
    return v


def t_spk():
    VIN0 = float(opt("vin")) if opt("vin") else None
    print(f"[spk] {'ideal' if IDEAL else TAG}{(' (st3v detector)' if 'st3v' in A else ' (st3 detector)') if ST3 else ''}: {NSPK} neurons (S=1000, 200 fF, Iin = 8 x rheobase, vm(0) = 1.27 V) spike "
          f"together on the far tap; vin {'cal (AH trip 1.28 V)' if VIN0 is None else VIN0}; {NDET - 2 - NSPK} idle lif_ah + 2 pdet on the line")
    print("corner  T  | v0-vin(mV) | peak far/near (mV) | min far (mV) | back<2mV of settled (ns) | Q +-100ns/neuron (fC) | t_spk (us) | vin")
    for c, T in CASES:
        VIN = cal_vin(c, T) if VIN0 is None else VIN0
        b = common(VIN, src=not IDEAL)
        if IDEAL:
            b += f"Vsi vsrc 0 {VIN}\n"
        rheo = G * 0.08
        sp = []
        for k in range(NSPK):
            sp.append(f"Is{k} vdd vs{k} {8 * rheo}\nXs{k} vs{k} sp{k} el l3s vrst vbl vbs vbr vdd 0 {LIF}")
        b += "Vam l3 l3s 0\n" + "\n".join(sp) + "\n.ic " + " ".join(f"v(vs{k})=1.27" for k in range(NSPK)) + "\n"
        b += idle_dets(NSPK)
        tstop = 5e-6
        d = deck(b, f"tran 0.5n {tstop}", ["v(vsrc)", "v(l3)", "v(sp0)", "i(vam)", "v(vs0)"], corner=c, temp=T)
        r = run(d, f"vsrc_spk_{'ideal' if IDEAL else TAG}{('_st3v' if 'st3v' in A else '_st3') if ST3 else ''}_{c}_{T}_n{NSPK}")
        t = r["_x"]
        st = crossings(t, r["v(sp0)"], 1.65)
        st = st[st > 0.3e-6]
        if not len(st):
            print(f"{c:7s} {T:3d} | no spike; vm max {r['v(vs0)'].max():.3f} at end {r['v(vs0)'][-1]:.3f}"); continue
        ts = st[0]
        far, near = r["v(l3)"], r["v(vsrc)"]
        v0 = np.interp(ts - 0.5e-6, t, far)
        m = (t > ts - 0.3e-6) & (t < ts + 3.0e-6)
        vend = np.interp(ts + 3.0e-6, t, far)       # settled value after the spike (load gone)
        pk_f = (far[m].max() - v0) * 1e3
        pk_n = (near[m].max() - v0) * 1e3
        mn_f = (far[m].min() - v0) * 1e3
        aft = m & (t > ts)
        bad = np.where(aft & (np.abs(far - vend) > 2e-3))[0]
        tb = (t[bad[-1]] - ts) * 1e9 if len(bad) else 0.0
        mq = (t > ts - 0.1e-6) & (t < ts + 0.1e-6)
        q = -np.trapezoid(r["i(vam)"][mq], t[mq]) / NSPK
        print(f"{c:7s} {T:3d} | {(v0 - VIN)*1e3:+7.2f} | {pk_f:7.1f} / {pk_n:7.1f} | {mn_f:7.1f} | {tb:8.0f} | "
              f"{q*1e15:8.0f} | {ts*1e6:.3f} | vin {VIN:.3f}", flush=True)


{"dc": t_dc, "ac": t_ac, "spk": t_spk}[TEST]()
