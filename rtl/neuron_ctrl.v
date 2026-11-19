// neuron_ctrl.v -- digital control plane of the TTGF26c analog neuron test
// chip, rev E (rev D minus the SC clock divider and the IDAC range decode;
// bias_b1 rev C fixed-range DAC ports; AdEx probe line; TRIM_MASK default
// 16'hC1FD). Write-only config latches + digital LIF; everything else lives
// in the demo-board RP2040/RP2350 PIO firmware.
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
//   clk  : reset bridge, LIF tick/event synchronizers, LIF_EN sync, digital LIF.
`default_nettype none

module neuron_ctrl #(
    parameter LIF_W = 12,   // digital LIF state width (8..12)
    parameter NTRIM = 16,   // trim nibbles in the map / on cfg_out (even, 2..16)
    parameter [15:0] TRIM_MASK = 16'hC1FD  // nibble n has latches only if TRIM_MASK[n];
                                           // others read 0 and drive 0 on cfg_out.
                                           // C1FD: nibbles 0, 2-8, 14, 15 (docs/08 §5)
) (
`include "nc_bias_ports.vh"                      // lines to bias_b1 (generated)
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
    output wire [7+4*NTRIM-1:0]  cfg_out,          // GRP_EN, PLATEAU_EN, D1_CHAIN, D1_BSEL, trims (CFG_*)
    output wire [3:0]            probe_rsel,       // array row of the selected slot
    output wire [3:0]            probe_en_c,       // PROBE_EN & (column of the selected slot == c)
    output wire                  probe_sub,        // PROBE_SUB[0]   (array vm/vr tap)
    output wire                  probe_sub_b,      // ~PROBE_SUB[0]
    output wire                  probe_sel_d1,     // PROBE_EN & SEL == 13 & SUB != 3 (D1, outside the array)
    output wire                  probe_sel_adex,   // PROBE_EN & SEL == 3  & SUB != 3 (AdEx, outside the array)
    output wire [1:0]            probe_sub_raw,    // PROBE_SUB[1:0] (D1 / AdEx tap select)
    output wire [3:0]            rt_out            // ui_in[6:3] & RT_EN
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
    // the rst_n pin (no clk needed). regs = byte image, 0 where no storage.
    // Every bit that leaves the macro unchanged is latched with its Q pin on
    // the port net itself (no feed-through buffer after flattening):
    //   cfg_out bits and PROBE_SUB here, IDAC / VDAC codes / BIAS_EN / IB_X2 in
    //   nc_bias_if.vh. In synthesis regs is 0 for those bits.
`ifdef NC_GF180_CELLS
`define NC_LAT(xI, xQ, xA, xB) gf180mcu_fd_sc_mcu7t5v0__latrnq_1 xI (.RN(rst_n), .E(le[xA]), .D(f_data[xB]), .Q(xQ));
`else
`define NC_LAT(xI, xQ, xA, xB) nc_latch xI (.rst_n(rst_n), .en(le[xA]), .d(f_data[xB]), .q(xQ));
`endif
    /* verilator lint_off WIDTHEXPAND */
    function integer cfg_idx;          // cfg_out bit of byte ra / bit rb, -1 = none
        input integer ra, rb;
        begin
            cfg_idx = -1;
            if (ra == A_ANA) begin
                if (rb < 4)                        cfg_idx = CFG_GRP + rb;
                else if (rb == 4)                  cfg_idx = CFG_PLAT;
                else if (rb == 5)                  cfg_idx = CFG_CHAIN;
                else if (rb == 7)                  cfg_idx = CFG_BSEL;
            end else if (ra >= A_TRIM0)            cfg_idx = CFG_TRIM + 8 * (ra - A_TRIM0) + rb;
        end
    endfunction
    function integer is_bias;          // 1: bit latched in nc_bias_if.vh
        input integer ra, rb;
        begin
            is_bias = ((ra < A_IDAC + 5) || (ra == A_VDAC && rb < 6)     // A_IDAC = 0
                    || (ra == A_ANA && rb == 6) || (ra == A_MODE && rb == 3)) ? 1 : 0;
        end
    endfunction
    function integer trim_on;          // 1: trim nibble n has storage
        input integer n;
        begin
            trim_on = (n >= 0 && n < NTRIM && n < 16) ? TRIM_MASK[n % 16] : 0;
        end
    endfunction
    /* verilator lint_on WIDTHEXPAND */

    localparam integer TRIM_BASE = {27'd0, A_TRIM0};
    wire [8*NREG-1:0] regs;
    genvar ri, bi;
    generate
        for (ri = 0; ri < NREG; ri = ri + 1) begin : g_reg
            localparam integer TI = 2 * (ri - TRIM_BASE);   // first trim nibble in this byte
            for (bi = 0; bi < 8; bi = bi + 1) begin : g_bit
                localparam integer CI = cfg_idx(ri, bi);
                localparam integer BB = is_bias(ri, bi);
                localparam integer PS = (ri == A_PROBE && (bi == 4 || bi == 5)) ? 1 : 0;
                if (BB != 0) begin : g_b
                    // latch and regs image in nc_bias_if.vh
                end else if (REG_USED[8*ri+bi] && (ri < A_TRIM0 || trim_on(TI + bi / 4) != 0)) begin : g_l
                    if (CI >= 0) begin : g_c
                        `NC_LAT(u_l, cfg_out[CI], ri, bi)
