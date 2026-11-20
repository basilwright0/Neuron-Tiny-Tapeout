"""det_ah with all biases off (BIAS_EN = 0): spk must be a clean 0 and the supply current ~ leakage.

usage: python3 sim/tb/tb_slot_detoff.py [variant ...]      variants: cur (cells/neuron/lif.spice det_ah), k1, k2
As sim/tb/tier2/tb_det_zero.py (AdEx track): vdd ramps 0 -> 3.3 V in 20 us, vm = 0, vsrc = 0, and vbp_st either an
unpowered 1/2 pmaster diode (B1 off state) or tied to 3.3 V; 1 ms transient. All 5 corners x 0/27/85 C.
Also vm = 1.4 V (a membrane left high when the bias goes off).
  k1: + keeper XK (pfet vdd -> pb, gate spk, W/L 0.22/1)
  k2: k1 + leaker XW (pfet vdd -> pb, gate vdd: off-state leakage only, W/L 2/0.28)
"""
import sys
from multiprocessing import Pool

sys.path.insert(0, "/work/sim/lib")
from ngs import deck, run, include, CORNERS, TEMPS   # noqa: E402

BASE = """XPS s   vbp_st vdd vdd pfet_03v3 W=1u L=2u
XPI n1  vm  s   vdd pfet_03v3 W=1u L=0.5u
XNI n1  vm  vsrc vss nfet_03v3 W=1u L=0.5u
XS2 s2  vbp_st vdd vdd pfet_03v3 W=1u L=2u
XP2 p   n1  s2  vdd pfet_03v3 W=1u L=0.28u
XN2 p   n1  vsrc vss nfet_03v3 W=0.22u L=2u
XS3 s3  vbp_st vdd vdd pfet_03v3 W=1u L=2u
XP3 pb  p   s3  vdd pfet_03v3 W=1u L=0.28u
XN3 pb  p   vsrc vss nfet_03v3 W=0.5u L=0.28u
Xi4 pb  spk vdd vss inv3
CFB spk vm {cfb}"""
EXTRA = {"k1": "XK  pb  spk vdd vdd pfet_03v3 W=0.22u L=1u",
         "k2": "XK  pb  spk vdd vdd pfet_03v3 W=0.22u L=1u\nXW  pb  vdd vdd vdd pfet_03v3 W=2u L=0.28u"}


def subckt(v):
    return f".subckt det_{v} vm spk vsrc vbp_st vdd vss cfb=8f\n{BASE}\n{EXTRA[v]}\n.ends det_{v}"


def case(arg):
    v, c, t, vbs, vm = arg
    det = "det_ah" if v == "cur" else f"det_{v}"
    body = f"""{include('neuron/membrane.spice', 'neuron/lif.spice')}
{subckt('k1')}
{subckt('k2')}
Vdd vdd 0 pwl(0 0 20u 3.3)
Vsr vsrc 0 0
{"Xbs vbp_st vdd pmaster w=1u l=2u" if vbs == "diode" else "Vbs vbp_st 0 3.3"}
Vm vm 0 {vm}
Xd vm spk vsrc vbp_st vdd 0 {det}
"""
    r = run(deck(body, "tran 1u 1m", ["v(spk)", "v(xd.pb)", "v(xd.p)", "v(xd.n1)", "i(Vdd)"], corner=c, temp=t),
            f"detoff/{v}_{c}_{t}_{vbs}_vm{vm}")
    return dict(v=v, c=c, t=t, vbs=vbs, vm=vm, spk=float(r["v(spk)"][-1]), pb=float(r["v(xd.pb)"][-1]),
                p=float(r["v(xd.p)"][-1]), n1=float(r["v(xd.n1)"][-1]), idd=float(-r["i(vdd)"][-1]))


if __name__ == "__main__":
    vs = sys.argv[1:] or ["cur", "k1", "k2"]
    cases = [(v, c, t, vbs, vm) for v in vs for c in CORNERS for t in TEMPS for vbs in ("diode", "3v3") for vm in (0.0, 1.4)]
    with Pool(6) as p:
        res = p.map(case, cases)
    for v in vs:
        rs = [r for r in res if r["v"] == v]
        worst_spk = max(r["spk"] for r in rs)
        worst_i = max(r["idd"] for r in rs)
        print(f"== {v}: worst spk {worst_spk * 1e3:.1f} mV, worst Idd {worst_i * 1e9:.2f} nA, min pb {min(r['pb'] for r in rs):.3f} V")
        for r in rs:
            if r["spk"] > 0.05 or r["idd"] > 1e-9:
                print(f"   {r['c']:7s} {r['t']:3d} vbp_st={r['vbs']:5s} vm={r['vm']}: spk {r['spk']:.3f} pb {r['pb']:.3f} "
                      f"p {r['p']:.3f} n1 {r['n1']:.3f} Idd {r['idd'] * 1e9:.2f} nA")
