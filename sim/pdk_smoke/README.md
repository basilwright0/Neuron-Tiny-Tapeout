# GF180MCU (gf180mcuD) PDK smoke tests

These decks check that ngspice-47 and the gf180mcuD models (open_pdks 026824c) work in
`hpretl/iic-osic-tools:2026.08`. They also pin down the device numbers that the analog neuron design depends on.

## How to run

From Windows (Git Bash):

```
wsl.exe -d Ubuntu-24.04 -- bash -lc 'docker run --rm -v "/mnt/c/Projects/Neuron TinyTapeout:/work" \
  --entrypoint bash hpretl/iic-osic-tools:2026.08 /work/sim/pdk_smoke/run_all.sh' | tr -d '\0'
```

Each `run_*.sh` script sets `PATH=/foss/tools/bin:$PATH` itself, so the runs work with `--entrypoint bash`.
The local `.spiceinit` holds the same settings as the image's `~/.spiceinit` (`ngbehavior=hsa`, `ng_nomodcheck`).

| Script | What it does | Output |
|---|---|---|
| `run_idvg.sh` | `idvg.cir.tmpl` sweeps Vgs 0..1.2 V for nfet_03v3 at W/L=1/1 and 0.5/2 µm and Vds=0.1 V and 1 V, across corners {typical, ff, ss} x {27, 85} °C | `out/idvg_summary.txt` |
| `run_mc.sh` | `gen_mc.py`: 30 instances per geometry at Vgs=0.35 V, Vds=1 V, with mismatch only, mismatch off, and global+mismatch | `out/mc_summary.txt` |
| `run_tran.sh` | `gen_tran.py`: 200 fF MIM discharged by an nfet at several gate biases, plus a poly-resistor RC and an ideal 1 nA calibration | `out/tran_summary.txt` |

## How to include the models (ngspice)

```
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice      ; switches: sw_stat_global/mismatch=0, mc_skew=3, fnoicor=0
.lib     /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical   ; MOS: typical|ff|ss|fs|sf|statistical
.lib     .../sm141064.ngspice mimcap_typical    ; mimcap_ff|mimcap_ss|mimcap_statistical
.lib     .../sm141064.ngspice res_typical       ; res_ff|res_ss|res_statistical
.lib     .../sm141064.ngspice moscap_typical    ; moscap_ff|moscap_ss
.lib     .../sm141064.ngspice diode_typical / bjt_typical (+ _ff/_ss, bjt_statistical)
```

- MOSFETs are subcircuits, so instances use the `X` prefix and SI units: `XM d g s b nfet_03v3 W=1u L=1u`.
- MIM caps: `XC a b cap_mim_2f0_m4m5_noshield c_width=10u c_length=10u`.
- Poly resistors: `XR a b sub ppolyf_u_3k r_width=1u r_length=333u`.

**Mismatch MC.** Each `nfet/pfet_03v3/06v0` wrapper (lib `fets_mm`, included by every corner) applies
`delvto = agauss(0, 0.7071*A_VT/sqrt(Weff*Leff))` and a `mulu0` term, scaled by `sw_stat_mismatch`.
- Turn mismatch on by placing `.param sw_stat_mismatch=1` after the `design.ngspice` include. It works with any corner.
- Each instance gets its own independent sample.
- Set the random seed with `.option seed=N`.

**Global (die-to-die) MC.** Use `.lib ... statistical` together with `.param sw_stat_global=1`, and run one seed per die.

## Results (27 °C typical unless noted)

### Id vs Vgs, nfet_03v3

| W/L (µm) | Vds | Id@Vgs=0 | SS (mV/dec) | Vg@1 pA | Vg@10 pA | Vg@1 nA | Vg@10 nA | Id@1.2 V |
|---|---|---|---|---|---|---|---|---|
| 1/1 | 0.1 | 13.8 fA | 83.3 | 0.198 | 0.281 | 0.450 | 0.540 | 6.10 µA |
| 1/1 | 1.0 | 14.5 fA | 83.3 | 0.194 | 0.277 | 0.446 | 0.535 | 16.3 µA |
| 0.5/2 | 0.1 | 11.9 fA | 83.6 | 0.221 | 0.305 | 0.477 | 0.573 | 1.61 µA |
| 0.5/2 | 1.0 | 12.3 fA | 83.6 | 0.219 | 0.302 | 0.474 | 0.570 | 4.18 µA |

Corners, for W/L=1/1 at Vds=1 V (the full table is in `out/idvg_summary.txt`):

| Corner | SS (mV/dec) | Vg@1 nA | Id@Vgs=0 |
|---|---|---|---|
| ff 27 °C | 82 | 0.339 | 88 fA |
| ss 27 °C | 85 | 0.553 | 10 fA |
| tt 85 °C | 99 | 0.341 | 0.39 pA |
| ff 85 °C | 98 | 0.234 | 4.3 pA (1 pA is already exceeded at Vgs=0) |
| ss 85 °C | 101 | 0.449 | 46 fA |

