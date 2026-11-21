"""b1c: analyse gen_b1c_pex.py logs: per corner/T, S (Iref 1e-7 -> S=10, 1e-6 -> S=100), DAC and variant
(sch / base PEX / new PEX): monotonic, DNL min/max, INL (endpoint) max |.|, code-0 floor, and the
max relative difference new vs base over codes 1..31."""
import glob, re, sys
import numpy as np
LINES = ["vbn_leak", "vbn_ref", "vbp_syn", "vbn_ax", "vbp_w"]
VAR = ["sch", "base", "new"]
rows = []
worst = dict(dnlmin=9, dnlmax=-9, inl=0, mono=True, dnb=0, floor=0)
print("corner T  S   line      | var : mono DNLmin DNLmax |INL| floor(code0)   | new-vs-base max rel diff (codes 1-31)")
for f in sorted(glob.glob("out/b1c/pex_*_*.log")):
    m = re.search(r"pex_(\w+)_(\d+)\.log", f); corner, T = m[1], m[2]
    data = {}
    for ln in open(f):
        if ln.startswith("D 1e"):
            p = ln.split(); data.setdefault(float(p[1]), {})[int(p[2])] = np.abs(np.array([float(x) for x in p[3:18]]))
    for iref, d in sorted(data.items()):
        S = int(round(iref / 1e-8))
        A = np.array([d[c] for c in range(32)])   # 32 x 15
        for k, ln in enumerate(LINES):
            out = []
            for v in range(3):
                I = A[:, v * 5 + k]
                lsb = (I[31] - I[0]) / 31
                dnl = np.diff(I) / lsb - 1
                inl = (I - I[0]) / lsb - np.arange(32)
                mono = bool(np.all(np.diff(I) > 0))
                out.append((mono, dnl.min(), dnl.max(), np.abs(inl).max(), I[0]))
                if v == 2:
                    worst["dnlmin"] = min(worst["dnlmin"], dnl.min()); worst["dnlmax"] = max(worst["dnlmax"], dnl.max())
                    worst["inl"] = max(worst["inl"], np.abs(inl).max()); worst["mono"] &= mono
                    worst["floor"] = max(worst["floor"], I[0])
            rel = np.max(np.abs(A[1:, 10 + k] / A[1:, 5 + k] - 1))
            worst["dnb"] = max(worst["dnb"], rel)
            s = " | ".join(f"{VAR[v]}: {'Y' if o[0] else 'N'} {o[1]:+.3f} {o[2]:+.3f} {o[3]:.3f} {o[4]:.1e}" for v, o in enumerate(out))
            print(f"{corner:2s} {T:>2s} {S:4d} {ln:9s} | {s} | {100*rel:.4f} %")
print(f"\nNEW layout, all 9 corner/T x S=10,100 x 5 DACs: monotonic {worst['mono']}, DNL {worst['dnlmin']:+.3f}..{worst['dnlmax']:+.3f} LSB, "
      f"|INL| <= {worst['inl']:.3f} LSB, code-0 floor <= {worst['floor']:.2e} A, new vs base <= {100*worst['dnb']:.4f} % per code")
