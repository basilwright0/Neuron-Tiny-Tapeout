"""Speed track: shared vsrc line (vsrc_buf, cells/vsrc) with N neurons spiking together at speed S.

usage: python3 sim/tb/speed/tb_vsrc.py <S> <n_spk> <corner> <temp> [ideal]
Adapted from sim/tb/vsrc/tb_vsrc.py 'spk' (read-only) with the current cells: det_ah with the starved
third stage (XS3), EL / Vreset 1.30 V, AH trip calibrated to 1.38 V at the S-scaled I_st (vth_ref tap
through 100 kOhm + 50 fF), detector/leak/refractory biases x S/100. The buffer bias (ib_r1 = 4 uA from
bias_vi) does NOT scale with S. Line: ~300 um Metal2 as 3 x (33 Ohm, 20 fF); 17 detectors on it
(15 lif_ah = 13 slots + D1 soma + AdEx, 2 D1 pdet); n spikers (Iin = 8 x rheobase, vm(0) = 1.37 V) on the far tap.
Reports: vsrc excursion (far end), time back within 2 mV, spikes per spiker vs the ideal-source run,
ISI change, idle-neuron spikes (must be 0). -> sim/results/speed/vsrc_<...>.json
"""
import json
import sys

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS  # noqa: E402
from ngs import deck, run, include, crossings  # noqa: E402

S, NSPK, corner, temp = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
IDEAL = "ideal" in sys.argv[5:]
C = 200e-15
EL, VTH, VRESET = 1.30, 1.38, 1.30
G = C * S / 10e-3
IB_LEAK = G / 6.33
I_REF = 50e-15 * 1.35 / (2e-3 / S)
I_ST = 100e-9 * max(1, S / 100)
TAU = C / G
RSEG, CSEG = 33, 20e-15
NLIF = 15
TAG = f"S{S:g}_n{NSPK}_{corner}_{temp}_{'ideal' if IDEAL else 'buf'}"


def ah_trip(vsrc):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=corner, temp=temp), f"vsrc_trip_{TAG}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


vin = 0.5
for _ in range(4):
    vin = float(np.clip(vin + (VTH - ah_trip(vin)) / 1.27, 0.2, 0.95))

L = [include('neuron/membrane.spice', 'neuron/lif.spice', 'readout/readout.spice', 'neuron/synapse.spice',
             'dendrite/dtrim.spice', 'dendrite/dendrite.spice', 'vsrc/vsrc_buf.spice'),
     f"""Vdd vdd 0 3.3
Vddb vddb 0 3.3
Ib vbp 0 4u
XPR vbp vbp vddb vddb pfet_03v3 W=0.4u L=1u
Ibl vdd vbl {IB_LEAK}
Xbl vbl 0 nmaster
Ibr vdd vbr {I_REF}
Xbr vbr 0 nmaster
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Vel el 0 {EL}
Vrs vrst 0 {VRESET}
Rl1 vsrc l1 {RSEG}
Rl2 l1 l2 {RSEG}
Rl3 l2 l3 {RSEG}
Cl1 l1 0 {CSEG}
Cl2 l2 0 {CSEG}
Cl3 l3 0 {CSEG}
Vam l3 l3s 0
"""]
if IDEAL:
    L.append(f"Vsi vsrc 0 {vin}")
else:
    L.append(f"Vin vin 0 {vin}\nRin vin vref 100k\nCin vref 0 50f\nXb vref vsrc vbp vddb 0 vsrc_buf")
taps = ("l1", "l2", "l3")
rheo = G * (VTH - EL)
for k in range(NSPK):
    L.append(f"Is{k} vdd vs{k} {8 * rheo}\nXs{k} vs{k} sp{k} el l3s vrst vbl vbs vbr vdd 0 lif_ah")
nidle = NLIF - NSPK
for k in range(nidle):
    L.append(f"Xi{k} vi{k} spi{k} el {taps[k % 3]} vrst vbl vbs vbr vdd 0 lif_ah")
L.append("Xpd1 el xb1 l2 vbs vdd 0 pdet\nXpd2 el xb2 l3 vbs vdd 0 pdet")
L.append(".ic " + " ".join([f"v(vs{k})=1.37" for k in range(NSPK)] + [f"v(vi{k})={EL}" for k in range(nidle)]))
tstop = 0.3e-6 + 1.0 * TAU
sv = ["v(vsrc)", "v(l3)", "i(vam)"] + [f"v(sp{k})" for k in range(NSPK)] + [f"v(spi{k})" for k in range(nidle)]
if not IDEAL:
    sv.append("i(vddb)")
r = run(deck("\n".join(L) + "\n", f"tran {min(1e-9, TAU / 2000)} {tstop}", sv, corner=corner, temp=temp),
        f"vsrc_{TAG}")
t = r["_x"]
spk = [crossings(t, r[f"v(sp{k})"], 1.65) for k in range(NSPK)]
idle = sum(len(crossings(t, r[f"v(spi{k})"], 1.65)) for k in range(nidle))
far = r["v(l3)"]
st0 = spk[0]
out = dict(S=S, n=NSPK, corner=corner, temp=temp, ideal=IDEAL, vin=vin, tau=TAU,
           nspk=[int(len(s)) for s in spk], idle_spikes=int(idle), spk0=st0.tolist())
if len(st0):
    ts = st0[0]
    v0 = np.interp(ts - 0.05e-6, t, far)
    m = (t > ts - 0.05e-6) & (t < ts + min(0.3 * TAU, 3e-6))
    vend = np.interp(ts + min(0.3 * TAU, 3e-6), t, far)
    aft = m & (t > ts)
    bad = np.where(aft & (np.abs(far - vend) > 2e-3))[0]
    out.update(v0=float(v0), dv0_mV=float((v0 - vin) * 1e3), pk_mV=float((far[m].max() - v0) * 1e3),
               mn_mV=float((far[m].min() - v0) * 1e3),
               t2mV_ns=float((t[bad[-1]] - ts) * 1e9) if len(bad) else 0.0,
               # sub-threshold load just before the spike: vsrc shift vs the idle value at t = 0.2 us
               pre_mV=float((v0 - np.interp(0.2e-6, t, far)) * 1e3),
               isi=[float(np.mean(np.diff(s))) if len(s) > 1 else float("nan") for s in spk])
(RESULTS / f"vsrc_{TAG}.json").write_text(json.dumps(out, indent=1))
print(f"{TAG}: vin {vin:.3f} spikes/spiker {out['nspk']} idle {idle} " +
      (f"dv0 {out['dv0_mV']:+.1f} pk {out['pk_mV']:+.1f} mn {out['mn_mV']:+.1f} mV t2mV {out['t2mV_ns']:.0f} ns "
       f"ISI0 {out['isi'][0]*1e6:.3f} us" if len(st0) else "NO SPIKE"))
