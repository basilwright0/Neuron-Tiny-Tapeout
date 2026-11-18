"""cocotb tests for the bit-serial digital LIF inside neuron_ctrl (rev C).

Ticks come from ui_in[7] (a tick generator here, PIO on the board); the
spike is observed on uio[6] (OUT_MUX = 0).
1. Tick-by-tick V trajectory vs the bit-exact Python port (DC and pulse input).
2. Firing rate vs input: port (exact), uio[6] pin count (exact) and
   model/reference.py LIF (qualitative: same rheobase side, monotonic, <15 %).
"""
import math
import os
import random
import sys

import numpy as np
import cocotb
from cocotb.triggers import ClockCycles, FallingEdge

from nc_driver import setup, wr, ns, stop_task, CLK_NS
from regmap import A, clkd, lif_sr
from lif_model import LifParams, lif_run, lif_step

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
from reference import LIF  # noqa: E402

U = lambda s: int(s.value)  # noqa: E731
TICK_CLK = 64                # clk per tick (update takes <= 46 clk at W=12)


class LifMonitor:
    """At every accepted tick record V before the update and the input bit."""

    def __init__(self, dut):
        self.lif = dut.u_ctrl.u_lif
        self.dut = dut
        self.v_before, self.inputs = [], []
        self.spikes = self.ticks = self.dropped = 0
        self.run = True

    async def loop(self):
        lif = self.lif
        while self.run:
            await FallingEdge(self.dut.clk)
            if U(lif.spike):
                self.spikes += 1
            if U(lif.en) and U(lif.en_q) and U(lif.tick):
                if U(lif.st) != 0:
                    self.dropped += 1
                    continue
                self.ticks += 1
                self.v_before.append(U(lif.v))
                self.inputs.append(U(lif.dc) | U(lif.pending) | U(lif.in_ev))


class TickGen:
    """Square wave on ui_in[7], period TICK_CLK clk, phase not aligned to clk."""

    def __init__(self, pins, period_clk=TICK_CLK):
        self.pins, self.half = pins, period_clk * CLK_NS / 2.0
        self.task = cocotb.start_soon(self.loop())

    async def loop(self):
        await ns(37.0)
        while True:
            self.pins.set_ui(7, 1)
            await ns(self.half)
            self.pins.set_ui(7, 0)
            await ns(self.half)

    def stop(self):
        stop_task(self.task)
        self.pins.set_ui(7, 0)


class PinCounter:
    """Counts rising edges on uio_out[6] (digital LIF spike pin)."""

    def __init__(self, dut):
        self.dut, self.n = dut, 0
        self.task = cocotb.start_soon(self.loop())

    async def loop(self):
        last = 0
        while True:
            await FallingEdge(self.dut.clk)
            b = (U(self.dut.uio_out) >> 6) & 1
            self.n += b & ~last & 1
            last = b

    def stop(self):
        stop_task(self.task)


def codes(p: LifParams):
    assert p.el % 16 == 0 and p.vth % 16 == 0 and p.vrst % 16 == 0
    return p.el >> 4, p.vth >> 4, p.vrst >> 4


async def configure(dut, pins, p, en=1, src=2):
    """Parameters are written only while LIF_EN = 0 (quasi-static contract)."""
    el, vth, vrst = codes(p)
    await wr(dut, pins, A["CLKD"], clkd(lif_en=0, lif_src=src))
    await wr(dut, pins, A["LIF_SR"], lif_sr(shift=p.shift, refr=p.refr))
    await wr(dut, pins, A["LIF_EL"], el)
    await wr(dut, pins, A["LIF_VTH"], vth)
    await wr(dut, pins, A["LIF_VRST"], vrst)
    await wr(dut, pins, A["LIF_W"], p.w)
    await wr(dut, pins, A["CLKD"], clkd(lif_en=en, lif_src=src))


def check_trajectory(mon, p):
    n = len(mon.v_before)
    assert mon.dropped == 0, "ticks dropped while busy"
    assert mon.v_before[0] == p.el
    vs, sp = lif_run(mon.inputs[:n - 1], p, v0=mon.v_before[0])
    assert vs == mon.v_before[1:], next(i for i in range(n - 1) if vs[i] != mon.v_before[i + 1])
    return n, sum(sp)


