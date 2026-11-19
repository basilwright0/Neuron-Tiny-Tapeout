#!/bin/bash
# rev B rails with the final 10 um decaps: re-run the tt rail checks + p settling (ss)
cd /work/sim/tb/bias; mkdir -p out/recheck/rails out/recheck/settle
{
for m in ac tran glitch; do for ct in "tt 27" "ss 0" "ff 85"; do set -- $ct
  echo "python3 gen_railchk.py out/recheck/rails/${m}_bias_rails_$1_$2.cir --mode $m --corner $1 --temp $2 && ngspice -b out/recheck/rails/${m}_bias_rails_$1_$2.cir > out/recheck/rails/${m}_bias_rails_$1_$2.log 2>&1"; done; done
for c in tt ss ff; do echo "python3 gen_settle.py out/recheck/settle/n_${c}_18_19.cir --corner $c && ngspice -b out/recheck/settle/n_${c}_18_19.cir > out/recheck/settle/n_${c}_18_19.log 2>&1"; done
for c in tt ss ff; do echo "python3 gen_settle.py out/recheck/settle/p_${c}_18_19.cir --corner $c --pol p && ngspice -b out/recheck/settle/p_${c}_18_19.cir > out/recheck/settle/p_${c}_18_19.log 2>&1"; done
} | xargs -P 3 -I{} bash -c "{}"
python3 analyze_recheck.py > out/recheck/rails_settle_summary.txt; cat out/recheck/rails_settle_summary.txt
