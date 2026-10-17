"""One Calculate command; conditional joint mechanics and visible detail gates.

Research outputs have their own runtime bundle and fingerprint. No result is
published to production Tn / V–T owners or serialized into Project JSON.
"""
from copy import deepcopy
from collections.abc import Mapping
import hashlib
import json
import math

import numpy as np
import pandas as pd
import streamlit as st
from shapely.geometry import Polygon

from concrete_pmm_pro.analysis import igird_joint37_model as model
from concrete_pmm_pro.analysis import igird_joint37_solver as solver
from concrete_pmm_pro.analysis.igird_joint37_detail import audit
from concrete_pmm_pro.analysis.igird_dowel_detail35 import resolve
from concrete_pmm_pro.analysis.igird_interface_connectors import at_station,STIRRUPS
from concrete_pmm_pro.analysis.igird_interface_shear import SURFACE_PRESETS

KEY='igird_joint37_settings'
TITLE='Girder–U-dowel–slab — coupled transfer review'


def settings(state):
    cfg=(state.get('project_metadata') or {}).get(KEY,{})
    return deepcopy(dict(cfg)) if isinstance(cfg,Mapping) else {}


def enabled(state):
    from . import igird_station36 as station
    return bool(station.settings(state).get('enabled')) and bool(settings(state).get('enabled',True))


def fingerprint(state,rows,*,route):
    from . import igird_station36 as station
    value={'version':model.VERSION,'settings':settings(state),'station':station.fingerprint(state,rows,route=route),
        'law':'prism trace-volume / continuous U / associated contact / nominal Pe reference v1'}
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def _summary(name,result):
    return {'Boundary / test':name,'Status':result.get('status'),
        'Conditional |T| (kN·m)':None if result.get('model_T_limit_Nmm') is None else result['model_T_limit_Nmm']/1e6,
        'Conditional V–T factor':result.get('model_VT_factor'),'Scope':'Idealized model only; not accepted design resistance'}


