"""D1 driven through the real synapse (cells/neuron/synapse.spice syn_in) instead of ideal sources.

usage: python3 sim/tb/dendrite/tb_synapse.py [corner] [temp]
The synapses are inside dend_d1 (one syn_in per subunit). Weight I_w from a 2/4 pmaster (as the
p-IDAC drives vbp_syn). Stimulus: N pulses on stim A and N on stim B (width TW, interval TI, B offset
by TI/2). D1_BSEL = 0: B also goes to d1 (clustered, 2N pulses into d1); D1_BSEL = 1: B goes to d2
(distributed). Same total charge. Plateau on, soma spiking.
Prints which configurations trigger a plateau (the two-layer / clustered-input test, CS EXP-08).
"""
import json
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
PEX = "pex" in sys.argv[3:]          # post-layout: dend_d1 from layout/dendrite/out/dend_d1_pex.spice
NS = (2, 3, 4) if PEX else (1, 2, 3, 4, 6)


def pex_dut():
    """Extracted dend_d1 (layout cell, trims included), ports mapped by name from the schematic DUT line."""
    import re
    src = open("/work/cells/dendrite/dendrite.spice").read().replace("\n+", " ")
    sch = [t for t in re.search(r"^\.subckt dend_d1 (.*)$", src, re.M).group(1).split() if "=" not in t]
    m = dict(zip(sch, DUT.split()[1:-1]))
    m["VSUBS"] = "0"
    pex = open("/work/layout/dendrite/out/dend_d1_pex.spice").read().replace("\n+", " ")
    ports = re.search(r"^\.subckt dend_d1 (.*)$", pex, re.M).group(1).split()
    return "XD " + " ".join(m[p] for p in ports) + " dend_d1"


def dut_cells():
    if not PEX:
        return cells(), DUT
    return (include("neuron/membrane.spice", "neuron/lif.spice", "readout/readout.spice", "dendrite/dtrim.spice") +
            "\n.include /work/layout/dendrite/out/dend_d1_pex.spice", pex_dut())


IW, TW, TI, T0 = 1.0e-9, 10e-6, 25e-6, 2e-3
vsrc = cal_vsrc(corner, temp)


def pulses(n, phase):
    segs = ["0 0"]
    for k in range(n):
        t = T0 + phase + k * TI
        segs += [f"{t:.6g} 0", f"{t + 0.2e-6:.6g} 3.3", f"{t + TW:.6g} 3.3", f"{t + TW + 0.2e-6:.6g} 0"]
    return "pwl(" + " ".join(segs) + ")"


HP = "xd."     # dend_d1 instance path
res = []
CELLS, DUTL = dut_cells()
for n in NS:
    for cfg in ("clustered", "distributed"):
        # stim A always into d1's synapse; stim B into d1 (D1_BSEL = 0) or d2 (D1_BSEL = 1)
        body = f"""{CELLS}
{bias(vsrc=vsrc, pl_en=1, iw=IW, bsel=int(cfg == 'distributed'), stim=False)}
Vsta sta 0 {pulses(n, 0)}
Vstb stb 0 {pulses(n, TI / 2)}
{DUTL}
"""
        r = run(deck(body, "tran 0.5u 4.5e-3", ["v(vs)", "v(d1)", "v(d2)", "v(spk)"] + ([] if PEX else [f"v({HP}xp1.xb)", f"v({HP}xp2.xb)"]),
                     corner=corner, temp=temp), f"dendrite/syn{'pex' if PEX else ''}_{cfg}_{n}_{corner}_{temp}")
        t = r["_x"]
        m = t > 1.9e-3
        base = {k: float(np.interp(1.95e-3, t, r[f"v({k})"])) for k in ("d1", "d2", "vs")}
        if PEX:   # extracted netlist has no internal names: plateau = subunit > +300 mV above its base
            p1 = bool(r["v(d1)"][m].max() - base["d1"] > 0.3)
            p2 = bool(r["v(d2)"][m].max() - base["d2"] > 0.3)
        else:
            p1 = bool((r[f"v({HP}xp1.xb)"][m] > 1.65).any())
            p2 = bool((r[f"v({HP}xp2.xb)"][m] > 1.65).any())
        nspk = len(crossings(t[m], r["v(spk)"][m], 1.65))
        d1m = float(r["v(d1)"][m].max() - base["d1"])
        d2m = float(r["v(d2)"][m].max() - base["d2"])
        res.append(dict(n=n, cfg=cfg, plateau_d1=p1, plateau_d2=p2, spikes=nspk, d1_peak=d1m, d2_peak=d2m))
        print(f"[{corner}_{temp}] N={n} {cfg:11s}: d1 peak +{d1m*1e3:5.0f} mV, d2 peak +{d2m*1e3:5.0f} mV, "
              f"plateau d1={p1} d2={p2}, soma spikes {nspk}", flush=True)
(OUT / f"synapse{'_pex' if PEX else ''}_{corner}_{temp}.json").write_text(json.dumps(dict(IW=IW, TW=TW, TI=TI, res=res), indent=1))
