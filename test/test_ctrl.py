"""cocotb tests for neuron_ctrl rev E: SCK/DATA/LOAD config port and latches,
latch reset, row x column probe decode (AdEx line, dummy slot never selected),
packed bias_b1 DAC codes + master lines vs the Python model, direct spike pins
+ output mux, config echo, rt pass-through, LIF tick / event-source / enable paths."""
import os
import random

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Edge, ReadOnly
from cocotb.utils import get_sim_time

from nc_driver import setup, wr, shift_bits, ns, stop_task, CLK_NS, _V2
from regmap import (A, NREG, FW, reg_used, cfg_pack, ana, probe, mode, lif_ctl, idac_word,
                    probe_lines, bias_lines, IDACS, VDACS, SLOT, D1_CH, ADEX_CH, DUMMY_SLOT,
                    REF_SLOT, TRIM_MASK_DEFAULT)

U = lambda s: int(s.value)  # noqa: E731
NTRIM = 16
TRIM_MASK = int(os.environ.get("TRIM_MASK", f"{TRIM_MASK_DEFAULT:X}"), 16)   # set by make TRIM_MASK=...
USED = reg_used(NTRIM, TRIM_MASK)


def now_ns():
    return get_sim_time(unit="ns") if _V2 else get_sim_time(units="ns")


def regs(dut):
    v = U(dut.u_ctrl.regs)
    return [(v >> (8 * a)) & 0xFF for a in range(NREG)]


def probe_got(dut):
    c = dut.u_ctrl
    return (U(c.probe_rsel), U(c.probe_en_c), U(c.probe_sel_d1), U(c.probe_sel_adex),
            U(c.probe_sub), U(c.probe_sub_b), U(c.probe_sub_raw))


def check_bias(dut, shadow, msg=""):
    exp = bias_lines(shadow)
    bad = {n: (U(getattr(dut.u_ctrl, n)), v) for n, v in exp.items() if U(getattr(dut.u_ctrl, n)) != v}
    assert not bad, f"{msg}: bias lines (got, exp) {bad}"


def check_image(dut, shadow, msg=""):
    got = regs(dut)
    assert got == shadow, f"{msg}: regs {[hex(x) for x in got]} != {[hex(x) for x in shadow]}"
    assert U(dut.cfg_out) == cfg_pack(shadow, NTRIM), f"{msg}: cfg_out packing"
    pr = shadow[A["PROBE"]]
    assert probe_got(dut) == probe_lines(pr & 0xF, (pr >> 4) & 3, (pr >> 6) & 1), f"{msg}: probe"
    check_bias(dut, shadow, msg)


@cocotb.test()
async def test_reset_defaults(dut):
    """Everything to the analog side is 0 after reset; pins are pass-through."""
    pins = await setup(dut)
    for b in range(3, 8):
        pins.set_ui(b, 1)
    pins.set_spk_all(0xA5C3)
    await ClockCycles(dut.clk, 20)
    assert regs(dut) == [0] * NREG
    assert U(dut.cfg_out) == 0
    assert probe_got(dut) == (0b0001, 0, 0, 0, 0, 1, 0), "probe: no column enabled"
    check_bias(dut, [0] * NREG, "reset: every DAC code 0 (off), ua0 = EXT/1, bias off")
    for p in IDACS:                               # explicit safe state
        assert all(U(getattr(dut.u_ctrl, f"{p}_b{j}")) == 0 for j in range(5)), p
    assert U(dut.u_ctrl.bias_en) == 0 and U(dut.u_ctrl.ua0_s0) == 1 and U(dut.u_ctrl.ua0_int) == 0
    assert U(dut.rt_out) == 0, "rt pass-through must default off"
    assert U(dut.uio_oe) == 0xFF
    assert U(dut.uo_out) == 0xC3
    uio = str(dut.uio_out.value)              # MSB first; uio[7] = echo, X until 13 SCK edges
    assert int(uio[2:], 2) == 0x25
    assert uio[1] == "0", "uio[6] = LIF spike (LIF off)"
    assert U(dut.u_ctrl.u_lif.en) == 0


