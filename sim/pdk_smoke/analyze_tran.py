import numpy as np, glob
Ut=8.617e-5*300.15
res={}
def load(k):
    d=np.loadtxt(f'out/tran_{k}.dat'); return d[:,0],d[:,1]
t,v=load('cal'); C=1e-9*(t[-1]-t[0])/(v[0]-v[-1]); res['C_extracted_fF']=C*1e15
lines=["C from 1 nA ideal discharge: %.2f fF"%(C*1e15)]
t,v=load('vg0'); lines.append("Vg=0 hold: V(10 s)=%.4f V, droop=%.4f V over 10 s -> I_leak ~ %.2e A (C*dV/dt)"%(v[-1],1-v[-1],C*(1-v[-1])/t[-1]))
for k in ['vg035','vg045','vg12','rpoly']:
    t,v=load(k)
    def tcross(x):
        i=np.where(v<=x)[0]; 
        if len(i)==0: return float('nan')
        i=i[0]; return t[i-1]+(x-v[i-1])*(t[i]-t[i-1])/(v[i]-v[i-1])
    t1e=tcross(np.exp(-1)); t50=tcross(0.5)
    # slope near start (constant-current phase) -> I
    m=(v<0.95)&(v>0.6); I0=C*-np.polyfit(t[m],v[m],1)[0] if m.sum()>3 else float('nan')
    # exponential tail fit
    if k in('rpoly','vg12'): m=(v<0.6)&(v>0.02)
    else: m=(v<0.02)&(v>0.002)
    tau=-1/np.polyfit(t[m],np.log(v[m]),1)[0] if m.sum()>3 else float('nan')
    lines.append("%-6s: t(1V->0.5V)=%.3e s  t(1V->1/e)=%.3e s  I(early)=%.3e A  tail tau(fit)=%.3e s  C*Ut/I=%.3e s"%(k,t50,t1e,I0,tau,C*Ut/I0))
print("\n".join(lines)); open('out/tran_summary.txt','w').write("\n".join(lines)+"\n")
