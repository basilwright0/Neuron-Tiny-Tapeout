#!/bin/bash
# Boat VM: AH400 without the vr probe tap (user decision 2026-11-21 22:33 UTC), search + final at one row-3 height,
# then self-stop. Usage: bash layout/compact/vm_batch_e.sh <CHAN> <name prefix> <VM id>
#   1.2 c  -> 32.49 um (F/AH50 cx* already clean);  1.8 cz -> 34.29 um (F/AH50 cz* already clean)
cd "$(dirname "$0")/../.."
T=ah400e_$2; rm -f /home/user/${T}_done
CB_W=12 NAME_PREFIX=$2 TAG=$T bash layout/compact/vm_compact.sh "slot_ah_400" "CHAN=$1;CONG=0" 8
bash layout/compact/vm_selfstop.sh "$3" /home/user/${T}_done 300
