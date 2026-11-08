#!/bin/bash
# Run every smoke test inside hpretl/iic-osic-tools:2026.08 (mounted at /work)
cd /work/sim/pdk_smoke
bash run_idvg.sh && bash run_mc.sh && bash run_tran.sh
