"""E2 full-chip droop check (MIL-362): the full-chip transient droops na / nb at ~-60..-70 mV/s at tt/27 and ff/85,
the block PEX at -0.003 / -9 mV/s. DC op of the full chip (E2 released: GRP_EN = 0, probe off) with na forced to
1.2858 V by an ideal source: I(force), and the same with each device / capacitor touching na cut off from na in turn
(its na terminal moved to a dummy node held by its own 1.2858 V source, whose current is reported).
  python3 sim/tb/top/e2_leakchk.py [corner] [T]          (in the EDA container)
Writes sim/results/top/e2_leakchk_<corner>_<T>.txt
"""
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import topbench as B          # noqa: E402
import topnet as T            # noqa: E402

CORNER = sys.argv[1] if len(sys.argv) > 1 else "typical"
TEMP = int(sys.argv[2]) if len(sys.argv) > 2 else 27
VNA = 1.2858
codes = B.op_point(100.0)
body = B.chip(100.0, codes=codes, state_over=T.config(codes=codes, grp_en=0))
NA = T.vnode("e2.na")
L = body.splitlines()
touch = [k for k, l in enumerate(L) if l[:1] in "XDRC" and re.search(r"(^|\s)" + re.escape(NA) + r"(\s|$)", l)]
src = [f"Vfna {NA} 0 {VNA}"]
for j, k in enumerate(touch):                     # every element on na gets its own forcing source
    L[k] = re.sub(r"(\s)" + re.escape(NA) + r"(?=\s|$)", rf"\1naf{j}", L[k])
    src.append(f"Vfn{j} naf{j} 0 {VNA}")
deck = B.deck("\n".join(L + src) + "\n", "op", ["i(vfna)"] + [f"i(vfn{j})" for j in range(len(touch))],
              corner=CORNER, temp=TEMP, opts="gmin=1e-18 abstol=1e-18")
r = B.go(deck, f"e2_leakchk_{CORNER}_{TEMP}")
out = [f"E2 na forced to {VNA} V, full-chip DC op, {CORNER} {TEMP} C (GRP_EN = 0, probe off); current INTO each element "
       f"from na (A; > 0 drains na). C = 217 fF: 1 pA = 4.6 mV/s"]
tot = 0.0
for j, k in enumerate(touch):
    i = -float(r[f"i(vfn{j})"][0])
    tot += i
    out.append(f"  {i:+.3e}  {L[k][:150]}")
out.append(f"  total {tot:+.3e} A -> {tot / 217e-15 * 1e3:+.2f} mV/s")
print("\n".join(out))
(B.OUT / f"e2_leakchk_{CORNER}_{TEMP}.txt").write_text("\n".join(out) + "\n")
