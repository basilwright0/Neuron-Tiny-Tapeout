#!/bin/bash
# Boat VM batches for M2 layout B with AH400 (MIL-127 N11, 2026-11-21): row 3 at 32.49 um.
# Usage: bash layout/compact/vm_batch_c.sh ah400|row3
#   ah400: compact AH400 (cap row NC at 7.07, CHAN 1.2 -> H 32.49): search + final -> /home/user/ah400_{out.tgz,done}
#   row3:  F and AH50 at H 32.49 (CHANS 2.225,2.225,2.22), names cx*             -> /home/user/row3c2_{out.tgz,done}
cd "$(dirname "$0")/../.."
case "$1" in
ah400) TAG=ah400 bash layout/compact/vm_compact.sh "slot_ah_400" "CHAN=1.2;CONG=0" 8 ;;
row3)  CHANS=2.225,2.225,2.22 NAME_PREFIX=cx TAG=row3c2 bash layout/compact/vm_compact.sh "slot_ah_f slot_ah_50" "CHAN=2.225;CONG=0" 6 ;;
esac
