// neuron_ctrl.v -- digital control plane (blocks C1 + L1) of the TTGF26c
// analog neuron test chip, rev B (byte-addressed register file).
// See docs/regmap.md for the register map and timing.
//
// Pins (TT naming):
//   ui_in[0] SCK  ui_in[1] MOSI  ui_in[2] CS_N        (SPI mode 0, oversampled)
//   ui_in[3] stim A  ui_in[4] stim B  ui_in[5] hold  ui_in[6] mem reset
//   ui_in[7] counter gate / digital-LIF external step
//   uio[0]   MISO (uio_oe[0]=1); uio[7:1] driven 0 with oe=0
//   uo[3:0]  spikes of neurons SEL0..SEL3     uo[4] OR of enabled neurons
//   uo[5]    digital LIF spike                uo[6] probe-valid (PROBE_EN) / counter window
//   uo[7]    heartbeat
//
// Single clock clk. rst_n: async assert, sync deassert (nc_rst_sync).
`default_nettype none

module neuron_ctrl #(
    parameter NSPK       = 32,  // analog spike inputs (<= 32)
    parameter NPROBE     = 32,  // probe one-hot width (<= 32)
    parameter LIF_W      = 12,  // digital LIF state width (8..12)
    parameter CNT_W      = 16,  // spike counter width (9..16)
    parameter RB_REGS    = 1,   // 1: writable registers are readable over MISO
    parameter STRETCH    = 2,   // stretched-pulse length in clk (>= 2)
    parameter HB_BIT     = 15,  // heartbeat = free_cnt[HB_BIT] (10 MHz -> 153 Hz)
    parameter SETTLE_BIT = 6    // probe-valid after 2^(SB+1)..2^(SB+2) clk (128..256)
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire [7:0]        ui_in,
    input  wire [7:0]        uio_in,
    output wire [7:0]        uo_out,
    output wire [7:0]        uio_out,
    output wire [7:0]        uio_oe,
    input  wire [NSPK-1:0]   spk_in,           // async spikes from analog neurons
    output wire [159:0]      cfg_out,          // register bytes 0x00..0x13 (byte a at [8a+7:8a])
    output reg  [NPROBE-1:0] probe_sel_onehot, // break-before-make one-hot
    output wire [3:0]        rt_out,           // gated ui_in[6:3]
    output reg               sc_clk            // SC-dendrite clock (clk / 2*SC_DIV)
);
`include "nc_regmap.vh"

    localparam FCW = (HB_BIT + 1 > 16) ? HB_BIT + 1 : 16;

    // ------------------------------------------------------------ reset
    wire rstn;
    nc_rst_sync u_rst (.clk(clk), .rst_n_in(rst_n), .rst_n_out(rstn));

    // ------------------------------------------------------------ SPI
    wire       we, rd, miso;
    wire [6:0] waddr, raddr;
    wire [7:0] wdata;
    reg  [7:0] rdata;

    nc_spi u_spi (
        .clk(clk), .rst_n(rstn),
        .sck(ui_in[0]), .mosi(ui_in[1]), .cs_n(ui_in[2]),
        .raddr(raddr), .rd(rd), .rdata(rdata), .miso(miso),
        .we(we), .waddr(waddr), .wdata(wdata)
    );

    // ------------------------------------------------------------ register latches
    // Transparent-high latches with async reset (latrnq, ~48 um2/bit). The
    // enable is AND(we, addr==a): we is a flop output and waddr/wdata are
    // stable while it is high, so each byte changes exactly once per write.
    wire [8*NREG-1:0] regs;
    genvar ri, bi;
    generate
        for (ri = 0; ri < NREG; ri = ri + 1) begin : g_reg
            wire le = we & (waddr == ri);
            for (bi = 0; bi < 8; bi = bi + 1) begin : g_bit
                if (REG_USED[8*ri+bi]) begin : g_l
                    nc_latch u_l (.rst_n(rstn), .en(le), .d(wdata[bi]), .q(regs[8*ri+bi]));
                end else begin : g_0
                    assign regs[8*ri+bi] = 1'b0;
                end
            end
        end
    endgenerate
    assign cfg_out = regs;

    wire       spk_mode = regs[8*A_CTRL+0];
    wire [1:0] cnt_mode = regs[8*A_CTRL+1 +: 2];
    wire [1:0] cnt_src  = regs[8*A_CTRL+3 +: 2];
    wire [3:0] rt_en    = regs[8*A_RT +: 4];
    wire [4:0] sel0     = regs[8*A_SEL0 +: 5];
    wire [4:0] sel1     = regs[8*A_SEL1 +: 5];
    wire [4:0] sel2     = regs[8*A_SEL2 +: 5];
    wire [4:0] sel3     = regs[8*A_SEL3 +: 5];
    wire [4:0] probe_sel= regs[8*A_PROBE +: 5];
    wire       probe_en = regs[8*A_PROBE+7];
    wire [7:0] grp_en   = regs[8*A_GRP +: 8];
    wire [3:0] sc_div   = regs[8*A_SC +: 4];

    // blank spike events for 5 clk after any write (mux re-selection glitches)
    reg [2:0] blank_cnt;
    always @(posedge clk or negedge rstn) begin
        if (!rstn)                 blank_cnt <= 3'd0;
        else if (we)               blank_cnt <= 3'd5;
        else if (blank_cnt != 0)   blank_cnt <= blank_cnt - 1'b1;
    end
    wire blank = (blank_cnt != 3'd0);

    // ------------------------------------------------------------ free counter
    reg [FCW-1:0] free_cnt;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) free_cnt <= {FCW{1'b0}};
        else       free_cnt <= free_cnt + 1'b1;
    end

    // ------------------------------------------------------------ ui sync
    wire ui3_s, ui4_s, ui7_s;
    nc_sync2 #(.W(3)) u_sync_ui (.clk(clk), .rst_n(rstn),
        .d({ui_in[7], ui_in[4], ui_in[3]}), .q({ui7_s, ui4_s, ui3_s}));
    reg ui3_d, ui4_d, ui7_d;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) {ui7_d, ui4_d, ui3_d} <= 3'b000;
        else       {ui7_d, ui4_d, ui3_d} <= {ui7_s, ui4_s, ui3_s};
    end
    wire ui3_rise = ui3_s & ~ui3_d;
    wire ui4_rise = ui4_s & ~ui4_d;
    wire ui7_rise = ui7_s & ~ui7_d;

    assign rt_out = ui_in[6:3] & rt_en;

    // ------------------------------------------------------------ spike channels
    function sel_spk;
        input [NSPK-1:0] s;
        input [4:0]      idx;
        begin
            sel_spk = ({27'd0, idx} < NSPK) ? s[idx] : 1'b0;
        end
    endfunction

    localparam GSZ = (NSPK + 7) / 8;
    wire [NSPK-1:0] en_mask;
    genvar gi;
    generate
        for (gi = 0; gi < NSPK; gi = gi + 1) begin : g_mask
            assign en_mask[gi] = grp_en[gi / GSZ];
        end
    endgenerate

    // ch 0..3 = SEL0..3, ch 4 = OR of enabled, ch 5 = digital LIF (sync)
    wire [5:0] ch_spk;
    assign ch_spk[0] = sel_spk(spk_in, sel0);
    assign ch_spk[1] = sel_spk(spk_in, sel1);
    assign ch_spk[2] = sel_spk(spk_in, sel2);
    assign ch_spk[3] = sel_spk(spk_in, sel3);
    assign ch_spk[4] = |(spk_in & en_mask);
    assign ch_spk[5] = 1'b0;

    wire [5:0] ch_ev, ch_out;
    wire       lif_spike;
    genvar ci;
    generate
        for (ci = 0; ci < 6; ci = ci + 1) begin : g_ch
            nc_spk_chan #(.SYNC_IN(ci == 5 ? 1 : 0), .STRETCH(STRETCH)) u_ch (
                .clk(clk), .rst_n(rstn),
                .spk(ch_spk[ci]), .ev_in(ci == 5 ? lif_spike : 1'b0),
                .blank(blank), .mode(spk_mode),
                .event_o(ch_ev[ci]), .out(ch_out[ci])
            );
        end
    endgenerate

    // ------------------------------------------------------------ probe one-hot (BBM)
    // Registered binary select psel_q + enable pen_q. On a change: pen_q drops
    // (break), psel_q updates while all outputs are 0, then pen_q rises (make)
    // => 2 clk all-off. Outputs = AND(pen_q, decode(psel_q)), glitch-free.
    wire       pen_next = probe_en && ({27'd0, probe_sel} < NPROBE);
    reg  [4:0] psel_q;
    reg        pen_q, sb_d, s1, s2;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin
            psel_q <= 5'd0;
            pen_q  <= 1'b0;
            sb_d   <= 1'b0;
            s1     <= 1'b0;
            s2     <= 1'b0;
        end else begin
            if (pen_q) begin
                if (psel_q != probe_sel || !pen_next) pen_q <= 1'b0;
            end else begin
                psel_q <= probe_sel;
                pen_q  <= pen_next && (psel_q == probe_sel);
            end
            sb_d <= free_cnt[SETTLE_BIT];
            if (!pen_q || (we && waddr == A_PROBE)) begin
                s1 <= 1'b0;
                s2 <= 1'b0;
            end else if (free_cnt[SETTLE_BIT] & ~sb_d) begin
                s1 <= 1'b1;
                s2 <= s1;
            end
        end
    end
    always @(*) begin
        probe_sel_onehot = {NPROBE{1'b0}};
        probe_sel_onehot[psel_q] = pen_q;
    end
    wire probe_valid = pen_q & s2;

    // ------------------------------------------------------------ spike counter
    reg  [CNT_W-1:0] cnt;
    reg              cnt_sat;
    reg              cnt_ev;
    always @(*) begin
        case (cnt_src)
            2'd0:    cnt_ev = ch_ev[0];
            2'd1:    cnt_ev = ch_ev[4];
            2'd2:    cnt_ev = lif_spike;
            default: cnt_ev = ui3_rise;
        endcase
    end
    wire cnt_gate = (cnt_mode == 2'd1) | (cnt_mode[1] & ui7_s);
    always @(posedge clk or negedge rstn) begin
        if (!rstn) begin
            cnt     <= {CNT_W{1'b0}};
            cnt_sat <= 1'b0;
        end else if (cnt_mode == 2'd0 || (cnt_mode == 2'd3 && ui7_rise)) begin
            cnt     <= {CNT_W{1'b0}};
            cnt_sat <= 1'b0;
        end else if (cnt_gate && cnt_ev) begin
            if (&cnt) cnt_sat <= 1'b1;
            else      cnt <= cnt + 1'b1;
        end
    end
    wire [15:0] cnt16 = {{(16-CNT_W){1'b0}}, cnt};

    // ------------------------------------------------------------ digital LIF
    wire [7:0]  lif0    = regs[8*A_LIF0 +: 8];
    wire [7:0]  lif1    = regs[8*A_LIF1 +: 8];
    wire        l_en    = lif0[0];
    wire [1:0]  l_src   = lif0[2:1];
    wire        l_step  = lif0[3];
    wire [3:0]  l_presc = lif0[7:4];
    wire [15:0] pmask   = ~(16'hFFFF << l_presc);
    wire        l_tick  = l_step ? ui7_rise : (&(free_cnt[15:0] | ~pmask));
    reg         l_in;
    always @(*) begin
        case (l_src)
            2'd0:    l_in = ui3_rise;
            2'd1:    l_in = ui4_rise;
            2'd2:    l_in = 1'b0;
            default: l_in = ch_ev[0];
        endcase
    end
    // 8-bit codes: EL/VTH/VRST scaled to the MSBs of the W-bit state, W in LSBs
    /* verilator lint_off UNUSEDSIGNAL */  // low bits unused when LIF_W < 12
    wire [11:0] el12  = {regs[8*A_LIF_EL +: 8],   4'b0};
    wire [11:0] vth12 = {regs[8*A_LIF_VTH +: 8],  4'b0};
    wire [11:0] vrs12 = {regs[8*A_LIF_VRST +: 8], 4'b0};
    wire [11:0] w12   = {4'b0, regs[8*A_LIF_W +: 8]};
    /* verilator lint_on UNUSEDSIGNAL */

    wire [LIF_W-1:0] lif_v;
    wire [3:0]       lif_ref;
    wire             lif_pend, lif_busy;

    digital_lif #(.W(LIF_W), .RW(4)) u_lif (
        .clk(clk), .rst_n(rstn), .en(l_en), .tick(l_tick),
        .in_ev(l_in), .dc(l_src == 2'd2),
        .el  (el12 [11 -: LIF_W]),
        .vth (vth12[11 -: LIF_W]),
        .vrst(vrs12[11 -: LIF_W]),
        .wgt (w12[LIF_W-1:0]),
        .shift(lif1[3:0]),
        .refr (lif1[7:4]),
        .spike(lif_spike), .v(lif_v), .ref_cnt(lif_ref),
        .pending(lif_pend), .busy(lif_busy)
    );
    wire [11:0] v12 = {{(12-LIF_W){1'b0}}, lif_v};

    // ------------------------------------------------------------ SC clock divider
    // sc_clk = clk / 2^SC_DIV (SC_DIV = 1..15 uses free_cnt[SC_DIV-1]; 0 = off),
    // re-registered so it is a clean flop output.
    always @(posedge clk or negedge rstn) begin
        if (!rstn)              sc_clk <= 1'b0;
        else if (sc_div == 4'd0) sc_clk <= 1'b0;
        else                    sc_clk <= free_cnt[sc_div - 1'b1];
    end

    // ------------------------------------------------------------ read mux + hold
    reg [7:0] hold;
    always @(posedge clk or negedge rstn) begin
        if (!rstn) hold <= 8'd0;
        else if (rd && raddr == A_CNT_L)  hold <= cnt16[15:8];
        else if (rd && raddr == A_LIFV_L) hold <= {lif_ref, v12[11:8]};
    end
    integer k;
    reg [7:0] rd_regs;
    always @(*) begin
        rd_regs = 8'h00;
        for (k = 0; k < NREG; k = k + 1)
            if ({25'd0, raddr} == k) rd_regs = regs[8*k +: 8];
    end
    wire [7:0] status = {cnt_gate, cnt_sat, probe_valid, l_en, lif_pend, lif_busy, 2'b00};
    always @(*) begin
        case (raddr)
            A_CNT_L:  rdata = cnt16[7:0];
            A_CNT_H:  rdata = hold;
            A_LIFV_L: rdata = v12[7:0];
            A_LIFV_H: rdata = hold;
            A_STATUS: rdata = status;
            A_ID:     rdata = CHIP_ID;
            default:  rdata = (RB_REGS != 0) ? rd_regs : 8'h00;
        endcase
    end

    // ------------------------------------------------------------ outputs
    wire heartbeat = free_cnt[HB_BIT];
    assign uo_out  = {heartbeat, probe_en ? probe_valid : cnt_gate, ch_out[5:0]};
    assign uio_out = {7'b0, miso};
    assign uio_oe  = 8'b0000_0001;

    wire _unused = &{1'b0, uio_in, ch_ev[5], ch_ev[3:1], 1'b0};
endmodule

`default_nettype wire
