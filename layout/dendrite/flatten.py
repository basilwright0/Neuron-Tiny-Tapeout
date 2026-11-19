"""Flatten dend_d1 (cells/dendrite/dendrite.spice + library cells) to transistors.

Used two ways:
  * by slotgen.py, which places one PDK device cell per transistor (single source of truth);
  * standalone, to write the LVS reference netlist slot_ah_lvs.spice (flat, numeric W/L, no Cfb).

Only what these cell files use is supported: .subckt with name=default params, X instances of
subckts or of nfet_03v3/pfet_03v3 (W=, L=), C elements, {param} expressions, SI suffixes.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ["cells/neuron/membrane.spice", "cells/neuron/lif.spice", "cells/readout/readout.spice",
         "cells/neuron/synapse.spice", "cells/dendrite/dtrim.spice", "cells/dendrite/dendrite.spice",
         ]
MODELS = {"nfet_03v3", "pfet_03v3"}
SI = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}


def num(s, env):
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
        if s in env:
            return env[s]
        return eval(s, {}, dict(env))
    if s in env:
        return env[s]
    m = re.fullmatch(r"([-+0-9.eE]+)(meg|[fpnumk])?", s.lower())
    if not m:
        raise ValueError(f"cannot parse number {s!r}")
    return float(m.group(1)) * SI.get(m.group(2) or "", 1.0)


def read_lines(files):
    out = []
    for f in files:
        cur = None
        for raw in (ROOT / f).read_text().splitlines():
            ln = raw.split(";")[0].rstrip()
            if not ln.strip() or ln.lstrip().startswith("*"):
                continue
            if ln.lstrip().startswith("+") and out:
                out[-1] += " " + ln.lstrip()[1:]
            else:
                out.append(ln.strip())
    return out


def parse(files=FILES):
    subckts = {}
    cur = None
    for ln in read_lines(files):
        tok = ln.split()
        if tok[0].lower() == ".subckt":
            ports, params = [], {}
            for t in tok[2:]:
                if "=" in t:
                    k, v = t.split("=", 1)
                    params[k] = v
                else:
                    ports.append(t)
            cur = dict(name=tok[1], ports=ports, params=params, body=[])
            subckts[tok[1]] = cur
        elif tok[0].lower() == ".ends":
            cur = None
        elif cur is not None:
            cur["body"].append(tok)
    return subckts


def flatten(top="dend_d1", files=FILES, keep_caps=False):
    """Return list of devices: dict(name, model, d, g, s, b, W, L) (W/L in um) and caps."""
    sub = parse(files)
    devs, caps = [], []

    def expand(cname, prefix, conn, overrides):
        sc = sub[cname]
        env = {}
        for k, v in sc["params"].items():
            env[k] = num(v, env)
        for k, v in overrides.items():
            env[k] = v
        nets = dict(zip(sc["ports"], conn))

        def net(n):
            if n in nets:
                return nets[n]
            if n in ("0",):
                return n
            return prefix + n

        for tok in sc["body"]:
            name = tok[0]
            if name[0].upper() == "C":
                caps.append(dict(name=prefix + name, a=net(tok[1]), b=net(tok[2]), C=num(tok[3], env)))
                continue
            if name[0].upper() != "X":
                raise ValueError(f"unsupported element {tok}")
            args = [t for t in tok[1:] if "=" not in t]
            kv = dict(t.split("=", 1) for t in tok[1:] if "=" in t)
            model = args[-1]
            pins = [net(a) for a in args[:-1]]
            if model in MODELS:
                d, g, s, b = pins
                devs.append(dict(name=prefix + name, model=model, d=d, g=g, s=s, b=b,
                                 W=round(num(kv["W"], env) * 1e6, 4), L=round(num(kv["L"], env) * 1e6, 4)))
            else:
                ov = {k: num(v, env) for k, v in kv.items()}
                expand(model, prefix + name + ".", pins, ov)

    expand(top, "", sub[top]["ports"], {})
    return sub[top]["ports"], devs, caps


def write_lvs(path, top="dend_d1"):
    ports, devs, caps = flatten(top)
    L = [f"* LVS reference for {top}: flattened from cells/dendrite/dendrite.spice by layout/dendrite/flatten.py",
         f"* Cfb (MOM capacitor, value from PEX) omitted: {', '.join(c['name'] for c in caps)}",
         f".subckt {top} {' '.join(ports)}"]
    for d in devs:
        nm = "X" + d["name"].replace(".", "_")
        L.append(f"{nm} {d['d']} {d['g']} {d['s']} {d['b']} {d['model']} W={d['W']:g}u L={d['L']:g}u")
    L.append(f".ends {top}")
    Path(path).write_text("\n".join(L) + "\n")
    return ports, devs, caps


if __name__ == "__main__":
    top = sys.argv[1] if len(sys.argv) > 1 else "dend_d1"
    out = Path(__file__).with_name(f"{top}_lvs.spice")
    ports, devs, caps = write_lvs(out, top)
    print(f"{len(devs)} transistors, {len(caps)} caps omitted -> {out}")
    for d in devs:
        print(f"  {d['name']:12s} {d['model'][0]} W={d['W']:<5g} L={d['L']:<5g} d={d['d']} g={d['g']} s={d['s']} b={d['b']}")
