# usage (in container): bash sim/tb/vsrc/sweep_ac.sh "<par1>" "<par2>" ...   (AC, line-only load, 3 corners)
for p in "$@"; do
  python3 sim/tb/vsrc/tb_vsrc.py ac nodet corners typical:27,ss:0,ff:85,sf:85 par "$p" | grep -v "^Note\|^Warn\|^corner"
done
