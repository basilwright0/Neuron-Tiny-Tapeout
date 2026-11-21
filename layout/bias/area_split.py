"""Area split of leaf GDS files (b1a, MIL-133): device (COMP|Poly2 +0.3), n-well only, p-tap ring, M1/M2 routing, empty.
   python3 layout/bias/area_split.py out/<cell>.gds ...  (EDA container)"""
import klayout.db as db, sys
L={'comp':(22,0),'poly':(30,0),'nwell':(21,0),'m1':(34,0),'m2':(36,0),'v1':(35,0)}
for f in sys.argv[1:]:
    ly=db.Layout(); ly.read(f); top=ly.top_cell()
    def R(n): return db.Region(top.begin_shapes_rec(ly.layer(*L[n]))).merged()
    fr=db.Region(top.bbox()); A=lambda r: r.area()*ly.dbu**2
    ring=db.Region(top.bbox()) - db.Region(top.bbox().enlarged(int(-1.2/ly.dbu)))
    core=(R('comp')+R('poly')).merged()
    dev=(core.sized(int(0.3/ly.dbu)).merged()&fr)-ring
    well=(R('nwell')-dev)&fr
    rout=((R('m1')+R('m2')).merged()-dev-well-ring)
    emp=fr-dev-well-ring-rout.sized(int(0.25/ly.dbu))
    tot=A(fr)
    print(f, 'frame %.0f'%tot, 'device(core+0.3) %.0f'%A(dev), 'core %.0f'%A(core), 'nwell-only %.0f'%A(well), 'ring %.0f'%A(ring), 'routing(M1/M2 +0.25 halo) %.0f'%A(rout.sized(int(0.25/ly.dbu))-dev-well-ring), 'empty %.0f'%A(emp))

    for nm,(y0,y1) in {'rails_res':(0,19.4),'rails_caps':(19.4,35.6),'rails_hdr_pins':(35.6,48)}.items():
        if 'rails' not in f: continue
        b=db.Region(db.Box(0,int(y0/ly.dbu),top.bbox().right,int(y1/ly.dbu)))
        print('  ',nm,'band %.0f'%A(b),'dev %.0f'%A(dev&b),'empty %.0f'%A(emp&b))
