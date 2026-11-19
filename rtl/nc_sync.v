// nc_sync.v -- synchronizers, reset bridge, latch and clock-gate cells for neuron_ctrl.
`default_nettype none

// 2-flop synchronizer. Async reset to RST_VAL.
module nc_sync2 #(
    parameter W       = 1,
    parameter RST_VAL = 0
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [W-1:0] d,
    output wire [W-1:0] q
);
    reg [W-1:0] s1, s2;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s1 <= {W{RST_VAL[0]}};
            s2 <= {W{RST_VAL[0]}};
        end else begin
            s1 <= d;
            s2 <= s1;
        end
    end
    assign q = s2;
endmodule

// Reset bridge: asynchronous assert, synchronous (2-flop) deassert.
module nc_rst_sync (
    input  wire clk,
    input  wire rst_n_in,
    output wire rst_n_out
);
    reg r1, r2;
    always @(posedge clk or negedge rst_n_in) begin
        if (!rst_n_in) begin
            r1 <= 1'b0;
            r2 <= 1'b0;
        end else begin
            r1 <= 1'b1;
            r2 <= r1;
        end
    end
    assign rst_n_out = r2;
endmodule

// Transparent-high latch with async active-low reset (maps to latrnq_1).
module nc_latch (
    input  wire rst_n,
    input  wire en,
    input  wire d,
    output wire q
);
`ifdef NC_GF180_CELLS
    // Q drives the port net directly (no alias -> no feed-through buffer)
    gf180mcu_fd_sc_mcu7t5v0__latrnq_1 u_lat (.D(d), .E(en), .RN(rst_n), .Q(q));
`else
    reg ql;
    always @(*) begin
        if (!rst_n)  ql = 1'b0;
        else if (en) ql = d;
    end
    assign q = ql;
`endif
endmodule

// Clock gate: gclk = clk & en, en latched while clk is low (glitch-free).
module nc_cg (
    input  wire clk,
    input  wire en,
    output wire gclk
);
`ifdef NC_GF180_CELLS
    gf180mcu_fd_sc_mcu7t5v0__icgtp_1 u_icg (.CLK(clk), .E(en), .TE(1'b0), .Q(gclk));
`else
    reg en_l;
    always @(*) if (!clk) en_l = en;
    assign gclk = clk & en_l;
`endif
endmodule

`default_nettype wire
