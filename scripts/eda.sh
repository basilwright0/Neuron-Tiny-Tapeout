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
if command -v wsl.exe >/dev/null 2>&1; then   # Windows host: Docker runs in the WSL distro
  wsl.exe -d Ubuntu-24.04 -- bash -lc "docker run --rm -v '$REPO_WSL:/work' --entrypoint bash $IMAGE /work/.tools/cmds/$TAG.sh" 2>&1 | tr -d '\0'
  rc=${PIPESTATUS[0]}
else                                            # Linux host (e.g. a cloud VM): native Docker
  docker run --rm -v "$REPO_WIN:/work" --entrypoint bash $IMAGE /work/.tools/cmds/$TAG.sh 2>&1
  rc=${PIPESTATUS[0]}
fi
rm -f "$REPO_WIN/.tools/cmds/$TAG.sh"
exit $rc
