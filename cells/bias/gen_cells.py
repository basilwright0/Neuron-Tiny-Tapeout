#!/usr/bin/env python3
"""Generator for the B1 shared bias generator netlists (cells/bias/*.spice).

Run:  python3 cells/bias/gen_cells.py      (writes the .spice files next to this script)

Every unit device is its own instance so that the PDK mismatch wrapper (one agauss
sample per subckt instance) gives the correct per-unit statistics.  Drain/source
junction areas are given explicitly (AD=AS=W*0.6um, PD=PS=2*(W+0.6um)) so that the
junction leakage floor is modelled (the PDK default is AD=AS=0 -> no leakage).

Rev B (2026-11-17, layout pass):
  * all poly resistors are ppolyf_u_1k (magic cannot extract ppolyf_u_3k, so it could not be
    LVS-checked); strings run at ~20 uA and are built from identical unit strips;
  * rail decaps are pfet accumulation caps referenced to the rail's own supply
    (vsn -> vss, vsp -> vdd); see docs/research/B1-bias-report.md "Re-checks";
  * bias_master: fixed m = 1 (I_in = I_nd/16), UA0 modes (ext /1, ext /16, stimulus, internal
    reference monitor), BIAS_EN, fixed outputs vbn_prb / ib_r1 / ib_t2;
  * idac: range one-hot comes decoded from the control macro (active high for idac_n,
    active low for idac_p), the in-cell logic inverters are gone;
  * receivers (rx_n / rx_p) and the B1 top level bias_b1 (the layout's LVS reference).

Rev C (2026-11-19, docs/08 Updated Plan.md s4):
  * fixed range per current DAC: bias_rangegen -> bias_ladder (two short R-2R ladders, one fixed tap
    per DAC); idac_n/_p lose the range mux (5-bit fine code, code 0 = off); speed S is set by I_nd;
  * five current DACs (vbn_leak, vbn_ref, vbp_syn, vbn_ax, vbp_w); vbp_st = I_nd/16 fixed;
  * voltage path: the rails string tap vglp (VDD*4/11 = 1.2 V) -> bias_vi (V-to-I, 20 uA) -> four
    resistor-chain DACs: el, vreset_src, vth_cmp (5 bit) and vth_ref (6 bit, 0.35-0.75 V); the
    64-tap string and the vdac6 tree are gone; everything is ua[0]-independent and VDD-ratiometric;
  * vbn_prb, ib_r1 (x2) and the internal master reference come from bias_vi (speed-independent);
    ib_t2 is gone (Tier 2 cut).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- unit devices
NU = (2.0, 2.0)    # idac / ladder / range-diode / master unit nfet  W,L [um]  (4 um^2)
PU = (2.0, 2.0)    # same for pfet
TU = (1.0, 2.0)    # trim-cell unit (2 um^2)
SW = (0.5, 0.5)    # steering / mux switch
INV_N = (0.5, 0.28)
INV_P = (1.0, 0.28)
TREE = (0.5, 0.28)  # vdac tree switch (nfet)

# ppolyf_u_1k: R = 1000 * L / (W - 2*0.0148)   (model r_dl ~ 0)
RSH = 1000.0
RW = 1.0
WEFF = RW - 2 * 0.0148
RUNIT_SQ = 15.0                     # unit strip: 15 squares = 15 kOhm
RUNIT_L = round(RUNIT_SQ * WEFF / 0.005) * 0.005     # 14.555 um
RSEG_SQ = 1.349                     # vref tap segment
RSEG_L = round(RSEG_SQ * WEFF / 0.005) * 0.005       # 1.310 um


def fet(kind, name, d, g, s, b, wl):
    w, l = wl
    a = w * 0.6
    p = 2 * (w + 0.6)
    model = "nfet_03v3" if kind == "n" else "pfet_03v3"
    return (f"X{name} {d} {g} {s} {b} {model} W={w:g}u L={l:g}u "
            f"ad={a:g}p as={a:g}p pd={p:g}u ps={p:g}u")


def res(name, a, b, L, W=RW):
    return f"X{name} {a} {b} vss ppolyf_u_1k r_width={W:g}u r_length={L:g}u"


def inv(name, i, o, vdd, vss):
    # pfet bulk = its own supply (an n-well per supply); nfet bulk is always the substrate (vss)
    return [fet("p", name + "p", o, i, vdd, vdd, INV_P),
            fet("n", name + "n", o, i, vss, "vss", INV_N)]


def area(wl):
    return wl[0] * wl[1]


AREA = {}   # cell -> active gate area (um^2) for the report


def write(fname, lines):
    with open(os.path.join(HERE, fname), "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ======================================================================= master
def gen_master():
    L = ["* bias_master: ua[0] master reference input stage (block B1), rev C",
         "* I_nd (current in the 16-unit master diode nd) sets the speed: S = 100 * I_nd / 1 uA",
         "* (S = 10 ... 1000 <-> I_nd = 0.1 ... 10 uA).  Ratioed to I_nd:",
         "*   in_n   sinks   I_nd/16  (n-ladder input)        in_p  sources I_nd/16 (p-ladder input)",
         "*   vbp_st sinks   I_nd/16  from the rx_p05 receiver (detector starve line, fixed ratio)",
         "* UA0 modes (decoded one-hot by the control macro from UA0_MODE / BIAS_EN, see regmap):",
         "*   s0     ua[0] -> nd directly          (mode 0 EXT/1: I_nd = Iref;  mode 3 INT_MON: pad reads V(nd))",
         "*   s1     ua[0] -> nx, 16:1 pre-mirror  (mode 1 EXT/16: I_nd = Iref/16)",
         "*   stim   ua[0] <-> ua0_stim (transmission gate; mode 2 STIM)",
         "*   intref internal reference: the ~1 uA current iint from bias_vi (V-to-I, ua[0]-independent)",
         "*          is switched into nd (modes 2, 3) -> I_nd ~1 uA, S ~100",
         "*   en     BIAS_EN: 0 pulls nd to vss (all ladder currents 0) and en_b turns the strings off",
         "* Secondary ESD: ua[0] -> 1 kOhm ppolyf_u_1k (W=4 um, 1 square) -> clamp diodes to vdd",
         "*   (diode_pd2nw_03v3) and vss (diode_nd2ps_03v3) on the inner node 'pin'; the pad switches see 'pin'.",
         ".subckt bias_master pad in_n in_p vbp_st ua0_stim iint s0 s1 stim intref en en_b vdd vss"]
    a = 0
    L.append(res("RS", "pad", "pin", 3.97, W=4.0))
    L.append("DDP pin vdd diode_pd2nw_03v3 area=10p pj=22u")
    L.append("DDN vss pin diode_nd2ps_03v3 area=10p pj=22u")
    L += inv("IEN", "en", "en_b", "vdd", "vss")
    L += inv("IST", "stim", "stim_b", "vdd", "vss")
    L += inv("IIR", "intref", "intref_b", "vdd", "vss")
    a += 3 * (area(INV_N) + area(INV_P))
    L.append(fet("n", "S0", "nd", "s0", "pin", "vss", (4.0, 0.5)))
    L.append(fet("n", "S1", "nx", "s1", "pin", "vss", (8.0, 0.5)))
    L.append(fet("n", "STN", "ua0_stim", "stim", "pin", "vss", (2.0, 0.5)))
    L.append(fet("p", "STP", "ua0_stim", "stim_b", "pin", "vdd", (4.0, 0.5)))
    a += 2 + 4 + 1 + 2
    # internal reference: iint (sourced by bias_vi) -> pfet switch -> nd
    L.append(fet("p", "SWI", "nd", "intref_b", "iint", "vdd", (2.0, 0.5))); a += 1
    # 16:1 pre-mirror: nx (16 units) -> 1 unit -> p mirror 2:2 -> nd
    for k in range(16):
        L.append(fet("n", f"DX{k}", "nx", "nx", "vss", "vss", NU)); a += area(NU)
    L.append(fet("n", "OX", "px", "nx", "vss", "vss", NU)); a += area(NU)
    for k in range(2):
        L.append(fet("p", f"PX{k}", "px", "px", "vdd", "vdd", PU)); a += area(PU)
        L.append(fet("p", f"QX{k}", "nd", "px", "vdd", "vdd", PU)); a += area(PU)
    for k in range(16):
        L.append(fet("n", f"D{k}", "nd", "nd", "vss", "vss", NU)); a += area(NU)
    L.append(fet("n", "PDN", "nd", "en_b", "vss", "vss", (4.0, 0.5))); a += 2
    L.append(fet("n", "ON", "in_n", "nd", "vss", "vss", NU)); a += area(NU)
    L.append(fet("n", "OP", "pd", "nd", "vss", "vss", NU)); a += area(NU)
    L.append(fet("n", "OS", "vbp_st", "nd", "vss", "vss", NU)); a += area(NU)
    for k in range(2):
        L.append(fet("p", f"PD{k}", "pd", "pd", "vdd", "vdd", PU)); a += area(PU)
        L.append(fet("p", f"PO{k}", "in_p", "pd", "vdd", "vdd", PU)); a += area(PU)
    L.append(".ends bias_master")
    AREA["bias_master"] = a + 8
    write("bias_master.spice", L)


# ======================================================================== rails
# string vdd -[hdr]- top -R- vsp -4R- vgln -2R- vglp -3R- vsn -R- vss ; R = 15 kOhm unit strip
RAIL_SEGS = [("top", "vsp", 1), ("vsp", "vgln", 4), ("vgln", "vglp", 2), ("vglp", "vsn", 3), ("vsn", "vss", 1)]
DECAP = 10.0     # um, square pfet accumulation cap (~2.1 fF/um^2 at |Vgb| = 0.3 V -> ~0.21 pF)


def gen_rails():
    def body(variant):
        L = []
        n = 0
        for a_, b_, k in RAIL_SEGS:
            nodes = [a_] + [f"{a_}_{b_}{i}" for i in range(1, k)] + [b_]
            for i in range(k):
                L.append(res(f"R{n}", nodes[i], nodes[i + 1], RUNIT_L)); n += 1
        L.append(fet("p", "HDR", "top", "en_b", "vdd", "vdd", (4.0, 0.5)))
        c = (DECAP, DECAP)
        if variant == "self":
            # vsn -> vss: pfet gate on vsn, well/S/D on vss (accumulation, Vgb = +0.3 V)
            L.append(f"XC1 vss vsn vss vss pfet_03v3 W={c[0]:g}u L={c[1]:g}u")
            # vsp -> vdd: pfet gate on vdd, its own n-well/S/D on vsp (Vgb = +0.3 V)
            L.append(f"XC2 vsp vdd vsp vsp pfet_03v3 W={c[0]:g}u L={c[1]:g}u")
        elif variant == "cross":   # rev A orientation (vsn -> vdd, vsp -> vss, strong inversion, 15.8 um)
            L.append("XC1 vdd vsn vdd vdd pfet_03v3 W=15.8u L=15.8u")
            L.append("XC2 vss vsp vss vss nfet_03v3 W=15.8u L=15.8u")
        return L

    hdr = ["* bias_rails: shifted-source rails and ladder gate biases (block B1), rev B",
           "* ppolyf_u_1k string of 11 identical 15 kOhm strips (165 kOhm, ~20 uA), ratiometric to VDD,",
           "* switched off by en_b (pfet header).  vsn ~0.3 V, vsp ~VDD-0.3 V, vgln ~1.8 V, vglp ~1.2 V.",
           "* Decaps: pfet accumulation caps referenced to each rail's own supply (vsn->vss, vsp->vdd),",
           f"* {DECAP:g} x {DECAP:g} um each (~0.21 pF at |Vgb| = 0.3 V).",
           "* Ports: vsn vsp vgln vglp en_b vdd vss"]
    L = hdr + [".subckt bias_rails vsn vsp vgln vglp en_b vdd vss"] + body("self") + [".ends bias_rails"]
    # comparison variants for the re-check benches (not used in the chip)
    L += ["* --- re-check variants: rev A cap orientation, and no decaps"]
    L += [".subckt bias_rails_cross vsn vsp vgln vglp en_b vdd vss"] + body("cross") + [".ends bias_rails_cross"]
    L += [".subckt bias_rails_nocap vsn vsp vgln vglp en_b vdd vss"] + body("none") + [".ends bias_rails_nocap"]
    AREA["bias_rails"] = 11 * RUNIT_L * 2.0 + 2 * (DECAP + 1.5) ** 2
    write("bias_rails.spice", L)


# ===================================================================== receivers
RX = {"n4": ("n", (2.0, 4.0), 4), "n1": ("n", (2.0, 4.0), 1), "n2": ("n", (2.0, 4.0), 2), "p05": ("p", (1.0, 4.0), 1),
      "p1": ("p", (1.0, 2.0), 1), "p24": ("p", (2.0, 4.0), 1)}


def gen_rx():
    L = ["* Receiving diodes (block B1): turn an idac output current into a gate-voltage line.",
         "*  rx_n4 : 4 x nfet 2/4 diode (vbn line; neuron tails are 2/4 -> I_neuron = I_line/4)",
         "*  rx_n2 : 2 x nfet 2/4 diode (I_neuron = I_line/2)",
         "*  rx_p05: pfet 1/4 diode (vbp line; neuron starve pfets are 1/2 -> I_neuron = 2 I_line)",
         "*  rx_p1 : pfet 1/2 diode (I_neuron = I_line)",
         "* Ports: line vdd vss"]
    for name, (pol, wl, k) in RX.items():
        L.append(f".subckt rx_{name} line vdd vss")
        for u in range(k):
            if pol == "n":
                L.append(fet("n", f"D{u}", "line", "line", "vss", "vss", wl))
            else:
                L.append(fet("p", f"D{u}", "line", "line", "vdd", "vdd", wl))
        L.append(f".ends rx_{name}")
    write("bias_rx.spice", L)


# ========================================================================= trim
def gen_trim():
    L = ["* trim4_p / trim4_n: per-neuron 4-bit offset-binary gain trim (block B1)",
         "*   I_out = I_ref * (8 + c)/16 , c = c0+2c1+4c2+8c3  -> 0.50x .. 1.4375x (c=8 -> 1.00x)",
         "*   Units 1/2 um (2 um^2): 8 always-on + 1,2,4,8 switched (drain switches).",
         "*   trim_ref_p/_n: the shared 16-unit diode that defines I_ref -> gate line vg.",
         "*   Not used by the floorplan of 2026-11-17 (threshold trims are voltage trims); kept for benches.",
         "* Ports trim4_p: out vg vsp c0 c1 c2 c3 vdd vss  (sources current into out)",
         "* Ports trim4_n: out vg vsn c0 c1 c2 c3 vdd vss  (sinks current from out)",
         "* Ports trim_ref_p: vg vsp vdd   (input current is drawn out of vg)",
         "* Ports trim_ref_n: vg vsn vss   (input current is pushed into vg)"]
    for pol in ("p", "n"):
        rail = "vsp" if pol == "p" else "vsn"
        bulk = "vdd" if pol == "p" else "vss"
        L.append(f".subckt trim4_{pol} out vg {rail} c0 c1 c2 c3 vdd vss")
        a = 0
        for u in range(8):
            L.append(fet(pol, f"B{u}", "out", "vg", rail, bulk, TU)); a += area(TU)
        for b in range(4):
            if pol == "p":
                L += inv(f"IC{b}", f"c{b}", f"cb{b}", "vdd", "vss"); g = f"cb{b}"
            else:
                g = f"c{b}"
            a += (area(INV_N) + area(INV_P)) if pol == "p" else 0
            for u in range(2 ** b):
                L.append(fet(pol, f"U{b}_{u}", f"d{b}", "vg", rail, bulk, TU)); a += area(TU)
            L.append(fet(pol, f"S{b}", "out", g, f"d{b}", bulk, SW)); a += area(SW)
        L.append(f".ends trim4_{pol}")
        AREA[f"trim4_{pol}"] = a
        L.append(f".subckt trim_ref_{pol} vg {rail} {'vdd' if pol=='p' else 'vss'}")
        for u in range(16):
            L.append(fet(pol, f"R{u}", "vg", "vg", rail, "vdd" if pol == "p" else "vss", TU))
        L.append(f".ends trim_ref_{pol}")
        AREA[f"trim_ref_{pol}"] = 16 * area(TU)
    write("bias_trim.spice", L)


# ======================================================================= ladder
# Fixed taps (rev C): ladder node k delivers I_in/2^(k+1) into an 8-unit diode -> idac LSB = I_in/2^(k+4)
LAD_N = (7, (3, 5, 6))      # n-ladder (in_n): nodes 0..6, taps -> pfet diodes -> vgp3 vgp5 vgp6 (idac_p)
LAD_P = (6, (3, 5))         # p-ladder (in_p): nodes 0..5, taps -> nfet diodes -> vgn3 vgn5 (idac_n)
FOLN, FOLP = "vgn5", "vgp6"  # follower-bias gate lines (deepest tap of each side)


def ladder_ports():
    return (["in_n", "in_p"] + [f"vgn{k}" for k in LAD_P[1]] + [f"vgp{k}" for k in LAD_N[1]]
            + ["vsn", "vsp", "vgln", "vglp", "vdd", "vss"])


def gen_ladder():
    L = ["* bias_ladder: two Bult-Geelen MOS R-2R ladders with fixed taps + tap diodes (block B1), rev C",
         f"* n-ladder (gates at vgln, input in_n) has nodes 0..{LAD_N[0]-1}; the shunts at nodes "
         + ",".join(map(str, LAD_N[1])) + " feed 8-unit pfet diodes",
         "*   (drain-boosted by a source follower) -> p gate lines vgp<k> (source vsp) for idac_p.",
         f"* p-ladder (gates at vglp, input in_p) has nodes 0..{LAD_P[0]-1}; taps "
         + ",".join(map(str, LAD_P[1])) + " -> nfet diodes -> vgn<k> (source vsn) for idac_n.",
         "* Node k shunt current = I_in/2^(k+1) = tap diode current; idac LSB = I_in/2^(k+4)  (I_in = I_nd/16).",
         "* (The BSIM split ratio is ~1.93 per halving, so real taps are ~5 % per halving larger.)",
         "* Ports: " + " ".join(ladder_ports()),
         ".subckt bias_ladder " + " ".join(ladder_ports())]
    a = 0
    for kind, pre, inp, gl, dump, bulk, tapn, (nsec, taps) in (
            ("n", "nn", "in_n", "vgln", "vdd", "vss", "xp", LAD_N),
            ("p", "np", "in_p", "vglp", "vss", "vdd", "xn", LAD_P)):
        node = lambda k: inp if k == 0 else f"{pre}{k}"
        for k in range(nsec):
            term = f"{tapn}{k}" if k in taps else dump
            L.append(fet(kind, f"{pre}SH{k}", term, gl, node(k), bulk, NU)); a += area(NU)
            if k < nsec - 1:
                for u in range(2):
                    L.append(fet(kind, f"{pre}SE{k}_{u}", node(k + 1), gl, node(k), bulk, NU)); a += area(NU)
        L.append(fet(kind, f"{pre}TERM", dump, gl, node(nsec - 1), bulk, NU)); a += area(NU)
    for r in LAD_N[1]:       # pfet tap diodes (from the n-ladder) -> vgp<r>
        for u in range(8):
            L.append(fet("p", f"DP{r}_{u}", f"xp{r}", f"vgp{r}", "vsp", "vdd", PU)); a += area(PU)
        L.append(fet("p", f"FP{r}", "vss", f"xp{r}", f"vgp{r}", f"vgp{r}", (2.0, 1.0))); a += 2
        # follower bias from the shifted rail (rev C): a vdd-referenced bias (uA at S = 1000) made the
        # follower Vsg so large at fs/0 C that the tap shunt went into triode (vbn_ref 0.46x at S = 1000)
        L.append(fet("p", f"BP{r}", f"vgp{r}", FOLP, "vsp", "vdd", PU)); a += area(PU)
    for r in LAD_P[1]:       # nfet tap diodes (from the p-ladder) -> vgn<r>
        for u in range(8):
            L.append(fet("n", f"DN{r}_{u}", f"xn{r}", f"vgn{r}", "vsn", "vss", NU)); a += area(NU)
        L.append(fet("n", f"FN{r}", "vdd", f"xn{r}", f"vgn{r}", "vss", (2.0, 1.0))); a += 2
        L.append(fet("n", f"BN{r}", f"vgn{r}", FOLN, "vsn", "vss", NU)); a += area(NU)
    L.append(".ends bias_ladder")
    AREA["bias_ladder"] = a
    write("bias_ladder.spice", L)


# ========================================================================= idac
def gen_idac():
    L = ["* idac_n / idac_p: 5-bit binary current-steering DAC on one fixed ladder tap (block B1), rev C.",
         "* I_out = code * LSB, LSB = tap diode current / 8 (see bias_ladder); code 0 = off.",
         "* Units: 31 x (2/2 um) devices (4 um^2), sources on the shifted rail; unselected",
         "* bits are steered to 'dump', so the gate node never moves on a fine-code change.",
         "* Ports (idac_n SINKS current from out, idac_p SOURCES current into out):",
         "*  out   : output, compliance 0.5-2.5 V",
         "*  dump  : tie to vdd (idac_n) / vss (idac_p)",
         "*  b0..b4: fine code (b4 = MSB), active high, 3.3 V logic",
         "*  g     : gate line (vgn<k> for idac_n, vgp<k> for idac_p, from bias_ladder; or any mirror line)",
         "*  vsn / vsp : unit source rail (shifted rail from bias_rails)",
         "*  vcas  : switch-gate level: vgln (~1.8 V) in bias_b1 for both polarities (rev B: vglp for idac_n);  vdd vss"]
    for pol in ("n", "p"):
        rail = "vsn" if pol == "n" else "vsp"
        bulk = "vss" if pol == "n" else "vdd"
        L.append(f".subckt idac_{pol} out dump b0 b1 b2 b3 b4 g {rail} vcas vdd vss")
        a = 0
        uwl = NU if pol == "n" else PU
        for b in range(5):
            for u in range(2 ** b):
                L.append(fet(pol, f"U{b}_{u}", f"d{b}", "g", rail, bulk, uwl)); a += area(uwl)
            # level inverters on the cascode supply: n swings vss<->vcas, p swings vcas<->vdd.
            on, off = f"bc{b}", f"bd{b}"
            if pol == "n":
                L += inv(f"IC{b}", f"b{b}", off, "vcas", "vss")
                L += inv(f"ID{b}", off, on, "vcas", "vss")
            else:
                L += inv(f"IC{b}", f"b{b}", on, "vdd", "vcas")
                L += inv(f"ID{b}", on, off, "vdd", "vcas")
            a += 2 * (area(INV_N) + area(INV_P))
            L.append(fet(pol, f"SO{b}", "out", on, f"d{b}", bulk, SW)); a += area(SW)
            L.append(fet(pol, f"SD{b}", "dump", off, f"d{b}", bulk, SW)); a += area(SW)
        L.append(f".ends idac_{pol}")
        AREA[f"idac_{pol}"] = a
    write("bias_idac.spice", L)


# ===================================================================== V-to-I + resistor DACs
# V-to-I tap: vglp of the rails string (VDD * 4/11 = 1.20 V, ratiometric, ua[0]-independent)
R0_SQ = 58.5           # V-to-I resistor (kOhm): I_vi = V(vglp)/R0 = 1.187 V (sim) / 58.5k = 20.3 uA
MO = (16.0, 2.0)       # M_out and the three full output copies (pfet), 1:1
MC = (16.0, 1.0)       # their cascodes (gate vglp)
MQ, MQC = (4.0, 2.0), (4.0, 1.0)   # quarter copy (vth_ref chain) and its cascode
VDACR = {  # name: (line, bits, base squares, LSB squares, copy)   V = V(vglp) * k * (base + code*lsb) / R0
    "el": ("el", 5, 48.0, 1.0, 1.0),                    # ~1.00 .. 1.63 V (sim, incl. switch R_on)
    "vr": ("vreset_src", 5, 43.0, 1.0, 1.0),            # ~0.90 .. 1.53 V
    "vc": ("vth_cmp", 5, 60.0, 2.0 / 3.0, 1.0),         # ~1.23 .. 1.64 V (M3 vdac: R_base 53 -> 60 sq, +0.14 V for CMP at EL 1.5)
    "vt": ("vth_ref", 6, 69.0, 1.27, 0.25),             # ~0.35 .. 0.75 V, ~6.4 mV LSB
}
RSW = {5: (8.0, 0.28), 6: (12.0, 0.28)}   # segment shorting switches (nfet), R_on ~180 / ~120 Ohm


def sq2l(sq, W=RW):
    return round(sq * (W - 2 * 0.0148) / 0.005) * 0.005


def chain_res(pre, a_, b_, pieces, sq):
    nodes = [a_] + [f"{pre}{i}" for i in range(1, pieces)] + [b_]
    return [res(f"{pre.upper()}{i}", nodes[i], nodes[i + 1], sq2l(sq / pieces)) for i in range(pieces)]


def gen_vi():
    L = ["* bias_vi (rev C): V-to-I converter I_vi = V(vglp)/R0 feeding the four resistor DACs, the probe",
         "* bias and R1's bias.  Independent of ua[0]: only VDD, the rails-string ratio (vglp = VDD*4/11)",
         "* and ppolyf_u_1k resistor ratios enter.",
         "*   OTA (nfet pair 4/2, pfet mirror, self-biased tail ~0.3 uA) forces x = vglp across R0",
         "*   (60 kOhm) through M_out (pfet 16/2) + cascode (16/1, gate vglp).  I_vi ~20 uA at VDD = 3.3 V.",
         "*   Copies (+ cascodes): 1:1 into el, vreset_src, vth_cmp; 1:4 (4/2) into vth_ref (vdacr_* chains):",
         "*     V = V(vglp) * k * R_chain / R0  -> ratio-accurate, speed-independent, VDD-ratiometric.",
         "*   vbn_prb: copy 0.8/2 (~1 uA) into a 2/2 nfet diode (probe-follower bias line).",
         "*   ib_r1:   4 x nfet 2/2 on vbn_prb (~4.2 uA sink for R1), +4 more with ib_x2.",
         "*   iint:    copy 0.8/2 (~1 uA), the internal master reference (switched into nd in bias_master).",
         "*   en = BIAS_EN: 0 pulls vgvi to vdd (all copies off -> outputs 0 V); startup via ns while vbt is low.",
         "* Ports: vgln vglp en ib_x2 el vreset_src vth_cmp vth_ref vbn_prb ib_r1 iint vdd vss",
         ".subckt bias_vi vgln vglp en ib_x2 el vreset_src vth_cmp vth_ref vbn_prb ib_r1 iint vdd vss"]
    # OTA: output vgvi on the vglp side (vglp > x -> vgvi down -> more current)
    L.append(fet("n", "N1", "vgvi", "vglp", "tl", "vss", (4.0, 2.0)))
    L.append(fet("n", "N2", "oa", "x", "tl", "vss", (4.0, 2.0)))
    L.append(fet("p", "P1", "oa", "oa", "vdd", "vdd", (2.0, 2.0)))
    L.append(fet("p", "P2", "vgvi", "oa", "vdd", "vdd", (2.0, 2.0)))
    L.append(fet("n", "NT", "tl", "vbt", "vss", "vss", (2.0, 2.0)))
    # self-bias: small copy of I_vi -> nfet diode vbt -> tail (1:1)
    L.append(fet("p", "PB", "vbt", "vgvi", "vdd", "vdd", (0.5, 4.0)))
    L.append(fet("n", "NB", "vbt", "vbt", "vss", "vss", (2.0, 2.0)))
    # startup: ns high while vbt is low -> pull vgvi down (only with en)
    L.append(fet("p", "PS", "ns", "vgln", "vdd", "vdd", (0.5, 10.0)))
    L.append(fet("n", "NS", "ns", "vbt", "vss", "vss", (8.0, 2.0)))
    L.append(fet("n", "MS1", "vgvi", "ns", "su", "vss", (0.5, 1.0)))
    L.append(fet("n", "MS2", "su", "en", "vss", "vss", (0.5, 1.0)))
    L.append(fet("p", "POFF", "vgvi", "en", "vdd", "vdd", (1.0, 0.5)))
    # M_out + cascode -> x -> R0; output copies
    for nm, outn, m, mc in (("O", "x", MO, MC), ("E", "el", MO, MC), ("R", "vreset_src", MO, MC),
                            ("C", "vth_cmp", MO, MC), ("T", "vth_ref", MQ, MQC)):
        L.append(fet("p", f"M{nm}", f"m{nm.lower()}", "vgvi", "vdd", "vdd", m))
        L.append(fet("p", f"K{nm}", outn, "vglp", f"m{nm.lower()}", "vdd", mc))
    L += chain_res("r0", "x", "vss", 4, R0_SQ)
    # probe bias line, R1 bias, internal reference
    L.append(fet("p", "PP", "vbn_prb", "vgvi", "vdd", "vdd", (0.8, 2.0)))
    L.append(fet("n", "DB", "vbn_prb", "vbn_prb", "vss", "vss", (2.0, 2.0)))
    for k in range(4):
        L.append(fet("n", f"OR{k}", "ib_r1", "vbn_prb", "vss", "vss", (2.0, 2.0)))
        L.append(fet("n", f"OX{k}", "ibx", "vbn_prb", "vss", "vss", (2.0, 2.0)))
    L.append(fet("n", "SX2", "ib_r1", "ib_x2", "ibx", "vss", (4.0, 0.5)))
    L.append(fet("p", "PI", "iint", "vgvi", "vdd", "vdd", (0.8, 2.0)))
    L.append(".ends bias_vi")
    AREA["bias_vi"] = 4 * (32 + 16) + 8 + 4 + 2 * 8 + 4 + 8 * 4 + 16 + R0_SQ * 2
    L += ["* vdacr_<k> (rev C): binary resistor-chain DAC fed by one I_vi copy (from bias_vi).",
          "*   out - R_base - n0 - [r] - n1 - [2r] - n2 - ... - [2^(N-1) r] - vss",
          "*   segment b is shorted by an nfet (gate = NOT b) when b = 0:  V = I*(R_base + code*r) (+ switch R_on).",
          "*   Monotonic by construction (each step adds r - R_on > 0); ratio-accurate (same ppolyf_u_1k as R0).",
          "*   Ports: out b0..b<N-1> vdd vss"]
    for k, (line, nb, base, lsb, cp) in VDACR.items():
        bits = " ".join(f"b{b}" for b in range(nb))
        L.append(f"* vdacr_{k}: {line}, {nb} bits, copy {cp:g}, R_base {base:g} sq, LSB {lsb:.4g} sq -> "
                 f"{1.2*cp*base/R0_SQ:.3f} .. {1.2*cp*(base+(2**nb-1)*lsb)/R0_SQ:.3f} V (+ switch R_on)")
        L.append(f".subckt vdacr_{k} out {bits} vdd vss")
        L += chain_res("rb", "out", "n0", int(-(-base // 15)), base)
        for b in range(nb):
            top, bot = f"n{b}", ("vss" if b == nb - 1 else f"n{b + 1}")
            sq = lsb * 2 ** b
            pieces = int(-(-sq // 15))
            if pieces == 1:      # short segments at W = 2 um (salicide-block area >= 2 um^2, SB.13)
                w = 2.0 if sq < 2.0 else RW
                L.append(res(f"RS{b}", top, bot, sq2l(sq, w), W=w))
            else:
                L += chain_res(f"rs{b}_", top, bot, pieces, sq)
            # input inverter with L = 1 um: the code lines are long top-level Metal3 runs (antenna ratio)
            L += [fet("p", f"IB{b}p", f"bb{b}", f"b{b}", "vdd", "vdd", (1.0, 1.0)),
                  fet("n", f"IB{b}n", f"bb{b}", f"b{b}", "vss", "vss", (0.5, 1.0))]
            L.append(fet("n", f"SW{b}", top, f"bb{b}", bot, "vss", RSW[nb]))
        L.append(f".ends vdacr_{k}")
        AREA[f"vdacr_{k}"] = (base + (2 ** nb - 1) * lsb) * 2 + nb * (area(INV_N) + area(INV_P) + RSW[nb][0] * 0.28)
    write("bias_vi.spice", L)


# ===================================================================== top level
# current DACs: (index, polarity, gate line, receiver, line)
IDACS = [
    (0, "p", "vgp5", "n4", "vbn_leak"),    # leak tails (2/4): line /4 per neuron
    (1, "p", "vgp3", "n2", "vbn_ref"),     # refractory (2/4): line /2
    (2, "n", "vgn5", "p24", "vbp_syn"),    # synapse weight (2/4): 1:1
    (3, "p", "vgp6", "n1", "vbn_ax"),      # D1 axial coupling (2/4): 1:1
    (4, "n", "vgn3", "p05", "vbp_w"),      # AdEx adaptation increment: rx_p05 (1/4) -> AdEx XPW (1/2) = 2x line
]
RDACS = [(0, "el", "vdacr_el"), (1, "vreset_src", "vdacr_vr"), (2, "vth_cmp", "vdacr_vc")]


def top_ports():
    dig = []
    for k, *_ in IDACS:
        dig += [f"i{k}_b{b}" for b in range(5)]
    for k, *_ in RDACS:
        dig += [f"r{k}_b{b}" for b in range(5)]
    dig += [f"v0_c{b}" for b in range(6)]
    dig += ["ua0_s0", "ua0_s1", "ua0_stim", "ua0_int", "bias_en", "ib_x2"]
    ana = ([ln for *_, ln in IDACS] + ["vbp_st", "vbn_prb", "vth_ref"] + [ln for _, ln, _ in RDACS]
           + ["ib_r1", "ua0_stim_out", "ua0"])
    return dig, ana


def gen_top():
    dig, ana = top_ports()
    L = ["* bias_b1: B1 shared bias generator, top level (block B1), rev C.  LVS reference of layout/bias.",
         "* REV C PORTS STABLE (2026-11-19): the port list below is final for rev C (unchanged from the DRAFT list).",
         "* Digital inputs from the control macro (3.3 V logic, active high; all-zero + bias_en = 0 is safe):",
         "*   i<k>_b0..b4 : current-DAC fine code (b4 = MSB), code 0 = off, fixed range per DAC:",
         "*       i0 vbn_leak, i1 vbn_ref, i2 vbp_syn, i3 vbn_ax, i4 vbp_w",
         "*   r<k>_b0..b4 : resistor-DAC code: r0 el, r1 vreset_src, r2 vth_cmp",
         "*   v0_c0..c5   : vth_ref 6-bit resistor-DAC code (c0 = LSB), ~0.35 .. 0.75 V",
         "*   ua0_s0 ua0_s1 ua0_stim ua0_int bias_en ib_x2 : master mode lines (see bias_master / bias_vi)",
         "* Analog outputs: " + " ".join(ana[:-1]) + " ; ua0 = the ua[0] pad",
         f".subckt bias_b1 {' '.join(dig)} {' '.join(ana)} vdd vss",
         "Xm ua0 in_n in_p vbp_st ua0_stim_out iint ua0_s0 ua0_s1 ua0_stim ua0_int bias_en en_b vdd vss bias_master",
         "Xr vsn vsp vgln vglp en_b vdd vss bias_rails",
         "Xg " + " ".join(ladder_ports()) + " bias_ladder",
         "Xvi vgln vglp bias_en ib_x2 el vreset_src vth_cmp vth_ref vbn_prb ib_r1 iint vdd vss bias_vi",
         "Xd3 vth_ref " + " ".join(f"v0_c{b}" for b in range(6)) + " vdd vss vdacr_vt"]
    for k, line, cell in RDACS:
        L.append(f"Xd{k} {line} " + " ".join(f"r{k}_b{b}" for b in range(5)) + f" vdd vss {cell}")
    for k, pol, g, rx, line in IDACS:
        ins = " ".join(f"i{k}_b{b}" for b in range(5))
        if pol == "n":
            # switch level vgln (1.8 V): the vbp lines sit at 2.3-2.7 V; vglp left the units too little Vds
            # at ss/0 C/S = 1000 (vbp_w MSB step -1 LSB, sim/tb/bias/out/revc/ncas_*.log)
            L.append(f"Xi{k} {line} vdd {ins} {g} vsn vgln vdd vss idac_n")
        else:
            L.append(f"Xi{k} {line} vss {ins} {g} vsp vgln vdd vss idac_p")
        L.append(f"Xx{k} {line} vdd vss rx_{rx}")
    L.append("Xxst vbp_st vdd vss rx_p05")
    L.append(".ends bias_b1")
    write("bias_b1.spice", L)


def gen_all():
    L = ["* B1 bias generator: include all cells (paths relative to the repo mounted at /work)"]
    for f in ("bias_master", "bias_rails", "bias_ladder", "bias_idac", "bias_rx", "bias_vi",
              "bias_trim", "bias_b1"):
        L.append(f".include /work/cells/bias/{f}.spice")
    write("bias_all.spice", L)


if __name__ == "__main__":
    gen_master(); gen_rails(); gen_ladder(); gen_idac(); gen_rx(); gen_vi(); gen_trim(); gen_top()
    gen_all()
    with open(os.path.join(HERE, "area_active.txt"), "w", newline="\n") as f:
        for k, v in AREA.items():
            f.write(f"{k:16s} {v:8.1f} um^2 (sum of W*L, resistors: L*2um)\n")
    print(open(os.path.join(HERE, "area_active.txt")).read())
