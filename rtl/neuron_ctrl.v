// neuron_ctrl.v -- digital control plane of the TTGF26c analog neuron test
// chip, rev C (minimal: write-only config latches + digital LIF; everything
// else lives in the demo-board RP2040/RP2350 PIO firmware).
// See docs/regmap.md for the map, the write protocol and the timing contract.
//
// Pins (TT naming):
//   ui_in[0] SCK   ui_in[1] DATA   ui_in[2] LOAD      (config shift/latch port)
//   ui_in[3] stim A  ui_in[4] stim B  ui_in[5] hold  ui_in[6] mem reset  (-> rt_out)
//   ui_in[7] digital-LIF tick (rising edge)
//   uo[7:0]  spikes of analog neurons 0..7         (combinational, buffered)
//   uio[5:0] spikes of analog neurons 8..13        (uio_oe = 0xFF)
//   uio[6]   OUT_MUX ? neuron 14 : digital-LIF spike
//   uio[7]   OUT_MUX ? neuron 15 : config echo (shift-register serial out)
//
// Clock domains:
//   SCK  : 13-bit shift register only (no reset)                    (nc_cfg)
//   none : config latches, enable = LOAD & (addr == a); async reset
//          straight from the rst_n pin, so config works without clk
//   clk  : reset bridge, LIF tick/event synchronizers, LIF_EN sync, digital LIF,
//          SC clock divider.
`default_nettype none

module neuron_ctrl #(
    parameter LIF_W = 12,   // digital LIF state width (8..12)
    parameter NTRIM = 16    // neurons with a 4-bit threshold trim (even, 2..16)
) (
    input  wire                  clk,
    input  wire                  rst_n,
    /* verilator lint_off SYNCASYNCNET */  // ui_in[0] (SCK) and the LIF event mux clock flops
    input  wire [7:0]            ui_in,
    /* verilator lint_on SYNCASYNCNET */
    input  wire [7:0]            uio_in,
    output wire [7:0]            uo_out,
    output wire [7:0]            uio_out,
    output wire [7:0]            uio_oe,
    input  wire [15:0]           spk_in,           // async spikes from analog neurons
    output wire [78+4*NTRIM-1:0] cfg_out,          // packed analog config (nc_regmap.vh CFG_*)
    output wire [15:0]           probe_sel_onehot, // AND(PROBE_EN, decode(PROBE_SEL))
    output wire [3:0]            rt_out,           // ui_in[6:3] & RT_EN
    output wire                  sc_clk            // SC-dendrite clock, clk / 2^SC_DIV
);
`include "nc_regmap.vh"

    // ------------------------------------------------------------ reset (clk domain)
    wire rstn;
    nc_rst_sync u_rst (.clk(clk), .rst_n_in(rst_n), .rst_n_out(rstn));

    // ------------------------------------------------------------ config port
    // SCK-clocked 13-bit shift register + LOAD-strobed address decode (nc_cfg.v)
    wire [NREG-1:0] le;
    wire [7:0]      f_data;
    wire            echo;
    nc_cfg u_cfg (
        .sck(ui_in[0]), .sdi(ui_in[1]), .load(ui_in[2]),
        .le(le), .data(f_data), .echo(echo)
    );

    // ------------------------------------------------------------ config latches
    // One transparent-high latch (latrnq) per stored bit; reset straight from
    // the rst_n pin (no clk needed). regs = byte image, 0 where no storage
    // (logic uses regs only for digital fields; analog fields read cfg_out).
    // Analog bits are latched straight onto their cfg_out bit (packing per
    // nc_regmap.vh CFG_*), so the latch Q pin drives the port net itself.
    /* verilator lint_off WIDTHEXPAND */
    function integer cfg_idx;          // cfg_out bit of byte ra / bit rb, -1 = digital only
        input integer ra, rb;
        begin
            cfg_idx = -1;
            if (ra <= A_IDAC0 + 5)                 cfg_idx = CFG_IDAC + 8 * ra + rb;
            else if (ra <= A_VDAC0 + 2) begin
                if (rb < 6)                        cfg_idx = CFG_VDAC + 6 * (ra - A_VDAC0) + rb;
            end else if (ra == A_ANA) begin
                if (rb < 4)                        cfg_idx = CFG_GRP + rb;
                else if (rb < 6)                   cfg_idx = CFG_PLAT + rb - 4;
                else if (rb == 6)                  cfg_idx = CFG_BIAS;
            end else if (ra == A_PROBE) begin
                if (rb == 4 || rb == 5)            cfg_idx = CFG_PSUB + rb - 4;
                else if (rb == 6)                  cfg_idx = CFG_PEN;
            end else if (ra == A_MODE) begin
                if (rb < 2)                        cfg_idx = CFG_UA0 + rb;
            end else if (ra >= A_TRIM0)            cfg_idx = CFG_TRIM + 8 * (ra - A_TRIM0) + rb;
        end
    endfunction
    /* verilator lint_on WIDTHEXPAND */

    wire [8*NREG-1:0] regs;
    genvar ri, bi;
    generate
        for (ri = 0; ri < NREG; ri = ri + 1) begin : g_reg
            localparam integer TI = 2 * (ri - 18);   // first trim neuron in this byte (18 = A_TRIM0)
            for (bi = 0; bi < 8; bi = bi + 1) begin : g_bit
                localparam integer CI = cfg_idx(ri, bi);
                if (REG_USED[8*ri+bi] && (ri < A_TRIM0 || TI + bi / 4 < NTRIM)) begin : g_l
                    if (CI >= 0) begin : g_a
