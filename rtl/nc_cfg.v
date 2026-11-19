// nc_cfg.v -- rev C/E write-only configuration port of neuron_ctrl (shift register + latch-enable decode).
//
// SCK (rising edge) shifts DATA into a 13-bit shift register, MSB first:
// frame = {ADDR[4:0], DATA[7:0]}. Only the last 13 bits before LOAD count.
// LOAD = 1 opens the byte latch bank ADDR (transparent-high latrnq); LOAD
// falling closes it. Timing contract (host): no SCK edge from t_su before
// LOAD rises until t_h after LOAD falls, so the address decode and the
// latch D inputs are static whenever any latch enable can be 1:
//      le[a] = LOAD & (sr[12:8] == a)
// is then a single clean pulse on exactly one byte (glitch-free: an AND of
// a static decode with one pin). echo = sr[12] (serial out, link check).
// No clk anywhere in this block. The latch banks themselves are instantiated
// in neuron_ctrl (so their Q pins drive cfg_out directly, without a
// feed-through buffer after flattening); they reset asynchronously from rst_n.
`default_nettype none

module nc_cfg (
    input  wire                  sck,
    input  wire                  sdi,
    input  wire                  load,
    output wire [22:0]           le,       // latch enable per byte address (width = NREG)
    output wire [7:0]            data,     // frame DATA field -> latch D inputs
    output wire                  echo
);
`include "nc_regmap.vh"

    // shift register: no reset, content is don't-care until a frame is in
    reg [FW-1:0] sr;
    always @(posedge sck) sr <= {sr[FW-2:0], sdi};
    wire [AW-1:0] f_addr = sr[FW-1:8];
    assign data = sr[7:0];
    assign echo = sr[FW-1];

    genvar ri;
    generate
        for (ri = 0; ri < NREG; ri = ri + 1) begin : g_le
            assign le[ri] = load & (f_addr == ri);
        end
    endgenerate
endmodule

`default_nettype wire
