import sys; sys.path.insert(0,'/work/model')
import numpy as np
from reference import Compartments
for n in (2,3):
    d=Compartments.star(n); R=d.steady_state_transfer(); print('star',n); print(np.round(R/1e6,1))
d=Compartments.chain(3); print('chain3'); print(np.round(d.steady_state_transfer()/1e6,1))
# plateau: steady state vs DC input into d1 (soma passive), sweep up and down
def ss(d, I, V0):
    V=V0.copy()
    for k in range(20000):
        dV=d._deriv(V,I)*d.C
        # Newton-free: relax with dt
        V=V+dV/ (d.gL+d.G.sum(1)+ (d.plateau_g if d.plateau_g is not None else 0)) *0.3
    return V
for gp in (3e-9,6e-9,10e-9,20e-9):
    d=Compartments.star(2, plateau_g=np.array([0,gp,gp]))
    V=np.full(3,d.EL); up=[]
    Is=np.arange(0,1001,20)*1e-12
    for I in Is:
        V=ss(d,np.array([0,I,0]),V); up.append(V.copy())
    dn=[]
    for I in Is[::-1]:
        V=ss(d,np.array([0,I,0]),V); dn.append(V.copy())
    up=np.array(up); dn=np.array(dn)[::-1]
    j=np.argmax(np.diff(up[:,1])>0.05)
    print(f"gp={gp*1e9:.0f}nS trigger I~{Is[j+1]*1e12:.0f}pA vd before {up[j,1]-d.EL:.3f} after {up[j+1,1]-d.EL:.3f} soma after {up[j+1,0]-d.EL:.3f}; at I=0 down-branch vd={dn[0,1]-d.EL:.3f} (latched if >0.15)")
