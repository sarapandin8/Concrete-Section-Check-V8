"""One critical transported-T station, independent of production acceptance.

Only calculate() builds/solves. Render reads a current stored result. Reuses the
existing Loads workflow; never invents U-to-mat continuity or interface forces.
"""
from copy import deepcopy
from collections.abc import Mapping
import hashlib
import json
import math

import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import igird_station36_truss as engine
from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.analysis.igird_dowel_detail35 import resolve,mesh_inventory
from concrete_pmm_pro.analysis.igird_interface_connectors import at_station
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.io.girder_csi_import import source_info

KEY='igird_station36_settings'
RECOMMENDATIONS='igird_station36_recommendations'


def settings(state):
    value=(state.get('project_metadata') or {}).get(KEY,{})
    return deepcopy(dict(value)) if isinstance(value,Mapping) else {}


def fingerprint(state,rows,*,route):
    from . import igird_coupled_model as cm
    strands=state.get('girder_strand_layout_table',[])
    if hasattr(strands,'to_json'):strands=strands.to_json(orient='records',double_precision=15)
    zones=state.get('beam_girder_shear_reinforcement_table',[])
    if hasattr(zones,'to_json'):zones=zones.to_json(orient='records',double_precision=15)
    payload={'version':engine.VERSION,'settings':settings(state),'base':cm.fingerprint(state,rows,route=route),
        'strands':strands,'hoop':state.get('beam_girder_torsion_settings'),
        'zones':zones,'bar_positions':state.get('rebars'),
        'code':state.get('project_design_code'),'edition':state.get('project_code_edition')}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def render_inputs(state):
    with st.expander('One-station 3D review — girder cage',expanded=False):
        cfg=settings(state)
        cfg['enabled']=st.toggle('Include one-station 3D review in Calculate',value=bool(cfg.get('enabled',False)),key='igird_station36_enabled')
        st.caption('Automatically selects the largest |transported Tu| among eligible source states for each girder. Reuses actual bar / strand positions, development and girder hoop zones. No additional solver inputs or Run button.')
        st.info('Includes the girder-cage benchmark and the JOINT37 U-dowel / slab transfer experiment with input-path intersection checks. Full-composite Tn / V–T acceptance remains unavailable.')
        ledger=(state.get('project_metadata') or {}).get(RECOMMENDATIONS,{}).get('changes',[])
        if ledger:
            st.caption('Proposed design inputs — verify against the revised drawing; these values do not describe confirmed construction.')
            st.dataframe(pd.DataFrame(ledger),hide_index=True,use_container_width=True)
    metadata=dict(state.get('project_metadata') or {});metadata[KEY]=cfg;state['project_metadata']=metadata


