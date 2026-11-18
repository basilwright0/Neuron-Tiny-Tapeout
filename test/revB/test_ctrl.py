"""cocotb tests for neuron_ctrl rev B: SPI register file, latches, spikes,
counter, one-hot decoder, rt gate, SC clock, heartbeat."""
import random

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb.utils import get_sim_time

from nc_driver import setup, spi_xfer, wr, rd, ns, ps, CLK_NS
from regmap import A, NREG, REG_USED, CHIP_ID, ctrl, probe, wframe, rframe

U = lambda s: int(s.value)  # noqa: E731


def cfg_byte(dut, a):
    return (U(dut.cfg_out) >> (8 * a)) & 0xFF


@cocotb.test()
async def test_reset_defaults(dut):
    """All outputs to the analog side are zero after reset; regs read 0."""
    pins = await setup(dut)
    for b in range(4):
        pins.set_ui(3 + b, 1)
    await ClockCycles(dut.clk, 20)
    assert U(dut.cfg_out) == 0
    assert U(dut.probe_sel_onehot) == 0
    assert U(dut.rt_out) == 0, "rt pass-through must default off"
    assert U(dut.sc_clk) == 0
    assert U(dut.uio_oe) == 0x01
    assert U(dut.uio_out) == 0
    assert U(dut.uo_out) & 0x7F == 0
    for a in range(NREG):
        assert await rd(dut, pins, a) == 0, f"reg {a:#x}"
    assert await rd(dut, pins, A["ID"]) == CHIP_ID
    assert U(dut.cfg_out) == 0, "reads must not write"


@cocotb.test()
async def test_spi_write_readback(dut):
    """Random writes to every register, read back in the same frame; ratios 6/8/10."""
    pins = await setup(dut)
    rng = random.Random(1)
    shadow = [0] * NREG
    for k in range(3):
        for a in rng.sample(range(NREG), NREG):
            v = rng.getrandbits(8)
            ratio = rng.choice([6, 8, 10])
            await wr(dut, pins, a, v, ratio=ratio, phase_ns=rng.uniform(0, CLK_NS))
            shadow[a] = v & REG_USED[a]
            assert cfg_byte(dut, a) == shadow[a], f"write {a:#x}"
        exp = sum(s << (8 * i) for i, s in enumerate(shadow))
        assert U(dut.cfg_out) == exp
        for a in range(NREG):
            ratio = rng.choice([6, 8, 10])
            got = await rd(dut, pins, a, ratio=ratio, phase_ns=rng.uniform(0, CLK_NS))
            assert got == shadow[a], f"read {a:#x} ratio {ratio}: {got:#x} != {shadow[a]:#x}"
    before = U(dut.cfg_out)
    # short frame (15 bits) -> no write
    await spi_xfer(dut, pins, wframe(A["GRP"], 0x5A) >> 1, nbits=15)
    assert U(dut.cfg_out) == before
    # writes to read-only / unused addresses are ignored
    for a in (A["CNT_L"], A["ID"], 0x7F):
        await wr(dut, pins, a, 0xFF)
    assert U(dut.cfg_out) == before
    # over-long frame: only the first 16 bits count
    await spi_xfer(dut, pins, (wframe(A["GRP"], 0x3C) << 8) | 0xFF, nbits=24)
    assert cfg_byte(dut, A["GRP"]) == 0x3C
    # read frame returns 0 on MISO during the address byte
    rx = await spi_xfer(dut, pins, rframe(A["GRP"]))
    assert rx == 0x3C


