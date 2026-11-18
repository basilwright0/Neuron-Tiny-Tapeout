// nc_spk_chan.v -- spike capture + output stage for one uo_out line.
//
// Async input (SYNC_IN=0): the selected spike line clocks a toggle flop
// (tog <= ~tog on every rising edge), so a pulse of any width above the
// flop's minimum clock pulse width (~1 ns in gf180 7t) is never lost. tog is
// brought into clk with a 2-flop synchronizer; XOR against the previous
// synchronized value gives one clk-domain event per spike. Metastability is
// confined to the first synchronizer flop; a late resolution only delays the
// event by one clk (latency 2-3 clk, jitter 1 clk). Two spikes closer than
// ~2 clk cancel in the toggle domain, so the countable rate is <= f_clk/3.
//
// Sync input (SYNC_IN=1): ev_in is already a 1-clk pulse in the clk domain;
// the toggle flop is then clocked by clk.
//
// mode: 0 stretched pulse (STRETCH clk, synchronous; not blanked, so a
//         selection write can show one spurious pulse -- events are blanked)
//       1 raw toggle flop (async path, no synchronizer latency)
`default_nettype none

module nc_spk_chan #(
    parameter SYNC_IN = 0,
    parameter STRETCH = 2          // clk cycles, >= 2
) (
    input  wire clk,
    input  wire rst_n,
    /* verilator lint_off UNUSEDSIGNAL */
    input  wire spk,               // async spike (SYNC_IN=0)
    input  wire ev_in,             // sync pulse  (SYNC_IN=1)
    input  wire blank,             // suppress events (selection just changed)
    /* verilator lint_on UNUSEDSIGNAL */
    input  wire mode,
    output wire event_o,           // 1-clk event in clk domain
    output wire out
);
    wire ev, tog, tog_c;   // tog_c: toggle in the clk domain
    reg [STRETCH-1:0] dl;  // delay line of tog_c

    generate
        if (SYNC_IN == 0) begin : g_async
            reg tog_a;
            always @(posedge spk or negedge rst_n) begin
                if (!rst_n) tog_a <= 1'b0;
                else        tog_a <= ~tog_a;
            end
            wire tog_s;
            nc_sync2 #(.W(1)) u_sync (.clk(clk), .rst_n(rst_n), .d(tog_a), .q(tog_s));
            assign ev    = (tog_s ^ dl[0]) & ~blank;   // dl[0] = tog_s delayed 1 clk
            assign tog   = tog_a;
            assign tog_c = tog_s;
        end else begin : g_sync
            reg tog_r;
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)     tog_r <= 1'b0;
                else if (ev_in) tog_r <= ~tog_r;
            end
            assign ev    = ev_in;
            assign tog   = tog_r;
            assign tog_c = tog_r;
        end
    endgenerate

    // Stretch by a delay line on the (synchronized) toggle: out = tog_s ^ tog_s
    // delayed by STRETCH clk -> a STRETCH-clk pulse per spike, using STRETCH-1
    // flops beyond the edge detector (cheaper than a counter).
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) dl <= {STRETCH{1'b0}};
        else        dl <= {dl[STRETCH-2:0], tog_c};
    end
    wire str_o = tog_c ^ dl[STRETCH-1];

    assign out     = mode ? tog : str_o;
    assign event_o = ev;
endmodule

`default_nettype wire