def select_station(state,rows):
    """Compare AFTER origin transport, preserve exact source identity / actions."""
    from . import analysis_page as ap,igird_station_section
    from .igird_combined_vt import concurrent_source_allowed
    candidates=[];excluded=[];geometry={}
    for ordinal,(_,raw) in enumerate(ref.prepare_analysis_frame(rows).iterrows()):
        row=dict(raw);info=source_info(row) or {};reason=None
        x=joint.number(row.get('Station x (m)'))
        if not math.isfinite(x):reason='Station unavailable'
        elif not all(math.isfinite(joint.number(row.get(k))) for k in ('Nu','Vuy','Vux','Tu','Muy','Mux')):reason='All six source actions must be explicitly available; unknown is not zero'
        elif not concurrent_source_allowed(info):reason='Concurrent state unverified'
        elif ref.SNAPSHOT_KEY not in info:reason='Immutable CSI origin missing'
        elif info[ref.SNAPSHOT_KEY].get('force_kind')!='GIRDER_COMPOSITE':reason='Composite Girder force source required'
        if reason is None:
            try:
                if x not in geometry:
                    local=igird_station_section.at_station(state,x)
                    prep,comp,messages=ap._beam_uls_final_composite_preparation(local)
                    if comp is None:raise ValueError('; '.join(messages))
                    geometry[x]=(local,prep,comp,ref.geometry_origin(prep.geometry,includes_deck=True))
                local,prep,comp,origin=geometry[x]
                moved=ref.translate_row(row,origin=origin)
                if moved.get(ref.RUNTIME_KEY,{}).get('mode')!='EXACT':raise ValueError('Exact concurrent origin transport required')
                if not all(math.isfinite(joint.number(moved.get(k))) for k in ('Nu','Vuy','Vux','Tu','Muy','Mux')):raise ValueError('All six actions must be finite')
                candidates.append((abs(float(moved['Tu'])),ordinal,row,moved,info,local,prep,comp,origin))
            except (ValueError,TypeError,AttributeError,KeyError) as exc:reason=str(exc)
        if reason is not None:excluded.append({'source_ordinal':ordinal,'x_m':x if math.isfinite(x) else None,'reason':reason})
    if not candidates:return None,{'eligible':0,'excluded':excluded,'selection':'Largest |Tu| AFTER exact transport; not governing utilization'}
    best=max(candidates,key=lambda v:(v[0],-v[1]))
    return best,{'eligible':len(candidates),'excluded':excluded,'ties':sum(abs(v[0]-best[0])<1e-9 for v in candidates),
        'selection':'Largest |Tu| AFTER exact transport among eligible states; not governing utilization'}


