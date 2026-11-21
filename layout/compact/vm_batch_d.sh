#!/bin/bash
# Boat VM batch, M2 row 3 (2026-11-21 20:45): AH400 did not route at 32.49 (CHAN 1.2; best 6 nets), so try one
# taller row-3 height per VM: AH400 (CB_W 12) then F and AH50 at the same height.
# Usage: bash layout/compact/vm_batch_d.sh y|z <VM id>
#   y: 33.39 um (AH400 CHAN 1.5; F/AH50 CHANS 2.525,2.525,2.52), names cy*
#   z: 34.29 um (AH400 CHAN 1.8; F/AH50 CHANS 2.825,2.825,2.82), names cz*
#   -> /home/user/row3<y|z>_{out.tgz,done}, then the VM stops itself 5 min later
cd "$(dirname "$0")/../.."
if [ "$1" = y ]; then C=1.5; CH=2.525,2.525,2.52; else C=1.8; CH=2.825,2.825,2.82; fi
T=row3$1; rm -f /home/user/${T}_done
CB_W=12 NAME_PREFIX=c$1 TAG=${T}a bash layout/compact/vm_compact.sh "slot_ah_400" "CHAN=$C;CONG=0" 8
CHANS=$CH NAME_PREFIX=c$1 TAG=${T}b bash layout/compact/vm_compact.sh "slot_ah_f slot_ah_50" "CHAN=${CH%%,*};CONG=0" 4
tar czf /home/user/${T}_out.tgz /home/user/${T}a_out.tgz /home/user/${T}b_out.tgz
echo DONE > /home/user/${T}_done
[ -n "$2" ] && bash layout/compact/vm_selfstop.sh "$2" /home/user/${T}_done 300