def calculate(state,rows,*,route,station):
    from . import analysis_page as ap,igird_station_section
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon
    result={**solver.base(),'enabled':enabled(state),'version':model.VERSION}
    if not result['enabled']:return result
    result['fingerprint']=fingerprint(state,rows,route=route)
    if not station or station.get('status')!='MODEL REVIEW ONLY':
        return {**result,'status':'MODEL BLOCKED','reason':'A current eligible STATION36 source / geometry inventory is required.'}
    result.update(source=deepcopy(station['source']),source_actions=deepcopy(station['source_actions']),
        transported_actions=deepcopy(station['transported_actions']),reference=deepcopy(station['reference']))
    try:
        local=igird_station_section.at_station(state,float(station['source']['x_m']))
        params=dict(local.get('section_parameters') or {})
        prep,comp,notes=ap._beam_uls_final_composite_preparation(local)
        if comp is None:raise ValueError('; '.join(notes))
        girder=Polygon(station['core_geometry_xy_mm']);full=to_shapely_polygon(prep.geometry);slab=full.difference(girder)
        if slab.geom_type!='Polygon' or slab.is_empty or slab.interiors:raise ValueError('One assigned solid slab strip is required.')
        interface=ap._igird_interface_shear_settings_from_state(local)
        if interface.get('connector_source')==STIRRUPS:raise ValueError('Girder stirrups cannot be counted again as a separate U supply; choose explicit U-dowels.')
        connector=at_station(interface,x_m=float(station['source']['x_m']),girder_zone=station['girder_hoop_zone'])
        if not connector.get('ready'):raise ValueError(connector.get('reason') or 'Dowel zoning unavailable.')
        dowel=connector['zone'];detail=resolve(interface.get('dowel_connection',{}),slab_thickness_mm=prep.deck_thickness_mm,db_mm=dowel['Diameter_mm'])
        result['u_anchorage']=deepcopy(station['u_dowel_anchorage'])
        if station['u_dowel_anchorage'].get('status')!='DIMENSION CHECKS MET':raise ValueError('Full-yield U hook / straight anchorage dimension checks are not met; no partial-fy shortcut is used.')
        if interface.get('surface_key') not in SURFACE_PRESETS:raise ValueError('Known interface surface category required; roughness is not guessed.')
        surface=SURFACE_PRESETS[interface['surface_key']];const=surface.constants_si(lightweight=False)
        width,_=ap._igird_interface_bvi_mm(local,interface)
        hoop={**station['girder_hoop_zone'],'cover_mm':model.number((local.get('beam_girder_torsion_settings') or {}).get('clear_cover_mm'))}
        geometry=audit(girder=girder,bars=station['longitudinal_inventory'],hoop=hoop,detail=detail,db_mm=dowel['Diameter_mm'],web_width_mm=params['T2_mm'])
        long=station['slab_longitudinal_inventory']
        if len(long)!=2:raise ValueError('Both existing slab longitudinal layers are required; disabled strength credit is not silently replaced.')
        long=model.expand_slab_layers(params,long,left_mm=slab.bounds[0],right_mm=slab.bounds[2])
        args={'girder':girder,'slab':slab,'origin':station['reference']['origin'],'girder_fc':float(prep.girder_fc_MPa),
            'slab_fc':float(prep.deck_fc_MPa),'girder_E':params['Ebeam_MPa'],'slab_E':params['Edeck_MPa'],
            'hoop':hoop,'bars':station['longitudinal_inventory'],'slab_longitudinal':long,'transverse':detail.get('slab_transverse_mesh',{}),
            'detail':detail,'dowel':dowel,'contact_width_mm':width,'mu':surface.mu,
            'interface_cap_MPa':min(const['K1']*min(prep.deck_fc_MPa,prep.girder_fc_MPa),const['K2_MPa']),
            'pitch_mm':200.,'nominal':True}
        nominal=model.build(**args);design=model.factored(nominal)
        no_dowel=model.without(design,'dowel');no_mesh=model.without(design,'slab_transverse')
        h=station['physical_wrench_N_Nmm'];pure=[0.,0.,0.,h[3],0.,0.]
        # This is a separate load-transfer experiment. Pure roll is introduced
        # into the slab cut, and only the girder is supported. Its torque is
        # NEVER relabeled as Girder Tu or as a member torsional capacity.
        transfer=model.slab_entry(design)
        commands=[('girder_entry_no_dowel',no_dowel,pure,'signed_torsion'),('girder_entry_with_U_slab',design,pure,'signed_torsion'),
            ('actual_five_held',design,h,'signed_torsion'),('actual_VT_ray',design,h,'VT_ray'),('actual_VT_ray_no_dowel',no_dowel,h,'VT_ray'),
            ('slab_entry_no_dowel',model.without(transfer,'dowel'),pure,'signed_torsion'),('slab_entry_with_U_slab',transfer,pure,'signed_torsion'),
            ('slab_entry_no_transverse_mesh',model.without(transfer,'slab_transverse'),pure,'signed_torsion')]
        geometry_bad=bool(geometry['U_intersections'] or geometry['derived_hoop_intersections'])
        if geometry_bad:
            tests={name:{**solver.base(),'ready':False,'status':'WITHHELD — INPUT PATH INTERSECTIONS',
                'model_T_limit_Nmm':None,'model_VT_factor':None} for name,*_ in commands}
        else:tests={name:solver.limit(m,actions,mode=mode) for name,m,actions,mode in commands}
        summaries=[_summary(name,item) for name,item in tests.items()]
        checks=[]
        def gate(name,state,reason):checks.append({'Check':name,'Status':state,'Meaning / action':reason})
        gate('Input U / longitudinal paths','REVIEW' if geometry['U_intersections'] else 'NO INTERSECTIONS',f"{len(geometry['U_intersections'])} input path intersections; explicit bars/strands are not moved silently.")
        gate('Derived hoop / longitudinal paths','REVIEW' if geometry['derived_hoop_intersections'] else 'NO INTERSECTIONS',f"{len(geometry['derived_hoop_intersections'])} intersections with the derived hoop; verify actual cage drawing.")
        gate('U anchorage dimensions','DIMENSIONS MET','Interface-based hook and straight-leg dimensions only; interior nodal anchorage is a separate check.')
        gate('Slab transverse anchorage','UNVERIFIED','Equivalent strip bars and mat crossings do not prove development beyond the actual node face.')
        gate('Concrete node faces / splitting','UNVERIFIED','Required face areas can be derived from model strut forces; actual available faces and confinement are not established.')
        gate('Interface slip / concrete law','UNVALIDATED','Assumed secant springs, perfect embedded bond and associated dilatant friction require calibration.')
        gate('Structural acceptance','WITHHELD','Software equilibrium and KKT benchmarks do not validate the actual composite structure.')
        # A physical compatible state is not offered on intersecting input
        # geometry. The generic energy engine remains independently testable.
        if geometry_bad:
            compatibility={**solver.base(),'ready':False,'status':'WITHHELD — INPUT PATH INTERSECTIONS',
                'reason':'Resolve the input cage geometry before interpreting displacement, slip or physical composite resistance.'}
        else:compatibility=solver.compatible_state(nominal,h)
        hook_top=girder.bounds[3]+detail['slab_ldh_available_mm'];hook_node_rows=[]
        hook_required=station['u_dowel_anchorage'].get('hook_required_mm')
        if hook_required is None:hook_required=station['u_dowel_anchorage'].get('checks',{}).get('slab_ldh_available_mm',{}).get('required_mm')
        for layer in nominal.trace['slab_transverse_layers']:
            hook_node_rows.append({'Slab layer':layer['layer'],'Mat centre y (mm)':layer['y'],'Outside hook y (mm)':hook_top,
                'Vertical hook distance from mat (mm)':hook_top-layer['y'],'Interface hook required (mm)':hook_required,
                'Scope':'Mat-centroid screen only. Actual STM node edge / anchorage remain unverified.'})
        result.update(status='INPUT GEOMETRY REVIEW' if geometry_bad else 'CONDITIONAL MODEL REVIEW',
            geometry_audit=geometry,validation=checks,trace=nominal.trace,tests=tests,summary=summaries,compatibility=compatibility,
            node_screen=hook_node_rows,slab_longitudinal_distribution=long,
            scope='One local 400-mm transfer experiment at the selected section. Not full-span capacity or recovered CSI Beam/Slab interface loading.')
        # Compact geometry for plotting only; no sparse solver object in cache.
        result['plot']={'U_path':nominal.trace['U_path_xy_mm'],'slab_bounds':list(slab.bounds),
            'longitudinal':long,'transverse':nominal.trace['slab_transverse_layers'],'contact_x':nominal.trace['contact_x_mm']}
    except (ValueError,TypeError,KeyError,AttributeError,ImportError) as exc:result.update(status='MODEL BLOCKED',reason=str(exc))
    return result


