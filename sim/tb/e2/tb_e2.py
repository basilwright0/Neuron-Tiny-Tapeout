"""E2 leakage test cell (e2_leak) benches on the PEX netlist (layout/e2/final/e2_leak_pex.spice, flattened so the
internal nodes na / nb can be probed and forced).

usage (in the EDA container, from /work):  python3 sim/tb/e2/tb_e2.py <corner> <temp> <vreset> [modes]
  corner: typical | ss | ff   modes (default all): reset droop leak probe
Writes sim/tb/e2/results/e2_<corner>_<temp>_<vreset>.json and prints a summary.

  reset : nodes start at 0 V, grp_en = 1 at t = 0: time until |v(node) - vreset| < 1 mV.
  droop : charge (grp_en = 1 for 20 us), release (fall 10 ns), transient to 10 s; vdd / vreset / abus currents.
  leak  : na / nb forced by DC sources, sweep vreset - 0.2 V .. vreset (+ 0.02): I(V); C from a 1 us ramp;
          dV/dt = I / C and the droop time to -10 / -100 mV integrated from the post-release voltage.
  step  : rev B. Charge to VR, release, then vreset steps to VR - dV (dV = 0, 0.3, 0.6, 1.2, VR) with clamp_en = 0 (mid
          floats: plain 2-stack) and 1 (mid held at vreset). DC I(V) of na / nb (forced together) at the stepped
          vreset, / C, integrated from VR; 10 s transients (dV = VR; at ff/85 also 0.3 / 0.6) (step 1 ms after release).
          Old modes run with clamp_en = 1 (rev A behaviour).
  probe : tap A then tap B on (en, rsel, sub = 1) into 5 pF + the pad pull-down; a schematic copy of the
          array tap (XPM_*, sub switch) on an ideal source at the same voltage gives the reference offset.
Leakage-level options: DC gmin 1e-22 (the shared header's gmin 1e-15 S would be 1 fA at 1 V); transients gmin 1e-18
(converge through the grp_en edge; 1 aA/V, below the ff/85 leakage, so the tt/ss droop numbers come from 'leak').
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sim" / "lib"))
import ngs  # noqa: E402
from ngs import header  # noqa: E402

corner = sys.argv[1] if len(sys.argv) > 1 else "typical"
temp = int(sys.argv[2]) if len(sys.argv) > 2 else 27
VR = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
MODES = sys.argv[4].split(",") if len(sys.argv) > 4 else ["reset", "droop", "leak", "probe", "step"]
PEX = Path(REPO / "layout/e2/final/e2_leak_pex.spice")
TAG = f"e2_{corner}_{temp}_{VR:.2f}"
OUTD = REPO / "sim/tb/e2/results"
OUTD.mkdir(parents=True, exist_ok=True)
ngs.RESULTS = OUTD / "raw"            # decks, ngspice logs and data next to the results
OPT_DC = ".option gmin=1e-22 abstol=1e-22 reltol=1e-6"
OPT_TR = ".option gmin=1e-18 abstol=1e-18 reltol=1e-4 method=gear"
OPT = OPT_DC


def run(text, name):
    return ngs.run(text, name)


GMIN_USED = {}


def run_dc(text, name):
    """DC at the smallest gmin that converges cleanly (1e-22 .. 1e-18): the floor gmin x V is recorded."""
    for gm in ("1e-22", "1e-21", "1e-20", "1e-19", "1e-18", "1e-17", "1e-16"):
        t = text.replace(OPT_DC, f".option gmin={gm} abstol={gm} reltol=1e-6")
        try:
            r = ngs.run(t, name)
        except RuntimeError:
            continue
        if "stepping failed" not in (ngs.RESULTS / f"{name}.log").read_text():
            GMIN_USED[name] = float(gm)
            return r
    raise RuntimeError(f"{name}: no converging gmin")


def flat():
    """PEX subckt body as top-level elements (port nets keep their names; VSUBS -> 0)."""
    txt = re.sub(r"\n\+", " ", PEX.read_text())
    m = re.search(r"^\.subckt\s+e2_leak\s+(.*?)$(.*?)^\.ends", txt, re.M | re.S | re.I)
    body = m.group(2)
    body = re.sub(r"\bVSUBS\b", "0", body)
    return body


def deck(body, analysis, save, opt=None):
    return f"""* {TAG}
{header(corner=corner, temp=temp)}
{opt or OPT}
.subckt nmaster vb vss w=2u l=4u
XM vb vb vss vss nfet_03v3 W={{w}} L={{l}}
.ends nmaster
{flat()}
Vss vss 0 0
Vdd vdd 0 3.3
Vhi hi 0 3.3
Ibp vbb vbn_prb 1u
Vbb vbb 0 3.3
Xbp vbn_prb 0 nmaster w=2u l=2u
Vvr vreset 0 {VR}
Vce clamp_en 0 3.3
Cab abus 0 5p
XPD abus hi 0 0 nfet_03v3 W=0.22u L=20u
{body}
.control
set wr_singlescale
set wr_vecnames
{analysis}
wrdata __OUT__ {' '.join(save)}
quit
.endc
.end
"""


res = dict(corner=corner, temp=temp, vreset=VR)
T_REL = 20e-6

if "reset" in MODES:
    b = """Vg grp_en 0 3.3
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
.ic v(na)=0 v(nb)=0
"""
    r = run(deck(b, "tran 1n 10u 0 2n uic", ["v(na)", "v(nb)"], OPT_TR), TAG + "_reset")
    t = r["_x"]
    for n in ("na", "nb"):
        v = r[f"v({n})"]
        bad = np.where(np.abs(v - VR) >= 1e-3)[0]
        res[f"tset_{n}"] = float(t[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(t) else (0.0 if not len(bad) else None)
        res[f"v10u_{n}"] = float(v[-1])

if "droop" in MODES:
    b = f"""Vg grp_en 0 PWL(0 3.3 {T_REL} 3.3 {T_REL + 10e-9} 0)
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
.ic v(na)={VR} v(nb)={VR}
"""
    r = run(deck(b, f"tran 10n 10 0 20m uic", ["v(na)", "v(nb)", "i(Vdd)", "i(Vvr)", "v(abus)"], OPT_TR),
            TAG + "_droop")
    res["tr_tend"] = float(r["_x"][-1])
    t = r["_x"]
    for n in ("na", "nb"):
        v = r[f"v({n})"]
        v0 = float(np.interp(T_REL + 100e-6, t, v))          # after the release kick
        res[f"tr_v0_{n}"] = v0
        res[f"tr_kick_{n}"] = v0 - VR
        for tt in (1e-3, 0.1, 1.0, 10.0):
            res[f"tr_v_{n}_{tt:g}s"] = float(np.interp(tt, t, v))
        res[f"tr_dvdt_{n}"] = float((np.interp(10.0, t, v) - np.interp(1.0, t, v)) / 9.0)
        for dv in (0.01, 0.1):
            k = np.where(v[t > T_REL + 100e-6] <= v0 - dv)[0]
            res[f"tr_t{int(dv * 1e3)}mV_{n}"] = float(t[t > T_REL + 100e-6][k[0]]) - T_REL if len(k) else None
    late = t > 1.0
    res["idd_off"] = float(np.mean(-r["i(vdd)"][late]))
    res["ivreset_off"] = float(np.mean(-r["i(vvr)"][late]))

if "leak" in MODES:
    b = f"""Vg grp_en 0 0
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
Vna na 0 {VR}
Vnb nb 0 {VR}
"""
    an = f"dc Vna {VR - 0.2:.3f} {VR + 0.02:.3f} 0.005 Vnb {VR - 0.2:.3f} {VR + 0.02:.3f} 0.22"
    r = run_dc(deck(b, an, ["i(Vna)", "i(Vdd)"]), TAG + "_leakA")
    # nested sweep (Vnb outer, 2 points): take the block with Vnb = VR - 0.2 for na (nb does not touch na)
    va = r["_x"]
    n1 = len(va) // 2
    VA, IA = va[:n1], r["i(vna)"][:n1]
    an = f"dc Vnb {VR - 0.2:.3f} {VR + 0.02:.3f} 0.005"
    r2 = run_dc(deck(b, an, ["i(Vnb)", "i(Vdd)"]), TAG + "_leakB")
    VB, IB = r2["_x"], r2["i(vnb)"]
    res["idd_held"] = float(-r2["i(vdd)"][np.argmin(np.abs(VB - VR))])
    # reset state proper: bias off (BIAS_EN = 0 -> vbn_prb at 0 V)
    r4 = run_dc(deck(b.replace("Ibp vbb vbn_prb 1u", "Ibp vbb vbn_prb 0"), f"dc Vna {VR} {VR} 0.1",
                  ["i(Vdd)", "i(Vvr)", "v(vbn_prb)"]), TAG + "_iddoff")
    res["idd_bias_off"] = float(-r4["i(vdd)"][0])
    res["ivreset_bias_off"] = float(-r4["i(vvr)"][0])
    res["gmin_used"] = dict(GMIN_USED)
    # capacitance: AC current of the forcing source at 1 kHz, node biased 50 mV below VR
    import subprocess
    b2 = b.replace(f"Vna na 0 {VR}", f"Vna na 0 dc {VR - 0.05} ac 1").replace(f"Vnb nb 0 {VR}", f"Vnb nb 0 dc {VR - 0.05} ac 1")
    txt = deck(b2, "ac lin 1 1e3 1e3\nlet cna = -imag(i(vna))/(2*pi*1e3)\nlet cnb = -imag(i(vnb))/(2*pi*1e3)\n"
                   "print cna cnb", ["cna"], OPT_TR).replace("wrdata __OUT__ cna\n", "")
    ngs.RESULTS.mkdir(parents=True, exist_ok=True)
    (ngs.RESULTS / f"{TAG}_cap.cir").write_text(txt)
    out = subprocess.run(["ngspice", "-b", str(ngs.RESULTS / f"{TAG}_cap.cir")], capture_output=True, text=True,
                         cwd=ngs.RESULTS).stdout
    (ngs.RESULTS / f"{TAG}_cap.log").write_text(out)
    Cv = {k: abs(float(v)) for k, v in re.findall(r"^c(na|nb)\s*=\s*([-+0-9.eE]+)", out, re.M)}
    for n, V, I in (("na", VA, IA), ("nb", VB, IB)):
        C = Cv[n]
        res[f"C_{n}"] = C
        # node current (into the node from the source = what leaks away): dV/dt of the floating node = I(V)/C
        dvdt = I / C           # I(Vx) < 0 when the node leaks down
        res[f"leak_{n}"] = dict(V=[float(x) for x in V], I=[float(x) for x in I])
        v0 = res.get(f"tr_v0_{n}", VR)
        res[f"dvdt_{n}_at_v0"] = float(np.interp(v0, V, dvdt))
        # integrate dt = dV / (dV/dt) from v0 downwards
        vv = np.linspace(v0, v0 - 0.1, 2001)
        rate = np.interp(vv, V, dvdt)
        tt = None
        times = {}
        acc = 0.0
        for k in range(1, len(vv)):
            rr = 0.5 * (rate[k] + rate[k - 1])
            if rr >= 0:                       # equilibrium (node no longer droops)
                acc = float("inf")
                break
            acc += (vv[k] - vv[k - 1]) / rr
            for dv in (0.01, 0.1):
                if f"{dv}" not in times and v0 - vv[k] >= dv - 1e-9:
                    times[f"{dv}"] = acc
        res[f"t10mV_{n}"] = times.get("0.01", float("inf"))
        res[f"t100mV_{n}"] = times.get("0.1", float("inf"))
        # equilibrium voltage (I = 0 crossing below VR), if any
        s = np.where(np.diff(np.sign(I)) != 0)[0]
        res[f"veq_{n}"] = float(V[s[0]]) if len(s) else None

if "probe" in MODES:
    T1, T2, T3 = 40e-6, 140e-6, 240e-6
    b = f"""Vg grp_en 0 PWL(0 3.3 {T_REL} 3.3 {T_REL + 10e-9} 0)
