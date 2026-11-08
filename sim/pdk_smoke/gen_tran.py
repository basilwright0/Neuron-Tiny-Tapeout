# 200 fF MIM (cap_mim_2f0_m4m5_noshield, option B M4-M5) discharged by nfet_03v3 W/L=1/1 at various gate biases,
# plus a ppolyf_u_3k poly resistor RC and an ideal 1 nA current-source cap check.
S="9.79u"   # 9.79 x 9.79 um -> 1.99e-3*A + 2.383e-10*P ~= 200 fF
hdr=f"""* {{title}}
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.temp 27
.option gmin=1e-18 abstol=1e-18 reltol=1e-4 method=gear
XC c 0 cap_mim_2f0_m4m5_noshield c_width={S} c_length={S}
.ic v(c)=1.0
"""
cases={
 'cal':   ("ideal 1nA discharge (C check)", "I1 c 0 1n", "10u", "200n"),
 'vg0':   ("nfet Vg=0 hold droop", "Vg g 0 0\nXM c g 0 0 nfet_03v3 W=1u L=1u", "10", "10m"),
 'vg035': ("nfet Vg=0.35", "Vg g 0 0.35\nXM c g 0 0 nfet_03v3 W=1u L=1u", "20m", "2u"),
 'vg045': ("nfet Vg=0.45", "Vg g 0 0.45\nXM c g 0 0 nfet_03v3 W=1u L=1u", "2m", "200n"),
 'vg12':  ("nfet Vg=1.2 (strong inversion, triode RC)", "Vg g 0 1.2\nXM c g 0 0 nfet_03v3 W=1u L=1u", "100n", "10p"),
 'rpoly': ("ppolyf_u_3k W=1u L=333u RC", "XR c 0 0 ppolyf_u_3k r_width=1u r_length=333u", "3u", "1n"),
}
for k,(t,dev,tstop,tstep) in cases.items():
    open(f"out/tran_{k}.cir","w").write(hdr.format(title=t)+dev+f"""
.control
tran {tstep} {tstop} uic
set wr_singlescale
wrdata out/tran_{k}.dat v(c)
quit
.endc
.end
""")