def figure(station,result):
    from .igird_station36 import figure as cage_figure
    import plotly.graph_objects as go
    p=result['trace']['pitch_mm']
    plot_source={**station,'pure_torsion':{**station['pure_torsion'],'trace':{**station['pure_torsion']['trace'],'pitch_mm':p}}}
    fig=cage_figure(plot_source)
    fig.data=tuple(t for t in fig.data if t.name!='Compression diagonals')
    plot=result['plot'];a,b,c,d=plot['slab_bounds']
    xs=[];ys=[];zs=[]
    for k in range(3):
        for x,y in [(a,b),(c,b),(c,d),(a,d),(a,b)]:xs.append(k*p);ys.append(x);zs.append(y)
        xs.append(None);ys.append(None);zs.append(None)
    fig.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode='lines',line={'color':'#8494a7','width':2},name='Assigned slab'))
    xx=[];yy=[];zz=[]
    for k in range(3):
        for x,y in plot['U_path']:xx.append(k*p);yy.append(x);zz.append(y)
        xx.append(None);yy.append(None);zz.append(None)
    fig.add_trace(go.Scatter3d(x=xx,y=yy,z=zz,mode='lines',line={'color':'#d67824','width':6},name='Continuous U-dowel'))
    xx=[];yy=[];zz=[]
    for layer in plot['transverse']:
        for k in range(3):xx.extend([k*p,k*p,None]);yy.extend([a,c,None]);zz.extend([layer['y'],layer['y'],None])
    for bar in plot['longitudinal']:
        xx.extend([0,2*p,None]);yy.extend([bar['x_mm'],bar['x_mm'],None]);zz.extend([bar['y_mm'],bar['y_mm'],None])
    fig.add_trace(go.Scatter3d(x=xx,y=yy,z=zz,mode='lines',line={'color':'#26836c','width':3},name='Slab mat strips'))
    clashes=result['geometry_audit']['U_intersections']
    if clashes:fig.add_trace(go.Scatter3d(x=[p]*len(clashes),y=[r['x_mm'] for r in clashes],z=[r['y_mm'] for r in clashes],
        text=[r['Bar']+f" · gap {r['U_clear_gap_mm']:.1f} mm" for r in clashes],hovertemplate='%{text}<extra></extra>',
        mode='markers',marker={'size':5,'color':'#c62b3c','symbol':'diamond'},name='Input path clashes'))
    fig.update_layout(height=700,title={'text':'Input cage + U-dowel + slab — inspect red intersections'},
        legend={'entrywidth':.33,'entrywidthmode':'fraction','orientation':'h'},margin={'l':15,'r':15,'t':65,'b':110})
    return fig


