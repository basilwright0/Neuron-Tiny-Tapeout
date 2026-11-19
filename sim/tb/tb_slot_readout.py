"""Readout settling with the slot's two-switch probe tap (prb_tap in cells/neuron/slot.spice).

Runs sim/tb/tb_readout.py unchanged except that every channel (selected and the 31 deselected ones)
is a prb_tap: follower + row-select switch XSW + sub-select switch XSB in series (the row x column
probe select of the 19-track band). Selected channel: sel = sb = 1; deselected: both 0.
usage: python3 sim/tb/tb_slot_readout.py [same flags as tb_readout.py, 'slot' implied]
Results carry the tag '_slot_tap' (sim/results/ro_*_slot_tap_*).
"""
import sys
from pathlib import Path

src = Path("/work/sim/tb/tb_readout.py").read_text()
rep = [
    ('f"Xo{k} vx{k} abus 0 0 vbn vdd 0 prb_nsf{FPAR}', 'f"Xo{k} vx{k} abus 0 0 0 vbn vdd 0 prb_tap{FPAR}'),
    ("include('neuron/membrane.spice', 'readout/readout.spice')",
     "include('neuron/membrane.spice', 'readout/readout.spice', 'neuron/lif.spice', 'neuron/synapse.spice', "
     "'trim/trim_gap.spice', 'neuron/slot.spice')"),
    ("Xp vm abus en sel vbn vdd 0 prb_nsf{FPAR}", "Xp vm abus en sel sel vbn vdd 0 prb_tap{FPAR}"),
    ('TAG = "_slot" if SLOT else ""', 'TAG = "_slot_tap"'),
]
for a, b in rep:
    assert a in src, a
    src = src.replace(a, b)
if "slot" not in sys.argv[1:]:
    sys.argv.append("slot")
sys.argv[0] = "/work/sim/tb/tb_readout.py"
exec(compile(src, "tb_readout.py(prb_tap)", "exec"))
