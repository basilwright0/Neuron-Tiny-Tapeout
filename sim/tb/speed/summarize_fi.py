"""Speed track: one line per f-I case (sim/results/speed/fi_*.json) -> sim/results/speed/fi_summary.txt"""
import glob, json
rows = []
for f in sorted(glob.glob("sim/results/speed/fi_*.json")):
    d = json.load(open(f))
    if d.get("skipped"):
        continue
    tag = f.split("fi_", 1)[1][:-5]
    r = {x["k"]: x for x in d["res"]}
    rat = lambda k: r[k]["rate"] / r[k]["ideal"] if r[k]["ideal"] else float("nan")
    allr = [rat(k) for k in r]
    ok = all(not r[k]["stuck"] or r[k]["rate"] > 0 for k in r) and min(allr) > 0
    rows.append((d["cell"], d["S"], d["corner"], d["temp"], tag, rat(1.1), min(allr[1:]), max(allr[1:]),
                 d["rheo_meas"] / d["rheo"], r[8]["t_ref"] / d["tref_nom"], r[8]["w_spk"] * 1e9, d["w_over_isi8"],
                 r[3]["idd"] * 1e6, d["vsrc"], ok))
rows.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
L = ["cell / S / corner: f/f_ideal at 1.1x rheo, min-max f/f_ideal over 1.5-8x, rheo_meas/rheo_nom (DC, AH only),",
     "t_ref meas/nom (8x run), spike width (ns), w/ISI at 8x, bench Idd at 3x (uA, incl. ~2x I_st + 1 uA probe master), vsrc, fires",
     f"{'case':38s} {'r1.1':>6s} {'rmin':>6s} {'rmax':>6s} {'rheo':>6s} {'tref':>6s} {'w(ns)':>7s} {'w/ISI':>6s} {'Idd':>6s} {'vsrc':>6s} ok"]
for x in rows:
    L.append(f"{x[4]:38s} {x[5]:6.3f} {x[6]:6.3f} {x[7]:6.3f} {x[8]:6.3f} {x[9]:6.3f} {x[10]:7.1f} {x[11]:6.3f} {x[12]:6.2f} {x[13]:6.3f} {'yes' if x[14] else 'NO'}")
open("sim/results/speed/fi_summary.txt", "w").write("\n".join(L) + "\n"); print("\n".join(L))