def calculate(state,rows,*,route):
    from . import analysis_page as ap
    from .igird_coupled_model import weakest_girder_zone
    from concrete_pmm_pro.analysis.igird_flexure_development import SectionEquilibrium,ordinary_bar_limits,development_settings
    from concrete_pmm_pro.analysis.igird_station36_steel import strand_ties
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon
    result={'version':engine.VERSION,'enabled':bool(settings(state).get('enabled')),'production_status':'UNVALIDATED — REVIEW',
        'accepted_phiTn_Nmm':None,'accepted_VT_factor':None,'full_composite_Tn_Nmm':None}
    if not result['enabled']:return result
    result['fingerprint']=fingerprint(state,rows,route=route)
    try:
        if state.get('project_design_code')!='AASHTO LRFD' or state.get('project_code_edition')!='AASHTO LRFD 9th Edition':
            raise ValueError('This research adapter uses the project AASHTO LRFD 9th Edition (2020) only.')
        chosen,selection=select_station(state,rows);result['selection']=selection
        if chosen is None:raise ValueError('No eligible concurrent Girder force state with an exact CSI origin.')
        _,ordinal,raw,moved,info,local,prep,comp,origin=chosen
        x=float(raw['Station x (m)']);params=dict(local.get('section_parameters') or {})
        polygon=to_shapely_polygon(local['section_geometry'])
        inp,notes=ap._beam_uls_flexure_analysis_input_for_station(comp,row=moved,strength_route=route,capacity_direction=1.,prestress_force_stage='final')
        if inp is None:raise ValueError('; '.join(notes))
        context=SectionEquilibrium(inp,1.)
        if context.unresolved_bar_materials:raise ValueError('Resolve ordinary-bar material names before force credit.')
        if inp.concrete_material.density_kg_m3<2200:raise ValueError('Normal-weight concrete is required by this model.')
        if not 0<float(prep.girder_fc_MPa)<=68.94757293168:raise ValueError('Adapter concrete scope is normal-weight f\'c <=10 ksi.')
        span=ap._beam_uls_span_length_from_state(state,is_building=False);dev=development_settings(state)
        factors,bar_trace=ordinary_bar_limits(context,x_m=x,span_m=span,settings=dev,params=params,girder_fc_mpa=float(prep.girder_fc_MPa))
        bars=[];slab=[]
        for bar,factor,trace in zip(context.bars,factors,bar_trace):
            material=context.materials[bar.material_name]
            record={'label':bar.label or bar.material_name,'kind':'ordinary','x_mm':bar.x_mm,'y_mm':bar.y_mm,
                'area_mm2':bar.area_mm2,'fy_MPa':material.fy_MPa,'capacity_N':bar.area_mm2*material.fy_MPa*factor,'development':trace}
            (slab if bar.material_name.startswith('Composite deck longitudinal rebar') else bars).append(record)
        if not bars:raise ValueError('No actual ordinary girder bars are available.')
        from concrete_pmm_pro.analysis.igird_end_sections import cut_ends
        left_cut,right_cut=cut_ends(params,span)
        strands=strand_ties(local.get('girder_strand_layout_table',[]),x_m=x,span_m=span,y_min_mm=polygon.bounds[1],
            depth_mm=polygon.bounds[3]-polygon.bounds[1],fy_tie_MPa=min(b['fy_MPa'] for b in bars),settings=dev,
            left_cut_m=left_cut,right_cut_m=right_cut)
        zone=weakest_girder_zone(ap._beam_uls_shear_reinforcement_dataframe_from_state(local).to_dict('records'),x)
        cover=joint.number((local.get('beam_girder_torsion_settings') or {}).get('clear_cover_mm'))
        kwargs={'cover_mm':cover,'db_mm':joint.number(zone['Diameter_mm']),'spacing_mm':joint.number(zone['Spacing_mm']),
            'fy_MPa':min(joint.number(zone['fy_MPa']),75*6.894757293168),'fc_MPa':float(prep.girder_fc_MPa),
            'origin_y_mm':origin['target_y_mm'],'origin_local3_mm':origin.get('target_local3_mm',0.)}
        # Ordinary steel and prestress share each bay's nodal equilibrium with
        # both concrete diagonal families. No separate torsion-steel addition.
        nominal=engine.core_cage(polygon,**kwargs,longitudinal=bars+strands,nominal=True)
        no_ps=engine.core_cage(polygon,**kwargs,longitudinal=bars,nominal=True)
        factored=engine.core_cage(polygon,**kwargs,longitudinal=bars+strands,nominal=False)
        values=ref.actions(moved)
        # actions() deliberately returns SOURCE actions for replay safety;
        # the actual transported values are read directly from moved columns.
        wrench=[float(moved['Nu'])*1000,float(moved['Vuy'])*1000,float(moved['Vux'])*1000,
            float(moved['Tu'])*1e6,-float(moved['Muy'])*1e6,float(moved['Mux'])*1e6]
        direction=-1. if wrench[3]<0 else 1.
        interface=ap._igird_interface_shear_settings_from_state(local);connector=at_station(interface,x_m=x,girder_zone=zone)
        anchor={'ready':False,'status':'CONNECTOR UNAVAILABLE','reason':connector.get('reason')}
        detail=joint.config(interface)
        if connector.get('ready'):
            dz=connector['zone'];detail=resolve(detail,slab_thickness_mm=float(prep.deck_thickness_mm),db_mm=dz.get('Diameter_mm'))
            anchor=joint.anchorage(detail,dz,{'fc_slab_MPa':float(prep.deck_fc_MPa),'fc_girder_MPa':float(prep.girder_fc_MPa),
                'slab_thickness_mm':float(prep.deck_thickness_mm),'girder_depth_mm':polygon.bounds[3]-polygon.bounds[1],
                'girder_polygon':[list(p) for p in polygon.exterior.coords],'girder_holes':[],
                'contact_center_x_mm':polygon.centroid.x,'contact_top_y_mm':polygon.bounds[3],'normal_weight':True})
        result.update(status='MODEL REVIEW ONLY',source={'ordinal':ordinal,'member':raw.get('Girder') or ' / '.join(str(info.get(k) or '') for k in ('bridge_object','girder')).strip(' / '),
            'case':info.get('case'),'app_case':raw.get('Case Name'),'step':info.get('step'),'location_type':info.get('location_type'),
            'x_m':x,'info':info},reference={'origin':origin,**ref.trace_columns(moved)},
            source_actions=values,transported_actions=dict(zip(('P','V2','V3','T','M2','M3'),[wrench[0]/1000,wrench[1]/1000,wrench[2]/1000,wrench[3]/1e6,-wrench[4]/1e6,wrench[5]/1e6])),
            physical_wrench_N_Nmm=wrench,core_geometry_xy_mm=[list(p) for p in polygon.exterior.coords],
            pure_torsion=engine.solve(nominal,[0.]*6,torsion_sign=direction),
            pure_torsion_without_prestress=engine.solve(no_ps,[0.]*6,torsion_sign=direction),
            actual_five_actions=engine.solve(factored,wrench,torsion_sign=direction),
            longitudinal_inventory=bars+strands,slab_longitudinal_inventory=slab,slab_mesh=mesh_inventory(detail,params),
            u_dowel_anchorage=anchor,girder_hoop_zone=dict(zone),
            closure_status='UNESTABLISHED — no U-to-slab closed torsion path or interface free-body is inferred',
            confirmation_status={'ordinary_continuity':dev.get('bars_continuous_confirmed',False),
                'scope':'Stored drawing declarations are preserved; numerical development is conditional on actual bar continuity.'},
            scope='Entire composite Girder wrench imposed on a GIRDER-CORE-ONLY truss benchmark. Neither slab nor dowel resistance is added.')
    except (ValueError,TypeError,KeyError,AttributeError,ImportError) as exc:result.update(status='MODEL BLOCKED',reason=str(exc))
    return result