`ifdef NC_GF180_CELLS   // cell instantiated here (no wrapper) so Q is the port net itself
                        gf180mcu_fd_sc_mcu7t5v0__latrnq_1 u_l (.RN(rst_n), .E(le[ri]), .D(f_data[bi]), .Q(cfg_out[CI]));
`else
                        nc_latch u_l (.rst_n(rst_n), .en(le[ri]), .d(f_data[bi]), .q(cfg_out[CI]));
`endif
`ifdef SYNTHESIS          // byte image of analog bits only for simulation/tests:
                        assign regs[8*ri+bi] = 1'b0;   // no alias of the port net in the netlist
`else
                        assign regs[8*ri+bi] = cfg_out[CI];
`endif
                    end else begin : g_d
`ifdef NC_GF180_CELLS
                        gf180mcu_fd_sc_mcu7t5v0__latrnq_1 u_l (.RN(rst_n), .E(le[ri]), .D(f_data[bi]), .Q(regs[8*ri+bi]));
`else
                        nc_latch u_l (.rst_n(rst_n), .en(le[ri]), .d(f_data[bi]), .q(regs[8*ri+bi]));
`endif
                    end
                end else begin : g_0
                    assign regs[8*ri+bi] = 1'b0;
                end
            end
        end
    endgenerate

    wire [3:0] probe_sel = regs[8*A_PROBE +: 4];
    wire       probe_en  = cfg_out[CFG_PEN];
    wire       out_mux   = regs[8*A_MODE+2];
    wire [3:0] rt_en     = regs[8*A_MODE+4 +: 4];
    wire [3:0] sc_div    = regs[8*A_CLKD  +: 4];
    wire       l_en_a    = regs[8*A_CLKD+4];
    wire [1:0] l_src     = regs[8*A_CLKD+5 +: 2];

    // ------------------------------------------------------------ probe one-hot
    // Combinational from the latches. Firmware: PROBE_EN=0, change SEL, PROBE_EN=1.
    genvar pi;
    generate
        for (pi = 0; pi < 16; pi = pi + 1) begin : g_probe
            assign probe_sel_onehot[pi] = probe_en & (probe_sel == pi);
        end
    endgenerate

    assign rt_out = ui_in[6:3] & rt_en;

    // ------------------------------------------------------------ LIF tick (ui_in[7])
    reg t_s1, t_s2, t_d;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) {t_s1, t_s2, t_d} <= 3'b000;
        else       {t_s1, t_s2, t_d} <= {ui_in[7], t_s1, t_s2};
    end
    wire l_tick = t_s2 & ~t_d;

    // ------------------------------------------------------------ LIF input event
    // Source mux before a single capture chain: the selected line clocks a
    // toggle flop (catches pulses of any width >= ~1 ns), which is 2-FF
    // synchronized; event = toggle edge. SRC only changes while LIF_EN = 0,
    // so a mux-switch glitch is discarded by the LIF (pending cleared).
    reg ev_src;
    always @(*) begin
        case (l_src)
            2'd0:    ev_src = ui_in[3];
            2'd1:    ev_src = ui_in[4];
            2'd2:    ev_src = 1'b0;          // DC mode
            default: ev_src = spk_in[0];
        endcase
    end
    reg e_tog;
    always @(posedge ev_src or negedge rstn) begin
        if (!rstn) e_tog <= 1'b0;
        else       e_tog <= ~e_tog;
    end
    reg e_s1, e_s2, e_d;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) {e_s1, e_s2, e_d} <= 3'b000;
        else       {e_s1, e_s2, e_d} <= {e_tog, e_s1, e_s2};
    end
    wire l_in = e_s2 ^ e_d;

    // LIF_EN crosses from the latch into clk: 2-FF sync. All other LIF
    // parameters are quasi-static (host changes them only while LIF_EN = 0).
    wire l_en;
    nc_sync2 u_sync_en (.clk(clk), .rst_n(rstn), .d(l_en_a), .q(l_en));

    // ------------------------------------------------------------ digital LIF
    // 8-bit codes: EL/VTH/VRST scaled to the MSBs of the W-bit state, W in LSBs
    /* verilator lint_off UNUSEDSIGNAL */  // low bits unused when LIF_W < 12
    wire [11:0] el12  = {regs[8*A_LIF_EL +: 8],   4'b0};
    wire [11:0] vth12 = {regs[8*A_LIF_VTH +: 8],  4'b0};
    wire [11:0] vrs12 = {regs[8*A_LIF_VRST +: 8], 4'b0};
    wire [11:0] w12   = {4'b0, regs[8*A_LIF_W +: 8]};
    wire [LIF_W-1:0] lif_v;
    wire [3:0]       lif_ref;
    wire             lif_pend, lif_busy;
    /* verilator lint_on UNUSEDSIGNAL */
    wire             lif_spike;

    digital_lif #(.W(LIF_W), .RW(4)) u_lif (
        .clk(clk), .rst_n(rstn), .en(l_en), .tick(l_tick),
        .in_ev(l_in), .dc(l_src == 2'd2),
        .el  (el12 [11 -: LIF_W]),
        .vth (vth12[11 -: LIF_W]),
        .vrst(vrs12[11 -: LIF_W]),
        .wgt (w12[LIF_W-1:0]),
        .shift(regs[8*A_LIF_SR +: 4]),
        .refr (regs[8*A_LIF_SR+4 +: 4]),
        .spike(lif_spike), .v(lif_v), .ref_cnt(lif_ref),
        .pending(lif_pend), .busy(lif_busy)
    );

    // ------------------------------------------------------------ SC clock divider
    nc_scdiv u_scdiv (.clk(clk), .rst_n(rstn), .div(sc_div), .sc_clk(sc_clk));

    // ------------------------------------------------------------ outputs
    assign uo_out  = spk_in[7:0];
    assign uio_out = {out_mux ? spk_in[15] : echo,
                      out_mux ? spk_in[14] : lif_spike,
                      spk_in[13:8]};
    assign uio_oe  = 8'hFF;

    /* verilator lint_off UNUSEDSIGNAL */   // trim-byte enables beyond NTRIM
    wire [NREG-1:0] le_unused = le;
    /* verilator lint_on UNUSEDSIGNAL */
    wire _unused = &{1'b0, uio_in, 1'b0};
endmodule

`default_nettype wire
