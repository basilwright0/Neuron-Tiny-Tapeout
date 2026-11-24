#!/bin/bash
# Run a command inside the pinned EDA image with this repo mounted at /work.
# Usage (from Windows Git Bash or WSL):  scripts/eda.sh "<command>"
# Each call writes its own command file, so concurrent calls do not clobber each other.
IMAGE=hpretl/iic-osic-tools:2026.08   # digest sha256:3c371645... (same pin as ~/neural-hardware-ic)
REPO_WIN="$(cd "$(dirname "$0")/.." && pwd)"
# `pwd -W` (C:/... path) only works in Git Bash/MSYS. WSL also has wsl.exe on PATH, so test this, not wsl.exe.
ON_WINDOWS=0
if W="$(cd "$REPO_WIN" && pwd -W 2>/dev/null)" && [ -n "$W" ]; then
  ON_WINDOWS=1; REPO_WIN="$W"; d="${REPO_WIN%%:*}"; REPO_WSL="/mnt/${d,,}${REPO_WIN#?:}"
fi
TAG="cmd_$$_${RANDOM}${RANDOM}"
mkdir -p "$REPO_WIN/.tools/cmds"
CMD="export PATH=/foss/tools/bin:/foss/tools/klayout:\$PATH PDK_ROOT=/foss/pdks PDK=gf180mcuD PYTHONPATH=/work/.tools/pydeps:/foss/tools/klayout/pymod; cd /work; $1"
printf '%s\n' "$CMD" > "$REPO_WIN/.tools/cmds/$TAG.sh"
if [ "$ON_WINDOWS" = 1 ]; then                 # Windows host: Docker runs in the WSL distro
  wsl.exe -d Ubuntu-24.04 -- bash -lc "docker run --rm -v '$REPO_WSL:/work' --entrypoint bash $IMAGE /work/.tools/cmds/$TAG.sh" 2>&1 | tr -d '\0'
  rc=${PIPESTATUS[0]}
else                                            # WSL or Linux host (e.g. a cloud VM): native Docker
  docker run --rm -v "$REPO_WIN:/work" --entrypoint bash $IMAGE /work/.tools/cmds/$TAG.sh 2>&1
  rc=${PIPESTATUS[0]}
fi
rm -f "$REPO_WIN/.tools/cmds/$TAG.sh"
exit $rc
