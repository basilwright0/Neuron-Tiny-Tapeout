"""Deck-generation check of every full-chip PEX bench on the current netlist (no ngspice run), for the smoke batch.

  python3 sim/tb/top/deckcheck.py          (in the EDA container, after ext_rc.tcl)

Each bench runs with --deck (topbench.go writes the deck to $TOP_DECK_DIR and stops); topbench.sch_bias is replaced by
dummy values so no schematic op is needed. Catches node-name / netlist problems (KeyError, missing victims) in
seconds. Prints one line per bench (OK + deck size, or the exception) and per deck the number of sources / switches.
"""
import os
import runpy
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("TOP_DECK_DIR", str(HERE.parents[2] / "sim/results/top/decks"))
sys.argv = [sys.argv[0], "--deck"]
sys.path.insert(0, str(HERE))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402

B.sch_bias = lambda S, codes=None, ib_x2=0: {n: 0.5 for n in B.PRE_LINES}
JOBS = [("tb_top_kick.py", ["typical", "27"]), ("tb_top_probe.py", ["step", "typical", "27"]),
        ("tb_top_bias.py", ["dc", "100"]), ("tb_top_bias.py", ["spk", "off"]), ("tb_top_bias.py", ["step", "10"]),
        ("tb_top_gndchk.py", ["100"]), ("tb_top_s10k.py", ["typical", "27"])]
if T.bay():
    JOBS += [("tb_top_bay.py", ["fire", "typical", "27"]), ("tb_top_bay.py", ["probe", "typical", "27"]),
             ("tb_top_bias.py#nobay", ["step", "10"])]
bad = 0
for f, args in JOBS:
    name = f
    if f.endswith("#nobay"):
        f = f.split("#")[0]
        os.environ["NOBAY"] = "1"
    sys.argv = [str(HERE / f)] + args + ["--deck"]
    try:
        runpy.run_path(str(HERE / f), run_name="__main__")
        print(f"{name} {args}: finished without writing a deck?")
    except SystemExit as e:
        print(f"{name} {args}: exit {e.code}")
        bad += e.code not in (0, None)
    except Exception:
        bad += 1
        print(f"{name} {args}: FAILED")
        traceback.print_exc()
    os.environ.pop("NOBAY", None)
    T._cache.pop("pterms", None)
dd = Path(os.environ["TOP_DECK_DIR"])
for d in sorted(dd.glob("*.cir")):
    txt = d.read_text().splitlines()
    print(f"  {d.name}: {len(txt)} lines, {sum(l.startswith('Spre') for l in txt)} precond switches, "
          f"{sum(l.startswith(('I', 'Vf')) for l in txt)} I/Vf sources")
print(f"deckcheck: {bad} failed")
sys.exit(1 if bad else 0)
