#!/bin/bash
# MIL-319 main job (in the EDA container): full-chip S = 10000 transient of one corner, with the CMP Monte Carlo
# (DAC MC of this job's MC corners, then mc_cmp.py) as a 1-core sidecar that stops once the transient is done and
# every MC corner has MC_NMIN dies.   usage: m319_job.sh <corner> <T> <MC corners> [icur]
cd /work
mkdir -p sim/results/m3mc sim/results/top
STOP=/work/sim/results/m3mc/chip_done_$1
rm -f $STOP
( timeout 130m nice -n 5 python3 sim/tb/top/tb_top_s10k.py $1 $2 > sim/results/top/s10k_$1_$2.log 2>&1
  echo "chip rc=$?" >> sim/results/top/s10k_$1_$2.log; touch $STOP ) &
CH=$!
TAG=${3//,/_}
nice -n 15 python3 sim/tb/speed/mc_vdac_vc.py 60 $3 > sim/results/m3mc/vdac_mc_$TAG.txt 2>&1
if [ "$4" = icur ]; then
  ICUR_CASES=S10000 timeout 40m nice -n 10 python3 sim/tb/top/tb_top_icur.py $1 $2 > sim/results/top/icur_S10000_$1_$2.log 2>&1 &&
  timeout 20m nice -n 10 python3 sim/tb/top/pgrid.py /work/sim/results/top/icur_S10000_$1_$2.json S10000_ibx2 \
    > sim/results/top/pgrid_S10000_$1_$2.log 2>&1
fi
for i in $(seq 60); do [ -s sim/results/m3mc/vdac_vc_mc_$TAG.json ] && break; sleep 10; done
MC_STOP=$STOP MC_NMIN=${MC_NMIN:-20} MC_NMAX=${MC_NMAX:-60} MC_TMAX=${MC_TMAX:-7800} \
  nice -n 15 python3 sim/tb/speed/mc_cmp.py $3 > sim/results/m3mc/mc_$TAG.log 2>&1
wait $CH
python3 sim/tb/speed/mc_cmp_sum.py > /dev/null 2>&1
tail -3 sim/results/m3mc/mc_$TAG.log; tail -40 sim/results/top/s10k_$1_$2.log
