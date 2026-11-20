"""Write pin_order.cfg and config_fp.json for floorplan v2 (docs/08 Updated Plan.md section 10).

The macro (166 x 166) sits at tile x 170-336, y 151-317. Each edge has 148 pin slots
(Metal2/3 tracks at 1.12 um pitch: slot k at 0.28 + 1.12 k um from the west / south
corner). Pins are put on chosen slots with "$n" virtual-pin spacers, so their positions
follow the blocks they face:
  N  uio_out, uo_out, ui_in, rst_n, clk in tile order, each under its TT tile pin where
     that pin is above the macro (uio_out and uo_out[7:3] are west of the macro: packed
     at the west end); clk / rst_n at the east end
  E  parked, unrouted: uio_in (unused), uio_oe (top level ties high next to the tile pins),
     the cfg_out bits of trim nibbles without storage (constant 0)
  W  neuron-array lines only, above the AdEx column (tile y > 215): array spikes, probe
     row/column lines and vm/vr tap, rt_out, in-array trim nibbles
  S  west -> east: AdEx (spk_in[3], probe_sel_adex), probe_sub_raw (AdEx + D1), D1 lines
     (spk_in[13], PLATEAU_EN, D1_CHAIN, D1_BSEL, D1 trims, probe_sel_d1), GRP_EN, leak-tau
     trims (TE cells); then the bias_b1 code lines in port order under B1's code inputs
     (tile x ~180-281) and the ua0 / bias_en / ib_x2 mode lines at the east end (tile x ~312+)
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
MX, MY, SIZE = 170.0, 151.0, 166.0   # macro origin in the tile, side (config.json DIE_AREA)
NSLOT, P0, PITCH = 148, 0.28, 1.12   # pin slots per edge (from the io placer log)
ADEX_TOP = 215.0                     # tile y of the AdEx column's top (west of the macro)
MASTER = ["ua0_s0", "ua0_s1", "ua0_stim", "ua0_int", "bias_en", "ib_x2"]

spec = importlib.util.spec_from_file_location("floorplan", os.path.join(HERE, "..", "..", "floorplan", "floorplan.py"))
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)
TN = fp.TRIM_NIBBLES
assert sum(1 << n for n in TN.values()) == TRIM_MASK, "floorplan TRIM_NIBBLES != TRIM_MASK"
nib_d1 = sorted(n for k, n in TN.items() if k.startswith("D1."))
nib_tau = sorted(n for k, n in TN.items() if k.endswith(".TAU"))
nib_arr = sorted(n for n in TN.values() if n not in nib_d1 + nib_tau)
nib_off = [n for n in range(NTRIM) if not (TRIM_MASK >> n) & 1]
OUTSIDE = (fp.SPIKE_CH["ADEX"], fp.SPIKE_CH["D1"])   # spike channels not in the array


def b(name, i):
    return rf"{name}\[{i}\]"


def bits(name, hi, lo):
    step = -1 if hi >= lo else 1
    return [b(name, i) for i in range(hi, lo + step, step)]


def nib(n):
    return bits("cfg_out", CFG_TRIM + 4 * n, CFG_TRIM + 4 * n + 3)


def slot(pos):
    """Nearest slot to a macro-local coordinate (um)."""
    return min(NSLOT - 1, max(0, round((pos - P0) / PITCH)))


def spread(pins, lo, hi):
    """(pin, slot) pairs spreading pins evenly over macro-local span [lo, hi] um."""
    a, z = slot(lo), slot(hi)
    n = len(pins)
    return [(p, a + (round(i * (z - a) / (n - 1)) if n > 1 else 0)) for i, p in enumerate(pins)]


def side(pairs, gap=1):
    """Pin list with $n spacers; slots forced increasing by >= gap, in list order."""
    out, last, fixed = [], -gap, []
    for p, k in pairs:
        k = max(k, last + gap)
        fixed.append((p, k))
        last = k
    assert last < NSLOT - 1, f"edge overflow: last slot {last}"
    prev = -1
    for p, k in fixed:
        if k - prev - 1 > 0:
            out.append(f"${k - prev - 1}")
        out.append(p)
        prev = k
    # pad to NSLOT - 1 entries, not NSLOT: io_place.py keeps the "$n" entries when
    # entries == tracks (assertion); with one fewer, tracks_per_pin = 1 from track 0
    if NSLOT - 2 - prev > 0:
        out.append(f"${NSLOT - 2 - prev}")
    return out, [p for p, _ in fixed], dict(fixed)


with open(os.path.join(HERE, "..", "nc_bias_ports.vh")) as f:
    BIAS = re.findall(r"output wire (\w+),", f.read())
CODES = [n for n in BIAS if n not in MASTER]
assert [n for n in BIAS if n in MASTER] == MASTER

# ---- N: under the TT tile pins (floorplan.py PINS_TOP), in tile order
tp = fp.PINS_TOP
west = bits("uio_out", 7, 0) + bits("uo_out", 7, 3)
n_pairs = [(p, 2 * i) for i, p in enumerate(west)]
for name in bits("uo_out", 2, 0) + bits("ui_in", 7, 0) + ["rst_n", "clk"]:
    n_pairs.append((name, slot(tp[name.replace("\\", "")] - MX)))
N, N_pins, N_slot = side(n_pairs, gap=2)

# ---- E: parked
E_pins = bits("uio_in", 7, 0) + bits("uio_oe", 7, 0) + sum((nib(n) for n in nib_off), [])
E = E_pins

# ---- W: array lines, above the AdEx column (bottom -> top)
arr_spk = [b("spk_in", i) for i in range(16) if i not in OUTSIDE]
w_list = (arr_spk + bits("probe_rsel", 0, 3) + bits("probe_en_c", 0, 3) + ["probe_sub", "probe_sub_b"]
          + bits("rt_out", 0, 3) + sum((nib(n) for n in nib_arr), []))
W, W_pins, W_slot = side(spread(w_list, ADEX_TOP + 6 - MY, SIZE - 2))

# ---- S: west -> east
s_west = ([b("spk_in", fp.SPIKE_CH["ADEX"]), "probe_sel_adex"] + bits("probe_sub_raw", 0, 1)
          + [b("spk_in", fp.SPIKE_CH["D1"])] + bits("cfg_out", 4, 6) + sum((nib(n) for n in nib_d1), [])
          + ["probe_sel_d1"] + bits("cfg_out", 0, 3) + sum((nib(n) for n in nib_tau), []))
s_pairs = (spread(s_west, 1, 1 + PITCH * (len(s_west) - 1))
           + spread(CODES, max(180 - MX, 2 + PITCH * len(s_west)), 281 - MX)
           + spread(MASTER, 312 - MX, SIZE - 2))
S, S_pins, S_slot = side(s_pairs)

allp = N_pins + E_pins + W_pins + S_pins
assert len(allp) == len(set(allp))
assert len([p for p in allp if p.startswith("cfg_out")]) == CFG_TRIM + 4 * NTRIM
assert len([p for p in allp if p.startswith("spk_in")]) == 16

with open(os.path.join(HERE, "pin_order.cfg"), "w", newline="\n") as f:
    for s_, pins in (("#N", N), ("#E", E), ("#S", S), ("#W", W)):
        f.write(s_ + "\n" + "\n".join(pins) + "\n")

c = json.load(open(os.path.join(HERE, "config.json")))
c["IO_PIN_ORDER_CFG"] = "dir::pin_order.cfg"
with open(os.path.join(HERE, "config_fp.json"), "w", newline="\n") as f:
    json.dump(c, f, indent=2)


def span(d, origin):
    xs = [origin + P0 + PITCH * k for k in d.values()]
    return f"{min(xs):.1f}-{max(xs):.1f}"


print({k: len(v) for k, v in dict(N=N_pins, E=E_pins, S=S_pins, W=W_pins).items()},
      f"trims: array {nib_arr}, D1 {nib_d1}, tau {nib_tau}, parked {nib_off}; {len(BIAS)} bias lines")
print("tile spans: S west", span({p: S_slot[p] for p in s_west}, MX), "| S codes", span({p: S_slot[p] for p in CODES}, MX),
      "| S master", span({p: S_slot[p] for p in MASTER}, MX), "| W y", span(W_slot, MY),
      "| N clk", span({"c": N_slot["clk"]}, MX), "rst_n", span({"r": N_slot["rst_n"]}, MX))
