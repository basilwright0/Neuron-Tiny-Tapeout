#!/bin/bash
# R2 C1 step 3: re-harden neuron_ctrl (N_SPK = 24, OUT_BANK, probe_sel_bay, probe_en_c4) on the shared VM.
# Same flow as rev E (docs/regmap.md "Hardened rev E"): rtl/librelane/run.sh with config_fp.json
# (= config.json + IO_PIN_ORDER_CFG pin_order.cfg), die 166 x 166, density 86, in the pinned
# iic-osic-tools image of scripts/eda.sh. pin_order.cfg is the rev E order + 12 added W pins only
# (frozen by hand, NOT from mkpins.py; check with pincheck.py).
# Usage (repo root, host with docker): bash rtl/librelane/vm_harden.sh [CFG] [TAG]
#   CFG = config file name in rtl/librelane (default config_fp.json), TAG = run tag (default c1spk_166)
# Output: rtl/librelane/c1spk_results/ for the default tag, else rtl/librelane/c1spk_results_<TAG>/
#   (logs, metrics.csv, final LEF/GDS/netlist/spice, reports, pin diff)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=hpretl/iic-osic-tools:2026.08          # same pin as scripts/eda.sh
CFG=${1:-config_fp.json}
TAG=${2:-c1spk_166}
if [ "$TAG" = c1spk_166 ]; then R=rtl/librelane/c1spk_results; else R=rtl/librelane/c1spk_results_$TAG; fi
cd "$ROOT"
rm -rf "$R"; mkdir -p "$R"
{ echo "start $(date -u +%FT%TZ) host $(hostname) commit $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  python3 -c "import json;import sys;c=json.load(open('rtl/librelane/'+sys.argv[1]));print('CFG',sys.argv[1],'DIE_AREA',c['DIE_AREA'],'DENS',c['PL_TARGET_DENSITY_PCT'],'PIN_CFG',c.get('IO_PIN_ORDER_CFG'));print({k:v for k,v in c.items() if 'MARGIN' in k or 'BUFFER_INPUT' in k})" "$CFG"
} > $R/info.txt 2>&1
python3 rtl/librelane/pincheck.py cfglef rtl/librelane/pin_order.cfg macros/neuron_ctrl/neuron_ctrl.lef > $R/pin_cfg_vs_revE.txt 2>&1

# Harden (<= 2 cores on the shared VM). Full librelane output -> harden.log
CMD="export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD; cd /work/rtl/librelane && \
librelane --pdk-root /foss/pdks --pdk gf180mcuD --scl gf180mcu_fd_sc_mcu7t5v0 --manual-pdk --run-tag $TAG --overwrite $CFG"
docker run --rm --cpus 2 -v "$ROOT:/work" --entrypoint bash $IMAGE -c "$CMD" > $R/harden.log 2>&1
rc=$?
echo "librelane rc=$rc end $(date -u +%FT%TZ)" >> $R/info.txt

RUN=rtl/librelane/runs/$TAG
F=$RUN/final
for x in lef/neuron_ctrl.lef gds/neuron_ctrl.gds nl/neuron_ctrl.nl.v spice/neuron_ctrl.spice metrics.csv metrics.json; do
  [ -f "$F/$x" ] && cp "$F/$x" $R/
done
cp $RUN/resolved.json $R/ 2>/dev/null
cp $RUN/error.log $RUN/warning.log $R/ 2>/dev/null
# step logs/reports worth reading: STA summary, DRC, LVS, antenna, placement
mkdir -p $R/reports
for d in $RUN/*-openroad-stapostpnr $RUN/*-magic-drc $RUN/*-klayout-drc $RUN/*-netgen-lvs $RUN/*-openroad-checkantennas* \
         $RUN/*-openroad-detailedplacement $RUN/*-openroad-globalplacement $RUN/*-openroad-ioplacement; do
  [ -d "$d" ] || continue
  b=$(basename "$d"); mkdir -p $R/reports/$b
  find "$d" -maxdepth 2 \( -name '*.rpt' -o -name '*.log' -o -name '*summary*' -o -name '*.txt' \) -size -5M -exec cp {} $R/reports/$b/ \;
done
if [ -f $R/neuron_ctrl.lef ]; then
  python3 rtl/librelane/pincheck.py lef macros/neuron_ctrl/neuron_ctrl.lef $R/neuron_ctrl.lef > $R/pin_diff_lef.txt 2>&1
  echo "pin diff rc=$?" >> $R/info.txt
fi
tail -60 $R/harden.log > $R/harden_tail.txt
exit $rc