At a fixed subthreshold bias, Vg spans about 0.21 V from ff to ss and about 0.1 V from 27 to 85 °C.

### 200 fF MIM and nfet leak transient

- Cap: `cap_mim_2f0_m4m5_noshield`, 9.79 x 9.79 µm. An ideal 1 nA discharge measures C = 200.07 fF.
- Vg=0 hold, starting from 1 V: the node falls to 0.279 V after 10 s. That is an average leak of about 14 fA, so the hold time is seconds, not minutes.
- Vg=0.35 V: I ≈ 73 pA. Within a few tens of mV of 0 V the decay becomes exponential, with fitted τ = 82 µs (C·Ut/I = 71 µs).
  - 1 V to 0.5 V takes 1.38 ms.
  - 1 V to 1/e takes 1.75 ms.
  - Above ~0.1 V the device is saturated, so the discharge is a linear current-source ramp, not an RC decay.
- Vg=0.45 V: I ≈ 1.09 nA, 1 V to 1/e takes 117 µs, tail τ = 5.5 µs.
- Vg=1.2 V (triode): 1 V to 1/e takes 8 ns, small-signal τ = 3.7 ns (Ron ≈ 19 kΩ).
- ppolyf_u_3k at W=1 µm, L=333 µm: τ = 223 ns, so R ≈ 1.12 MΩ. This is a true exponential decay.

### Mismatch MC: nfet_03v3 at Vgs=0.35 V, Vds=1 V, 30 instances per geometry

| Run | W/L 1/1: mean, σ/mean | W/L 0.5/2: mean, σ/mean |
|---|---|---|
| mismatch only, seed 1 | 77.0 pA, 14.9 % | 37.4 pA, 14.2 % |
| mismatch only, seed 2 | 78.2 pA, 14.1 % | 37.8 pA, 12.0 % |
| mismatch off (control) | 75.7 pA, 0 % | 37.9 pA, 0 % |
| global+mismatch, 5 dies | per-die means 17 to 139 pA | σ/mean within a die 11 to 17 % |

- The measured σ(ln I) of about 0.15 matches σVth = 0.7071·7.148 mV·µm/√(Weff·Leff) ≈ 5.2 mV divided by n·Ut ≈ 36 mV.
- The model's A_VT is 7.15 mV·µm for nfet_03v3 and 6.66 mV·µm for pfet_03v3.

## Device facts (from the PDK files)

- **MOS devices**
  - nfet_03v3 / pfet_03v3: Lmin 0.28 µm, Wmin 0.22 µm, tox 8 nm, VT0 about 0.63 V and -0.73 V.
  - nfet_06v0: Lmin 0.7 µm, Wmin 0.3 µm. pfet_06v0: Lmin 0.55 µm, Wmin 0.3 µm.
  - nfet_06v0_nvt (native): Lmin 1.8 µm, Wmin 0.8 µm.
  - nfet/pfet_05v0: Lmin 0.6 / 0.5 µm.
  - Also present: `_dss` variants, nfet/pfet_10v0_asym (xschem/magic only), bipolar devices, and diodes.
- **MIM**: gf180mcuD uses MiM option B, between Metal4 and Metal5, in a 5LM stack with an 11 kÅ top metal (klayout `run_lvs.py` variant D; magic tech layer `mimcap` on metal4).
  - Use `cap_mim_2f0_m4m5_noshield`: 1.99 fF/µm² area plus 0.238 fF/µm perimeter.
  - The magic PCell (`cap_mim_2p0fF`) allows 5 to 100 µm per side, so the minimum is 5x5 µm ≈ 54 fF.
  - The models also contain 1f0 and 1f5 variants and m2m3/m3m4/m5m6 placements. The PDK packages only the 2 fF/µm² cap.
  - Corners: ff x0.9, ss x1.1. Global MC σ = 2.5 % (with mc_skew=3).
- **MOS cap** (`cap_nmos_03v3`, in moscap libs): about 4.0 fF/µm² at maximum (tanh C-V curve from about 0.02 to 3.98 fF/µm²). The 6 V version is about 2.2 fF/µm².
- **Resistors (Rsh in Ω/sq)**
  - High-R poly: ppolyf_u_1k = 1000, ppolyf_u_2k = 2000, ppolyf_u_3k = 3000 (TC1 -1.67e-3/K). Wmin is 1 µm in magic.
  - Other poly: ppolyf_u = 350, npolyf_u = 310.
  - Diffusion and well: nplus_u = 60, pplus_u = 185, nwell = 1000.