`ifdef SYNTHESIS          // byte image of these bits only for simulation/tests:
                        assign regs[8*ri+bi] = 1'b0;   // no alias of the port net in the netlist
`else
                        assign regs[8*ri+bi] = cfg_out[CI];
`endif
                    end else if (PS != 0) begin : g_p
                        `NC_LAT(u_l, probe_sub_raw[bi-4], ri, bi)
`ifdef SYNTHESIS
                        assign regs[8*ri+bi] = 1'b0;
`else
                        assign regs[8*ri+bi] = probe_sub_raw[bi-4];
`endif
                    end else begin : g_d
                        `NC_LAT(u_l, regs[8*ri+bi], ri, bi)
                    end
                end else begin : g_0
                    assign regs[8*ri+bi] = 1'b0;
                    if (CI >= 0 && CI < 7 + 4 * NTRIM) begin : g_t     // masked trim nibble: tie off
                        assign cfg_out[CI] = 1'b0;
                    end
                end
            end
        end
    endgenerate

    // bias_b1 lines: pass-through latches and master lines
`include "nc_bias_if.vh"

    wire [3:0] probe_sel = regs[8*A_PROBE +: 4];
    wire       probe_en  = regs[8*A_PROBE+6];
    wire       out_mux   = regs[8*A_MODE+2];
    wire [3:0] rt_en     = regs[8*A_MODE+4 +: 4];
    wire       l_en_a    = regs[8*A_LIF_CTL];
    wire [1:0] l_src     = regs[8*A_LIF_CTL+1 +: 2];

    // ------------------------------------------------------------ probe (row x column)
    // Spike channel k -> array slot (row, col) = floorplan/floorplan.py slot_map()
    // (row 0 = bottom). ch3 (AdEx) and ch13 (D1) are outside the array:
    // probe_sel_adex / probe_sel_d1. Slot (0,3) is a dummy and is never
    // selected. PROBE_SUB = 3 selects the REF follower in slot (0,0) whatever SEL is.
    // Combinational from the latches. Firmware: PROBE_EN=0, change SEL/SUB, PROBE_EN=1.
    reg [1:0] p_row, p_col;
    reg       p_arr;
    always @(*) begin
        p_arr = 1'b1;
        case (probe_sel)
            4'd0:    {p_row, p_col} = {2'd0, 2'd1};   // S1
            4'd1:    {p_row, p_col} = {2'd1, 2'd2};   // F1
            4'd2:    {p_row, p_col} = {2'd0, 2'd2};   // H1
            4'd4:    {p_row, p_col} = {2'd1, 2'd3};   // S2
            4'd5:    {p_row, p_col} = {2'd2, 2'd3};   // F2
            4'd6:    {p_row, p_col} = {2'd1, 2'd0};   // H2
            4'd7:    {p_row, p_col} = {2'd2, 2'd0};   // P2
            4'd8:    {p_row, p_col} = {2'd3, 2'd0};   // S3
            4'd9:    {p_row, p_col} = {2'd3, 2'd1};   // F3
            4'd10:   {p_row, p_col} = {2'd2, 2'd1};   // H3
            4'd11:   {p_row, p_col} = {2'd3, 2'd2};   // P3
            4'd12:   {p_row, p_col} = {2'd1, 2'd1};   // CMP
            4'd14:   {p_row, p_col} = {2'd2, 2'd2};   // AH50
            4'd15:   {p_row, p_col} = {2'd3, 2'd3};   // AH800
            default: begin                             // 3 AdEx, 13 D1: not in the array
                {p_row, p_col} = 4'd0;
                p_arr = 1'b0;
            end
        endcase
        if (probe_sub_raw == 2'd3) begin              // REF follower, slot (0,0)
            {p_row, p_col} = 4'd0;
            p_arr = 1'b1;
        end
    end
    genvar pi;
    generate
        for (pi = 0; pi < 4; pi = pi + 1) begin : g_probe
            assign probe_rsel[pi] = p_arr & (p_row == pi);
            assign probe_en_c[pi] = probe_en & p_arr & (p_col == pi);
        end
    endgenerate
    assign probe_sel_d1   = probe_en & ~p_arr &  probe_sel[3];   // SEL 13
    assign probe_sel_adex = probe_en & ~p_arr & ~probe_sel[3];   // SEL 3
    assign probe_sub    = probe_sub_raw[0];
    assign probe_sub_b  = ~probe_sub_raw[0];

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
