"""Effective compartment capacitance, schematic vs post-layout (PEX incl. device junctions).

usage: python3 sim/tb/dendrite/tb_cnode.py [pex]
hold = 1 (leak, axial, plateau outputs disconnected), then a 20 pA step into vs, d1, d2 in turn for 200 us:
C = I * dt / dV.
"""
import sys
sys.path.insert(0, "/work/sim/tb/dendrite")
from dcommon import *  # noqa
PEX = "pex" in sys.argv[1:]
if PEX:
    sys.argv = ["tb_synapse.py", "typical", "27", "pex"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("ts", "/work/sim/tb/dendrite/tb_synapse.py")
    src = open("/work/sim/tb/dendrite/tb_synapse.py").read()
    src = src[:src.index("IW, TW, TI, T0")]          # only the helpers (pex_dut, dut_cells)
    g = {}
    exec(compile(src, "ts", "exec"), g)
    CELLS, DUTL = g["dut_cells"]()
else:
    CELLS, DUTL = cells(), DUT
vsrc = cal_vsrc("typical", 27)
out = []
for node in ("vs", "d1", "d2"):
    body = f"""{CELLS}
{bias(vsrc=1.4, pl_en=0, hold=1)}
Iinj vdd {node} pwl(0 0 100u 0 100.1u 20p)
{DUTL}
"""
    r = run(deck(body, "tran 1u 400u", [f"v({node})"]), f"dendrite/cnode_{'pex' if PEX else 'sch'}_{node}")
    t, v = r["_x"], r[f"v({node})"]
    dv = np.interp(350e-6, t, v) - np.interp(150e-6, t, v)
    out.append(f"{node}: C = {20e-12 * 200e-6 / dv * 1e15:.1f} fF")
print(("PEX " if PEX else "schematic ") + ", ".join(out))
