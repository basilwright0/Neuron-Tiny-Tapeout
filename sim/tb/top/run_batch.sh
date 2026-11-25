#!/bin/bash
# Full-chip PEX spot checks as one unattended batch (host-level script; each job runs in the EDA container).
#
#   bash sim/tb/top/run_batch.sh smoke    # fast environment check: static coupling + bias DC op (~15 min)
#   bash sim/tb/top/run_batch.sh full     # every remaining check, at most $JOBS at once
#   bash sim/tb/top/run_batch.sh ramp     # probe DC transfer as ramps (replaces the full-chip DC sweeps)
#   bash sim/tb/top/run_batch.sh pex      # M2 VM set (sim/tb/top/vm_pex.sh): static coupling + kick transient for
#                                         # every neuron, probe step, bias DC / spiking neighbours; no DC sweeps
#                                         # R2 (MIL-362): + bay firing / bay probe (SEL 16-18) / bias-line settling at
#                                         # S = 10 with and without the bay devices, icur S10000, gndchk, s10k
#   PEX_SKIP=<egrep pattern>: leave out the pex jobs whose name matches (e.g. 'bias_spk_on')
#
# Env: JOBS (default 5)  JOB_TIMEOUT (minutes per job, default 150; inside the container)  FORCE=1 reruns jobs that already have a .ok marker  STOP_SELF=1 to stop this Boat VM when the batch ends (any outcome)
#      WAIT_PATTERN=<pgrep -f pattern> to wait for other jobs on the VM before stopping.
# Logs and the summary go to sim/results/top/batch/ ; per-bench results to sim/results/top/ (as before).
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-full}"
JOBS="${JOBS:-5}"
OUT=sim/results/top/batch
mkdir -p "$OUT"
SUMMARY="$OUT/summary_${MODE}.txt"

run() {  # name, command (run inside the container from /work); a finished job leaves $OUT/<name>.ok and is skipped
  local name="$1"; shift                               # on a rerun (FORCE=1 reruns everything)
  if [ -e "$OUT/$name.ok" ] && [ "${FORCE:-0}" != 1 ]; then
    printf '%-28s skipped (done earlier, %s)\n' "$name" "$(cat "$OUT/$name.ok")" >> "$SUMMARY"; return 0
  fi
  local t0=$(date +%s)
  bash scripts/eda.sh "timeout ${JOB_TIMEOUT:-150}m nice -n 15 $*" > "$OUT/$name.log" 2>&1
  local rc=$?
  [ $rc = 0 ] && date -u '+%F %T' > "$OUT/$name.ok"
  printf '%-28s rc=%-3s %5d min   %s\n' "$name" "$rc" $(( ($(date +%s) - t0) / 60 )) "$*" >> "$SUMMARY"
  return $rc
}
export -f run
export OUT SUMMARY JOB_TIMEOUT

if [ "$MODE" = ramp ]; then      # probe-chain DC transfer as up/down ramps, one job per tap and corner
  JOBLIST=()
  for c in "typical 27" "ss 0"; do for k in 0 1 2 3; do
    JOBLIST+=("probe_ramp_${c// /}_tap$k|python3 sim/tb/top/tb_top_probe.py ramp $c $k")
  done; done
elif [ "$MODE" = pex ]; then      # longest first (kick: 210 us transient); no full-chip DC sweeps (M1: OOM)
  JOBLIST=(
    "kick_typ27|python3 sim/tb/top/tb_top_kick.py typical 27"
    "probe_step_typ27|python3 sim/tb/top/tb_top_probe.py step typical 27"
    "coupling|python3 sim/tb/top/tb_top_coupling.py"
    "bias_dc_S100|python3 sim/tb/top/tb_top_bias.py dc 100"
    "bias_spk_on|python3 sim/tb/top/tb_top_bias.py spk on"
    "bias_spk_off|python3 sim/tb/top/tb_top_bias.py spk off"
  )
  if grep -q "^BAY = " floorplan/floorplan.py; then
    JOBLIST=(                     # R2 (MIL-362), longest first; the M3 jobs keep their definitions
      "s10k_typ27|env S10K_TIMEOUT=6000 python3 sim/tb/top/tb_top_s10k.py typical 27"
      "bias_spk_off|python3 sim/tb/top/tb_top_bias.py spk off"
      "bay_fire_typ27|python3 sim/tb/top/tb_top_bay.py fire typical 27"
      "bias_spk_on|python3 sim/tb/top/tb_top_bias.py spk on"
      "probe_step_typ27|python3 sim/tb/top/tb_top_probe.py step typical 27"
      "bias_step_S10|env STEP_TW=2 python3 sim/tb/top/tb_top_bias.py step 10"
      "bias_step_S10_nobay|env NOBAY=1 STEP_TW=2 python3 sim/tb/top/tb_top_bias.py step 10"
      "bay_probe_typ27|python3 sim/tb/top/tb_top_bay.py probe typical 27"
      "kick_typ27|python3 sim/tb/top/tb_top_kick.py typical 27"
      "icur_pgrid_S10000|env ICUR_CASES=S10000 python3 sim/tb/top/tb_top_icur.py typical 27 && python3 sim/tb/top/pgrid.py /work/sim/results/top/icur_S10000_typical_27.json S10000_ibx2"
      "gndchk_S100|python3 sim/tb/top/tb_top_gndchk.py 100"
      "coupling|python3 sim/tb/top/tb_top_coupling.py"
      "bias_dc_S100|python3 sim/tb/top/tb_top_bias.py dc 100"
      "bias_dc_S100_r2c22|env BIAS_R2=22 python3 sim/tb/top/tb_top_bias.py dc 100"
    )
  fi
  if [ -n "${PEX_SKIP:-}" ]; then
    K=(); for j in "${JOBLIST[@]}"; do echo "${j%%|*}" | grep -qE "$PEX_SKIP" || K+=("$j"); done; JOBLIST=("${K[@]}")
  fi
elif [ "$MODE" = smoke ]; then
  JOBLIST=(
    "smoke_coupling|python3 sim/tb/top/tb_top_coupling.py"
    "smoke_bias_dc_S100|python3 sim/tb/top/tb_top_bias.py dc 100"
    "smoke_decks|python3 sim/tb/top/deckcheck.py"
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

{                                                        # appended: a rerun keeps the earlier jobs' lines
  echo
  echo "PEX batch '$MODE' on $(hostname), $(nproc) CPUs, $(free -g | awk '/Mem/{print $2}') GB RAM, JOBS=$JOBS"
  echo "started $(date -u '+%F %T') UTC"
} >> "$SUMMARY"

printf '%s\n' "${JOBLIST[@]}" | xargs -P "$JOBS" -I{} bash -c 'j="{}"; run "${j%%|*}" "${j#*|}"'

# WAIT_PATTERN: before stopping, wait for other jobs on this VM (e.g. an earlier batch) matching the pattern
if [ -n "${WAIT_PATTERN:-}" ]; then
  while pgrep -f "$WAIT_PATTERN" > /dev/null; do sleep 60; done
  echo "waited for '$WAIT_PATTERN' until $(date -u '+%F %T') UTC" >> "$SUMMARY"
fi
FAILS=$(awk '/^PEX batch/{f=0} / rc=[1-9]/{f++} END{print f+0}' "$SUMMARY")   # this run's failures only
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
