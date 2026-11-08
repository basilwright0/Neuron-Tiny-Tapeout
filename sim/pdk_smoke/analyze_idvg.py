import numpy as np, glob, os
targets=[1e-12,1e-11,1e-9,1e-8]
def vg_at(v,i,t):
    li=np.log10(np.maximum(i,1e-30))
    k=np.where(li>=np.log10(t))[0]
    if len(k)==0: return float('nan')
    k=k[0]
    if k==0: return float('nan')  # already above target at Vgs=0
    return v[k-1]+(np.log10(t)-li[k-1])*(v[k]-v[k-1])/(li[k]-li[k-1])
rows=[]
for f in sorted(glob.glob('out/idvg_*.dat')):
    d=np.loadtxt(f,skiprows=1); v=d[:,0]
    tag=os.path.basename(f)[5:-4]
    for j,name in enumerate(['W1L1 Vds0.1','W1L1 Vds1.0','W0.5L2 Vds0.1','W0.5L2 Vds1.0']):
        i=d[:,j+1]; li=np.log10(np.maximum(i,1e-30))
        ss=np.diff(v)/np.diff(li); m=(i[1:]>1e-14)&(i[1:]<1e-8)
        ssmin=np.min(ss[m])*1e3 if m.any() else float('nan')
        vt=[vg_at(v,i,t) for t in targets]
        rows.append((tag,name,i[0],ssmin,*vt,i[-1]))
hdr="%-12s %-15s %10s %8s %8s %8s %8s %8s %10s"%("corner_T","device","Id@Vgs=0","SSmV/dec","Vg@1pA","Vg@10pA","Vg@1nA","Vg@10nA","Id@1.2V")
print(hdr)
with open('out/idvg_summary.txt','w') as fo:
    fo.write(hdr+"\n")
    for r in rows:
        s="%-12s %-15s %10.3e %8.1f %8.3f %8.3f %8.3f %8.3f %10.3e"%r
        print(s); fo.write(s+"\n")
