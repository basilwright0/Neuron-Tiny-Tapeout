"""Kept-slot transistors: a gate shorter than its footprint, drawn inside the footprint of the longer device.

Level 4 (docs/m2-level4-proposal.md, cells aabada4): the leak OTA inputs and degeneration diodes went L 1 -> 0.5 um at
the same W. Drawn with their own PDK cells they would be 0.5 um narrower, their source/drain stripes would move and every
neighbour, pin access and cached route with them. A kept-slot cell is the L = 1 um PDK cell with only the channel
narrowed: the gate (nmos/pmos) and its poly end caps shrink to L about the centre, the freed channel becomes plain
diffusion (longer source/drain, contacts unchanged). Diffusion outline, contact stripes, metal1, well and checkpaint
are those of the footprint cell, so the generators place and route it exactly like the old device. Magic extracts
the drawn L (LVS against the 0.5 um schematic); PEX sees the larger source/drain area.

Cell name: <footprint name with l<L>>_k<slot>, e.g. n_w4_l0p5_k1 (W 4, L 0.5 in the L 1 slot). Written next to the
PDK cells on first use from <model>_w<W>_l<slot>.mag (which gen_devices.tcl makes from the devlist).

    slotgen.py / dendgen.py / cgen.py (via geom.py): KEPT_L = {device name: slot L}
"""
import re
from pathlib import Path

U = 200          # magic internal units per um (magscale 1 10)


def fmt(v):
    return ("%g" % v).replace(".", "p")


def kept_name(model, W, L, slot):
    return f"{model[0]}_w{fmt(W)}_l{fmt(L)}_k{fmt(slot)}"


def base_name(model, W, slot):
    return f"{model[0]}_w{fmt(W)}_l{fmt(slot)}"


def make(devdir, model, W, L, slot):
    """Write devdir/<kept_name>.mag from the footprint cell (W, L = slot) if it is missing; return the cell name."""
    devdir = Path(devdir)
    name = kept_name(model, W, L, slot)
    out = devdir / f"{name}.mag"
    if out.exists():
        return name
    src = devdir / f"{base_name(model, W, slot)}.mag"
    txt = src.read_text()
    gate_layer = "nmos" if model[0] == "n" else "pmos"
    diff_layer = "ndiff" if model[0] == "n" else "pdiff"
    layers, order, layer = {}, [], None
    head = []
    for ln in txt.splitlines():
        m = re.match(r"<< (\w+) >>", ln)
        if m:
            layer = m.group(1)
            if layer not in ("properties", "end"):   # gencell/parameters dropped: not a PDK generator output
                order.append(layer)
                layers.setdefault(layer, [])
            continue
        if layer is None:
            head.append(ln)
        elif layer in ("properties", "end"):
            continue
        elif ln.startswith("rect"):
            layers[layer].append(tuple(int(v) for v in ln.split()[1:5]))
    gates = layers[gate_layer]
    if len(gates) != 1:
        raise ValueError(f"{src}: expected one {gate_layer} rect, got {len(gates)}")
    gx0, gy0, gx1, gy1 = gates[0]
    if gx1 - gx0 != round(slot * U):
        raise ValueError(f"{src}: gate length {(gx1 - gx0) / U} != slot {slot}")
    pad = round((slot - L) * U / 2)
    if pad <= 0 or (gx1 - gx0 - 2 * pad) != round(L * U):
        raise ValueError(f"{name}: L {L} does not fit slot {slot} on the 0.005 um grid")
    nx0, nx1 = gx0 + pad, gx1 - pad
    layers[gate_layer] = [(nx0, gy0, nx1, gy1)]
    layers[diff_layer] = layers.get(diff_layer, []) + [(gx0, gy0, nx0, gy1), (nx1, gy0, gx1, gy1)]
    if diff_layer not in order:
        order.insert(order.index(gate_layer) + 1, diff_layer)
    # poly end caps: the rects that span exactly the old gate in x
    layers["polysilicon"] = [(nx0, y0, nx1, y1) if (x0, x1) == (gx0, gx1) else (x0, y0, x1, y1)
                             for x0, y0, x1, y1 in layers.get("polysilicon", [])]
    lines = list(head)
    for lay in order:
        lines.append(f"<< {lay} >>")
        lines += [f"rect {r[0]} {r[1]} {r[2]} {r[3]}" for r in sorted(layers[lay], key=lambda r: (r[1], r[0]))]
    lines += ["<< properties >>", f"string kept_slot w {W:g} l {L:g} slot {slot:g} from {src.stem}", "<< end >>"]
    out.write_text("\n".join(lines) + "\n")
    return name
