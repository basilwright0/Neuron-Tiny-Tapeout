#!/bin/bash
# B1 rev C transients (bias_b1): BIAS_EN 0->1 at 10 us (startup), resistor-DAC codes 0->31 at 60 us,
# vth_ref 0->63 at 80 us; 2 pF on each voltage output.  -> out/revc/tran_<corner>_<T>.dat
cd /work/sim/tb/bias; mkdir -p out/revc
printf '%s\n' "tt 27" "ss 0" "ff 85" | xargs -P ${J:-1} -L 1 bash -c '
  f=out/revc/tran_$0_$1; python3 gen_revc.py $f.cir tran --corner $0 --temp $1 --irefs 1e-6
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
python3 analyze_tran.py