@cocotb.test()
async def test_cfg_write_all(dut):
    """Random writes to every address (incl. unused 0x1A..0x1F) in random order,
    with 13-bit and 16-bit (3 leading don't-care bits) frames; check the whole
    byte image and the packed cfg_out after every write."""
    pins = await setup(dut)
    rng = random.Random(1)
    shadow = [0] * NREG
    for _ in range(3):
        for a in rng.sample(range(32), 32):
            v = rng.getrandbits(8)
            lead = [rng.getrandbits(1) for _ in range(rng.choice([0, 3, 7]))]
            await wr(dut, pins, a, v, lead=lead, half_ns=rng.choice([10, 20, 50]))
            if a < NREG:
                shadow[a] = v & USED[a]
            check_image(dut, shadow, f"write {a:#x}={v:#x}")
    # field-level spot checks of the packing
    await wr(dut, pins, A["ANA"], ana(grp=0b1010, plat=1, chain=0, bias=1, bsel=1))
    await wr(dut, pins, A["TRIM0"] + 7, 0x9C)
    await wr(dut, pins, A["TRIM0"] + 0, 0x00)
    c = U(dut.cfg_out)
    assert c & 0xF == 0b1010 and (c >> 4) & 1 == 1 and (c >> 5) & 1 == 0 and (c >> 6) & 1 == 1
    assert (c >> (7 + 4 * 14)) & 0xF == 0xC and (c >> (7 + 4 * 15)) & 0xF == 0x9
    assert (c >> 7) & 0xFF == 0
    # masked nibbles (no storage) stay 0 on cfg_out whatever is written
    for t in range(8):
        await wr(dut, pins, A["TRIM0"] + t, 0xFF)
    c = U(dut.cfg_out)
    for n in range(NTRIM):
        assert (c >> (7 + 4 * n)) & 0xF == (0xF if (TRIM_MASK >> n) & 1 else 0), f"nibble {n}"
    assert U(dut.u_ctrl.bias_en) == 1
    await wr(dut, pins, A["ANA"], ana(chain=1))
    c = U(dut.cfg_out)
    assert c & 0x7F == 1 << 5 and U(dut.u_ctrl.bias_en) == 0


@cocotb.test()
async def test_load_glitch_free(dut):
    """SCK activity with LOAD low never writes; a LOAD pulse changes only the
    addressed byte, exactly once."""
    pins = await setup(dut)
    rng = random.Random(2)
    shadow = [0] * NREG
    for a in range(NREG):
        shadow[a] = 0x5A & USED[a]
        await wr(dut, pins, a, 0x5A)
    check_image(dut, shadow, "preload")

    changes = []

    async def mon():
        last = regs(dut)
        while True:
            await Edge(dut.u_ctrl.regs)
            await ReadOnly()                  # settle all bits of this time step
            cur = regs(dut)
            if cur != last:
                changes.append(cur)
                last = cur

    t = cocotb.start_soon(mon())
    # 200 random bits shifted, LOAD low: nothing may change
    await shift_bits(pins, [rng.getrandbits(1) for _ in range(200)], half_ns=10)
    await ns(200)
    assert changes == [], "SCK with LOAD low changed a latch"
    for a in rng.sample(range(NREG), 12):
        v = rng.getrandbits(8)
        changes.clear()
        await wr(dut, pins, a, v, t_load=rng.choice([10, 40, 500]))
        exp = list(shadow)
        exp[a] = v & USED[a]
        if exp == shadow:
            assert changes == [], f"addr {a:#x}: spurious change"
        else:
            assert changes == [exp], f"addr {a:#x}: {len(changes)} changes"
        shadow = exp
    stop_task(t)


