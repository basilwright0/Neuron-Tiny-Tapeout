"""Bit-exact Python port of rtl/digital_lif.v (one call = one update tick)."""
from dataclasses import dataclass


@dataclass
class LifParams:
    el: int = 300
    vth: int = 600
    vrst: int = 300
    w: int = 20
    shift: int = 4
    refr: int = 2
    width: int = 12


def lif_step(v, ref, inp, p: LifParams):
    """Return (v_next, ref_next, spike)."""
    if ref > 0:
        return p.vrst, ref - 1, 0
    leak = (p.el - v) >> p.shift          # Python >> floors, same as Verilog >>>
    s = v + leak + (p.w if inp else 0)
    s = max(0, min((1 << p.width) - 1, s))
    if s >= p.vth:
        return p.vrst, p.refr, 1
    return s, 0, 0


def lif_run(inputs, p: LifParams, v0=None):
    """inputs: iterable of 0/1 per tick. Returns (V list after each tick, spike list)."""
    v = p.el if v0 is None else v0
    ref = 0
    vs, sp = [], []
    for inp in inputs:
        v, ref, s = lif_step(v, ref, inp, p)
        vs.append(v)
        sp.append(s)
    return vs, sp
