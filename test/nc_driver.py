"""cocotb helpers for neuron_ctrl rev C: clock/reset, pins, SCK/DATA/LOAD writer.

Works with cocotb 1.8 (TT template pin) and cocotb 2.x (container).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles

from regmap import FW, frame

_V2 = int(cocotb.__version__.split(".")[0]) >= 2
CLK_NS = 100  # 10 MHz

SCK, SDI, LOAD = 0, 1, 2


def ps(t_ps):
    t_ps = int(round(t_ps))
    return Timer(t_ps, unit="ps") if _V2 else Timer(t_ps, units="ps")


def ns(t_ns):
    return ps(t_ns * 1000)


class Pins:
    """Keeps the testbench-driven ui_in / spk_in state."""

    def __init__(self, dut):
        self.dut = dut
        self.ui = 0
        self.spk = 0
        dut.ui_in.value = 0
        dut.spk_in.value = 0
        dut.uio_in.value = 0

    def set_ui(self, bit, val):
        if val:
            self.ui |= 1 << bit
        else:
            self.ui &= ~(1 << bit)
        self.dut.ui_in.value = self.ui

    def set_spk(self, idx, val):
        if val:
            self.spk |= 1 << idx
        else:
            self.spk &= ~(1 << idx)
        self.dut.spk_in.value = self.spk

    def set_spk_all(self, v):
        self.spk = v
        self.dut.spk_in.value = v

    async def spike(self, idx, width_ns=20.0):
        self.set_spk(idx, 1)
        await ns(width_ns)
        self.set_spk(idx, 0)

    async def ui_pulse(self, bit, width_ns):
        self.set_ui(bit, 1)
        await ns(width_ns)
        self.set_ui(bit, 0)


def start_clock(dut, clk_ns=CLK_NS):
    clk = Clock(dut.clk, clk_ns, unit="ns") if _V2 else Clock(dut.clk, clk_ns, units="ns")
    return cocotb.start_soon(clk.start())


def stop_task(task):
    if hasattr(task, "cancel"):
        task.cancel()
    else:
        task.kill()


async def setup(dut, clk_ns=CLK_NS):
    task = start_clock(dut, clk_ns)
    pins = Pins(dut)
    pins.clk_task = task
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    return pins


async def shift_bits(pins, bits, half_ns=20.0, on_rise=None):
    """Shift a list of bits (first element first) on SCK rising edges."""
    for b in bits:
        pins.set_ui(SDI, b)
        await ns(half_ns)
        pins.set_ui(SCK, 1)
        await ns(1)
        if on_rise is not None:
            on_rise()
        await ns(half_ns - 1)
        pins.set_ui(SCK, 0)


def frame_bits(addr, data, lead=()):
    w = frame(addr, data)
    return list(lead) + [(w >> (FW - 1 - i)) & 1 for i in range(FW)]


async def load_pulse(pins, t_su=20.0, t_load=40.0, t_h=20.0):
    await ns(t_su)
    pins.set_ui(LOAD, 1)
    await ns(t_load)
    pins.set_ui(LOAD, 0)
    await ns(t_h)


async def wr(dut, pins, addr, data, lead=(), half_ns=20.0, **kw):
    """Write one config byte: 13 (+ lead) bits on SCK/DATA, then a LOAD pulse."""
    await shift_bits(pins, frame_bits(addr, data, lead), half_ns=half_ns)
    await load_pulse(pins, **kw)
