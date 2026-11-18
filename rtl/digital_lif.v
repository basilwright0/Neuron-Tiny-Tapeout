// digital_lif.v -- fixed-point leaky integrate-and-fire reference neuron,
// bit-serial datapath (LSB first, three 1-bit full adders, no barrel shifter).
//
// Per update tick (same ordering as model/reference.py LIF.simulate):
//   if ref > 0:   V <= Vreset, ref <= ref - 1               (no integration, no spike)
//   else:         Vn = sat( V + ((EL - V) >>> SHIFT) + I_in )
//                 if Vn >= Vth: spike, V <= Vreset, ref <= REFR
//                 else          V <= Vn
// I_in = W if an input pulse arrived since the previous tick (or every tick in
// DC mode), else 0; at most one weight per tick. '>>>' floors. sat() clamps
// to [0, 2^W-1] (Vn >= 0 always holds, and a saturated Vn is >= Vth, so
// overflow simply forces a spike). Linear equivalent:
//   a = 1 - 2^-SHIFT (= exp(-dt/tau)),  V_inf = EL + I_in * 2^SHIFT.
//
// Sequencing after an accepted tick (DW = W+2 bit datapath):
//   P1  DW clk : D = EL - V        serial subtract, V rotates back to itself
//   SH  s+1 clk: D = D >>> 1       arithmetic shift in the D shift register
//   P2  DW clk : Vn = D + V + I    two serial adders; Vn shifts into V, the
//                                  Vn >= Vth compare runs bit-serially
//   WB  1 clk  : spike / reset to Vreset
// Busy for 2*DW + SHIFT + 3 clk (<= 46 at W=12). Ticks that arrive while busy
// are dropped, so space ticks (rev C: ui_in[7] rising edges) >= 2W+SHIFT+7 clk.
// While en = 0 (and on the first clk after en rises) V = EL, ref = 0.
`default_nettype none

module digital_lif #(
    parameter W  = 12,      // state width, 8..12
    parameter RW = 4        // refractory counter width
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          en,
    input  wire          tick,       // update request (1-clk pulse)
    input  wire          in_ev,      // input spike (1-clk pulse, clk domain)
    input  wire          dc,         // 1: add weight on every tick
    input  wire [W-1:0]  el,
    input  wire [W-1:0]  vth,
    input  wire [W-1:0]  vrst,
    input  wire [W-1:0]  wgt,
    input  wire [3:0]    shift,
    input  wire [RW-1:0] refr,
    output reg           spike,      // 1-clk pulse at write-back
    output reg  [W-1:0]  v,
    output reg  [RW-1:0] ref_cnt,
    output reg           pending,
    output wire          busy
);
    localparam DW = W + 2;
    localparam S_IDLE = 3'd0, S_P1 = 3'd1, S_SH = 3'd2, S_P2 = 3'd3, S_WB = 3'd4;
    localparam integer ILASTI = DW - 1;
    localparam [3:0]   ILAST  = ILASTI[3:0];

    reg  [2:0]    st;
    reg  [3:0]    i;          // bit index in P1/P2, shift count in SH
    reg  [DW-1:0] d;          // no reset: fully written in P1 before use
    reg           c1, c2;     // serial carries
    reg           inp_q, ge, ovf, en_q;

    wire in_v  = ({28'd0, i} < W);          // bit index inside the W-bit state
    /* verilator lint_off WIDTHTRUNC */
    /* verilator lint_off UNUSEDSIGNAL */
    wire [3:0] ib = in_v ? i : 4'd0;       // safe index for the parameter muxes
    wire vb    = in_v & v[0];
    wire elb   = in_v & el[ib];
    wire vthb  = in_v & vth[ib];
    wire wb    = in_v & inp_q & wgt[ib];
    /* verilator lint_on UNUSEDSIGNAL */
    /* verilator lint_on WIDTHTRUNC */

    // P1: EL + ~V + 1  (c1 starts at 1)
    wire s1    = elb ^ ~vb ^ c1;
    wire s1c   = (elb & ~vb) | (elb & c1) | (~vb & c1);
    // P2: (D + V) + Wb
    wire t     = d[0] ^ vb ^ c1;
    wire tc    = (d[0] & vb) | (d[0] & c1) | (vb & c1);
    wire r     = t ^ wb ^ c2;
    wire rc    = (t & wb) | (t & c2) | (wb & c2);

    wire start = (st == S_IDLE) & tick & (ref_cnt == {RW{1'b0}});

    // datapath shift register D on a gated clock (no hold mux, no reset)
    wire d_en = (st == S_P1) | (st == S_P2) | ((st == S_SH) & (i != 4'd0));
    wire d_clk;
    nc_cg u_cg (.clk(clk), .en(d_en), .gclk(d_clk));
    always @(posedge d_clk) begin
        if (st == S_P1)      d <= {s1, d[DW-1:1]};
        else if (st == S_SH) d <= {d[DW-1], d[DW-1:1]};
        else                 d <= {1'b0, d[DW-1:1]};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_q    <= 1'b0;
            st      <= S_IDLE;
            i       <= 4'd0;
            c1      <= 1'b0;
            c2      <= 1'b0;
            inp_q   <= 1'b0;
            ge      <= 1'b0;
            ovf     <= 1'b0;
            v       <= {W{1'b0}};
            ref_cnt <= {RW{1'b0}};
            spike   <= 1'b0;
            pending <= 1'b0;
        end else begin
            en_q  <= en;
            spike <= 1'b0;
            if (!en || !en_q) begin
                st      <= S_IDLE;
                v       <= el;
                ref_cnt <= {RW{1'b0}};
                pending <= 1'b0;
            end else begin
                if (in_ev && !(st == S_IDLE && tick)) pending <= 1'b1;
                case (st)
                    S_IDLE: if (tick) begin
                        pending <= 1'b0;
                        if (!start) begin                 // refractory tick
                            v       <= vrst;
                            ref_cnt <= ref_cnt - 1'b1;
                        end else begin
                            inp_q <= dc | pending | in_ev;
                            i     <= 4'd0;
                            c1    <= 1'b1;
                            st    <= S_P1;
                        end
                    end
                    S_P1: begin
                        c1 <= s1c;
                        if (in_v) v <= {v[0], v[W-1:1]};  // rotate back
                        if (i == ILAST) begin
                            i  <= shift;
                            st <= S_SH;
                        end else begin
                            i <= i + 1'b1;
                        end
                    end
                    S_SH: begin
                        if (i != 4'd0) begin
                            i <= i - 1'b1;
                        end else begin
                            c1  <= 1'b0;
                            c2  <= 1'b0;
                            ge  <= 1'b1;
                            ovf <= 1'b0;
                            st  <= S_P2;
                        end
                    end
                    S_P2: begin
                        c1 <= tc;
                        c2 <= rc;
                        if (in_v) begin
                            v <= {r, v[W-1:1]};               // Vn shifts in
                            if (r != vthb) ge <= r;           // LSB-first compare
                        end else if (r) begin
                            ovf <= 1'b1;
                        end
                        if (i == ILAST) st <= S_WB;
                        else            i  <= i + 1'b1;
                    end
                    default: begin                            // S_WB
                        if (ge | ovf) begin
                            spike   <= 1'b1;
                            v       <= vrst;
                            ref_cnt <= refr;
                        end
                        st <= S_IDLE;
                    end
                endcase
            end
        end
    end

    assign busy = (st != S_IDLE);
endmodule

`default_nettype wire