def render_result(state,rows,stored,*,route,station):
    if not enabled(state):return
    with st.expander(TITLE,expanded=False):
        if not stored or stored.get('fingerprint')!=fingerprint(state,rows,route=route):
            st.info('Joint / slab review is missing or stale. Use Calculate Flexure.');return
        st.warning('Full composite Tn / V–T acceptance: WITHHELD. This is a conditional local transfer model; actual nodal strength, anchorage and physical slip laws are not validated.')
        if stored.get('status')=='MODEL BLOCKED':st.info(stored.get('reason'));return
        source=stored['source'];st.markdown(f"**{source['member']} · {source['case']} / {source['step']} / {source['location_type']} · x={source['x_m']:.3f} m**")
        st.dataframe(pd.DataFrame(stored['validation']),hide_index=True,use_container_width=True)
        geometry=stored['geometry_audit']
        if geometry['U_intersections']:
            st.error(f"Input U path intersects {len(geometry['U_intersections'])} longitudinal-bar / strand positions. This describes the input model, not a confirmed construction defect.")
        if not geometry['A_only_can_resolve_straight_leg_intersections']:
            st.info(f"For the common straight U detail, bend/cover require A={geometry['A_bend_minimum_mm']:g}–{geometry['A_web_cover_maximum_mm']:g} mm. No value in that interval clears the supplied longitudinal positions. Review the cage / strand arrangement together; an A default alone cannot resolve it.")
        st.plotly_chart(figure(station,stored),use_container_width=True,key='igird_joint37_input_figure')
        st.caption('Input geometry only. Slab longitudinal lines distribute equivalent As over Be; actual transverse bar phasing is not inferred. Red markers identify U / longitudinal input intersections. Rotate / zoom to inspect.')
        with st.expander('Input path conflicts / anchorage location',expanded=False):
            st.dataframe(pd.DataFrame(geometry['U_intersections']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(geometry['derived_hoop_intersections']),hide_index=True,use_container_width=True)
            st.dataframe(pd.DataFrame(stored['node_screen']),hide_index=True,use_container_width=True)
            st.caption('A full hook development length measured from the interface does not automatically develop full fy at a slab-mat node closer to the bend.')
        with st.expander('Calculation trace / Equations — joint transfer',expanded=False):
            st.latex(r'\mathbf B\mathbf f+\mathbf p=0,\qquad \mathbf R\mathbf f\le\mathbf r,\qquad f_{min}\le\mathbf f\le f_{max}')
            st.latex(r'A_{U,leg}=\frac{\pi d_b^2}{4}\frac{\Delta x}{s_U}w,\qquad T_{leg,max}=A_{U,leg}f_y')
            st.caption('One physical leg area per crossing. w=0.5 at segment ends and 1.0 internally. The U return and hook tails share the same bar supply; their forces are not added as independent torsion capacities.')
            st.latex(r'\sqrt{q_x^2+q_z^2}\le\mu C,\qquad C\ge0,\qquad c=0')
            st.caption('An inscribed octagon lies within this friction circle. Longitudinal and transverse friction share the same contact compression; interface stress ceilings are checked separately.')
            st.latex(r'\min_{\mathbf f}\ \frac12\sum_e\frac{(f_e-f_e^0)^2}{k_e},\qquad -\mathbf B^T\mathbf u=\delta_{elastic}+\delta_{plastic}')
            st.caption('Compatible state uses nominal material bounds and a self-equilibrated girder-only reference that retains post-loss Pe. The assumed associated friction law dilates and is not a calibrated physical joint-slip law.')
            st.write('Compatible state:',stored['compatibility']['status'])
            st.caption('Conditional strut force C requires Acn >= C/(φνfc), with ν=0.45 absent verified crack-control detail. Available actual nodal faces / splitting remain unverified.')
        with st.expander('Conditional mechanics experiments — not design resistance',expanded=False):
            st.warning('Experiments are withheld for intersecting input geometry. Otherwise they demonstrate the assumed numerical mechanism only; never compare slab-entry torque directly with Girder Tu or add it to girder strength.')
            st.dataframe(pd.DataFrame(stored['summary']),hide_index=True,use_container_width=True,
                column_config={'Conditional |T| (kN·m)':st.column_config.NumberColumn(format='%.3f'),'Conditional V–T factor':st.column_config.NumberColumn(format='%.4f')})
            transfer=stored['tests'].get('slab_entry_with_U_slab',{})
            if transfer.get('ready'):
                rows=[]
                for item in transfer['interface']['plane_wrenches']:
                    rows.append({'Plane':item['plane'],'x local (mm)':item['longitudinal_mm'],
                        **{k:v/1000 for k,v in zip(('Fx kN','F2 kN','F3 kN'),item['force_on_slab_N'])},
                        **{k:v/1e6 for k,v in zip(('Roll kN·m','Physical M2 kN·m','M3 kN·m'),item['moment_on_slab_Nmm'])}})
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                st.caption('Forces acting on the slab, recovered from the internal model solution. They are not CSI interface exports and do not equal the Girder Tu input.')
            st.json({'model_scope':stored['scope'],'limitations':stored['trace']['limitations'],
                'mesh':{k:stored['trace'][k] for k in ('nodes','members','prismatic_cells','concrete_volumes_mm3','contact_area_mm2')}})
