"""Check 3: kicks on quiet neurons from top-level digital activity (full-chip PEX transient, S = 100, typ 27 C).

  python3 sim/tb/top/tb_top_kick.py [corner] [T]

No neuron has an input; every membrane starts at EL. Events (macro outputs driven with 0.5 ns edges behind 1.5 k), all 40 us later than listed (settling after the
preconditioning release at 0.5 us, see topbench.chip):
   20 us  HOLD on (rt_out[2])            40 us  HOLD off
   60 us  MRESET pulse 1 us (rt_out[3])
   80 us  PROBE_EN on, far slot (3,0) selected (M2 layout B: F2; en_c0)   90 us  PROBE_EN off
   95 us  SEL -> H1 (its rsel row; M2: (0,1))   100 us sub -> 1
  110 us  config write (LOAD): H1 trim 8 -> 7 (nibble 0 = cfg_out[7..10], 4 lines toggle)
  130 us  config write: IDAC word byte 0x02 (vbn_ax / vbp_w codes, B1 code lines toggle; BIAS_EN stays 1)
  150 us  stimulus A pulse 2 us (rt_out[0]), nominal weight (every array neuron gets ~2 fC of synapse charge)
edge = vm change 20-60 ns after the edge (the capacitive kick, before the synapse / leak act), step = mean of
1-3 us after minus the pre-event baseline (pre-event slope removed). Hold drift: vm slope in the HOLD window.
Victims: vm of every array neuron (floorplan MAP, REF excluded), D1 vs / d1 / d2, AdEx vm.
Writes sim/results/top/kick_<corner>_<T>.txt.   `--list`: print the victims and probe targets only (no PEX).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topnet as T            # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CORNER = ARGS[0] if len(ARGS) > 0 else "typical"
TEMP = int(ARGS[1]) if len(ARGS) > 1 else 27
FAR = (3, 0)                                          # top row, column 0: longest abus / column-line path
FAR_N = T.fp.slot_map()[FAR]
H1 = T.slot_pos("H1")                                 # trim nibble 0 (TRIM_NIBBLES["H1.VTH"])
assert T.fp.TRIM_NIBBLES["H1.VTH"] == 0
VICT = {f"{n} {i}": f"{i}.vm" for n, i, c in T.neurons()}
VICT.update({"D1 vs": "d1.vs", "D1 d1": "d1.d1", "D1 d2": "d1.d2", "AdEx vm": "ax.vm"})
if "--list" in sys.argv:
    print(f"probe: far {FAR_N} {FAR}, then SEL -> H1 {H1}")
    for k, n in VICT.items():
        print(f"  {k:12s} {n}")
    sys.exit(0)

import numpy as np            # noqa: E402
import topbench as B          # noqa: E402

S = 100.0
codes = B.op_point(S)
EL = 1.30
c0 = T.config(codes=codes)
evs = [(0.0, c0)]


def at(t, **kw):
    base = dict(codes=codes, probe=None, rt=(0, 0, 0, 0))
    base.update(kw)
    evs.append((t, T.config(**base)))


cw = dict(codes)
EVENTS = [("HOLD on", 60e-6), ("HOLD off", 80e-6), ("MRESET on", 100e-6), ("MRESET off", 101e-6),
          (f"PROBE_EN on ({FAR_N})", 120e-6), ("PROBE_EN off", 130e-6), (f"SEL row {FAR[0]}->{H1[0]}", 135e-6),
          ("SUB 0->1", 140e-6),
          ("LOAD: H1 trim 8->7", 150e-6), ("LOAD: IDAC byte 2", 170e-6), ("stim A on", 190e-6),
          ("stim A off", 192e-6)]
at(60e-6, rt=(0, 0, 1, 0))
at(80e-6)
at(100e-6, rt=(0, 0, 0, 1))
at(101e-6)
at(120e-6, probe=dict(row=FAR[0], col=FAR[1], sub=0))
at(130e-6, probe=dict(row=FAR[0], col=FAR[1], sub=0, en=0))
at(135e-6, probe=dict(row=H1[0], col=H1[1], sub=0, en=0))
at(140e-6, probe=dict(row=H1[0], col=H1[1], sub=1, en=0))
st = T.config(codes=codes, probe=dict(row=H1[0], col=H1[1], sub=1, en=0))
for j in range(4):                                    # nibble 0 (H1) = cfg_out[7..10]: 8 -> 7
    st[f"cfg_out[{7 + j}]"] = 3.3 * ((7 >> j) & 1)
evs.append((150e-6, dict(st)))
cw = dict(codes, i3=codes["i3"] ^ 0b10101, i4=codes["i4"] ^ 0b01010)   # byte 2 holds i3[4:1], i4[3:0]
st2 = T.config(codes=cw, probe=dict(row=H1[0], col=H1[1], sub=1, en=0))
for j in range(4):
    st2[f"cfg_out[{7 + j}]"] = 3.3 * ((7 >> j) & 1)
evs.append((170e-6, dict(st2)))
st3 = dict(st2)
st3["rt_out[0]"] = 3.3
evs.append((190e-6, st3))
evs.append((192e-6, dict(st2)))
TEND = 210e-6
LINES = ["vbn_leak", "vbn_ref", "vbp_syn", "vbp_st", "vbn_prb", "el", "vreset", "vsrc", "vth_ref", "aux3",
         "vbn_ax", "vbp_w"]
body = B.chip(S, state_over=B.timeline(evs))
ns = "\n".join(f".nodeset v({T.vnode(n)})={EL}" for n in VICT.values())
sv = [f"v({T.vnode(n)})" for n in VICT.values()] + [f"v({T.vnode(n)})" for n in LINES]
d = B.deck(body + ns + "\n", f"tran 2n {TEND:g} 0 20n", sv, corner=CORNER, temp=TEMP)
r = B.go(d, f"kick_{CORNER}_{TEMP}")
t = r["_x"]
out = [f"Kicks on quiet nodes, full-chip PEX, {CORNER} {TEMP} C, S = {S:g} (no inputs; leak restores vm with "
       f"tau = 100 us). Step = mean(1-3 us after) - mean(1 us before), drift-corrected; peak = max |excursion| in 2 us.", ""]


def kick(y, te):
    pre = (t > te - 1.2e-6) & (t < te - 0.05e-6)
    post = (t > te + 1e-6) & (t < te + 3e-6)
    edge = (t > te + 20e-9) & (t < te + 60e-9)
    p = np.polyfit(t[pre], y[pre], 1) if pre.sum() > 3 else (0, np.mean(y[pre]))
    base = np.polyval(p, t)
    return np.mean((y - base)[edge]), np.mean((y - base)[post])


hdr = "event                 " + " ".join(f"{k:>14s}" for k in VICT)
out.append("vm / node kicks, edge (step) in mV")
out.append(hdr)
worst = (0, "")
for nm, te in EVENTS:
    row = f"{nm:21s} "
    for k, n in VICT.items():
        y = r[f"v({T.vnode(n)})".lower()]
        e_, s_ = kick(y, te)
        row += f" {e_ * 1e3:+6.2f}({s_ * 1e3:+6.1f})"
        if "MRESET" not in nm and abs(e_) > abs(worst[0]):
            worst = (e_, f"{k} at {nm}")
    out.append(row)
out.append(f"worst edge kick (MRESET excluded: it resets every membrane by design): {worst[0] * 1e3:+.2f} mV, {worst[1]}")
out += ["", "hold window (60-80 us): vm slope, mV/ms (from 62 to 79 us)"]
m = (t > 62e-6) & (t < 79e-6)
out.append("  " + "  ".join(f"{k}: {np.polyfit(t[m], r[f'v({T.vnode(n)})'.lower()][m], 1)[0] * 1e3 * 1e-3:+.2f}"
                            for k, n in VICT.items()))
out += ["", "shared lines: peak excursion (mV) within 9 us of each event / time to come back within 1 mV (us)"]
out.append("event                 " + " ".join(f"{k:>16s}" for k in LINES))
for nm, te in EVENTS:
    row = f"{nm:21s} "
    for ln in LINES:
        y = r[f"v({T.vnode(ln)})".lower()]
        pre = np.mean(y[(t > te - 1e-6) & (t < te - 0.05e-6)])
        win = y[(t > te) & (t < te + 9e-6)] - pre
        p_ = win[np.argmax(np.abs(win))]
        late = np.where((np.abs(y - pre) > 1e-3) & (t > te) & (t < te + 9e-6))[0]
        rec = (t[late[-1]] - te) * 1e6 if len(late) else 0.0
        row += f" {p_ * 1e3:+6.1f}/{rec:5.1f}us"
    out.append(row)
txt = "\n".join(out)
print(txt)
(B.OUT / f"kick_{CORNER}_{TEMP}.txt").write_text(txt + "\n")
