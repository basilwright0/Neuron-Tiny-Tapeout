"""Write pin_order.cfg and config_fp.json for the tile floorplan (docs/06 Floorplan.md).

Macro sits at tile (132, 134). Edges:
  N  TT pins uio_out/uo_out/ui_in, tile west->east order (tile pins are directly above)
  E  rst_n, clk (tile pins just east of the macro); uio_oe/uio_in parked here, unrouted
     (top level drives uio_oe with tie-high cells next to the tile pins; uio_in is unused)
  W  everything the neuron array needs: spikes, probe one-hot, stimulus, trims
     (the neuron array NA sits directly west of the macro)
  S  sc_clk (Tier-2 zone, bottom-left), misc analog bits, bias DAC codes (B1, bottom-right)
Usage (container, in rtl/librelane): python3 mkpins.py
"""
import json

NTRIM = 16


def bits(name, hi, lo):
    step = -1 if hi >= lo else 1
    return [rf"{name}\[{i}\]" for i in range(hi, lo + step, step)]


N = bits("uio_out", 7, 0) + bits("uo_out", 7, 0) + bits("ui_in", 7, 0)
E = bits("uio_in", 7, 0) + bits("uio_oe", 7, 0) + ["rst_n", "clk"]   # E/W list bottom->top: clk/rst_n at the top
W = (bits("spk_in", 0, 15) + bits("probe_sel_onehot", 0, 15) + bits("rt_out", 0, 3)
     + bits("cfg_out", 78, 78 + 4 * NTRIM - 1))
S = ["sc_clk"] + bits("cfg_out", 66, 77) + bits("cfg_out", 65, 0)

with open("pin_order.cfg", "w") as f:
    for side, pins in (("#N", N), ("#E", E), ("#S", S), ("#W", W)):
        f.write(side + "\n" + "\n".join(pins) + "\n")

c = json.load(open("config.json"))
c["IO_PIN_ORDER_CFG"] = "dir::pin_order.cfg"
json.dump(c, open("config_fp.json", "w"), indent=2)
print({k: len(v) for k, v in dict(N=N, E=E, S=S, W=W).items()})