Vea en_a 0 PWL(0 0 {T1} 0 {T1 + 10e-9} 3.3 {T2} 3.3 {T2 + 10e-9} 0)
Veb en_b 0 PWL(0 0 {T2 + 20e-9} 0 {T2 + 30e-9} 3.3)
Vrs rsel 0 PWL(0 0 {T1} 0 {T1 + 10e-9} 3.3)
Vsb sub 0 PWL(0 0 {T1} 0 {T1 + 10e-9} 3.3)
.ic v(na)={VR} v(nb)={VR}
* reference: the array tap (XPM_*, last switch on sub) on an ideal source at the post-release node voltage
Vref vin 0 {VR}
XMF vdd vin rp 0 nfet_03v3 W=4u L=2u
XME rp hi rs 0 nfet_03v3 W=1u L=0.28u
XMB rs vbn_prb 0 0 nfet_03v3 W=2u L=2u
XSC rp hi rmc 0 nfet_03v3 W=1u L=0.28u
XSW rmc hi rm 0 nfet_03v3 W=1u L=0.28u
XSB rm hi rabus 0 nfet_03v3 W=1u L=0.28u
Cr rabus 0 5p
XPDr rabus hi 0 0 nfet_03v3 W=0.22u L=20u
"""
    r = run(deck(b, f"tran 10n {T3} 0 20n uic", ["v(na)", "v(nb)", "v(abus)", "v(rabus)"], OPT_TR), TAG + "_probe")
    t = r["_x"]
    g = lambda k, tt: float(np.interp(tt, t, r[k]))  # noqa: E731
    res["probe"] = dict(
        na_before=g("v(na)", T1 - 1e-6), na_on=g("v(na)", T1 + 30e-6), na_end=g("v(na)", T2 - 1e-6),
        na_after=g("v(na)", T3 - 1e-6), na_rel=g("v(na)", T_REL + 5e-6), nb_rel=g("v(nb)", T_REL + 5e-6),
        nb_before=g("v(nb)", T2 - 1e-6), nb_on=g("v(nb)", T3 - 1e-6),
        abus_a=g("v(abus)", T2 - 1e-6), abus_b=g("v(abus)", T3 - 1e-6), ref=g("v(rabus)", T3 - 1e-6))
    p = res["probe"]
    p["off_a"] = p["abus_a"] - p["na_on"]
    p["off_b"] = p["abus_b"] - p["nb_on"]
    p["off_ref"] = p["ref"] - VR
    p["kick_na_release"] = p["na_rel"] - VR
    p["kick_nb_release"] = p["nb_rel"] - VR
    p["drift_na_probing_100us"] = p["na_end"] - p["na_on"]
    p["dna_tap"] = p["na_on"] - p["na_before"]
    p["dnb_tap"] = p["nb_on"] - p["nb_before"]
    # settling of abus to within 1 mV of its final value after en_a
    v = r["v(abus)"]
    k = np.where((t > T1) & (t < T2) & (np.abs(v - p["abus_a"]) > 1e-3))[0]
    p["tsettle_a"] = float(t[k[-1]] - T1) if len(k) else 0.0


def droop_times(V, I, C, v0):
    dvdt = I / C
    vv = np.linspace(v0, v0 - 0.1, 2001)
    rate = np.interp(vv, V, dvdt)
    acc, times = 0.0, {}
    for k in range(1, len(vv)):
        rr = 0.5 * (rate[k] + rate[k - 1])
        if rr >= 0:
            acc = float("inf")
            break
        acc += (vv[k] - vv[k - 1]) / rr
        for dv in (0.01, 0.1):
            if dv not in times and v0 - vv[k] >= dv - 1e-9:
                times[dv] = acc
    return float(np.interp(v0 - 0.002, V, dvdt)), times.get(0.01, float("inf")), times.get(0.1, float("inf"))


if "step" in MODES:
    assert "C_na" in res, "step needs leak (C)"
    st = res["step"] = {}
    for ce in (0, 1):
        for dV in (0.0, 0.3, 0.6, 1.2, VR):
            b = f"""Vg grp_en 0 0
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
Vdrv drv 0 {VR}
Vna na drv 0
Vnb nb drv 0
.nodeset v(mid)={VR} v(cx)={VR}
"""
            txt = deck(b, f"dc Vdrv {VR - 0.2:.3f} {VR + 0.001:.3f} 0.005", ["i(Vna)", "i(Vnb)", "i(Vdd)"])
            txt = txt.replace(f"Vvr vreset 0 {VR}", f"Vvr vreset 0 {VR - dV:.3f}").replace(
                "Vce clamp_en 0 3.3", f"Vce clamp_en 0 {3.3 * ce}")
            name = f"{TAG}_step_c{ce}_d{int(dV * 1e3)}"
            r = run_dc(txt, name)
            V = r["_x"]
            k = f"c{ce}_d{int(dV * 1e3)}"
            st[k] = dict(gmin=GMIN_USED.get(name), idd=float(-r["i(vdd)"][-1]))
            for n in ("na", "nb"):
                I = r[f"i(v{n})"]
                rate, t10, t100 = droop_times(V, I, res[f"C_{n}"], VR)
                st[k][n] = dict(dvdt=rate, t10=t10, t100=t100, I_at_v0=float(np.interp(VR - 0.002, V, I)))
    for ce in (0, 1):
        for dV in ((0.3, 0.6, VR) if corner == "ff" else (VR,)):
            if True:
                b = f"""Vg grp_en 0 PWL(0 3.3 {T_REL} 3.3 {T_REL + 10e-9} 0)
