#!/bin/bash
# rev B2 (ESD 1k + clamps, ib_x2, vbp_syn/vbn_ax allocation): UA0 modes / pad voltage, vdac DC + transient
cd /work/sim/tb/bias; mkdir -p out/recheck out/vdac
bash run_recheck_div.sh > /dev/null
{
for c in tt ff ss fs sf; do for t in 0 27 85; do echo "python3 gen_vdac.py out/vdac/dc_${c}_${t}.cir --corner $c --temp $t && ngspice -b out/vdac/dc_${c}_${t}.cir > out/vdac/dc_${c}_${t}.log 2>&1"; done; done
for v in 2.97 3.63; do echo "python3 gen_vdac.py out/vdac/dc_tt_27_v$v.cir --vdd $v && ngspice -b out/vdac/dc_tt_27_v$v.cir > out/vdac/dc_tt_27_v$v.log 2>&1"; done
for c in tt ss; do echo "python3 gen_vdac.py out/vdac/tran_${c}.cir --corner $c --temp 0 --mode tran && ngspice -b out/vdac/tran_${c}.cir > out/vdac/tran_${c}.log 2>&1"; done
} | xargs -P 1 -I{} bash -c "{}"
python3 analyze_rest.py 2>/dev/null | sed -n '/vdac DC/,/trim4_p: gain/p' > out/recheck/vdac_revB.txt
cat out/recheck/div_summary.txt out/recheck/vdac_revB.txt
