"""Speed track: can the probe path follow a spiking membrane at speed S into the board capacitance?

usage: python3 sim/tb/speed/tb_readout.py [nproc]   -> sim/results/speed/readout_summary.txt
DUT: a real slot_ah (schematic, biases x S/100, Iin = 3 x rheobase, vsrc calibrated) with its vm probe tap
ENABLED (rsel = sub_b = en = 1, vbn_prb from a 1 uA master: NOT scaled with S), abus with the 31 other
(deselected) prb_tap followers + 50 fF, then pad_psf (400 uA from ib_r1 = 4 uA, NOT scaled), the TT mux
(500 Ohm, 2 pF) and 3 pF + CB board capacitance, CB = 20 / 50 / 100 pF.
Analysis: pad = a * vm + b fitted on the slow part of each ISI (|dvm/dt| < 0.1 V/tau); e = (pad - b)/a - vm.
  t2mV       time after each spike until |e| stays < 2 mV (vm-referred) for the rest of the ISI
  frac_ok    fraction of the ISI with |e| < 2 mV
  peak_err   (pad-referred-to-vm peak before the spike) - (vm peak before the Cfb kick, i.e. vm at the trip)
  vis_spike  pad excursion above the fitted vm level at the spike (mV, vm-referred): is the spike visible?
"""
import json
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/work/sim/tb/speed")
from common import RESULTS, sb  # noqa: E402
from ngs import deck, run, crossings  # noqa: E402

CBS = (20, 50, 100)


def case(arg):
    corner, temp, S, CB = arg
    b = sb.Bias(S)
    vsrc = sb.cal_vsrc(corner, temp, S, tag=f"ro_{corner}_{temp}_S{S:g}_{CB}")
    ports = sb.PORTS["slot_ah"]
    n = dict(sb.nets("slot_ah"), rsel="on", sub="0", sub_b="on", en="on", vbn_prb="vbp")
    inst = "Xn " + " ".join(n[p] for p in ports) + " slot_ah"
    others = "\n".join(f"Xo{k} vx abus 0 0 0 vbp vdd 0 prb_tap wf=4u lf=2u" for k in range(31))
    extra = f"""Von on 0 3.3
Vx vx 0 1.3
{others}
Cbus abus 0 50f
Ibpd vbpad 0 4u
Xbpd vbpad vdd pmaster w=0.4u l=1u
Venb enb 0 0
Xd abus padi enb vbpad vdd 0 pad_psf
Rsw padi pad 500
Cpi padi 0 2p
Cpad pad 0 {3 + CB}p
"""
    body = sb.slot_body("slot_ah", b, vsrc, iin=3 * b.rheo, i_syn=1e-15, code=8, inst=inst, extra=extra)
    body = body.replace("Vab abus 0 0.6\n", "")     # slotbench holds abus; here the bus is free
    assert "Vab abus" not in body
    tstop = 8 * b.tau
    r = run(deck(body + f".ic v(vm)={sb.EL}\n", f"tran {min(b.tau / 400, 25e-9)} {tstop} uic",
                 ["v(vm)", "v(spk)", "v(pad)", "v(abus)"], corner=corner, temp=temp),
            f"ro_{corner}_{temp}_S{S:g}_cb{CB}")
    t, vm, pad, spk = r["_x"], r["v(vm)"], r["v(pad)"], r["v(spk)"]
    st = crossings(t, spk, 1.65)
    st = st[st > 2 * b.tau]
    dv = np.gradient(vm, t) * b.tau
    slow = (t > 2 * b.tau) & (np.abs(dv) < 0.1)
    # exclude 5% of each ISI right after a spike from the fit
    for s in st:
        slow &= ~((t > s) & (t < s + 0.05 * b.tau))
    a, c0 = np.polyfit(vm[slow], pad[slow], 1)
    e = (pad - c0) / a - vm
    t2, fr, pk, vis = [], [], [], []
    for i in range(len(st) - 1):
        m = (t > st[i]) & (t < st[i + 1])
        tm, em = t[m], e[m]
        bad = np.where(np.abs(em) > 2e-3)[0]
        last_bad = tm[bad[-1]] if len(bad) else st[i]
        # time for the error to settle (only count if it settles before the end of the ISI)
        t2.append(last_bad - st[i])
        fr.append(float(np.mean(np.abs(em) < 2e-3)))
        mp = (t > st[i + 1] - 0.3 * (st[i + 1] - st[i])) & (t < st[i + 1])
        vtrip = float(np.interp(st[i + 1] - 3e-9, t, vm))
        pk.append(float(((pad[mp] - c0) / a).max()) - vtrip)
        ms = (t > st[i + 1]) & (t < st[i + 1] + 0.1 * (st[i + 1] - st[i]))
        vis.append(float(((pad[ms] - c0) / a).max()) - vtrip)
    isi = float(np.mean(np.diff(st))) if len(st) > 1 else float("nan")
    return dict(corner=corner, temp=temp, S=S, CB=CB, gain=float(a), isi=isi, t2mV=float(np.median(t2)) if t2 else float("nan"),
                t2mV_max=float(max(t2)) if t2 else float("nan"), frac_ok=float(np.mean(fr)) if fr else float("nan"),
                peak_err_mV=float(np.mean(pk)) * 1e3 if pk else float("nan"),
                vis_spike_mV=float(np.mean(vis)) * 1e3 if vis else float("nan"), nspk=int(len(st)))


if __name__ == "__main__":
    NP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    cases = [(c, t, S, cb) for S in (1000.0, 10000.0) for c, t in (("typical", 27), ("ss", 0)) for cb in (20, 100)]
    with Pool(NP) as p:
        res = p.map(case, cases)
    L = ["Probe readout of a spiking slot_ah (Iin = 3 x rheobase) through prb_tap + abus + pad_psf + 500 Ohm + (5 + CB) pF",
         "     S corner  T  CB(pF)  gain  ISI(us)  t2mV med/max (us)  t2mV/ISI  frac|e|<2mV  peak_err(mV)  spike_vis(mV)"]
    for r in res:
        L.append(f" {r['S']:5.0f} {r['corner']:7s} {r['temp']:3d} {r['CB']:5d}  {r['gain']:.3f} {r['isi']*1e6:8.3f}  "
                 f"{r['t2mV']*1e6:7.3f} / {r['t2mV_max']*1e6:7.3f}   {r['t2mV']/r['isi']:6.3f}     {r['frac_ok']:6.3f}"
                 f"      {r['peak_err_mV']:+7.1f}       {r['vis_spike_mV']:+7.1f}")
    txt = "\n".join(L)
    print(txt)
    (RESULTS / "readout_summary.txt").write_text(txt + "\n")
    (RESULTS / "readout.json").write_text(json.dumps(res, indent=1))
