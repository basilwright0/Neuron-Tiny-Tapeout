// nc_spi.v -- oversampled SPI mode-0 slave, 16-bit {RW, ADDR[6:0], DATA[7:0]}.
//
// SCK/MOSI/CS_N pass through 2-flop synchronizers; everything runs on clk.
// * CS_N fall: bit counter cleared.
// * Each synchronized SCK rising edge (CS active, < 16 bits so far) shifts
//   MOSI into in_sr and advances MISO (out_sr) by one bit.
// * After the 8th bit, if RW=1, out_sr is loaded with rdata(ADDR) in the same
//   clk: the addressed byte is returned in bits 7..0 of the SAME frame.
// * After the 16th bit, if RW=0, a 1-clk write pulse (we) is issued with
//   addr/wdata held stable until the next frame (shifting stops at 16 bits).
// Frames shorter than 16 bits never write. Extra SCK edges are ignored.
//
// Timing: f_clk/f_SCK >= 6 (8 recommended); SCK high/low >= 2 clk each;
// MISO valid <= 4 clk after an SCK rising edge; CS_N fall -> first SCK rise
// >= 4 clk; CS_N high between frames >= 4 clk.
`default_nettype none

module nc_spi (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       sck,
    input  wire       mosi,
    input  wire       cs_n,
    output wire [6:0] raddr,      // address for the read mux (valid at rd)
    output wire       rd,         // 1-clk: read of raddr happens now
    input  wire [7:0] rdata,      // combinational read data for raddr
    output wire       miso,
    output reg        we,         // 1-clk write pulse (1 clk after the 16th shift)
    output wire [6:0] waddr,
    output wire [7:0] wdata
);
    wire sck_s, mosi_s, cs_s;
    nc_sync2 #(.W(2), .RST_VAL(0)) u_sync_d (.clk(clk), .rst_n(rst_n), .d({sck, mosi}), .q({sck_s, mosi_s}));
    nc_sync2 #(.W(1), .RST_VAL(1)) u_sync_c (.clk(clk), .rst_n(rst_n), .d(cs_n), .q(cs_s));

    reg        sck_d, cs_d;
    reg [4:0]  bitcnt;
    reg [14:0] in_sr;     // no reset needed: fully shifted before use
    reg [7:0]  out_sr;
    reg        we_pre;

    wire sck_rise = sck_s & ~sck_d;
    wire cs_fall  = ~cs_s & cs_d;
    wire shift    = ~cs_s & ~cs_d & sck_rise & ~bitcnt[4];

    assign raddr = {in_sr[5:0], mosi_s};          // address incl. the 8th bit
    assign rd    = shift & (bitcnt == 5'd7) & in_sr[6];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_d  <= 1'b0;
            cs_d   <= 1'b1;
            bitcnt <= 5'd0;
            out_sr <= 8'd0;
            we     <= 1'b0;
            we_pre <= 1'b0;
        end else begin
            sck_d <= sck_s;
            cs_d  <= cs_s;
            // we is delayed one clk so that waddr/wdata (in_sr) are already
            // stable when the latch enables open: no wrong-address glitch.
            we_pre <= shift & (bitcnt == 5'd15) & ~in_sr[14];
            we     <= we_pre;
            if (cs_fall) begin
                bitcnt <= 5'd0;
                out_sr <= 8'd0;
            end else if (shift) begin
                bitcnt <= bitcnt + 1'b1;
                out_sr <= rd ? rdata : {out_sr[6:0], 1'b0};
            end
        end
    end

    always @(posedge clk) begin
        if (shift) in_sr <= {in_sr[13:0], mosi_s};
    end

    assign miso  = ~cs_d & out_sr[7];
    assign waddr = in_sr[14:8];
    assign wdata = in_sr[7:0];
endmodule

`default_nettype wire