def figure(result):
    import plotly.graph_objects as go
    trace=result['pure_torsion']['trace'];ring=trace['ring_xy_mm'];pitch=trace['pitch_mm']
    fig=go.Figure()
    for k in range(3):
        xy=ring+[ring[0]]
        fig.add_trace(go.Scatter3d(x=[k*pitch]*len(xy),y=[p[0] for p in xy],z=[p[1] for p in xy],mode='lines',
            line={'color':'#2364a0','width':5},name='Derived girder hoop',showlegend=k==0))
    for i in range(len(ring)):
        a=ring[i];b=ring[(i+1)%len(ring)]
        for k in range(2):
            fig.add_trace(go.Scatter3d(x=[k*pitch,(k+1)*pitch],y=[a[0],b[0]],z=[a[1],b[1]],mode='lines',
                line={'color':'rgba(130,144,158,0.55)','width':2},name='Compression diagonals',showlegend=i==k==0,hoverinfo='skip'))
    for kind,color,name in [('ordinary','#c66a1c','Ordinary bars'),('prestress','#a02f52','Strands')]:
        bars=[b for b in result['longitudinal_inventory'] if b['kind']==kind]
        xx=[];yy=[];zz=[]
        for b in bars:xx.extend([0,2*pitch,None]);yy.extend([b['x_mm'],b['x_mm'],None]);zz.extend([b['y_mm'],b['y_mm'],None])
        fig.add_trace(go.Scatter3d(x=xx,y=yy,z=zz,mode='lines',line={'color':color,'width':3},name=name))
    fig.update_layout(height=610,margin={'l':15,'r':15,'b':85,'t':65},
        legend={'orientation':'h','x':0.,'y':-.07,'entrywidth':.5,'entrywidthmode':'fraction','font':{'size':11}},
        scene={'xaxis':{'title':'Along girder (mm)','nticks':4},'yaxis':{'title':'Section x (mm)','nticks':4},
            'zaxis':{'title':'Section y (mm)','nticks':6},
            'aspectmode':'data','camera':{'eye':{'x':2.0,'y':-3.0,'z':1.0},'projection':{'type':'perspective'}}},
        title={'text':'Girder-core benchmark — slab / U-dowel not added','font':{'size':16}})
    return fig