@cocotb.test()
async def test_lif_trajectory_dc(dut):
    pins = await setup(dut)
    p = LifParams(el=304, vth=608, vrst=256, w=27, shift=4, refr=3)
    mon = LifMonitor(dut)
    cocotb.start_soon(mon.loop())
    await configure(dut, pins, p, src=2)
    tg = TickGen(pins)
    pc = PinCounter(dut)
    await ClockCycles(dut.clk, TICK_CLK * 300)
    mon.run = False
    tg.stop()
    await ClockCycles(dut.clk, 60)
    pc.stop()
    n, nsp = check_trajectory(mon, p)
    assert n > 250 and nsp >= 5, (n, nsp)
    assert pc.n == mon.spikes, "uio[6] spike count"
    dut._log.info(f"DC trajectory: {n} ticks, {nsp} spikes, bit-exact")


@cocotb.test()
async def test_lif_trajectory_pulses(dut):
    """Input pulses on ui_in[3] (stimulus A), weight added once per pulse."""
    pins = await setup(dut)
    rng = random.Random(7)
    p = LifParams(el=192, vth=640, vrst=160, w=230, shift=3, refr=2)
    mon = LifMonitor(dut)
    cocotb.start_soon(mon.loop())
    await configure(dut, pins, p, src=0)
    tg = TickGen(pins)
    npulse = 30
    for _ in range(npulse):
        await ns(rng.uniform(13000, 22000))           # >= 2 ticks apart
        await pins.ui_pulse(3, rng.uniform(150, 400))
    await ns(15000)
    mon.run = False
    tg.stop()
    n, nsp = check_trajectory(mon, p)
    assert sum(mon.inputs) == npulse, (sum(mon.inputs), npulse)
    assert nsp >= 2, nsp
    # single-stepping: each ui_in[7] edge runs exactly one update (bit-exact)
    lif = dut.u_ctrl.u_lif
    for k in range(6):
        await ClockCycles(dut.clk, 60)
        v0, r0 = U(lif.v), U(lif.ref_cnt)
        await pins.ui_pulse(3, 300)
        await ns(1000)
        await pins.ui_pulse(7, 400)
        await ClockCycles(dut.clk, 60)
        vn, rn, _ = lif_step(v0, r0, 1, p)
        assert (U(lif.v), U(lif.ref_cnt)) == (vn, rn), (k, v0, r0)
    dut._log.info(f"pulse trajectory: {n} ticks, {npulse} inputs, {nsp} spikes")


@cocotb.test()
async def test_lif_rate_vs_input(dut):
    pins = await setup(dut)
    base = dict(el=304, vth=608, vrst=304, shift=4, refr=3)
    a = 1.0 - 2.0 ** -base["shift"]
    tau = -1.0 / math.log(a)                        # in ticks
    rows = []
    for w in [5, 15, 24, 30, 40, 60, 90]:
        p = LifParams(w=w, **base)
        mon = LifMonitor(dut)
        cocotb.start_soon(mon.loop())
        await configure(dut, pins, p, src=2)
        pc = PinCounter(dut)
        tg = TickGen(pins)
        await ClockCycles(dut.clk, TICK_CLK * 500)
        tg.stop()
        await ClockCycles(dut.clk, 60)
        await wr(dut, pins, A["CLKD"], clkd(lif_en=0, lif_src=2))
        mon.run = False
        pc.stop()
        ticks = mon.ticks
        _, sp = lif_run([1] * ticks, p)
        ref = LIF(C=tau, gL=1.0, EL=p.el, Vth=p.vth, Vreset=p.vrst, t_ref=float(p.refr))
        _, rsp = ref.simulate(np.full(ticks, w * 2.0 ** p.shift), dt=1.0)
        rows.append((w, ticks, mon.spikes, sum(sp), pc.n, len(rsp)))
        dut._log.info(f"w={w:3d} ticks={ticks} rtl={mon.spikes} port={sum(sp)} "
                      f"pin={pc.n} reference={len(rsp)}")
        assert mon.dropped == 0
        assert mon.spikes == sum(sp), "RTL vs Python port"
        assert pc.n == mon.spikes, "uio[6] pin count vs observed spikes"
    rtl = [r[2] / r[1] for r in rows]
    refr = [r[5] / r[1] for r in rows]
    assert all(rtl[i] <= rtl[i + 1] for i in range(len(rtl) - 1)), "rate monotonic in input"
    for (w, _, s, _, _, rs), r1, r2 in zip(rows, rtl, refr):
        if w <= 15:
            assert s == 0 and rs == 0, "both silent below rheobase"
        if w >= 30:
            assert abs(r1 - r2) / r2 < 0.15, f"w={w}: rate {r1:.4f} vs ref {r2:.4f}"
