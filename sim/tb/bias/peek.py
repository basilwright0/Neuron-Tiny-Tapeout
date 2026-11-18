import numpy as np, sys
for f in sys.argv[1:]:
  a=np.loadtxt(f,skiprows=1); t=a[:,0]; y=a[:,1]
  print(f.split('/')[-1], ' '.join('%.0fus:%.3g'%(tt*1e6,np.interp(tt,t,y)) for tt in [0.15e-3,0.2005e-3,0.202e-3,0.21e-3,0.25e-3,0.3e-3,0.5e-3,1e-3,2e-3,3e-3,3.99e-3] if tt<=t[-1]))