@cocotb.test()
async def test_latch_no_glitch(dut):
    """Only the addressed byte changes, once, after the 16th bit."""
    pins = await setup(dut)
    await wr(dut, pins, A["PROBE"], probe(sel=3, en=1))
    await wr(dut, pins, A["DAC_VTH"], 0x77)
    await ClockCycles(dut.clk, 4)
    changes, bits = [], [0]
    stop = [False]

    async def monitor():
        last = U(dut.cfg_out)
        while not stop[0]:
            await RisingEdge(dut.clk)
            await ps(1)
            c = U(dut.cfg_out)
            assert bin(U(dut.probe_sel_onehot)).count("1") <= 1
            if c != last:
                changes.append((c ^ last, bits[0]))
                last = c

    cocotb.start_soon(monitor())
    for a, v in ((A["DAC_VTH"], 0x88), (A["PROBE"], probe(sel=28, en=1)), (A["SC"], 0x45)):
        changes.clear()
        bits[0] = 0

        def on_bit(i):
            bits[0] = i + 1

        await spi_xfer(dut, pins, wframe(a, v), on_bit=on_bit)
        await ClockCycles(dut.clk, 5)
        assert len(changes) == 1, f"addr {a:#x}: {len(changes)} changes"
        diff, nb = changes[0]
        assert diff >> (8 * a) << (8 * a) == diff and diff >> (8 * (a + 1)) == 0, "other bytes changed"
        assert nb == 16, f"changed after bit {nb}"
    stop[0] = True


@cocotb.test()
async def test_onehot_decoder(dut):
    """probe_sel_onehot = 1<<PROBE_SEL when enabled; break-before-make; uo[6] valid."""
    pins = await setup(dut)
    for sel in [0, 1, 7, 16, 31, 5]:
        await wr(dut, pins, A["PROBE"], probe(sel=sel, en=1))
        await ClockCycles(dut.clk, 3)
        assert U(dut.probe_sel_onehot) == 1 << sel, f"sel {sel}"
        assert (U(dut.uo_out) >> 6) & 1 == 0, "probe-valid must wait for settle"
        await ClockCycles(dut.clk, 260)
        assert (U(dut.uo_out) >> 6) & 1 == 1, "probe-valid after settle"
    await wr(dut, pins, A["PROBE"], probe(sel=9, en=0))
    await ClockCycles(dut.clk, 3)
    assert U(dut.probe_sel_onehot) == 0
    await wr(dut, pins, A["PROBE"], probe(sel=3, en=1))
    await ClockCycles(dut.clk, 3)
    seen = []

    async def mon():
        for _ in range(400):
            await RisingEdge(dut.clk)
            await ps(1)
            seen.append(U(dut.probe_sel_onehot))

    t = cocotb.start_soon(mon())
    await wr(dut, pins, A["PROBE"], probe(sel=4, en=1))
    await t
    seq = [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]]
    assert seq == [1 << 3, 0, 1 << 4], [hex(s) for s in seq]
    assert seen.count(0) >= 2, "at least 2 clk all-off"


