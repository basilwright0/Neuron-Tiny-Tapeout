#!/bin/bash
# Speed track: D1 re-run (axial bias scaled with S) and vsrc at S = 3000 (same items as the tail of queue_b.sh).
cd /work; O=sim/results/speed
for S in 1000 10000; do [ -f $O/d1_S${S}.json ] || python3 sim/tb/speed/tb_d1.py $S typical:27,ss:0,ff:85 1 >> $O/d1.out 2>&1; done
for ct in typical:27 ss:0 ff:85; do co=${ct%%:*}; t=${ct##*:}
  for n in 4 13; do [ -f $O/vsrc_S3000_n${n}_${co}_${t}_buf.json ] || python3 sim/tb/speed/tb_vsrc.py 3000 $n $co $t >> $O/vsrc.out 2>&1; done
  [ -f $O/vsrc_S3000_n13_${co}_${t}_ideal.json ] || python3 sim/tb/speed/tb_vsrc.py 3000 13 $co $t ideal >> $O/vsrc.out 2>&1
done
echo QCDONE
