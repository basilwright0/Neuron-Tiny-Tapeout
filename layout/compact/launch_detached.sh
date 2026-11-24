#!/usr/bin/env bash
# Launch one cgen.py search detached from the agent session (survives the end of a Paperclip turn).
#   layout/compact/launch_detached.sh <NAME> VAR=value ...        e.g.  ... h6 CELL=slot_ah_h SWEEP="CHAN=1.8" SEEDS=4
# Runs under millstone-heavy (memory rule: <= 2 workers per job). Log out/<NAME>.log, PID out/<NAME>.pid.
# Check later: kill -0 $(cat out/<NAME>.pid); grep '^seed' out/<NAME>.log
set -euo pipefail
cd "$(dirname "$0")"
NAME="$1"; shift
if [ -f "out/$NAME.pid" ] && kill -0 "$(cat "out/$NAME.pid")" 2>/dev/null; then
  echo "$NAME already running (pid $(cat "out/$NAME.pid"))"; exit 1
fi
mkdir -p out
# playbook limit: at most 4 local search workers in total (a job = 1 parent + 2 workers)
running=$(pgrep -fc '^python3 -u cgen.py searchonly' || true)
if [ "$running" -gt 0 ] && [ $(( running * 2 / 3 + 2 )) -gt 4 ]; then
  echo "refused: ~$(( running * 2 / 3 )) search workers already running (limit 4); wait or use boat"; exit 75
fi
setsid nohup /home/basil/.local/bin/millstone-heavy --project "Tiny Tapeout" -- \
  env JOBS=2 NAME="$NAME" "$@" python3 -u cgen.py searchonly > "out/$NAME.log" 2>&1 < /dev/null &
echo $! > "out/$NAME.pid"
echo "launched $NAME pid $! log out/$NAME.log"