def render_result(state,rows,stored,*,route,joint_review=None):
    with st.expander('One-station 3D review — girder cage',expanded=False):
        if not settings(state).get('enabled'):
            st.caption('Enable under Edit composite / dowel inputs, then use Calculate Flexure.');return
        if not stored or stored.get('fingerprint')!=fingerprint(state,rows,route=route):
            st.info('One-station review missing or stale. Use Calculate Flexure.');return
        st.warning('Model review only. Full composite Tn / V–T: NOT AVAILABLE. The derived girder cage, rigid end sections and concrete interaction have not been structurally validated.')
        if stored.get('status')=='MODEL BLOCKED':st.info(stored.get('reason'));return
        source=stored['source']
        st.markdown(f"**{source['member']} · {source['case']} / {source['step']} / {source['location_type']} · x={source['x_m']:.3f} m**")
        st.caption(stored['selection']['selection']+f" · {stored['selection']['eligible']} eligible source states.")
        st.dataframe(pd.DataFrame([{'Origin':'CSI source',**stored['source_actions']},{'Origin':'Composite centroid',**stored['transported_actions']}]),hide_index=True,use_container_width=True)
        st.caption('P,V2,V3: kN; T,M2,M3: kN·m. Physical 3D moment vector = (T, −M2, M3). All six actions retained; no endpoint zeroing.')
        from . import igird_joint37 as joint_ui
        geometry_blocked=bool(joint_review and joint_review.get('status')=='INPUT GEOMETRY REVIEW'
            and joint_review.get('fingerprint')==joint_ui.fingerprint(state,rows,route=route))
        results=[]
        for key,label in [('pure_torsion_without_prestress','Pure T — ordinary bars only'),('pure_torsion','Pure T — developed strands included'),('actual_five_actions','Signed T — other five actual actions held')]:
            item=stored[key];value=None if geometry_blocked else item.get('model_T_limit_Nmm')
            results.append({'Benchmark':label,'Model limit (kN·m)':None if value is None else value/1e6,
                'Status':'WITHHELD — INPUT PATH INTERSECTIONS' if geometry_blocked else item['status']})
        if geometry_blocked:st.error('JOINT37 found intersecting input paths. Girder-core benchmark values are withheld here; inspect the Girder–U-dowel–slab coupled transfer review below.')
        st.dataframe(pd.DataFrame(results),hide_index=True,use_container_width=True,
            column_config={'Model limit (kN·m)':st.column_config.NumberColumn(format='%.2f')})
        st.caption('These are girder-core truss limits, not full-composite Tn or production φTn. Actual-actions benchmark uses steel 0.90 / concrete 0.70; pure-T benchmarks use nominal supplies. Infeasible means this idealization cannot carry the held actions; it is not a fabricated zero resistance or a certified section failure.')
        st.plotly_chart(figure(stored),use_container_width=True,key='igird_station36_cage_figure')
        st.caption('Geometric view: one diagonal family shown; the solver shares concrete between both families. Rotate / zoom to inspect. Hoop outline is derived, pending drawing verification.')
        st.markdown('**U-dowel / slab transfer:** '+stored['closure_status'])
        st.caption('90° hooks may anchor a tension tie. Their presence beside orthogonal mesh does not establish a continuous torsion cage, node capacity or joint slip compatibility. Joint dimension status: '+str(stored['u_dowel_anchorage'].get('status')))
        with st.expander('Station trace / steel allocation / numerical witness',expanded=False):
            st.dataframe(pd.DataFrame(stored['longitudinal_inventory']).drop(columns=['development'],errors='ignore'),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(stored['slab_mesh']),hide_index=True,use_container_width=True)
            fields=('reference','u_dowel_anchorage','confirmation_status') if geometry_blocked else ('reference','u_dowel_anchorage','confirmation_status','pure_torsion','actual_five_actions')
            st.json({k:stored[k] for k in fields})