@cocotb.test()
async def test_latch_reset_and_no_clk(dut):
    """rst_n clears every latch; writes and reset work with clk stopped."""
    pins = await setup(dut)
    for a in range(NREG):
        await wr(dut, pins, a, 0xFF)
    assert regs(dut) == USED
    assert probe_got(dut) == probe_lines(15, 3, 1)       # SUB = 3: REF slot (0,0)
    stop_task(pins.clk_task)
    await ns(1000)
    dut.rst_n.value = 0
    await ns(50)
    assert regs(dut) == [0] * NREG, "async latch reset (no clk)"
    assert U(dut.cfg_out) == 0 and U(dut.probe_en_c) == 0 and U(dut.probe_sel_d1) == 0
    assert U(dut.probe_sel_adex) == 0
    check_bias(dut, [0] * NREG, "after reset")
    # LOAD during reset: reset dominates
    await wr(dut, pins, A["ANA"], 0x7F)
    assert regs(dut)[A["ANA"]] == 0
    dut.rst_n.value = 1
    await ns(50)
    shadow = [0] * NREG
    for a in (A["IDAC"] + 1, A["PROBE"], A["TRIM0"] + 2):
        await wr(dut, pins, a, 0x3C)
        shadow[a] = 0x3C & USED[a]
    check_image(dut, shadow, "writes without clk")


@cocotb.test()
async def test_config_echo(dut):
    """uio[7] (OUT_MUX = 0) is the shift-register MSB: each bit reappears 13
    SCK edges later (link check)."""
    pins = await setup(dut)
    rng = random.Random(3)
    bits = [rng.getrandbits(1) for _ in range(60)]
    seen = []
    await shift_bits(pins, bits, on_rise=lambda: seen.append((U(dut.uio_out) >> 7) & 1))
    assert seen[FW - 1:] == bits[:len(bits) - FW + 1]


@cocotb.test()
async def test_spike_pins_and_out_mux(dut):
    """Spike inputs reach uo / uio combinationally; OUT_MUX picks uio[7:6]."""
    pins = await setup(dut)
    rng = random.Random(4)
    await shift_bits(pins, [1, 0] * 8)        # echo now well defined
    for om in (0, 1, 0):
        await wr(dut, pins, A["MODE"], mode(out_mux=om))
        echo = U(dut.u_ctrl.u_cfg.echo)
        for _ in range(40):
            v = rng.getrandbits(16)
            pins.set_spk_all(v)
            await ns(1)
            assert U(dut.uo_out) == v & 0xFF
            uio = U(dut.uio_out)
            assert uio & 0x3F == (v >> 8) & 0x3F
            if om:
                assert uio >> 6 == (v >> 14) & 3
            else:
                assert (uio >> 6) & 1 == 0          # LIF disabled
                assert uio >> 7 == echo
            assert U(dut.uio_oe) == 0xFF
    # a 2 ns spike on neuron 9 is visible without any clk involvement
    seen = []

    async def watch():
        await Edge(dut.uio_out)
        seen.append(U(dut.uio_out))

    pins.set_spk_all(0)
    await ns(5)
    w = cocotb.start_soon(watch())
    await pins.spike(9, 2.0)
    await ns(5)
    assert seen and (seen[0] >> 1) & 1, "short spike on uio[1]"
    stop_task(w)


