// tb.v -- cocotb wrapper around neuron_ctrl rev C (iverilog).
`default_nettype none
`timescale 1ns / 1ps

module tb ();
    initial begin
        $dumpfile("tb.vcd");
        $dumpvars(0, tb);
        #1;
    end

    localparam NTRIM = 16;

    reg          clk;
    reg          rst_n;
    reg  [7:0]   ui_in;
    reg  [7:0]   uio_in;
    reg  [15:0]  spk_in;
    wire [7:0]   uo_out;
    wire [7:0]   uio_out;
    wire [7:0]   uio_oe;
    wire [78+4*NTRIM-1:0] cfg_out;
    wire [15:0]  probe_sel_onehot;
    wire [3:0]   rt_out;
    wire         sc_clk;

    neuron_ctrl #(.LIF_W(12), .NTRIM(NTRIM)) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .ui_in(ui_in), .uio_in(uio_in),
        .uo_out(uo_out), .uio_out(uio_out), .uio_oe(uio_oe),
        .spk_in(spk_in), .cfg_out(cfg_out),
        .probe_sel_onehot(probe_sel_onehot), .rt_out(rt_out), .sc_clk(sc_clk)
    );
endmodule

`default_nettype wire
