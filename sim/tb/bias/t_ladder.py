import sys
P="/foss/pdks/gf180mcuD/libs.tech/ngspice"
corner, temp, vgl, vterm, L_ = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
o=[f"* ladder test", f".include {P}/design.ngspice", f".lib {P}/sm141064.ngspice {corner}", f".temp {temp}",
   ".option gmin=1e-18 abstol=1e-18 reltol=1e-6", "Iin n0 0 500n", f"Vg g 0 {vgl}", f"Vt t 0 {vterm}"]
def f(n,d,g,s): return f"X{n} {d} {g} {s} 0 nfet_03v3 W=2u L={L_}u ad=1.2p as=1.2p pd=5.2u ps=5.2u"
for k in range(19):
    o.append(f"Vs{k} t s{k} 0"); o.append(f("SH%d"%k, f"s{k}", "g", f"n{k}"))
    if k<18:
        o.append(f("SEa%d"%k, f"n{k+1}", "g", f"n{k}")); o.append(f("SEb%d"%k, f"n{k+1}", "g", f"n{k}"))
o.append("Vst t st 0"); o.append(f("TERM","st","g","n18"))
o += [".control","op","echo R " + " ".join(f"$&i(vs{k})" for k in range(19)), "echo V $&v(n0) $&v(n9) $&v(n18)", "quit",".endc",".end"]
open("out/lad.cir","w").write("\n".join(o)+"\n")
