"""Write a size/density variant of config.json: python3 mkcfg.py <side_um> <density_pct> [period_ns]
-> sweep_s<side>_d<density>[_p<period>].json (same directory, so dir:: paths stay valid)."""
import json, sys
side, dens = float(sys.argv[1]), int(sys.argv[2])
c = json.load(open("config.json"))
c["DIE_AREA"] = [0, 0, side, side]
c["PL_TARGET_DENSITY_PCT"] = dens
name = f"sweep_s{sys.argv[1]}_d{dens}"
if len(sys.argv) > 3:
    c["CLOCK_PERIOD"] = float(sys.argv[3]); name += f"_p{sys.argv[3]}"
json.dump(c, open(name + ".json", "w"), indent=2)
print(name)
