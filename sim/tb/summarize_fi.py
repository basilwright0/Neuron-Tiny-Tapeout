import json, glob, numpy as np
rows = []
for f in sorted(glob.glob("/work/sim/results/fi_*_S*.json")):
    d = json.load(open(f))
    rr = [r for r in d["results"] if r["Iin"] >= 1.5 * d["rheo"] and r["rate_ref"] > 0]
    ratios = np.array([r["rate"] / r["rate_ref"] for r in rr])
    rest = d["results"][0]["ivdd"]
    rows.append((d["variant"], d["corner"], d["temp"], d["S"], ratios.min(), ratios.max(), rest))
print("variant corner  T   S     ratio_min ratio_max  I_rest(nA)")
for r in sorted(rows):
    flag = "" if 0.9 <= r[4] and r[5] <= 1.1 else "  <-- outside +/-10%"
    print(f"{r[0]:4s} {r[1]:8s} {r[2]:3d} {r[3]:6.0f}  {r[4]:8.3f} {r[5]:8.3f}  {r[6]*1e9:9.1f}{flag}")
