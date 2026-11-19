#!/bin/bash
# B1 rev C DC suite: current DACs (S = 10/100/1000 via Iref, /1 and /16, internal reference) and the
# voltage path (Iref sweep 0..10 uA at tt; one Iref at the other corners) over corners x temperature.
# Skips runs whose log already has results.  -> out/revc/
cd /work/sim/tb/bias; mkdir -p out/revc
J=${J:-2}
jobs=()
for c in tt ss ff fs sf; do for t in 0 27 85; do
  jobs+=("idac $c $t 0 1e-7,1e-6,1e-5")
  if [ $c = tt ]; then jobs+=("vout $c $t 0 0,1e-7,1e-6,1e-5"); else jobs+=("vout $c $t 0 1e-6"); fi
done; done
for c in tt ss ff; do
  jobs+=("idac $c 27 1 1.6e-6,1.6e-5,1.6e-4")
  jobs+=("idac $c 27 2 0")
done
printf '%s\n' "${jobs[@]}" | xargs -P $J -L 1 bash -c '
  f=out/revc/$0_$1_$2_m$3; grep -qE "^(D .* 31|V .* 63) " $f.log 2>/dev/null && exit 0
  python3 gen_revc.py $f.cir $0 --corner $1 --temp $2 --mode $3 --irefs $4 --codes 0,1,2,4,8,15,16,31
  ngspice -b $f.cir > $f.log 2>&1 || echo FAIL $f'
for v in 2.97 3.63; do
  f=out/revc/vout_tt_27_vdd$v; python3 gen_revc.py $f.cir vout --vdd $v --irefs 1e-6; ngspice -b $f.cir > $f.log 2>&1
done
echo DONE
