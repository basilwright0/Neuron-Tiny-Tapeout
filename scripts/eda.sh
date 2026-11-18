#!/bin/bash
# Run a command inside the pinned EDA image with this repo mounted at /work.
# Usage (from Windows Git Bash or WSL):  scripts/eda.sh "<command>"
# Each call writes its own command file, so concurrent calls do not clobber each other.
IMAGE=hpretl/iic-osic-tools:2026.08   # digest sha256:3c371645... (same pin as ~/neural-hardware-ic)
REPO_WIN="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
d="${REPO_WIN%%:*}"; REPO_WSL="/mnt/${d,,}${REPO_WIN#?:}"
TAG="cmd_$$_${RANDOM}${RANDOM}"
mkdir -p "$REPO_WIN/.tools/cmds"
CMD="export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; cd /work; $1"
printf '%s\n' "$CMD" > "$REPO_WIN/.tools/cmds/$TAG.sh"
wsl.exe -d Ubuntu-24.04 -- bash -lc "docker run --rm -v '$REPO_WSL:/work' --entrypoint bash $IMAGE /work/.tools/cmds/$TAG.sh" 2>&1 | tr -d '\0'
rc=${PIPESTATUS[0]}
rm -f "$REPO_WIN/.tools/cmds/$TAG.sh"
exit $rc