@cocotb.test()
async def test_probe_decode(dut):
    """Exhaustive SEL x SUB x EN against the floorplan-derived model: row/column
    lines, D1 and AdEx lines, sub taps. At most one target is enabled, the
    dummy slot (0,3) is never selected, and every array channel reaches its own
    slot."""
    pins = await setup(dut)
    dr, dc = DUMMY_SLOT
    reached = set()
    for sel in range(16):
        for sub in range(4):
            for en in (0, 1):
                await wr(dut, pins, A["PROBE"], probe(sel=sel, sub=sub, en=en))
                got = probe_got(dut)
                exp = probe_lines(sel, sub, en)
                assert got == exp, (sel, sub, en, got, exp)
                rsel, enc, d1, adex = got[:4]
                assert bin(enc).count("1") + d1 + adex <= 1 and bin(rsel).count("1") <= 1
                assert not ((rsel >> dr) & 1 and (enc >> dc) & 1), f"dummy slot selected by {sel},{sub}"
                assert not (en == 0 and (enc or d1 or adex)), "PROBE_EN = 0 must enable nothing"
                if en and enc:
                    reached.add((rsel.bit_length() - 1, enc.bit_length() - 1))
                if sub != 3 and sel in (D1_CH, ADEX_CH):      # outside the array: no row, no column
                    assert rsel == 0 and enc == 0
                    assert (d1, adex) == ((en, 0) if sel == D1_CH else (0, en))
    assert reached == set(SLOT.values()) | {REF_SLOT}, "every array channel and REF reachable"
    assert DUMMY_SLOT not in reached
    # spot checks against the floorplan table (docs/regmap.md section 3.1)
    for sel, sub, rc in ((0, 0, (0, 1)), (12, 1, (1, 1)), (15, 0, (3, 3)), (7, 2, (2, 0)), (9, 3, (0, 0)),
                         (3, 3, (0, 0)), (13, 3, (0, 0))):
        await wr(dut, pins, A["PROBE"], probe(sel=sel, sub=sub, en=1))
        assert U(dut.probe_rsel) == 1 << rc[0] and U(dut.probe_en_c) == 1 << rc[1], (sel, sub)
        assert U(dut.probe_sel_d1) == 0 and U(dut.probe_sel_adex) == 0
    for sub in range(3):
        await wr(dut, pins, A["PROBE"], probe(sel=ADEX_CH, sub=sub, en=1))
        assert U(dut.probe_sel_adex) == 1 and U(dut.probe_sel_d1) == 0
        assert U(dut.probe_en_c) == 0 and U(dut.probe_rsel) == 0
        assert U(dut.probe_sub_raw) == sub and U(dut.probe_sub) == sub & 1
        assert U(dut.probe_sub_b) == 1 - (sub & 1)
    await wr(dut, pins, A["PROBE"], probe(sel=13, sub=2, en=1))
    assert U(dut.probe_sel_d1) == 1 and U(dut.probe_sel_adex) == 0
    assert U(dut.probe_sub_raw) == 2 and U(dut.probe_sub) == 0 and U(dut.probe_sub_b) == 1
    await wr(dut, pins, A["PROBE"], probe(sel=13, sub=2, en=0))
    assert U(dut.probe_sel_d1) == 0


@cocotb.test()
async def test_bias_decode(dut):
    """bias_b1 lines vs the Python model: every UA0_MODE x BIAS_EN x IB_X2 master
    state; each current-DAC code walked through all 32 values (others random), so
    the packed 40-bit word is checked bit-exact across byte boundaries; the
    voltage-DAC code through all 64 values; BIAS_EN does not touch the codes."""
    pins = await setup(dut)
    rng = random.Random(11)
    shadow = [0] * NREG

    async def put(a, v):
        await wr(dut, pins, a, v)
        shadow[a] = v & USED[a]

    for m in range(4):
        for be in (0, 1):
            for x2 in (0, 1):
                await put(A["MODE"], mode(ua0=m, ib_x2=x2))
                await put(A["ANA"], ana(bias=be))
                check_bias(dut, shadow, f"master M={m} BIAS_EN={be} IB_X2={x2}")

    async def put_codes(codes):
        for i, b in enumerate(idac_word(codes)):
            await put(A["IDAC"] + i, b)

    for k in range(8):
        for c in range(32):
            codes = [rng.getrandbits(5) for _ in range(8)]
            codes[k] = c
            await put_codes(codes)
            check_bias(dut, shadow, f"DAC {k} ({IDACS[k]}) code {c}")
            got = sum(U(getattr(dut.u_ctrl, f"{IDACS[k]}_b{j}")) << j for j in range(5))
            assert got == c, (k, got, c)
    for be in (0, 1, 0):
        await put(A["ANA"], ana(bias=be))
        check_bias(dut, shadow, f"codes kept with BIAS_EN={be}")
    for v in range(64):
        await put(A["VDAC"], v | 0xC0)                 # [7:6] have no storage
        check_bias(dut, shadow, f"VDAC {v}")
        assert sum(U(getattr(dut.u_ctrl, f"{VDACS[0]}_c{j}")) << j for j in range(6)) == v
    await put_codes([0] * 8)
    check_bias(dut, shadow, "all codes 0 = off")
    check_image(dut, shadow, "image")


