#!/bin/bash
# Speed track: vsrc / D1 / AdEx / readout queue (one ngspice at a time). Logs in sim/results/speed/*.out
cd /work; O=sim/results/speed
for S in 1000 10000; do for ct in typical:27 ss:0 ff:85 sf:0; do co=${ct%%:*}; t=${ct##*:}
  for n in 1 4 13; do [ -f $O/vsrc_S${S}_n${n}_${co}_${t}_buf.json ] || python3 sim/tb/speed/tb_vsrc.py $S $n $co $t >> $O/vsrc.out 2>&1; done
  [ -f $O/vsrc_S${S}_n13_${co}_${t}_ideal.json ] || python3 sim/tb/speed/tb_vsrc.py $S 13 $co $t ideal >> $O/vsrc.out 2>&1
done; done
for S in 100 1000 10000; do [ -f $O/d1_S${S}.json ] || python3 sim/tb/speed/tb_d1.py $S typical:27,ss:0,ff:85 1 >> $O/d1.out 2>&1; done
for S in 100 1000 10000; do [ -f $O/adex_S${S}.json ] || python3 sim/tb/speed/tb_adex.py $S typical:27,ss:0,ff:85 1 >> $O/adex.out 2>&1; done
[ -f $O/readout.json ] || python3 sim/tb/speed/tb_readout.py 1 > $O/readout.out 2>&1
echo QDONE
for ct in typical:27 ss:0 ff:85; do co=${ct%%:*}; t=${ct##*:}
  for n in 4 13; do [ -f $O/vsrc_S3000_n${n}_${co}_${t}_buf.json ] || python3 sim/tb/speed/tb_vsrc.py 3000 $n $co $t >> $O/vsrc.out 2>&1; done
  [ -f $O/vsrc_S3000_n13_${co}_${t}_ideal.json ] || python3 sim/tb/speed/tb_vsrc.py 3000 13 $co $t ideal >> $O/vsrc.out 2>&1
done
echo QB2DONE
for S in 1000 10000; do [ -f $O/d1_S${S}.json ] || python3 sim/tb/speed/tb_d1.py $S typical:27,ss:0,ff:85 1 >> $O/d1.out 2>&1; done
echo QB3DONE
