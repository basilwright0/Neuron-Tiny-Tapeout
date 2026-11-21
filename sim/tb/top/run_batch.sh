#!/bin/bash
# Full-chip PEX spot checks as one unattended batch (host-level script; each job runs in the EDA container).
#
#   bash sim/tb/top/run_batch.sh smoke    # fast environment check: static coupling + bias DC op (~15 min)
#   bash sim/tb/top/run_batch.sh full     # every remaining check, at most $JOBS at once
#   bash sim/tb/top/run_batch.sh ramp     # probe DC transfer as ramps (replaces the full-chip DC sweeps)
#
# Env: JOBS (default 5)  STOP_SELF=1 to stop this Boat VM when the batch ends (any outcome)
#      WAIT_PATTERN=<pgrep -f pattern> to wait for other jobs on the VM before stopping.
# Logs and the summary go to sim/results/top/batch/ ; per-bench results to sim/results/top/ (as before).
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-full}"
JOBS="${JOBS:-5}"
OUT=sim/results/top/batch
mkdir -p "$OUT"
SUMMARY="$OUT/summary_${MODE}.txt"

run() {  # name, command (run inside the container from /work)
  local name="$1"; shift
  local t0=$(date +%s)
  scripts/eda.sh "nice -n 15 $*" > "$OUT/$name.log" 2>&1
  local rc=$?
  printf '%-28s rc=%-3s %5d min   %s\n' "$name" "$rc" $(( ($(date +%s) - t0) / 60 )) "$*" >> "$SUMMARY"
  return $rc
}
export -f run
export OUT SUMMARY

if [ "$MODE" = ramp ]; then      # probe-chain DC transfer as up/down ramps, one job per tap and corner
  JOBLIST=()
  for c in "typical 27" "ss 0"; do for k in 0 1 2 3; do
    JOBLIST+=("probe_ramp_${c// /}_tap$k|python3 sim/tb/top/tb_top_probe.py ramp $c $k")
  done; done
elif [ "$MODE" = smoke ]; then
  JOBLIST=(
    "smoke_coupling|python3 sim/tb/top/tb_top_coupling.py"
    "smoke_bias_dc_S100|python3 sim/tb/top/tb_top_bias.py dc 100"
  )
else
  JOBLIST=(
    "probe_dc_typ27|python3 sim/tb/top/tb_top_probe.py dc typical 27"
    "probe_step_typ27|python3 sim/tb/top/tb_top_probe.py step typical 27"
    "probe_dc_ss0|python3 sim/tb/top/tb_top_probe.py dc ss 0"
    "probe_step_ss0|python3 sim/tb/top/tb_top_probe.py step ss 0"
    "kick_typ27|python3 sim/tb/top/tb_top_kick.py typical 27"
    "bias_spk_on|python3 sim/tb/top/tb_top_bias.py spk on"
    "bias_spk_off|python3 sim/tb/top/tb_top_bias.py spk off"
    "bias_step_S1000|python3 sim/tb/top/tb_top_bias.py step 1000"
    "gndchk_S100|python3 sim/tb/top/tb_top_gndchk.py 100"
    "icur_pgrid_ss0|python3 sim/tb/top/tb_top_icur.py ss 0 && python3 sim/tb/top/pgrid.py sim/results/top/icur_ss_0.json S100_probe_off && python3 sim/tb/top/pgrid.py sim/results/top/icur_ss_0.json S1000_probe_on_ibx2"
  )
fi

{
  echo "PEX batch '$MODE' on $(hostname), $(nproc) CPUs, $(free -g | awk '/Mem/{print $2}') GB RAM, JOBS=$JOBS"
  echo "started $(date -u '+%F %T') UTC"
} > "$SUMMARY"

printf '%s\n' "${JOBLIST[@]}" | xargs -P "$JOBS" -I{} bash -c 'j="{}"; run "${j%%|*}" "${j#*|}"'

# WAIT_PATTERN: before stopping, wait for other jobs on this VM (e.g. an earlier batch) matching the pattern
if [ -n "${WAIT_PATTERN:-}" ]; then
  while pgrep -f "$WAIT_PATTERN" > /dev/null; do sleep 60; done
  echo "waited for '$WAIT_PATTERN' until $(date -u '+%F %T') UTC" >> "$SUMMARY"
fi
FAILS=$(grep -c ' rc=[1-9]' "$SUMMARY")
{
  echo "finished $(date -u '+%F %T') UTC; failed jobs: $FAILS"
  echo
  echo "Result files (sim/results/top):"
  ls -1t sim/results/top/*.txt 2>/dev/null | head -40
} >> "$SUMMARY"
tar czf "$OUT/results_${MODE}.tgz" sim/results/top/*.txt sim/results/top/*.json "$OUT"/*.log "$OUT"/summary_*.txt 2>/dev/null
echo "batch '$MODE' done, $FAILS failed; see $SUMMARY"

if [ "${STOP_SELF:-0}" = 1 ]; then
  sync
  boat stop self || sudo poweroff
fi