@cocotb.test()
async def test_rt_passthrough(dut):
    pins = await setup(dut)
    rng = random.Random(5)
    for en in range(16):
        await wr(dut, pins, A["MODE"], mode(rt_en=en, ua0=en & 3))
        assert U(dut.u_ctrl.ua0_s1) == int(en & 3 == 1)
        for _ in range(6):
            u = rng.getrandbits(4)
            for b in range(4):
                pins.set_ui(3 + b, (u >> b) & 1)
            await ns(1)
            assert U(dut.rt_out) == u & en


async def count_pulses(dut, sig, n_clk):
    c = 0
    for _ in range(n_clk):
        await FallingEdge(dut.clk)
        c += U(sig)
    return c


@cocotb.test()
async def test_lif_enable_and_tick(dut):
    """LIF_EN reaches the LIF through a 2-FF sync; one 1-clk tick per ui_in[7]
    rising edge (2-FF sync + edge detect)."""
    pins = await setup(dut)
    lif = dut.u_ctrl.u_lif
    await wr(dut, pins, A["LIF_CTL"], lif_ctl(lif_en=1, lif_src=2))
    lat = 0
    while not U(lif.en):
        await RisingEdge(dut.clk)
        lat += 1
    assert 1 <= lat <= 3, lat
    ticks = []

    async def mon():
        while True:
            await FallingEdge(dut.clk)
            if U(lif.tick):
                ticks.append(now_ns())

    m = cocotb.start_soon(mon())
    rng = random.Random(6)
    edges = []
    for _ in range(25):
        await ns(rng.uniform(250, 900))
        edges.append(now_ns())
        await pins.ui_pulse(7, rng.uniform(250, 600))
    await ns(1000)
    stop_task(m)
    assert len(ticks) == len(edges), (len(ticks), len(edges))
    for e, t in zip(edges, ticks):
        assert CLK_NS < t - e < 4 * CLK_NS, f"tick latency {t - e} ns"
    await wr(dut, pins, A["LIF_CTL"], lif_ctl(lif_en=0))
    await ClockCycles(dut.clk, 4)
    assert U(lif.en) == 0


@cocotb.test()
async def test_lif_event_sources(dut):
    """SRC 0/1/3 route stim A / stim B / analog neuron 0 to the LIF input
    event (one 1-clk event per rising edge, short pulses captured); SRC 2 is
    DC (no events, dc = 1)."""
    pins = await setup(dut)
    lif = dut.u_ctrl.u_lif
    rng = random.Random(8)
    srcs = {0: ("ui", 3), 1: ("ui", 4), 3: ("spk", 0)}

    async def pulse(kind, idx, w):
        if kind == "ui":
            await pins.ui_pulse(idx, w)
        else:
            await pins.spike(idx, w)

    for src in (0, 1, 3, 2):
        await wr(dut, pins, A["LIF_CTL"], lif_ctl(lif_en=0, lif_src=src))
        await wr(dut, pins, A["LIF_CTL"], lif_ctl(lif_en=1, lif_src=src))
        await ClockCycles(dut.clk, 6)
        assert U(lif.dc) == (1 if src == 2 else 0)
        cnt = {"n": 0}

        async def mon():
            while True:
                await FallingEdge(dut.clk)
                cnt["n"] += U(lif.in_ev)

        m = cocotb.start_soon(mon())
        npulse = 0
        for _ in range(20):
            # pulse on every candidate line; only the selected one may count
            for s, (kind, idx) in srcs.items():
                w = rng.uniform(2, 15) if kind == "spk" else rng.uniform(150, 400)
                await pulse(kind, idx, w)
                await ns(rng.uniform(350, 600))
                if s == src:
                    npulse += 1
        await ClockCycles(dut.clk, 6)
        stop_task(m)
        assert cnt["n"] == npulse, f"src {src}: {cnt['n']} events, {npulse} pulses"
    await wr(dut, pins, A["LIF_CTL"], lif_ctl(lif_en=0))