Vea en_a 0 0
Veb en_b 0 0
Vrs rsel 0 0
Vsb sub 0 0
.ic v(na)={VR} v(nb)={VR}
"""
                txt = deck(b, "tran 10n 10 0 20m uic", ["v(na)", "v(nb)"], OPT_TR)
                txt = txt.replace(f"Vvr vreset 0 {VR}", f"Vvr vreset 0 PWL(0 {VR} 1m {VR} 1.001m {VR - dV:.3f})").replace(
                    "Vce clamp_en 0 3.3", f"Vce clamp_en 0 {3.3 * ce}")
                r = run(txt, f"{TAG}_steptr_c{ce}_d{int(dV * 1e3)}")
                t = r["_x"]
                st[f"c{ce}_d{int(dV * 1e3)}"]["tran"] = {
                    n: dict(v2ms=float(np.interp(2e-3, t, r[f"v({n})"])), v1s=float(np.interp(1.0, t, r[f"v({n})"])),
                            v10s=float(np.interp(10.0, t, r[f"v({n})"]))) for n in ("na", "nb")}

prev = OUTD / f"{TAG}.json"          # keep results of modes not run this time
if prev.exists():
    res = {**json.loads(prev.read_text()), **res}
prev.write_text(json.dumps(res, indent=1))
short = {k: v for k, v in res.items() if not k.startswith("leak_")}
print(json.dumps(short, indent=1))
