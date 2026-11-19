#!/bin/bash
# rev B DC regression: idac LSB/monotonicity at 9 corners (Vout 1 V), vdac DC at 15 corners + VDD +-10 %, vdac transient
cd /work/sim/tb/bias; mkdir -p out/corners out/vdac
{
for c in tt ff ss; do for t in 0 27 85; do echo "f=out/corners/idac_${c}_${t}_1.0; python3 gen_idac.py \$f.cir --corner $c --temp $t --vout 1.0 && ngspice -b \$f.cir > \$f.log 2>&1"; done; done
for c in tt ff ss fs sf; do for t in 0 27 85; do echo "python3 gen_vdac.py out/vdac/dc_${c}_${t}.cir --corner $c --temp $t && ngspice -b out/vdac/dc_${c}_${t}.cir > out/vdac/dc_${c}_${t}.log 2>&1"; done; done
for v in 2.97 3.63; do echo "python3 gen_vdac.py out/vdac/dc_tt_27_v$v.cir --vdd $v && ngspice -b out/vdac/dc_tt_27_v$v.cir > out/vdac/dc_tt_27_v$v.log 2>&1"; done
for c in tt ss; do echo "python3 gen_vdac.py out/vdac/tran_${c}.cir --corner $c --temp 0 --mode tran && ngspice -b out/vdac/tran_${c}.cir > out/vdac/tran_${c}.log 2>&1"; done
} | xargs -P 1 -I{} bash -c "{}"
rm -f out/corners/idac_*_2.5.log out/corners/idac_*_0.5.log out/corners/idac_fs_* out/corners/idac_sf_*
python3 analyze_idac.py out/corners > out/recheck/idac_corners_revB.txt
python3 analyze_rest.py 2>/dev/null | sed -n '/vdac DC/,/trim4_p: gain/p' > out/recheck/vdac_revB.txt
cat out/recheck/idac_corners_revB.txt out/recheck/vdac_revB.txt
