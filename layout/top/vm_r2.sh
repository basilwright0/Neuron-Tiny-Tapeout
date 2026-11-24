#!/bin/bash
# MIL-344 R2 (B1 re-pack, branch r2-b1-pack): full-chip gate from the committed work/routes.json (routes are made
# locally: host prep.py + route.py reroute, see docs/r2/b1-repack-handoff.md): assembly, extraction, LVS, magic +
# KLayout DRC/antenna, TT precheck (vm_top3.sh nopex). Logs: layout/top/work/vm3/ (copied to work/vmr2/).
# Usage (repo root, on the shared queue VM): bash layout/top/vm_r2.sh
cd "$(dirname "$0")/../.."
[ -d .tools/tt-support-tools ] || { mkdir -p .tools && cp -r /home/user/m3/main/.tools/tt-support-tools .tools/; }
bash layout/top/vm_top3.sh nopex
rm -rf layout/top/work/vmr2; cp -r layout/top/work/vm3 layout/top/work/vmr2
