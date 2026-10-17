"""Reviewable design proposals; never as-built facts or acceptance flags.

Called explicitly by the project preparation workflow, not by rendering or
project loading. Existing values and proposal bases are retained in a ledger.
"""
from copy import deepcopy
import math
import re

from .igird_dowel_detail35 import value,resolve
from .igird_dowel_joint import development_requirements
from .igird_station36_steel import positions


def propose(interface,params,strand_rows,*,dowel_db_mm,dowel_fy_MPa,mesh_proposal=None):
    out=deepcopy(interface);rows=deepcopy(strand_rows);changes=[]
    detail=out['dowel_connection']
    def change(target,key,new,label,basis):
        old=deepcopy(target.get(key))
        if old!=new:
            target[key]=new;changes.append({'Input':label,'Previous':str(old),'Proposed':str(new),'Basis':basis})
    db,fy=float(dowel_db_mm),float(dowel_fy_MPa)
    width,cover,A=[value(v) for v in (params.get('T2_mm'),detail.get('girder_clear_cover_required_mm'),detail.get('row_spacing_mm'))]
    if all(v is not None and v>0 for v in (width,cover,A)) and (width-A-db)/2<cover:
        proposed=math.floor((width-2*cover-db)/10)*10.
        if proposed>db:
            change(detail,'row_spacing_mm',proposed,'A — U-leg centres (mm)',
                f'Proposed design: web {width:g} − two covers {cover:g} − db {db:g}; round down to 10 mm. Verify full polygon fit.')
    req=development_requirements(db_mm=db,fy_MPa=fy,fc_slab_MPa=float(params['deck_fc_MPa']),
        fc_girder_MPa=float(params['girder_fc_MPa']),coating=detail.get('coating'))
    ts=value(params.get('Tslab_mm'));B=value(resolve(detail,slab_thickness_mm=ts,db_mm=db).get('slab_ldh_available_mm'))
    # The existing unmodified full-yield requirement; no excess-steel or
    # unverified confinement reduction is substituted for tie anchorage.
    needed=float(req['hook_required_mm']);proposed=math.ceil(needed/10)*10.
    slabcover=value(detail.get('slab_clear_cover_required_mm'))
    if B is not None and B<needed and ts is not None and slabcover is not None and ts-proposed>=slabcover:
        change(detail,'hook_top_depth_mm',ts-proposed,'E — slab top to outside hook (mm)',
            f'Proposed design: B={proposed:g} >= full-yield hook requirement {needed:.3f} mm; E=Tslab−B. No anchorage reduction assumed.')
    detail.update(resolve(detail,slab_thickness_mm=ts,db_mm=db))
    if mesh_proposal:
        mesh=detail.setdefault('slab_transverse_mesh',{})
        for layer in ('top','bottom'):
            saved=mesh.setdefault(layer,{})
            prefix='deck_long_rebar_'+layer+'_'
            # Explicit PROPOSED transverse-inside-longitudinal arrangement.
            # Not an inference from required minimum cover or a photographed mat.
            basecover=value(params.get(prefix+'cover_mm'));longdb=value(params.get(prefix+'diameter_mm'))
            inputs={'Diameter_mm':mesh_proposal['Diameter_mm'],'Spacing_mm':mesh_proposal['Spacing_mm'],
                'fy_MPa':params.get(prefix+'fy_MPa',params.get('deck_long_rebar_fy_MPa')),
                'Clear_cover_mm':None if basecover is None or longdb is None else basecover+longdb}
            for key,new in inputs.items():
                if value(saved.get(key)) is None and new is not None:
                    change(saved,key,float(new),layer.title()+' transverse mesh / '+key,
                        'Design proposal only: transverse DB12@150 placed just inside the existing outer longitudinal layer; deck design and drawing verification remain required.')
    for row in rows:
        if not row.get('Active',True) or float(row.get('No. Strands',0))<=0:continue
        count=int(round(float(row['No. Strands'])));name=str(row.get('Group ID') or 'Strand row')
        try:positions(row.get('Strand x positions mm'),count)
        except ValueError:
            spacing=value(row.get('Computed spacing_mm'));centre=value(row.get('Row center x_mm'))
            if spacing is not None and spacing>0 and centre is not None:
                xs=[centre+(i-(count-1)/2)*spacing for i in range(count)]
                text=','.join(f'{x:g}' for x in xs)
                change(row,'Strand x positions mm',text,name+' explicit x positions (mm)',
                    'Proposed symmetric positions using existing row centre / computed spacing; count, forces, area and sleeves unchanged.')
        raw=str(row.get('Debonded strand nos') or '')
        tokens=[t.strip() for t in raw.split(',') if t.strip()]
        if tokens and all(re.fullmatch(r'\d+',t) for t in tokens):
            valid=[t for t in tokens if 1<=int(t)<=count]
            if len(valid)!=len(tokens):
                change(row,'Debonded strand nos',','.join(valid),name+' debonded strand numbers',
                    'Remove out-of-range IDs already ignored by the existing participation parser; no valid sleeve assignment or effective strand count changes.')
    return out,rows,{'version':'IGIRDER.STATION36','status':'PROPOSED DESIGN — NOT AS-BUILT',
        'authorization':'User authorized recommended values for invalid inputs, 2026-10-16.',
        'changes':changes,'unresolved':['Actual U-to-mat closure / node geometry / bond-slip / structural validation remain unverified.',
            'No continuity, anchorage, Be verification or production-acceptance flag is set by this proposal.']}
