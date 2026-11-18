# neuron_ctrl: single synchronous clock; all ui_in/spk_in are asynchronous.
create_clock -name clk -period $::env(CLOCK_PERIOD) [get_ports clk]
set_clock_uncertainty 0.5 [get_clocks clk]
set non_clk [delete_from_list [all_inputs] [get_ports clk]]
set_input_delay  4 -clock clk $non_clk
set_output_delay 4 -clock clk [all_outputs]
# asynchronous inputs (2-FF synchronised on chip), spike-clocked toggle flops
set_false_path -from [get_ports {ui_in[*] spk_in[*] rst_n uio_in[*]}]
set_load 0.05 [all_outputs]
