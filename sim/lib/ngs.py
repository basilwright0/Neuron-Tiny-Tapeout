"""Minimal ngspice harness for gf180mcuD (runs inside the pinned EDA container).

Usage from a testbench script (run via scripts/eda.sh "python3 sim/tb/xxx.py"):

    from ngs import deck, run, crossings
    d = deck(body, analysis="tran 10n 2m", save=["v(vm)", "v(spk)"], corner="typical", temp=27)
    data = run(d, "lif_fi_typ")          # dict: {"time": array, "v(vm)": array, ...}

Corners: typical | ff | ss | fs | sf | statistical.  mismatch=True turns on
per-instance Vth/mobility mismatch (sw_stat_mismatch=1) with .option seed=N.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

PDK = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "sim" / "results"
SPICEINIT = REPO / "sim" / "pdk_smoke" / ".spiceinit"
CELLS = REPO / "cells"

_SIDE_LIBS = ("moscap", "res", "diode")


def header(corner="typical", temp=27, mismatch=False, seed=1, global_var=False):
    side = "typical" if corner in ("typical", "fs", "sf", "statistical") else corner
    L = [f".include {PDK}/design.ngspice"]
    if mismatch:
        L.append(".param sw_stat_mismatch=1")
    if global_var:
        L.append(".param sw_stat_global=1")
    L.append(f".lib {PDK}/sm141064.ngspice {corner}")
    for lib in _SIDE_LIBS:
        L.append(f".lib {PDK}/sm141064.ngspice {lib}_{side}")
    L.append(f".temp {temp}")
    if mismatch or global_var:
        L.append(f".option seed={seed}")
    L.append(".option gmin=1e-15 abstol=1e-16 reltol=1e-4 method=gear")
    return "\n".join(L)


def include(*cells):
    return "\n".join(f".include {CELLS / c}" for c in cells)


def deck(body, analysis, save, title="tb", **hdr):
    vecs = " ".join(save)
    return f"""* {title}
{header(**hdr)}
{body}
.control
set wr_singlescale
set wr_vecnames
{analysis}
wrdata __OUT__ {vecs}
quit
.endc
.end
"""


def run(deck_text, name, timeout=3600):
    RESULTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPICEINIT, RESULTS / ".spiceinit")
    out = RESULTS / f"{name}.dat"
    cir = RESULTS / f"{name}.cir"
    log = RESULTS / f"{name}.log"
    if out.exists():
        out.unlink()
    cir.write_text(deck_text.replace("__OUT__", str(out)))
    p = subprocess.run(["ngspice", "-b", str(cir)], cwd=RESULTS, capture_output=True,
                       text=True, timeout=timeout)
    log.write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
    # ngspice can exit 0 on an aborted transient: require the data file.
    if not out.exists() or out.stat().st_size == 0:
        tail = "\n".join((p.stdout + p.stderr).splitlines()[-30:])
        raise RuntimeError(f"ngspice produced no data for {name}; see {log}\n{tail}")
    with open(out) as f:
        names = [n.lower() for n in f.readline().split()]
    arr = np.loadtxt(out, skiprows=1, ndmin=2)
    data = {n: arr[:, i] for i, n in enumerate(names)}
    data["_x"] = arr[:, 0]
    return data


def crossings(t, v, level, rising=True):
    """Interpolated times where v crosses level."""
    s = v - level
    idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] if rising else \
        np.where((s[:-1] > 0) & (s[1:] <= 0))[0]
    return t[idx] - s[idx] * (t[idx + 1] - t[idx]) / (s[idx + 1] - s[idx])


def rate(spike_times, t_settle=0.0):
    st = spike_times[spike_times >= t_settle]
    if len(st) < 3:
        return 0.0
    return 1.0 / np.mean(np.diff(st))


CORNERS = ["typical", "ff", "ss", "fs", "sf"]
TEMPS = [0, 27, 85]
