cd /work/sim/tb/bias
for cfg in "typical 27 2.6 3.3 2" "typical 27 2.6 2.4 2" "typical 27 3.3 3.3 2" "typical 27 2.0 3.3 2" "typical 27 2.6 3.3 6" "typical 27 1.5 3.3 2"; do
python3 t_ladder.py $cfg; ngspice -b out/lad.cir 2>/dev/null | grep -E '^(R|V) ' | python3 -c "
import sys
for l in sys.stdin:
  t=l.split()
  if t[0]=='R':
    x=[float(v) for v in t[1:]]; print('$cfg ratios', ' '.join('%.3f'%(x[k]/x[k+1]) for k in range(0,18)))
  else: print(l.strip())
"
done
