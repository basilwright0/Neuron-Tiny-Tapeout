"""cocotb helpers for neuron_ctrl rev B: clock/reset, pins, 16-bit SPI master.

Works with cocotb 1.8 (TT template pin) and cocotb 2.x (container).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles

from regmap import wframe, rframe

_V2 = int(cocotb.__version__.split(".")[0]) >= 2
CLK_NS = 100  # 10 MHz


def ps(t_ps):
    t_ps = int(round(t_ps))
    return Timer(t_ps, unit="ps") if _V2 else Timer(t_ps, units="ps")


def ns(t_ns):
    return ps(t_ns * 1000)


class Pins:
    """Keeps the testbench-driven ui_in / spk_in state."""

    def __init__(self, dut):
        self.dut = dut
        self.ui = 0b0000_0100  # CS_N idle high
        self.spk = 0
        dut.ui_in.value = self.ui
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

    async def spike(self, idx, width_ns=20.0):
        self.set_spk(idx, 1)
        await ns(width_ns)
        self.set_spk(idx, 0)

    async def ui_pulse(self, bit, width_ns):
        self.set_ui(bit, 1)
        await ns(width_ns)
        self.set_ui(bit, 0)


async def setup(dut, clk_ns=CLK_NS):
    clk = Clock(dut.clk, clk_ns, unit="ns") if _V2 else Clock(dut.clk, clk_ns, units="ns")
    cocotb.start_soon(clk.start())
    pins = Pins(dut)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    return pins


def miso(dut):
    return int(dut.uio_out.value) & 1


async def spi_xfer(dut, pins, word, nbits=16, ratio=8, clk_ns=CLK_NS,
                   phase_ns=0.0, on_bit=None):
    """Mode-0 transfer, MSB first, SCK period = ratio * clk period.
    Returns the nbits read on MISO (sampled at each SCK rising edge)."""
    half = ratio * clk_ns / 2.0
    if phase_ns:
        await ns(phase_ns)
    pins.set_ui(0, 0)
    pins.set_ui(2, 0)                     # CS_N low
    await ns(max(half, 5 * clk_ns))
    rx = 0
    for i in range(nbits):
        pins.set_ui(1, (word >> (nbits - 1 - i)) & 1)
        await ns(half)
        rx = (rx << 1) | miso(dut)        # master samples at rising edge
        pins.set_ui(0, 1)
        await ns(half)
        pins.set_ui(0, 0)
        if on_bit is not None:
            on_bit(i)
    await ns(half)
    pins.set_ui(2, 1)
    pins.set_ui(1, 0)
    await ns(5 * clk_ns)                  # CS high time
    return rx


async def wr(dut, pins, addr, data, **kw):
    await spi_xfer(dut, pins, wframe(addr, data), **kw)


async def rd(dut, pins, addr, **kw):
    return (await spi_xfer(dut, pins, rframe(addr), **kw)) & 0xFF
