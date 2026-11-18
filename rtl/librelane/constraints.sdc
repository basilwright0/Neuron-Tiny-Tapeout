# neuron_ctrl rev C.
#   clk : LIF, synchronizers, SC divider.
#   sck : ui_in[0], clocks only the 13-bit config shift register (CTS builds
#         its tree so the shift chain is hold-fixed). Asynchronous to clk.
#   Config latches are enabled by LOAD (ui_in[2]) & address decode: not a
#   clock, their outputs are quasi-static (host contract, docs/regmap.md).
#   ui_in[7:1], spk_in, rst_n are asynchronous (2-FF synchronised on chip or
#   combinational pass-through to pins / analog).
create_clock -name clk -period $::env(CLOCK_PERIOD) [get_ports clk]
create_clock -name sck -period 50 [get_ports {ui_in[0]}]
set_clock_groups -asynchronous -group {clk} -group {sck}
set_clock_uncertainty 0.5 [all_clocks]
set async_in [get_ports {ui_in[1] ui_in[2] ui_in[3] ui_in[4] ui_in[5] ui_in[6] ui_in[7] spk_in[*] rst_n uio_in[*]}]
set_input_delay  4 -clock clk $async_in
set_output_delay 4 -clock clk [all_outputs]
set_false_path -from $async_in
set_load 0.05 [all_outputs]
