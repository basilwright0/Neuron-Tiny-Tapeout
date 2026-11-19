"""Write pin_order.cfg and config_fp.json for the tile floorplan (rev E).

Edges:
  N  TT pins uio_out/uo_out/ui_in, tile west->east order (tile pins are directly above)
  E  rst_n, clk (tile pins just east of the macro); uio_oe/uio_in parked here, unrouted
     (top level drives uio_oe with tie-high cells next to the tile pins; uio_in is unused),
     and the cfg_out bits of trim nibbles without storage (constant 0, left unconnected)
  W  lines into the neuron array (directly west): spikes, probe row/column lines and
     vm/vr tap, rt_out, the in-array trim nibbles
  S  bottom band, west -> east: leak-tau trims (TE strip), GRP_EN, D1 lines (PLATEAU_EN,
     D1_CHAIN, D1_BSEL, D1 trims, probe_sel_d1), probe_sub_raw (D1 and AdEx), probe_sel_adex,
     then the bias_b1 lines in bias_b1 port order (rtl/nc_bias_ports.vh)
Trim nibble -> block comes from floorplan/floorplan.py TRIM_NIBBLES and must match TRIM_MASK.
Usage (container, in rtl/librelane): python3 mkpins.py
"""
import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NTRIM = 16
TRIM_MASK = 0xC1FD   # rtl/neuron_ctrl.v default
CFG_TRIM = 7         # rtl/nc_regmap.vh: cfg_out = {trims, D1_BSEL, D1_CHAIN, PLATEAU_EN, GRP_EN[3:0]}

spec = importlib.util.spec_from_file_location("floorplan", os.path.join(HERE, "..", "..", "floorplan", "floorplan.py"))
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)
TN = fp.TRIM_NIBBLES
assert sum(1 << n for n in TN.values()) == TRIM_MASK, "floorplan TRIM_NIBBLES != TRIM_MASK"
nib_d1 = sorted(n for k, n in TN.items() if k.startswith("D1."))
nib_tau = sorted(n for k, n in TN.items() if k.endswith(".TAU"))
nib_arr = sorted(n for n in TN.values() if n not in nib_d1 + nib_tau)
nib_off = [n for n in range(NTRIM) if not (TRIM_MASK >> n) & 1]


def bits(name, hi, lo):
    step = -1 if hi >= lo else 1
    return [rf"{name}\[{i}\]" for i in range(hi, lo + step, step)]


def nib(n):
    return bits("cfg_out", CFG_TRIM + 4 * n, CFG_TRIM + 4 * n + 3)


with open(os.path.join(HERE, "..", "nc_bias_ports.vh")) as f:
    BIAS = re.findall(r"output wire (\w+),", f.read())

N = bits("uio_out", 7, 0) + bits("uo_out", 7, 0) + bits("ui_in", 7, 0)
E = (bits("uio_in", 7, 0) + bits("uio_oe", 7, 0) + sum((nib(n) for n in nib_off), [])
     + ["rst_n", "clk"])                                  # E/W lists bottom->top: clk/rst_n at the top
W = (bits("spk_in", 0, 15) + bits("probe_rsel", 0, 3) + bits("probe_en_c", 0, 3)
     + ["probe_sub", "probe_sub_b"] + bits("rt_out", 0, 3) + sum((nib(n) for n in nib_arr), []))
S = (sum((nib(n) for n in nib_tau), [])                   # TE strip (west end of the band)
     + bits("cfg_out", 0, 3)                              # GRP_EN
     + bits("cfg_out", 4, 6) + sum((nib(n) for n in nib_d1), []) + ["probe_sel_d1"]
     + bits("probe_sub_raw", 0, 1) + ["probe_sel_adex"]
     + BIAS)

allp = N + E + W + S
assert len(allp) == len(set(allp))
assert len([p for p in allp if p.startswith("cfg_out")]) == CFG_TRIM + 4 * NTRIM

with open(os.path.join(HERE, "pin_order.cfg"), "w", newline="\n") as f:
    for side, pins in (("#N", N), ("#E", E), ("#S", S), ("#W", W)):
        f.write(side + "\n" + "\n".join(pins) + "\n")

c = json.load(open(os.path.join(HERE, "config.json")))
c["IO_PIN_ORDER_CFG"] = "dir::pin_order.cfg"
with open(os.path.join(HERE, "config_fp.json"), "w", newline="\n") as f:
    json.dump(c, f, indent=2)
print({k: len(v) for k, v in dict(N=N, E=E, S=S, W=W).items()},
      f"trims: array {nib_arr}, D1 {nib_d1}, tau {nib_tau}, parked {nib_off}; {len(BIAS)} bias lines")
