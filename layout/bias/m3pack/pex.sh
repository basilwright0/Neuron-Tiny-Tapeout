# run inside EDA container from /work: PEX of the 4 vdacr leaves currently in layout/bias, tag $1
set -e
cd /work/layout/bias
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
for c in el vr vc vt; do
  CELL=vdacr_$c; export BCELL=$CELL PEX=1
  mkdir -p out/ext_$CELL out/pex_$CELL
  magic -dnull -noconsole -rcfile $RC build.tcl > /work/layout/bias/m3pack/${1}_${CELL}_magic.log 2>&1
  sed "s/\bvdacr_$c\b/vdacr_${c}_$1/g" out/${CELL}_pex.spice > /work/layout/bias/m3pack/${1}_${CELL}.spice
  grep MAGIC_DRC_COUNT /work/layout/bias/m3pack/${1}_${CELL}_magic.log
done
