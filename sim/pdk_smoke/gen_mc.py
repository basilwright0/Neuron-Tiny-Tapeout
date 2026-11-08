# generates out/mc_mismatch_<seed>.cir: N instances per geometry, mismatch on (sw_stat_mismatch=1)
import sys
N=int(sys.argv[1]); seed=int(sys.argv[2]); lib=sys.argv[3]; glob_=sys.argv[4]; mm=sys.argv[5]
vg=0.35
L=[f"* nfet_03v3 MC: lib={lib} sw_stat_global={glob_} sw_stat_mismatch={mm} seed={seed}",
   ".option seed=%d"%seed,
   ".include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice",
   f".param sw_stat_global={glob_}", f".param sw_stat_mismatch={mm}",
   f".lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {lib}",
   ".temp 27", f"Vg g 0 {vg}", "Vd d 0 1.0"]
for k in range(N):
    L.append(f"VA{k} d a{k} 0"); L.append(f"XA{k} a{k} g 0 0 nfet_03v3 W=1u L=1u")
    L.append(f"VB{k} d b{k} 0"); L.append(f"XB{k} b{k} g 0 0 nfet_03v3 W=0.5u L=2u")
L.append(".control"); L.append("op")
L.append("echo IA " + " ".join("$&i(VA%d)"%k for k in range(N)) )
L.append("echo IB " + " ".join("$&i(VB%d)"%k for k in range(N)) )
L.append("quit"); L.append(".endc"); L.append(".end")
open(f"out/mc_{lib}_g{glob_}_m{mm}_s{seed}.cir","w").write("\n".join(L)+"\n")
