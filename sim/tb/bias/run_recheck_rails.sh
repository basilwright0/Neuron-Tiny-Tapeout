#!/bin/bash
# Rail re-checks (rev B decaps) and settling at 150 pA.  3 jobs at a time (shared machine).
cd /work/sim/tb/bias; mkdir -p out/recheck/rails out/recheck/settle
{
for c in tt ss ff; do for t in 0 27 85; do echo "python3 gen_railchk.py out/recheck/rails/ac_bias_rails_${c}_${t}.cir --corner $c --temp $t --mode ac && ngspice -b out/recheck/rails/ac_bias_rails_${c}_${t}.cir > out/recheck/rails/ac_bias_rails_${c}_${t}.log 2>&1"; done; done
for r in bias_rails_cross bias_rails_nocap; do echo "python3 gen_railchk.py out/recheck/rails/ac_${r}_tt_27.cir --mode ac --rails $r && ngspice -b out/recheck/rails/ac_${r}_tt_27.cir > out/recheck/rails/ac_${r}_tt_27.log 2>&1"; done
for m in tran glitch; do
  for r in bias_rails bias_rails_cross bias_rails_nocap; do echo "python3 gen_railchk.py out/recheck/rails/${m}_${r}_tt_27.cir --mode $m --rails $r && ngspice -b out/recheck/rails/${m}_${r}_tt_27.cir > out/recheck/rails/${m}_${r}_tt_27.log 2>&1"; done
  for ct in "ss 0" "ff 85"; do set -- $ct; echo "python3 gen_railchk.py out/recheck/rails/${m}_bias_rails_$1_$2.cir --mode $m --corner $1 --temp $2 && ngspice -b out/recheck/rails/${m}_bias_rails_$1_$2.cir > out/recheck/rails/${m}_bias_rails_$1_$2.log 2>&1"; done
done
for c in tt ss ff; do echo "python3 gen_settle.py out/recheck/settle/n_${c}_18_19.cir --corner $c && ngspice -b out/recheck/settle/n_${c}_18_19.cir > out/recheck/settle/n_${c}_18_19.log 2>&1"; done
for c in tt ss ff; do echo "python3 gen_settle.py out/recheck/settle/p_${c}_18_19.cir --corner $c --pol p && ngspice -b out/recheck/settle/p_${c}_18_19.cir > out/recheck/settle/p_${c}_18_19.log 2>&1"; done
echo "python3 gen_settle.py out/recheck/settle/n_tt_19_9.cir --c0 19 --c1 9 && ngspice -b out/recheck/settle/n_tt_19_9.cir > out/recheck/settle/n_tt_19_9.log 2>&1"
echo "python3 gen_settle.py out/recheck/settle/n_tt_held.cir --held --tstop 1m && ngspice -b out/recheck/settle/n_tt_held.cir > out/recheck/settle/n_tt_held.log 2>&1"
echo "python3 gen_settle.py out/recheck/settle/p_tt_held.cir --held --pol p --tstop 1m && ngspice -b out/recheck/settle/p_tt_held.cir > out/recheck/settle/p_tt_held.log 2>&1"
echo "python3 gen_settle.py out/recheck/settle/n_tt_cross.cir --rails bias_rails_cross && ngspice -b out/recheck/settle/n_tt_cross.cir > out/recheck/settle/n_tt_cross.log 2>&1"
echo "python3 gen_settle.py out/recheck/settle/n_tt_nocap.cir --rails bias_rails_nocap && ngspice -b out/recheck/settle/n_tt_nocap.cir > out/recheck/settle/n_tt_nocap.log 2>&1"
} | xargs -P 3 -I{} bash -c "{}"
python3 analyze_recheck.py > out/recheck/rails_settle_summary.txt; cat out/recheck/rails_settle_summary.txt