async def check_capture(dut, pins, mode, rng):
    """Fire 20 ns pulses on the neurons routed to uo[0..3] and the OR on uo[4]."""
    sels = [2, 9, 17, 30]
    await wr(dut, pins, A["CTRL"], ctrl(spk_mode=mode))
    for k, s in enumerate(sels):
        await wr(dut, pins, A[f"SEL{k}"], s)
    await wr(dut, pins, A["GRP"], 1 << (sels[2] // 4))
    await ClockCycles(dut.clk, 10)
    routes = [(0, sels[0]), (1, sels[1]), (2, sels[2]), (3, sels[3]), (4, sels[2])]
    for bit, nidx in routes:
        for rep in range(3):
            before = (U(dut.uo_out) >> bit) & 1
            hist = []

            async def watch():
                for _ in range(10):
                    await RisingEdge(dut.clk)
                    await ps(1)
                    hist.append((U(dut.uo_out) >> bit) & 1)

            await ps(rng.randrange(0, CLK_NS * 1000))      # random phase vs clk
            w = cocotb.start_soon(watch())
            await pins.spike(nidx, 20.0)
            if mode == 1:
                await ns(1)
                assert ((U(dut.uo_out) >> bit) & 1) == 1 - before, "raw toggle is immediate"
            await w
            if mode == 0:
                assert before == 0
                assert sum(hist) == 2, f"uo[{bit}] n{nidx} rep{rep}: stretched {hist}"
                assert hist.index(1) <= 3, f"latency {hist}"
            else:
                assert all(h == 1 - before for h in hist), f"uo[{bit}] toggle {hist}"
            # a non-selected / disabled neuron must not disturb this output
            other = (nidx + 5) % 32
            if other not in sels:
                lvl = (U(dut.uo_out) >> bit) & 1
                await pins.spike(other, 20.0)
                await ClockCycles(dut.clk, 8)
                assert ((U(dut.uo_out) >> bit) & 1) == lvl
            await ClockCycles(dut.clk, 5)


@cocotb.test()
async def test_spike_capture_stretched(dut):
    """20 ns async pulse at random phase, clk 10 MHz -> 2-clk stretched pulse."""
    pins = await setup(dut)
    await check_capture(dut, pins, 0, random.Random(2))


@cocotb.test()
async def test_spike_capture_raw_toggle(dut):
    """20 ns async pulse at random phase -> raw async toggle per spike."""
    pins = await setup(dut)
    await check_capture(dut, pins, 1, random.Random(3))


async def read_cnt(dut, pins):
    lo = await rd(dut, pins, A["CNT_L"])
    hi = await rd(dut, pins, A["CNT_H"])
    return lo | (hi << 8)


@cocotb.test()
async def test_counter_window(dut):
    """16-bit counter gated by ui_in[7]; coherent 2-byte read via HOLD."""
    pins = await setup(dut)
    rng = random.Random(4)
    n = 5

    async def burst(k, spacing_ns=700):
        for _ in range(k):
            await pins.spike(n, 20.0)
            await ns(spacing_ns + rng.uniform(0, 100))

    await wr(dut, pins, A["SEL0"], n)
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=2, cnt_src=0))
    await burst(7)                     # gate closed
    pins.set_ui(7, 1)
    await ns(300)
    assert (U(dut.uo_out) >> 6) & 1 == 1, "uo[6] shows the counter window"
    await burst(23)
    await ns(300)
    pins.set_ui(7, 0)
    await ns(300)
    await burst(4)
    assert await read_cnt(dut, pins) == 23
    pins.set_ui(7, 1); await ns(300); await burst(10); pins.set_ui(7, 0); await ns(300)
    assert await read_cnt(dut, pins) == 33
    # mode 3: window opening clears
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=3, cnt_src=0))
    pins.set_ui(7, 1); await ns(300); await burst(6); pins.set_ui(7, 0); await ns(300)
    assert await read_cnt(dut, pins) == 6
    # mode 0 clears
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=0))
    assert await read_cnt(dut, pins) == 0
    # mode 1, source = ui3 stimulus; count > 255 exercises the high byte
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=1, cnt_src=3))
    for _ in range(300):
        await pins.ui_pulse(3, 300)
        await ns(300)
    assert await read_cnt(dut, pins) == 300
    # source = OR of enabled groups
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=0))
    await wr(dut, pins, A["GRP"], 0x02)            # neurons 4..7
    await wr(dut, pins, A["CTRL"], ctrl(cnt_mode=1, cnt_src=1))
    for k in range(12):
        await pins.spike(4 + k % 4, 20.0)          # enabled
        await ns(500)
        await pins.spike(9, 20.0)                  # disabled group
        await ns(500)
    assert await read_cnt(dut, pins) == 12
    st = await rd(dut, pins, A["STATUS"])
    assert st & 0x80, "status: gate"


@cocotb.test()
async def test_rt_gate_sc_clk_heartbeat(dut):
    """rt_out follows ui_in[6:3] only for enabled lines; SC divider; heartbeat."""
    pins = await setup(dut)
    await wr(dut, pins, A["RT"], 0b0101)
    await wr(dut, pins, A["SC"], 3)                # clk / 2^3
    for v in range(16):
        for b in range(4):
            pins.set_ui(3 + b, (v >> b) & 1)
        await ns(1)
        assert U(dut.rt_out) == v & 0b0101
    edges = []
    for _ in range(4):
        await RisingEdge(dut.sc_clk)
        edges.append(get_sim_time("ns"))
    periods = {round(edges[i + 1] - edges[i]) for i in range(3)}
    assert periods == {8 * CLK_NS}, periods
    seen = set()
    for _ in range(200):                           # tb HB_BIT=6 -> 128 clk period
        await RisingEdge(dut.clk)
        seen.add(U(dut.uo_out) >> 7)
    assert seen == {0, 1}
