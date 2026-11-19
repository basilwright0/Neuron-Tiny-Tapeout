#!/usr/bin/env python3
"""Summary of run_recheck_div.sh: rails, I_nd, and idac currents per mode / Iref, relative to mode 0 at Iref=8 uA."""
import glob, re, os
rows = {}
for f in sorted(glob.glob("out/recheck/div/*.log")):
    m = re.match(r"m(\d)_(\w\w)_i([\de.\-+]+)", os.path.basename(f)[:-4])
    mode, corner, iref = int(m.group(1)), m.group(2), float(m.group(3))
    d, rails = {}, None
    for ln in open(f):
        t = ln.split()
        if t and t[0] == "RAILS":
            rails = [float(x) for x in t[1:]]
        elif t and t[0] == "D":
            d[(int(t[1]), int(t[2]))] = (abs(float(t[3])), abs(float(t[4])))
    rows[(corner, mode, iref)] = (rails, d)
print("== rev B master: UA0 modes (0 ext/1, 1 ext/16, 2 stim+internal ref, 3 internal ref monitor)")
print("   I_nd = current in the master diode (from ib_r1 = I_nd/2);  ratio = idac current / (mode 0, Iref 8 uA, same corner)")
for (corner, mode, iref), (rails, d) in sorted(rows.items()):
    if rails is None:
        print(corner, mode, iref, "NO DATA"); continue
    ref = rows.get((corner, 0, 8e-6), (None, {}))[1]
    ind = 2 * abs(rails[7])
    s = f"{corner} mode {mode} Iref {iref*1e6:6.1f}u  I_nd {ind*1e6:6.2f}u  vsn {rails[0]:.3f} vsp {rails[1]:.3f} vgln {rails[2]:.3f} vglp {rails[3]:.3f} pad {rails[9]:.3f} vbn_prb {rails[8]:.3f} |"
    for k in sorted(d):
        n, p = d[k]
        rn = n / ref[k][0] if k in ref and ref[k][0] else float('nan')
        rp = p / ref[k][1] if k in ref and ref[k][1] else float('nan')
        s += f" r{k[0]}c{k[1]} {rn:5.3f}/{rp:5.3f}"
    print(s)
print()
print("absolute (n / p) at tt mode 0 Iref 8 uA: " + " ".join(f"r{k[0]}c{k[1]} {v[0]:.3g}/{v[1]:.3g}" for k, v in sorted(rows[('tt', 0, 8e-6)][1].items())))
