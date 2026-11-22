#!/usr/bin/env python3
"""vdac (MIL-133): summarise out/pack_vdac/pack_<c>_<t>.log (s = schematic R_base 60, old = b1-b packed PEX
R_base 53, new = R_base 60 PEX) -> layout/bias/m3pack/vdac_pex_dc_summary.txt.  Target 1.62 V needs code <= 30
(>= 1 LSB below full scale); low end must stay below the nominal S = 100 setting (~1.38-1.43 V)."""
import numpy as np
from pathlib import Path
D = Path(__file__).resolve().parent / "out/pack_vdac"
DACS = [("el", 32), ("vr", 32), ("vc", 32), ("vt", 64)]
L = ["corner T | vc new: v0 vfs (V) LSB mV DNL min/max INL|max| mono | code@1.62 V (margin LSB) code@1.58 | "
     "new-old shift mV min/max | max|new-sch| mV | el/vr/vt max|new-old| mV"]
W = dict(dnl=(9, -9), inl=0, marg=99, pexs=0, oth=0)
for c in ("tt", "ss", "ff"):
    for t in (0, 27, 85):
        rows = [ln.split() for ln in (D / f"pack_{c}_{t}.log").read_text().splitlines() if ln.startswith("P ")]
        a = np.array([[float(x) for x in r[2:]] for r in rows])
        oth = 0
        for i, (k, n) in enumerate(DACS):
            s, o, nw = a[:n, 3 * i], a[:n, 3 * i + 1], a[:n, 3 * i + 2]
            if k != "vc":
                oth = max(oth, np.max(np.abs(nw - o)) * 1e3)
                continue
            lsb = (nw[-1] - nw[0]) / 31
            d = np.diff(nw) / lsb - 1
            inl = (nw - (nw[0] + lsb * np.arange(32))) / lsb
            c162 = int(np.argmax(nw >= 1.62)) if nw[-1] >= 1.62 else None
            cr = (1.62 - nw[0]) / lsb
            c158 = int(np.argmin(np.abs(nw - 1.58)))
            sh = (nw - o) * 1e3
            pexs = np.max(np.abs(nw - s)) * 1e3
            mono = np.all(np.diff(nw) > 0)
            L.append(f"{c} {t:2d} | {nw[0]:.4f} {nw[-1]:.4f} {lsb*1e3:.2f} {d.min():+.2f}/{d.max():+.2f} {np.abs(inl).max():.2f} "
                     f"{'mono' if mono else 'NONMONO'} | {c162} ({31 - cr:.2f}) {c158}={nw[c158]:.4f} | {sh.min():.1f}/{sh.max():.1f} | "
                     f"{pexs:.2f}")
            W["dnl"] = (min(W["dnl"][0], d.min()), max(W["dnl"][1], d.max())); W["inl"] = max(W["inl"], np.abs(inl).max())
            W["marg"] = min(W["marg"], 31 - cr); W["pexs"] = max(W["pexs"], pexs)
        L[-1] += f" | {oth:.3f}"; W["oth"] = max(W["oth"], oth)
L.append(f"WORST vc: DNL {W['dnl'][0]:+.2f}/{W['dnl'][1]:+.2f} INL {W['inl']:.2f} LSB; 1.62 V margin to full scale "
         f"{W['marg']:.2f} LSB; max|PEX-sch| {W['pexs']:.2f} mV; other DACs max|new-old| {W['oth']:.4f} mV")
out = Path("/work/layout/bias/m3pack/vdac_pex_dc_summary.txt")
out.write_text("\n".join(L) + "\n")
print("\n".join(L))
