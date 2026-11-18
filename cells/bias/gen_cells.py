#!/usr/bin/env python3
"""Generator for the B1 shared bias generator netlists (cells/bias/*.spice).

Run:  python3 cells/bias/gen_cells.py      (writes the .spice files next to this script)

Every unit device is its own instance so that the PDK mismatch wrapper (one agauss
sample per subckt instance) gives the correct per-unit statistics.  Drain/source
junction areas are given explicitly (AD=AS=W*0.6um, PD=PS=2*(W+0.6um)) so that the
junction leakage floor is modelled (the PDK default is AD=AS=0 -> no leakage).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- unit devices
NU = (2.0, 2.0)    # idac / ladder / range-diode unit nfet  W,L [um]  (4 um^2)
PU = (2.0, 2.0)    # same for pfet
NM = (4.0, 2.0)    # master mirror unit nfet (8 um^2)
PM = (4.0, 2.0)    # master p-mirror unit (8 um^2)
TU = (1.0, 2.0)    # trim-cell unit (2 um^2)
SW = (0.5, 0.5)    # steering / mux switch
INV_N = (0.5, 0.28)
INV_P = (1.0, 0.28)
TREE = (0.5, 0.28)  # vdac tree switch (nfet)


def fet(kind, name, d, g, s, b, wl):
    w, l = wl
    a = w * 0.6
    p = 2 * (w + 0.6)
    model = "nfet_03v3" if kind == "n" else "pfet_03v3"
    return (f"X{name} {d} {g} {s} {b} {model} W={w:g}u L={l:g}u "
            f"ad={a:g}p as={a:g}p pd={p:g}u ps={p:g}u")


def inv(name, i, o, vdd, vss):
    return [fet("p", name + "p", o, i, vdd, vdd, INV_P),
            fet("n", name + "n", o, i, vss, vss, INV_N)]


def area(wl):
    return wl[0] * wl[1]


AREA = {}   # cell -> active gate area (um^2) for the report


def write(fname, lines):
    with open(os.path.join(HERE, fname), "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ======================================================================= master
def gen_master():
    L = ["* bias_master: ua[0] master reference input stage (block B1)",
         "* Ports:",
         "*  iref_pad : from ua[0]; external current Iref (1-100 uA) flows INTO this pin",
         "*  in_n     : sink output  I = Iref*m/16 (drawn out of the n-ladder input node)",
         "*  in_p     : source output I = Iref*m/16 (pushed into the p-ladder input node)",
         "*  m0..m3   : ratio code m = m0+2*m1+4*m2+8*m3 (0..15), 3.3 V logic",
         "*  vdd vss  : 3.3 V / 0 V",
         "* Series ppolyf_u_1k 2 kOhm between pad and diode (secondary ESD / isolation);",
         "* the TT pad ring supplies the primary ESD clamp.  Diode = 16 x (4/2) nfet.",
         ".subckt bias_master iref_pad in_n in_p m0 m1 m2 m3 vdd vss"]
    L.append("XRS iref_pad nd vss ppolyf_u_1k r_width=2u r_length=4u")
    a = 0
    for k in range(16):
        L.append(fet("n", f"D{k}", "nd", "nd", "vss", "vss", NM)); a += area(NM)
    for grp, dst in (("a", "in_n"), ("b", "pd")):
        for bit in range(4):
            for u in range(2 ** bit):
                L.append(fet("n", f"O{grp}{bit}_{u}", f"x{grp}{bit}", "nd", "vss", "vss", NM)); a += area(NM)
            L.append(fet("n", f"S{grp}{bit}", dst, f"m{bit}", f"x{grp}{bit}", "vss", (2.0, 0.5))); a += 1.0
    for k in range(8):
        L.append(fet("p", f"PD{k}", "pd", "pd", "vdd", "vdd", PM)); a += area(PM)
        L.append(fet("p", f"PO{k}", "in_p", "pd", "vdd", "vdd", PM)); a += area(PM)
    L.append(".ends bias_master")
    AREA["bias_master"] = a + 8.0  # + resistor 2x4 um
    write("bias_master.spice", L)


# ===================================================================== rangegen
NSEC = 19                      # ladder nodes 0..18
TAPS = {3: 0, 6: 1, 9: 2, 12: 3, 15: 4, 18: 5}   # ladder node -> range index


def gen_rangegen():
    L = ["* bias_rangegen: two Bult-Geelen MOS R-2R ladders + range diodes (block B1)",
         "* n-ladder (gates at vgln) halves the in_n current 19 times; shunts at nodes",
         "* 3,6,..,18 feed 8-unit pfet diodes (drain-boosted by a source follower) -> p gate",
         "* lines vgp0..5 (source vsp).  p-ladder (gates at vglp) does the same for in_p ->",
         "* nfet diodes + followers -> vgn0..5 (source vsn).",
         "* Diode current D_r = I_in/16/8^r ; idac LSB = D_r/8 = I_in/128/8^r.",
         "* Ports:",
         "*  in_n in_p        : ladder inputs (from bias_master)",
         "*  vgn0..vgn5       : n gate lines (ranges 0..5, x8 steps), referenced to vsn",
         "*  vgp0..vgp5       : p gate lines, referenced to vsp",
         "*  vsn vsp          : shifted-source rails (from bias_rails)",
         "*  vgln vglp        : ladder gate biases (from bias_rails)",
         "*  vdd vss",
         ".subckt bias_rangegen in_n in_p vgn0 vgn1 vgn2 vgn3 vgn4 vgn5 "
         "vgp0 vgp1 vgp2 vgp3 vgp4 vgp5 vsn vsp vgln vglp vdd vss"]
    a = 0
    # n ladder: node nn0 = in_n (lowest voltage).  shunt: d=terminal s=node
    for kind, pre, inp, gl, dump, bulk, tapn in (("n", "nn", "in_n", "vgln", "vdd", "vss", "xp"),
                                                 ("p", "np", "in_p", "vglp", "vss", "vdd", "xn")):
        node = lambda k: inp if k == 0 else f"{pre}{k}"
        for k in range(NSEC):
            term = f"{tapn}{TAPS[k]}" if k in TAPS else dump
            L.append(fet(kind, f"{pre}SH{k}", term, gl, node(k), bulk, NU)); a += area(NU)
            if k < NSEC - 1:
                for u in range(2):
                    L.append(fet(kind, f"{pre}SE{k}_{u}", node(k + 1), gl, node(k), bulk, NU)); a += area(NU)
        L.append(fet(kind, f"{pre}TERM", dump, gl, node(NSEC - 1), bulk, NU)); a += area(NU)
    # range diodes with source-follower "drain boost": the tap current enters the diode
    # drain x*, the follower sets the gate line one Vgs below/above x*, so the diode keeps
    # Vds ~0.5 V even when its Vgs is ~0 (shifted-source sub-off-current regime) and the
    # gate line becomes a low-impedance node (follower bias: one unit with gate on line 4 and source on vss/vdd, ~nA, so a line may sit below vsn / above vsp).
    for r in range(6):
        for u in range(8):
            L.append(fet("p", f"DP{r}_{u}", f"xp{r}", f"vgp{r}", "vsp", "vdd", PU)); a += area(PU)
            L.append(fet("n", f"DN{r}_{u}", f"xn{r}", f"vgn{r}", "vsn", "vss", NU)); a += area(NU)
        L.append(fet("n", f"FN{r}", "vdd", f"xn{r}", f"vgn{r}", "vss", (2.0, 1.0))); a += 2
        L.append(fet("n", f"BN{r}", f"vgn{r}", "vgn4", "vss", "vss", NU)); a += area(NU)
        L.append(fet("p", f"FP{r}", "vss", f"xp{r}", f"vgp{r}", f"vgp{r}", (2.0, 1.0))); a += 2
        L.append(fet("p", f"BP{r}", f"vgp{r}", "vgp4", "vdd", "vdd", PU)); a += area(PU)
    L.append(".ends bias_rangegen")
    AREA["bias_rangegen"] = a
    write("bias_rangegen.spice", L)


def gen_rails():
    # string VDD - Ra - vsp - Rb1 - vgln - Rb2 - vglp - Rb3 - vsn - Rc - VSS, ppolyf_u_3k W=1um
    # target: vsp=3.0, vgln=1.8, vglp=1.2, vsn=0.3 at 10 uA
    segs = [("vdd", "vsp", 0.3), ("vsp", "vgln", 1.2), ("vgln", "vglp", 0.6),
            ("vglp", "vsn", 0.9), ("vsn", "vss", 0.3)]
    L = ["* bias_rails: shifted-source rails and ladder gate biases (block B1)",
         "* ppolyf_u_3k string, 10 uA (330 kOhm, 110 squares at W=1 um), ratiometric to VDD.",
         "* vsn ~0.3 V, vsp ~VDD-0.3 V, vgln ~1.8 V (n-ladder gates), vglp ~1.2 V (p-ladder gates).",
         "* 1 pF MOS decaps (MIM needs Metal5, forbidden on TT GF): pfet gate cap vsn->vdd (strong inversion),",
         "* nfet gate cap vsp->vss (strong inversion). ~4 fF/um^2 -> 15.8x15.8 um each.",
         "* Ports: vsn vsp vgln vglp vdd vss",
         ".subckt bias_rails vsn vsp vgln vglp vdd vss"]
    rsq = 3000.0
    tot = 0
    for i, (a_, b_, v) in enumerate(segs):
        r = v / 10e-6
        n = r / rsq
        Lr = n * 1.0 - 2 * 0.0932   # compensate model end correction (r_l = L - 2*dl, dl<0)
        L.append(f"XR{i} {a_} {b_} vss ppolyf_u_3k r_width=1u r_length={Lr:.3f}u")
        tot += n
    L.append("XC1 vdd vsn vdd vdd pfet_03v3 W=15.8u L=15.8u")
    L.append("XC2 vss vsp vss vss nfet_03v3 W=15.8u L=15.8u")
    L.append(".ends bias_rails")
    AREA["bias_rails"] = tot * 1.0 * 3 + 2 * 15.8 * 15.8 * 1.3   # resistor incl. spacing + MOS decaps
    write("bias_rails.spice", L)


# ========================================================================= idac
def gen_idac():
    L = ["* idac_n / idac_p: 3-bit range (one-hot r0..r5, x8 steps) + 5-bit binary fine code",
         "* current-steering DAC on the shared shifted-source gate lines (block B1).",
         "* I_out = code * LSB_r ,  LSB_r = I_in/128/8^r  (I_in = Iref*m/16 from bias_master)",
         "* Nominal Iref=8 uA, m=1: ideal LSB 3.9n,488p,61p,7.6p,0.95p,0.12p; simulated (tt 27C,",
         "* ladder step ~7.1-7.7 instead of 8) 3.5n, 480p, 68p, 9.2p, 1.2p, 0.16p ; FS = 31 LSB",
         "* Units: 31 x (2/2 um) devices (4 um^2), sources on the shifted rail; unselected",
         "* bits are steered to 'dump', so the gate node never moves on a fine-code change.",
         "* Ports (idac_n, SINKS current from out):",
         "*  out   : output, compliance 0.5-2.5 V",
         "*  dump  : tie to vdd (idac_n) / vss (idac_p)",
         "*  r0..r5: range select, one-hot, active high;  roff: 1 = no range (gate to rail)",
         "*  b0..b4: fine code (b4 = MSB), active high, 3.3 V logic",
         "*  g0..g5: gate lines vgn0..5 (idac_n) or vgp0..5 (idac_p) from bias_rangegen",
         "*  vsn / vsp : shifted-source rail",
         "*  vcas  : cascode level for the output switch gates: vglp (~1.2 V) for idac_n,",
         "*          vgln (~1.8 V) for idac_p (both from bias_rails);  vdd vss"]
    for pol in ("n", "p"):
        rail = "vsn" if pol == "n" else "vsp"
        L.append(f".subckt idac_{pol} out dump r0 r1 r2 r3 r4 r5 roff b0 b1 b2 b3 b4 "
                 f"g0 g1 g2 g3 g4 g5 {rail} vcas vdd vss")
        bulk = "vss" if pol == "n" else "vdd"
        a = 0
        # inverters
        if pol == "n":
            for b in range(5):
                L += inv(f"IB{b}", f"b{b}", f"bb{b}", "vdd", "vss")
            selg = [f"r{r}" for r in range(6)]
            offg = "roff"
        else:
            for b in range(5):
                L += inv(f"IB{b}", f"b{b}", f"bb{b}", "vdd", "vss")
            for r in range(6):
                L += inv(f"IR{r}", f"r{r}", f"rb{r}", "vdd", "vss")
            L += inv("IRO", "roff", "rboff", "vdd", "vss")
            selg = [f"rb{r}" for r in range(6)]
            offg = "rboff"
        a += 11 * (area(INV_N) + area(INV_P)) if pol == "p" else 5 * (area(INV_N) + area(INV_P))
        for r in range(6):
            L.append(fet(pol, f"MX{r}", f"g{r}", selg[r], "gl", bulk, (0.5, 1.0))); a += 0.5
        L.append(fet(pol, "MXOFF", rail, offg, "gl", bulk, (0.5, 1.0))); a += 0.5
        uwl = NU if pol == "n" else PU
        for b in range(5):
            for u in range(2 ** b):
                L.append(fet(pol, f"U{b}_{u}", f"d{b}", "gl", rail, bulk, uwl)); a += area(uwl)
            # output/dump switch gates swing vss<->vcas (n) or vcas<->vdd (p): the "on" switch is a
            # cascode that pins the unit drain (~0.8 V n / ~2.5 V p) independent of out.
            # the dump switch gets the same cascode level, so the unit drain stays at the
            # same voltage in both states (no slewing of d<b>, no wrong-sign glitch).
            if pol == "n":
                L += inv(f"IC{b}", f"bb{b}", f"bc{b}", "vcas", "vss")
                L += inv(f"ID{b}", f"bc{b}", f"bd{b}", "vcas", "vss")
            else:
                L += inv(f"IC{b}", f"b{b}", f"bc{b}", "vdd", "vcas")
                L += inv(f"ID{b}", f"bc{b}", f"bd{b}", "vdd", "vcas")
            on = f"bc{b}"; off = f"bd{b}"
            a += 2 * (area(INV_N) + area(INV_P))
            L.append(fet(pol, f"SO{b}", "out", on, f"d{b}", bulk, SW)); a += area(SW)
            L.append(fet(pol, f"SD{b}", "dump", off, f"d{b}", bulk, SW)); a += area(SW)
        L.append(f".ends idac_{pol}")
        AREA[f"idac_{pol}"] = a
    write("bias_idac.spice", L)


# ========================================================================= vdac
def gen_vdac():
    # string: Rbot (0.3 V), 63 segments of 1.7/63 V, Rtop (1.3 V); 3.3 uA total
    I = 3.3e-6
    rsq = 3000.0
    L = ["* vref_string64: shared ratiometric poly string (ppolyf_u_3k, W=1 um, 3.3 uA)",
         "*   t_k = VDD*(0.3 + k*1.7/63)/3.3   (0.30 .. 2.00 V at VDD=3.3 V)",
         "*   Ports: t0..t63 vdd vss.  One string serves all vdac6 instances.",
         ".subckt vref_string64 " + " ".join(f"t{k}" for k in range(64)) + " vdd vss"]
    def res(name, a_, b_, v):
        n = v / I / rsq
        return f"XR{name} {a_} {b_} vss ppolyf_u_3k r_width=1u r_length={n - 2*0.0932:.4f}u", n
    tot = 0
    l, n = res("bot", "t0", "vss", 0.3); L.append(l); tot += n
    for k in range(63):
        l, n = res(f"s{k}", f"t{k+1}", f"t{k}", 1.7 / 63); L.append(l); tot += n
    l, n = res("top", "vdd", "t63", 1.3); L.append(l); tot += n
    L.append(".ends vref_string64")
    AREA["vref_string64"] = tot * 1.0 * 3
    L += ["* vdac6: 6-bit binary nfet pass-gate tree selecting one string tap (no buffer).",
          "*   Ports: out t0..t63 c0..c5 (c0 = LSB, 3.3 V logic) vdd vss",
          ".subckt vdac6 out " + " ".join(f"t{k}" for k in range(64)) + " c0 c1 c2 c3 c4 c5 vdd vss"]
    a = 0
    for b in range(6):
        L += inv(f"IC{b}", f"c{b}", f"cb{b}", "vdd", "vss"); a += area(INV_N) + area(INV_P)
    prev = [f"t{k}" for k in range(64)]
    for lev in range(6):
        nxt = []
        for j in range(len(prev) // 2):
            o = "out" if len(prev) == 2 else f"n{lev}_{j}"
            L.append(fet("n", f"T{lev}_{j}a", prev[2*j], f"cb{lev}", o, "vss", TREE))
            L.append(fet("n", f"T{lev}_{j}b", prev[2*j+1], f"c{lev}", o, "vss", TREE))
            a += 2 * area(TREE)
            nxt.append(o)
        prev = nxt
    L.append(".ends vdac6")
    AREA["vdac6"] = a
    write("bias_vdac.spice", L)


# ========================================================================= trim
def gen_trim():
    L = ["* trim4_p / trim4_n: per-neuron 4-bit offset-binary gain trim (block B1)",
         "*   I_out = I_ref * (8 + c)/16 , c = c0+2c1+4c2+8c3  -> 0.50x .. 1.4375x (c=8 -> 1.00x)",
         "*   Units 1/2 um (2 um^2): 8 always-on + 1,2,4,8 switched (drain switches).",
         "*   trim_ref_p/_n: the shared 16-unit diode that defines I_ref -> gate line vg.",
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


def gen_all():
    L = ["* B1 bias generator: include all cells (paths relative to the repo mounted at /work)"]
    for f in ("bias_master", "bias_rails", "bias_rangegen", "bias_idac", "bias_vdac", "bias_trim"):
        L.append(f".include /work/cells/bias/{f}.spice")
    write("bias_all.spice", L)


if __name__ == "__main__":
    gen_master(); gen_rails(); gen_rangegen(); gen_idac(); gen_vdac(); gen_trim(); gen_all()
    with open(os.path.join(HERE, "area_active.txt"), "w", newline="\n") as f:
        for k, v in AREA.items():
            f.write(f"{k:16s} {v:8.1f} um^2 (sum of W*L, resistors: squares*W*3)\n")
    print(open(os.path.join(HERE, "area_active.txt")).read())
