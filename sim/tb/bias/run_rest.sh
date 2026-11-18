#!/bin/bash
# vdac and trim benches (settling is in run_settle.sh)
cd /work/sim/tb/bias; mkdir -p out/settle out/vdac out/trim
{
for c in tt ff ss fs sf; do for t in 0 27 85; do echo "python3 gen_vdac.py out/vdac/dc_${c}_${t}.cir --corner $c --temp $t && ngspice -b out/vdac/dc_${c}_${t}.cir > out/vdac/dc_${c}_${t}.log 2>&1"; done; done
for v in 2.97 3.63; do echo "python3 gen_vdac.py out/vdac/dc_tt_27_v$v.cir --vdd $v && ngspice -b out/vdac/dc_tt_27_v$v.cir > out/vdac/dc_tt_27_v$v.log 2>&1"; done
for c in tt ss; do echo "python3 gen_vdac.py out/vdac/tran_${c}.cir --corner $c --temp 0 --mode tran && ngspice -b out/vdac/tran_${c}.cir > out/vdac/tran_${c}.log 2>&1"; done
echo "python3 gen_vdac.py out/vdac/reset_tt.cir --mode reset && ngspice -b out/vdac/reset_tt.cir > out/vdac/reset_tt.log 2>&1"
for i in 100p 1n 1u; do for c in tt ff ss fs sf; do for t in 0 27 85; do echo "python3 gen_trim.py out/trim/t_${c}_${t}_${i}.cir --corner $c --temp $t --iref $i --nt 1 && ngspice -b out/trim/t_${c}_${t}_${i}.cir > out/trim/t_${c}_${t}_${i}.log 2>&1"; done; done; done
for i in 100p 1n 1u; do for s in $(seq 1 50); do echo "python3 gen_trim.py out/trim/mc_${i}_$s.cir --seed $s --iref $i --nt 4 && ngspice -b out/trim/mc_${i}_$s.cir > out/trim/mc_${i}_$s.log 2>&1"; done; done
} | xargs -P 8 -I{} bash -c "{}"
python3 analyze_rest.py > out/rest_summary.txt; cat out/rest_summary.txt
