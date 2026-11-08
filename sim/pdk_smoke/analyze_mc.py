import sys,glob,re,numpy as np
def parse(f):
    A=B=None
    for line in open(f,errors='ignore'):
        if line.startswith('IA '): A=np.array([float(x) for x in line.split()[1:]])
        if line.startswith('IB '): B=np.array([float(x) for x in line.split()[1:]])
    return A,B
out=[]
for f in sorted(glob.glob('out/mc_*.log')):
    A,B=parse(f)
    if A is None: out.append(f"{f}: NO DATA"); continue
    for nm,x in (("W1/L1",A),("W0.5/L2",B)):
        out.append("%-40s %-8s n=%d mean=%.3e A  sigma=%.3e A  sigma/mean=%.1f%%  sigma(lnI)=%.3f  min=%.3e max=%.3e"%(
            f,nm,len(x),x.mean(),x.std(ddof=1),100*x.std(ddof=1)/x.mean(),np.log(x).std(ddof=1),x.min(),x.max()))
print("\n".join(out)); open('out/mc_summary.txt','w').write("\n".join(out)+"\n")
