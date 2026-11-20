"""Top-level assembly configuration for tt_um_basilwright0_analog_neurons (plain Python, no dependencies).

Block geometry comes from floorplan/floorplan.py (single source of truth). This file says which layout
and LVS netlist each block uses, whether it is FINAL (real GDS) or a PLACEHOLDER (pins only, black box in
LVS), and how every block pin connects (net table `nets()`).

Block swap: when an owner delivers a final block, set FINAL[<cell>] = True (or leave it True), make sure
the GDS / LVS netlist paths below point at it, and re-run `bash layout/top/build.sh`. Pin positions are
read from the GDS labels, so moved pins are re-routed automatically.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location("floorplan", ROOT / "floorplan" / "floorplan.py")
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)

TOP = "tt_um_basilwright0_analog_neurons"
WORK = HERE / "work"

# ------------------------------------------------------------------ block library
# cell -> dict(gds, lvs (reference netlist with the .subckt), prefix for subcell names, final flag)
LIB = {
    "neuron_ctrl": dict(gds="macros/neuron_ctrl/neuron_ctrl.gds", lvs="macros/neuron_ctrl/neuron_ctrl.spice",
                        prefix=None, final=True, kind="macro"),
    "bias_b1":     dict(gds="layout/bias/out/bias_b1.gds", lvs="layout/bias/out/ref_bias_b1.spice",
                        prefix="b1_", final=True),
    "r1_ua1":      dict(gds="layout/readout/out/r1_ua1.gds", lvs="layout/readout/r1_corner_lvs.spice",
                        prefix="r1_", final=True, sub="r1_corner"),
    "trim_tau4":   dict(gds="layout/slot/out/trim_tau4.gds", lvs="layout/slot/trim_tau4_lvs.spice",
                        prefix="tt_", final=True),
    "dend_d1":     dict(gds="layout/dendrite/out/dend_d1.gds", lvs="layout/dendrite/dend_d1_lvs.spice",
                        prefix="d1_", final=True, size=(70.0, 104.0)),
    "adex_a1":     dict(gds="layout/tier2/out/adex_a1.gds", lvs="layout/tier2/adex_a1_lvs.spice",
                        prefix="ax_", final=True, size=(38.0, 73.0)),
}
_SLOT_FINAL = {"slot_ah": True, "slot_ah_h": True, "slot_ah_p": True, "slot_ah_f": True, "slot_cmp_h": True,
               "slot_ah_50": True, "slot_ah_800": True, "slot_ref": True, "slot_dummy": True}
for _i, (_c, _f) in enumerate(_SLOT_FINAL.items()):
    LIB[_c] = dict(gds=f"layout/slot/out/{_c}.gds", lvs=f"layout/slot/{_c}_lvs.spice", prefix=f"s{_i}_",
                   final=_f, size=(fp.SLOT_W, fp.SLOT_H * (2 if _c == fp.SLOT_CELL["CMP"] else 1)))
# Placeholder pin overrides (cell-local x ranges moved by dx; pins moved to a new edge position). Empty: the
# D1 placeholder now uses the pins of the 70 x 104 D1 GDS as drawn by the D1 track (2026-11-19 16:12).
PH_SHIFT = {}
PH_MOVE = {}
# CMP slot gap trim: True while slot_cmp_h has its in-slot trim (nibble 6; since 2026-11-20 the 28 x 87 double
# slot). False (with the trimless slot_cmp_h_notrim): cfg_out[31..34] (CMP.VTH) are left unconnected at the
# top level (macro / TRIM_MASK unchanged).
CMP_TRIM = True
# aux column lines with no user: they float (connected only by abutment). Column 3 carries vth_cmp (CMP).
FLOAT_AUX = {"aux1"}
# Ports that are internal test nodes (left unconnected at the top level)
OPEN_PORTS = {"vm", "vw", "vs", "d1", "d2", "la1", "dl1", "la2", "dl2"}

# ------------------------------------------------------------------ instances: name -> (cell, x, y)
def instances():
    I = {"ctrl": ("neuron_ctrl", fp.MACRO_X, fp.MACRO_Y),
         "b1": ("bias_b1", fp.B1_BOX[0], fp.B1_BOX[1]),
         "r1": ("r1_ua1", 262.0, 0.0),
         # D1 / AdEx are nudged so their 0.7 um pin pitch lands on the router grid (geom.OX + 0.14 i)
         "d1": ("dend_d1", fp.BLOCKS["D1 dendrite"][0] - 0.03, fp.BLOCKS["D1 dendrite"][1]),
         "ax": ("adex_a1", fp.BLOCKS["A1 AdEx"][0] + 0.08, fp.BLOCKS["A1 AdEx"][1]),
         "tau0": ("trim_tau4", *fp.BLOCKS[fp.TAU_COLS[0]][:2]),
         "tau2": ("trim_tau4", *fp.BLOCKS[fp.TAU_COLS[2]][:2])}
    for (r, c), n in fp.slot_map().items():          # instance named by map position; CMP: s13 at (0,3)
        x, y = fp.cell_box((r, c))[:2]
        I[f"s{r}{c}"] = (fp.slot_cell(n), x, y)
    return I


# ------------------------------------------------------------------ connectivity
COLUMN_NETS = ["vbp_syn", "el", "vbn_leak", "vsrc", "vbp_st", "vbn_prb", "vbn_ref", "vreset", "abus"]
RT = ["sta", "stb", "hold", "mreset"]          # rt_out[0..3]


def nib_bits(n):
    return [f"cfg_out[{7 + 4 * n + j}]" for j in range(4)]


def nets():
    """Return {net: [(inst, pin), ...]} for every routed / connected signal (power excluded).
    Slot row-band and column connections are included (they are drawn by the array generator)."""
    N = {}
    def add(net, inst, pin):
        N.setdefault(net, []).append((inst, pin))
    grid = fp.slot_map()
    tn = fp.TRIM_NIBBLES
    # ---- neuron array
    for (r, c), name in grid.items():
        s = f"s{r}{c}"
        for ln in COLUMN_NETS:
            add(ln, s, ln)
        add(f"en_c{c}", s, "en")
        add(f"aux{c}", s, "aux")
        if name == "REF":
            add(f"probe_rsel[{r}]", s, "rsel"); add("probe_sub", s, "sub")
            continue
        for k, rt in enumerate(RT):
            add(f"rt_out[{k}]", s, rt)
        if name == "DUMMY":
            continue
        add(f"probe_rsel[{r}]", s, "rsel"); add("probe_sub", s, "sub"); add("probe_sub_b", s, "sub_b")
        add(f"spk_in[{fp.SPIKE_CH[name]}]", s, "spk")
        key = f"{name}.VTH"
        if key in tn and (name != "CMP" or CMP_TRIM):
            for j, b in enumerate(nib_bits(tn[key])):
                add(b, s, f"t{j}")
    # ---- macro (W, S edges; N edge to TT pins)
    for c in range(4):
        add(f"en_c{c}", "ctrl", f"probe_en_c[{c}]")
    for r in range(4):
        add(f"probe_rsel[{r}]", "ctrl", f"probe_rsel[{r}]")
    add("probe_sub", "ctrl", "probe_sub"); add("probe_sub_b", "ctrl", "probe_sub_b")
    for k in range(4):
        add(f"rt_out[{k}]", "ctrl", f"rt_out[{k}]")
    for ch in range(16):
        add(f"spk_in[{ch}]", "ctrl", f"spk_in[{ch}]")
    for key, n in tn.items():
        if key == "CMP.VTH" and not CMP_TRIM:
            continue
        for b in nib_bits(n):
            add(b, "ctrl", b)
    for io in ("uio_out", "uo_out", "ui_in"):
        for i in range(8):
            add(f"{io}[{i}]", "ctrl", f"{io}[{i}]"); add(f"{io}[{i}]", "TT", f"{io}[{i}]")
    for p in ("rst_n", "clk"):
        add(p, "ctrl", p); add(p, "TT", p)
    # ---- B1 codes / modes <-> macro S edge
    for d in ("i0", "i1", "i2", "i3", "i4", "r0", "r1", "r2"):
        for j in range(5):
            add(f"{d}_b{j}", "ctrl", f"{d}_b{j}"); add(f"{d}_b{j}", "b1", f"{d}_b{j}")
    for j in range(6):
        add(f"v0_c{j}", "ctrl", f"v0_c{j}"); add(f"v0_c{j}", "b1", f"v0_c{j}")
    for m in ("ua0_s0", "ua0_s1", "ua0_stim", "ua0_int", "bias_en", "ib_x2"):
        add(m, "ctrl", m); add(m, "b1", m)
    # ---- B1 analog outputs
    for ln in ("vbp_syn", "el", "vbn_leak", "vbp_st", "vbn_prb", "vbn_ref"):
        add(ln, "b1", ln)
    cmp_col = fp.grid_col(grid, "CMP")
    add(f"aux{cmp_col}", "b1", "vth_cmp")        # CMP threshold rides on its column's aux line (column 3)
    add("vbn_ax", "b1", "vbn_ax"); add("vbp_w", "b1", "vbp_w")
    add("vth_ref", "b1", "vth_ref"); add("vth_ref", "r1", "vth_ref")       # abutting pins (notch top)
    add("vreset_src", "b1", "vreset_src"); add("vreset_src", "r1", "vrin")
    add("ib_r1", "b1", "ib_r1"); add("ib_r1", "r1", "ibias")
    add("ua[0]", "b1", "ua0"); add("ua[0]", "TT", "ua[0]")
    add("ua[1]", "r1", "pad"); add("ua[1]", "TT", "ua[1]")
    # ---- R1 feed-throughs
    for ln in ("vreset", "vsrc", "abus"):
        add(ln, "r1", ln)
    add("en_b", "r1", "en_b")
    # ---- tau-trim cells (rev B, 2026-11-20): aux of column 0 / 2, codes from nibbles 14 / 15; reference = B1's
    #      vbn_leak (mirrored on vss: the cells' p-tap ring, hooked up in geom.blocks_power)
    for c, inst in ((0, "tau0"), (2, "tau2")):
        add(f"aux{c}", inst, "aux")
        add("vbn_leak", inst, "vbn_leak")
        pn = [n for n, cc in fp.el_columns().items() if cc == c][0]
        for j, b in enumerate(nib_bits(tn[f"{pn}.TAU"])):
            add(b, inst, f"c{j}")
    # ---- D1
    for ln in ("vbp_syn", "el", "vsrc", "vreset", "vbn_leak", "vbp_st", "vbn_ref", "vbn_prb", "vbn_ax", "abus"):
        add(ln, "d1", ln)
    add("vsrc", "d1", "vsrcp")
    for k, rt in enumerate(RT):
        add(f"rt_out[{k}]", "d1", rt)
    add("spk_in[13]", "d1", "spk")
    add("cfg_out[4]", "d1", "pl_en"); add("cfg_out[4]", "ctrl", "cfg_out[4]")
    add("cfg_out[5]", "d1", "chain"); add("cfg_out[5]", "ctrl", "cfg_out[5]")
    add("cfg_out[6]", "d1", "d1_bsel"); add("cfg_out[6]", "ctrl", "cfg_out[6]")
    for j, b in enumerate(nib_bits(tn["D1.PLAT1"])):
        add(b, "d1", f"ta{j}")
    for j, b in enumerate(nib_bits(tn["D1.PLAT2"])):
        add(b, "d1", f"tb{j}")
    add("probe_sel_d1", "d1", "en"); add("probe_sel_d1", "ctrl", "probe_sel_d1")
    for k in range(3):
        add(f"d1_sel{k}", "d1", f"sel{k}")
    # ---- AdEx
    for ln in ("vbp_syn", "el", "vsrc", "vreset", "vbn_leak", "vbp_st", "vbn_ref", "vbn_prb", "vbp_w", "abus"):
        add(ln, "ax", ln)
    for k, rt in enumerate(RT):
        add(f"rt_out[{k}]", "ax", rt)
    add("spk_in[3]", "ax", "spk")
    add("probe_sel_adex", "ax", "sel_adex"); add("probe_sel_adex", "ax", "en"); add("probe_sel_adex", "ctrl", "probe_sel_adex")
    add("probe_sub_raw[0]", "ax", "sub0"); add("probe_sub_raw[0]", "ctrl", "probe_sub_raw[0]")
    add("probe_sub_raw[1]", "ax", "sub1"); add("probe_sub_raw[1]", "ctrl", "probe_sub_raw[1]")
    # ---- glue logic (std cells, layout/top): en_b = NOR(en_c0..3, sel_d1, sel_adex); D1 tap decode
    for c in range(4):
        add(f"en_c{c}", "g_or", f"A{c + 1}")
    add("g_any", "g_or", "Z"); add("g_any", "g_enb", "A1")
    add("probe_sel_d1", "g_enb", "A2"); add("probe_sel_adex", "g_enb", "A3"); add("en_b", "g_enb", "ZN")
    add("probe_sel_d1", "g_in", "I"); add("g_nsel", "g_in", "ZN")
    add("probe_sub_raw[0]", "g_i0", "I"); add("g_ns0", "g_i0", "ZN")
    add("probe_sub_raw[1]", "g_i1", "I"); add("g_ns1", "g_i1", "ZN")
    for k, (a2, a3) in enumerate([("probe_sub_raw[1]", "probe_sub_raw[0]"), ("probe_sub_raw[1]", "g_ns0"),
                                  ("g_ns1", "probe_sub_raw[0]")]):
        g = f"g_s{k}"
        add("g_nsel", g, "A1"); add(a2, g, "A2"); add(a3, g, "A3"); add(f"d1_sel{k}", g, "ZN")
    # ---- uio_oe tie-high cells
    for i in range(8):
        add(f"uio_oe[{i}]", f"tie{i}", "Z"); add(f"uio_oe[{i}]", "TT", f"uio_oe[{i}]")
    return N


# std cells: inst -> (cell, x, y)  (lower-left, R0); widths from the PDK LEF
SC = "gf180mcu_fd_sc_mcu7t5v0__"
SC_W = {"tieh": 2.24, "filltie": 1.12, "inv_1": 2.24, "nor3_1": 4.48, "or4_1": 6.72}
SC_H = 3.92


def std_cells():
    S = {}
    # tie row: tieh with its Z pin (x 1.22-1.58) under the uio_oe pin, filltie on its east side
    for i in range(8):
        px = fp.PINS_TOP[f"uio_oe[{i}]"]
        x = round(round((px - 1.40) / 0.005) * 0.005, 3)
        S[f"tie{i}"] = ("tieh", x, fp.TIE_ROW_Y)
        S[f"tap{i}"] = ("filltie", x + SC_W["tieh"], fp.TIE_ROW_Y)
    # glue row (west -> east)
    x, y = fp.GLUE_ROW
    for inst, cell in [("gtap0", "filltie"), ("g_or", "or4_1"), ("g_enb", "nor3_1"), ("g_in", "inv_1"),
                       ("g_i0", "inv_1"), ("g_i1", "inv_1"), ("g_s0", "nor3_1"), ("g_s1", "nor3_1"),
                       ("g_s2", "nor3_1"), ("gtap1", "filltie")]:
        S[inst] = (cell, round(x, 3), y)
        x += SC_W[cell]
    return S


if __name__ == "__main__":
    N = nets()
    print(len(N), "nets;", sum(len(v) for v in N.values()), "pin connections")
    I = instances()
    print(len(I), "block instances;", len(std_cells()), "std cells")
    for n, v in sorted(N.items()):
        if len(v) < 2:
            print("single-pin net:", n, v)
