// tb.v -- cocotb wrapper around neuron_ctrl rev E (iverilog).
`default_nettype none
`timescale 1ns / 1ps

module tb ();
    initial begin
        $dumpfile("tb.vcd");
        $dumpvars(0, tb);
        #1;
    end

    localparam NTRIM = 16;
    parameter [15:0] TRIM_MASK = 16'hC1FD;   // rev E default; make TRIM_MASK=FFFF for every nibble

    reg          clk;
    reg          rst_n;
    reg  [7:0]   ui_in;
    reg  [7:0]   uio_in;
    reg  [15:0]  spk_in;
    wire [7:0]   uo_out;
    wire [7:0]   uio_out;
    wire [7:0]   uio_oe;
    wire [7+4*NTRIM-1:0] cfg_out;
    wire [3:0]   probe_rsel, probe_en_c;
    wire         probe_sub, probe_sub_b, probe_sel_d1, probe_sel_adex;
    wire [1:0]   probe_sub_raw;
    wire [3:0]   rt_out;

    // the bias_b1 lines are left open here; the tests read them via u_ctrl.<name>
    neuron_ctrl #(.LIF_W(12), .NTRIM(NTRIM), .TRIM_MASK(TRIM_MASK)) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .ui_in(ui_in), .uio_in(uio_in),
        .uo_out(uo_out), .uio_out(uio_out), .uio_oe(uio_oe),
        .spk_in(spk_in), .cfg_out(cfg_out),
        .probe_rsel(probe_rsel), .probe_en_c(probe_en_c), .probe_sub(probe_sub),
        .probe_sub_b(probe_sub_b), .probe_sel_d1(probe_sel_d1), .probe_sel_adex(probe_sel_adex),
        .probe_sub_raw(probe_sub_raw), .rt_out(rt_out)
    );
endmodule

`default_nettype wire
