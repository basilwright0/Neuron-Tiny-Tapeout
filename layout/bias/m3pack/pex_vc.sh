# vdac (MIL-133): PEX of the vdacr_vc leaf currently in layout/bias -> m3pack/<tag>_vdacr_vc.spice (run in /work)
set -e
cd /work/layout/bias
RC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc
CELL=vdacr_vc; export BCELL=$CELL PEX=1
mkdir -p out/ext_$CELL out/pex_$CELL
magic -dnull -noconsole -rcfile $RC build.tcl > /work/layout/bias/m3pack/${1}_${CELL}_magic.log 2>&1
sed "s/\bvdacr_vc\b/vdacr_vc_$1/g" out/${CELL}_pex.spice > /work/layout/bias/m3pack/${1}_${CELL}.spice
grep MAGIC_DRC_COUNT /work/layout/bias/m3pack/${1}_${CELL}_magic.log
