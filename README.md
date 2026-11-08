# Analog Neuron Test Bench — Tiny Tapeout TTGF26c

An analog neuromorphic test chip for **TTGF26c**: gf180mcuD, analog 1×2 tile, 2 analog pins. Submission closes **2026-12-07**.
It is Phase-0 silicon for the Neural Hardware programme (`C:\Projects\Neural Hardware`).

## Read first

1. [docs/01 Conversation Summary](docs/01%20Conversation%20Summary.md): goals and a turn-by-turn summary of the planning chat.
2. [docs/02 Reconciliation with Prior Work](docs/02%20Reconciliation%20with%20Prior%20Work.md): how this fits the NH, CS and CV vaults, and what to build first.
3. [docs/03 Research Findings](docs/03%20Research%20Findings.md): shuttle rules, GF180 device facts, circuit topologies, and the measurement plan.
4. [docs/04 Design Plan](docs/04%20Design%20Plan.md): block tiers, schedule and gates, pin map, and open decisions.

## Layout of this repo

| Path | Contents |
|---|---|
| `info.yaml`, `src/project.v`, `docs/info.md`, `.github/` | From the official `TinyTapeout/ttgf-analog-template` (actions `@ttgf26c`) |
| `mag/` | Magic layout; `init_project.tcl` + `tt_analog_1x2.def` build the empty frame |
| `gds/`, `lef/` | Exported layout (what CI submits) |
| `xschem/` | Schematics |
| `sim/pdk_smoke/` | GF180 device characterisation decks (Id-Vg, RC, Monte Carlo, MOS-cap C-V) |
| `sim/tb/` | Per-cell testbenches (to come) |
| `model/reference.py` | Numerical reference models (LIF, AdEx, compartments) |
| `scripts/` | `eda.sh` (runs a command in the pinned EDA container), `precheck.sh`, `layout_init.sh` |
| `.tools/` | Untracked clones of `tt-support-tools` (needed for the local precheck) and the template |

## Everyday commands

These run from Git Bash in this folder. Docker Desktop must be running.

```bash
scripts/eda.sh "bash scripts/precheck.sh"
```

```bash
scripts/eda.sh "cd sim/pdk_smoke && bash run_all.sh"
```

```bash
scripts/eda.sh "python3 model/reference.py"
```

The image is `hpretl/iic-osic-tools:2026.08`. It is the same digest-pinned image used by `~/neural-hardware-ic`.
If `docker: command not found` appears inside WSL, Docker Desktop's WSL integration has dropped. Restart Docker Desktop, then run `wsl --shutdown`.
