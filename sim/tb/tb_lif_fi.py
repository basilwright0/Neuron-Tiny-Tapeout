"""LIF f-I curves (comparator and axon-hillock variants) vs the numerical reference.

usage: python3 sim/tb/tb_lif_fi.py [variant] [corner] [temp] [S]
Writes sim/results/fi_<variant>_<corner>_<temp>_S<S>.json and prints a table.
"""
import json, sys
import numpy as np
sys.path.insert(0, "/work/sim/lib"); sys.path.insert(0, "/work/model")
from ngs import deck, run, include, crossings, rate, RESULTS

variant = sys.argv[1] if len(sys.argv) > 1 else "cmp"
corner = sys.argv[2] if len(sys.argv) > 2 else "typical"
temp = int(sys.argv[3]) if len(sys.argv) > 3 else 27
S = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0

C = 200e-15
G_PER_IB = 0.927e-9 / 150e-12       # degenerated leak OTA, measured (tb_leak_iv)
g = C * S / 10e-3                   # tau_bio = 10 ms
IB_LEAK = g / G_PER_IB
EL, VTH, VRESET = 1.20, 1.28, 1.20
VSRC = float(__import__("os").environ.get("VSRC", "0.505"))
# AH threshold knob: REPLICA=1 uses the (unverified, currently unstable) ah_replica servo;
# default is a global per-die calibration of vsrc (CAL=1), emulating what silicon bring-up
# does once per die/temperature: find vsrc so the detector trips at VTH.
REPLICA = __import__("os").environ.get("REPLICA", "0") == "1"
CAL = __import__("os").environ.get("CAL", "1") == "1"


def ah_trip(vsrc):
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vsr vsrc 0 {vsrc}
Ibs vbs 0 {100e-9 * max(1, S / 100)}
Xbs vbs vdd pmaster w=1u l=2u
Vm vm 0 1.0
Xd vm spk vsrc vbs vdd 0 det_ah
"""
    r = run(deck(body, "dc Vm 0.6 2.2 1m", ["v(spk)"], corner=corner, temp=temp),
            f"ahtrip_{corner}_{temp}_S{S:g}")
    x = crossings(r["_x"], r["v(spk)"], 1.65)
    return float(x[0]) if len(x) else float("nan")


if variant == "ah" and CAL and not REPLICA:
    v = VSRC
    for _ in range(4):
        tr = ah_trip(v)
        v = float(np.clip(v + (VTH - tr) / 1.27, 0.05, 1.2))
    VSRC = v
    print(f"calibrated vsrc = {VSRC:.4f} V (trip {ah_trip(VSRC):.4f} V)")
TREF_BIO = 2e-3
I_REF = 50e-15 * (3.3 - 1.95) / (TREF_BIO / S)   # rough: Cr * dV / t_ref
I_CMP, I_ST = 100e-9 * max(1, S / 100), 100e-9 * max(1, S / 100)

tau = C / g
rheo = g * (VTH - EL)
Iins = rheo * np.array([0.5, 1.1, 1.5, 2, 3, 5, 8])
tstop = 40 * tau
results = []
SRCNET = (f"Vsr vsrc 0 {VSRC}" if not REPLICA else
          "Xrep vsrc vth vbs vbsk vdd 0 ah_replica\nIbsk vdd vbsk 5u\nXbsk vbsk 0 nmaster w=4u l=2u")
for Iin in Iins:
    if variant == "cmp":
        cell = f"Xn vm spk el vth vrst vbl vbs vbr vdd 0 lif_cmp"
    else:
        cell = f"Xn vm spk el vsrc vrst vbl vbs vbr vdd 0 lif_ah"
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
Vdd vdd 0 3.3
Vel el 0 {EL}
Vth vth 0 {VTH}
Vrs vrst 0 {VRESET}
{SRCNET}
Ibl vdd vbl {IB_LEAK}
Xbl vbl 0 nmaster
Ibc vdd vbc {I_CMP}
Xbc vbc 0 nmaster w=2u l=2u
Ibr vdd vbr {I_REF}
Xbr vbr 0 nmaster
Ibs vbs 0 {I_ST}
Xbs vbs vdd pmaster w=1u l=2u
Iin vdd vm {Iin}
{cell}
.ic v(vm)={EL}
"""
    d = deck(body, f"tran {tau/200} {tstop} uic", ["v(vm)", "v(spk)", "i(vdd)"],
             corner=corner, temp=temp)
    name = f"fi_{variant}{"R" if REPLICA and variant=="ah" else ""}_{corner}_{temp}_S{S:g}_I{Iin*1e12:.0f}p"
    r = run(d, name)
    t, vm, spk = r["_x"], r["v(vm)"], r["v(spk)"]
    st = crossings(t, spk, 1.65)
    f = rate(st, t_settle=5 * tau)
    m = t > 5 * tau
    ivdd = -np.trapezoid(r["i(vdd)"][m], t[m]) / (t[m][-1] - t[m][0])
    results.append(dict(Iin=Iin, rate=f, nspk=len(st), vm_min=float(vm[t > 5*tau].min()),
                        vm_max=float(vm[t > 5*tau].max()), ivdd=ivdd))

# reference: linear LIF with the same g, EL, Vth, Vreset and the measured refractory
from reference import LIF
ref = LIF(C=C, gL=g, EL=EL, Vth=VTH, Vreset=VRESET, t_ref=TREF_BIO / S)
print(f"{variant} {corner} {temp}C S={S:g}: tau={tau*1e6:.1f}us g={g*1e9:.2f}nS Ib_leak={IB_LEAK*1e12:.0f}pA "
      f"rheobase={rheo*1e12:.0f}pA I_ref={I_REF*1e9:.2f}nA")
print(" Iin/rheo   Iin(pA)  rate_spice(Hz)  rate_ref(Hz)  ratio  vm[min,max]   Ivdd(nA)")
for r_ in results:
    fr = ref.rate(r_["Iin"])
    ratio = r_["rate"] / fr if fr > 0 else float("nan")
    r_["rate_ref"] = fr
    print(f" {r_['Iin']/rheo:7.2f} {r_['Iin']*1e12:9.0f} {r_['rate']:14.1f} {fr:13.1f} {ratio:6.3f}  "
          f"[{r_['vm_min']:.3f},{r_['vm_max']:.3f}] {r_['ivdd']*1e9:9.1f}")
(RESULTS / f"fi_{variant}{"R" if REPLICA and variant=="ah" else ""}_{corner}_{temp}_S{S:g}.json").write_text(json.dumps(
    dict(variant=variant, corner=corner, temp=temp, S=S, tau=tau, g=g, rheo=rheo, results=results),
    indent=1))
