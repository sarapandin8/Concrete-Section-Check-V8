"""Automatic input reuse and read-only presentation for the composite review.

No new input form/checkbox, no invented drawing confirmation, no mutation of
the original loads, and no solver in render(). Production checks stay separate.
"""
from dataclasses import asdict, replace
import math

import pandas as pd

from concrete_pmm_pro.analysis import igird_composite_steel45 as engine

KEY = "composite_steel45_review"
RUNTIME_KEY = "_igird_composite_steel45_review_runtime"


def core_hoop_supply(state, *, x_m):
    """Read actual qualified steel/geometry independently of demand screening.

    A below-threshold code result legitimately omits capacity fields. It must
    neither erase an existing closed hoop nor fabricate one that is missing.
    """
    from . import analysis_page as ap
    from concrete_pmm_pro.core.models import SectionGeometry
    from concrete_pmm_pro.code_checks import aashto_torsion_transverse_design_fy_mpa
    source = ap._beam_uls_igird_torsion_zone_source(state, x_m=x_m)
    if not source.get('ready'):
        raise ValueError('I-hoop qualification: '+str(source.get('reason') or 'Closed hoop / hook source missing.'))
    zone = source['zone']
    geometry = state['section_geometry']
    if isinstance(geometry, dict):
        geometry = SectionGeometry.model_validate(geometry)
    derived = ap._beam_uls_igird_aashto_solid_torsion_geometry(geometry, settings={
        **ap._beam_uls_igird_torsion_settings(state),
        'closed_loop_confirmed':source['closed_loop_confirmed'], 'ph_mm':source['ph_mm']})
    if not derived.get('ready'):
        raise ValueError('I-hoop geometry: '+str(derived.get('Note') or 'Unavailable.'))
    area = ap._beam_uls_stirrup_area_mm2(zone)
    spacing, legs = float(zone['Spacing_mm']), float(zone['Legs'])
    fy, policy = aashto_torsion_transverse_design_fy_mpa(float(zone['fy_MPa']))
    if not all(math.isfinite(v) and v>0 for v in (area,spacing,fy)) or not math.isfinite(legs) or legs<2:
        raise ValueError('I-hoop requires positive area/spacing/fy and at least two physical legs.')
    return {'Ao mm2':float(derived['Ao mm2']), 'ph mm':float(derived['ph mm']),
        'At/s mm2/mm':area/spacing, 'fy MPa':fy, 'fy policy':policy,
        'Closed loop confirmed':bool(source['closed_loop_confirmed']),
        '135° hook confirmed':bool(source['hook_135_confirmed']), 'Zone':source.get('zone_name'),
        'Source':'Actual station-qualified hoop; independent of Tu threshold screen'}


def detach_review(state, result, *, fingerprint):
    """Separate review storage BEFORE any production or collection cache write."""
    clean = dict(result)
    review = clean.pop(KEY,None)
    if review is not None:
        runtime = dict(state.get(RUNTIME_KEY) or {})
        runtime[str(fingerprint)] = review
        # Runtime only. Source signatures, not navigation, select each result.
        while len(runtime)>24: runtime.pop(next(iter(runtime)))
        state[RUNTIME_KEY] = runtime
    return clean


def current(state, fingerprint):
    return (state.get(RUNTIME_KEY) or {}).get(str(fingerprint))


def payload(state, rows, *, route):
    if not route.is_bridge or str(state.get('section_preset_key') or '') != 'parametric_i_girder':
        return {}
    try:
        from . import analysis_page as ap
        shared_hash=ap._beam_uls_check_input_hash(state,rows,strength_route=route,check_name='Shear + Torsion')
        for saved in (state.get(RUNTIME_KEY) or {}).values():
            if saved.get('model_input_hash')==shared_hash and saved.get('version')==engine.VERSION:
                return {KEY:saved}
        result=calculate(state,rows,route=route)
        result['model_input_hash']=shared_hash
        return {KEY:result}
    except (ValueError,TypeError,KeyError,AttributeError,ImportError) as exc:
        # A review model must never destroy a completed primary code check.
        return {KEY:{'version':engine.VERSION,'enabled':True,'rows':[],
            'reason':str(exc),'production_status':'UNVALIDATED — REVIEW'}}


def calculate(state, rows, *, route):
    from . import analysis_page as ap, igird_station_section, csi_reference_analysis, igird_shear_section, igird_composite_scan48 as scan
    from .igird_combined_vt import concurrent_source_allowed
    from .igird_coupled_model import weakest_girder_zone
    from concrete_pmm_pro.io.girder_csi_import import source_info
    from concrete_pmm_pro.io import csi_force_reference as ref
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon
    from concrete_pmm_pro.analysis.igird_flexure_development import (
        SectionEquilibrium, ordinary_bar_limits, development_settings)
    from concrete_pmm_pro.analysis.igird_station36_steel import strand_ties
    from concrete_pmm_pro.analysis.igird_interface_connectors import at_station, STIRRUPS
    from concrete_pmm_pro.analysis.igird_dowel_detail35 import resolve
    from concrete_pmm_pro.analysis.igird_dowel_joint import anchorage, config
    from concrete_pmm_pro.analysis.igird_interface_shear import surface_preset
    if not bool((state.get('section_parameters') or {}).get('composite_enabled')):
        return {'version':engine.VERSION,'enabled':False,'rows':[]}
    result = {'version':engine.VERSION,'scan_version':scan.VERSION,'enabled':True,'rows':[],
        'production_status':'UNVALIDATED — REVIEW','accepted_Vn_kN':None,'accepted_Tn_kNm':None,'accepted_VT_factor':None,
        'selection':scan.SELECTION}
    # Per-Calculate preparation caches only; never mutate the project inputs.
    state = dict(state)
    state.setdefault(igird_shear_section.RUNTIME_KEY, {'active_df':rows})
    candidates, entries, excluded = [], [], []
    solve_cache = engine.SolveCache()
    nominal_fps_cache = {}
    span = ap._beam_uls_span_length_from_state(state,is_building=False)
    for ordinal, (_, raw) in enumerate(ref.prepare_analysis_frame(rows).iterrows()):
        row = raw.to_dict(); info = source_info(row) or {}
        try:
            x = float(row.get('Station x (m)'))
        except (ValueError,TypeError):
            x = float('nan')
        name = str(row.get('Girder') or info.get('girder') or '')
        identity = {'Girder':name,'Case':info.get('case'),'x (m)':x,
            'Source Excel row':info.get('row'),'Source StepType':info.get('step'),
            'Source location type':info.get('location_type'), 'Source input ordinal':ordinal}
        if math.isfinite(x) and (abs(x)<=1e-9 or abs(x-span)<=1e-9):
            excluded.append({**identity,'Status':'OUTSIDE MODEL SCOPE',
                'Reason':'Physical end: bearing/transfer/diaphragm D-region resistance is not represented by this interior model.'})
            continue
        if not math.isfinite(x) or not 0<x<span:
            entries.append({**identity,'Status':'MODEL SOURCE BLOCKED','Reason':'Station must lie within the physical girder.'})
            continue
        if not concurrent_source_allowed(info) or ref.SNAPSHOT_KEY not in info or info[ref.SNAPSHOT_KEY].get('force_kind')!='GIRDER_COMPOSITE':
            entries.append({**identity,'Status':'MODEL SOURCE BLOCKED',
                'Reason':'One declared concurrent composite Girder vector and recorded CSI origin are required.'})
            continue
        candidates.append((identity,row,info))
    for identity, row, info in candidates:
        name = identity['Girder']
        entry = {'Girder':name,'Case':info.get('case'),'x (m)':float(row['Station x (m)']),
            **identity,
            'Status':'MODEL BLOCKED','accepted_Vn_kN':None,'accepted_Tn_kNm':None,'accepted_VT_factor':None}
        try:
            local = igird_station_section.at_station(state,entry['x (m)'])
            x = entry['x (m)']; params = dict(local.get('section_parameters') or {})
            prep, composite, messages = ap._beam_uls_final_composite_preparation(local)
            if composite is None: raise ValueError('; '.join(messages))
            poly = to_shapely_polygon(local['section_geometry'])
            source = csi_reference_analysis.convert_for_check(local,row,check_name='Shear + Torsion')
            inp, notes = ap._beam_uls_flexure_analysis_input_for_station(composite,row=source,
                strength_route=route,capacity_direction=-1. if float(source['Mux'])<0 else 1.,prestress_force_stage='final')
            if inp is None: raise ValueError('; '.join(notes))
            context = SectionEquilibrium(inp,1.)
            if context.unresolved_bar_materials: raise ValueError('Longitudinal steel materials must be resolved.')
            if inp.concrete_material.density_kg_m3 < 2200: raise ValueError('Normal-weight model only.')
            dev = development_settings(local)
            factors, traces = ordinary_bar_limits(context,x_m=x,span_m=span,settings=dev,params=params,
                girder_fc_mpa=float(prep.girder_fc_MPa))
            # Conditional measured-length development is retained even when an
            # old continuity checkbox is false; the false flag stays in audit
            # and prevents design acceptance. It is never silently set true.
            steel = []
            for bar, factor, trace in zip(context.bars,factors,traces):
                mat = context.materials[bar.material_name]
                steel.append({'label':bar.label,'component':'slab' if bar.material_name.startswith('Composite deck longitudinal rebar') else 'girder',
                    'y_mm':bar.y_mm,'area_mm2':bar.area_mm2,'factor':factor,
                    'force_N':bar.area_mm2*mat.fy_MPa*factor,'development':trace})
            from concrete_pmm_pro.analysis.igird_end_sections import cut_ends
            left,right = cut_ends(params,span)
            ps = strand_ties(local.get('girder_strand_layout_table',[]),x_m=x,span_m=span,
                y_min_mm=poly.bounds[1],depth_mm=poly.bounds[3]-poly.bounds[1],
                fy_tie_MPa=min(m.fy_MPa for m in context.materials.values()),settings=dev,left_cut_m=left,right_cut_m=right,
                require_x_positions=False)
            for record in ps:
                steel.append({'label':record['label'],'component':'strand','y_mm':record['y_mm'],
                    'area_mm2':record['area_mm2'],'force_N':record['capacity_N'],'factor':None,'development':record['development'],
                    'spatial_position_verified':record['spatial_position_verified']})
            mid = .5*(poly.bounds[1]+poly.bounds[3]+float(prep.deck_thickness_mm))
            for bar in steel: bar['pool'] = 'bottom' if bar['y_mm'] <= mid else 'top'
            bottom = sum(b['force_N'] for b in steel if b['pool']=='bottom')
            top = sum(b['force_N'] for b in steel if b['pool']=='top')
            zone = weakest_girder_zone(ap._beam_uls_shear_reinforcement_dataframe_from_state(local).to_dict('records'),x)
            interface = ap._igird_interface_shear_settings_from_state(local)
            if interface['connector_source'] == STIRRUPS:
                raise ValueError('Extended I-hoops are the same steel, not a second U-dowel supply. Choose the actual independent dowel source.')
            selected = at_station(interface,x_m=x,girder_zone=zone)
            if not selected['ready']: raise ValueError(selected['reason'])
            dowel = selected['zone']
            if dowel['Legs'] != 2: raise ValueError('The physical U model requires exactly two legs.')
            detail = resolve(config(interface),slab_thickness_mm=prep.deck_thickness_mm,db_mm=dowel['Diameter_mm'])
            anchor = anchorage(detail,dowel,{'fc_slab_MPa':prep.deck_fc_MPa,'fc_girder_MPa':prep.girder_fc_MPa,
                'slab_thickness_mm':prep.deck_thickness_mm,'girder_depth_mm':poly.bounds[3]-poly.bounds[1],
                'girder_polygon':list(poly.exterior.coords),'girder_holes':[list(h.coords) for h in poly.interiors],
                'contact_center_x_mm':poly.centroid.x,'contact_top_y_mm':poly.bounds[3],'normal_weight':True})
            if not anchor['ready']: raise ValueError('U anchorage dimensions: '+ '; '.join(anchor.get('reasons',[])))
            torsion = ap._beam_uls_torsion_result_for_row(local,row,strength_route=route)
            shear = ap._beam_uls_shear_result_for_row(local,row,strength_route=route)
            # All candidates were source-gated above. Reuse the SAME checked
            # row function, including its gate, station/CSI conversion and
            # detailing. A one-row dataframe used to reset nominal fps reuse
            # and rerun the identical torsion check for every vector.
            if abs(float(source['Mux'])) <= 1e-9:
                raise ValueError('One exact concurrent tension-face result is required; zero M needs both faces.')
            from .igird_combined_vt import _check_row
            concurrent = _check_row(local,row,strength_route=route,
                face='top' if float(source['Mux']) < 0 else 'bottom',
                source_index=identity['Source input ordinal'], nominal_cache=nominal_fps_cache,
                ambiguous_case=False, torsion_result=torsion)
            hoop = core_hoop_supply(local,x_m=x)
            db = float(dowel['Diameter_mm']); radius = .5*(float(detail['hook_inside_bend_mm'])+db)
            width = float(detail['row_spacing_mm'])
            height = float(detail['girder_ld_available_mm'])+float(detail['slab_ldh_available_mm'])+radius-db/2
            if min(width,height) <= 0: raise ValueError('Positive actual U dimensions required.')
            closings = []
            for face in ('top','bottom'):
                mat = detail.get('slab_transverse_mesh',{}).get(face,{})
                d,s,fy = [float(mat[k]) for k in ('Diameter_mm','Spacing_mm','fy_MPa')]
                if min(d,s,fy)<=0 or not all(math.isfinite(v) for v in (d,s,fy)):
                    raise ValueError('Known top and bottom slab transverse steel required.')
                closings.append(math.pi*d*d/4/s*min(fy,60*6.894757293168))
            dv = min(float(shear['dv mm']),height)
            cot = float(concurrent['θ cot']); fc = min(prep.deck_fc_MPa,prep.girder_fc_MPa)
            contact,_ = ap._igird_interface_bvi_mm(local,interface)
            surface = surface_preset(interface['surface_key']); const = surface.constants_si(lightweight=False)
            # Article 5.7.4.5 interface dv is NOT the web-shear dv above.
            # Reuse the same bottom-steel centroid rule as Interface Shear.
            tension_y = ap._beam_uls_reinforcement_y_centroid_for_face(inp,tension_face='bottom')
            slab_mid_y = poly.bounds[3] + .5*float(prep.deck_thickness_mm)
            interface_dv = slab_mid_y-float(tension_y) if tension_y is not None else float('nan')
            if not math.isfinite(interface_dv) or interface_dv<=0:
                raise ValueError('Whole-composite interface lever arm requires a known tension-steel centroid.')
            if float(source['Mux']) < -1e-9:
                raise ValueError('Whole-interface approximation currently covers positive bending; negative-moment slab tension needs a separately verified interface field.')
            # Separate physical paths. Ao of the existing I hoop is unchanged;
            # a*H describes the explicitly HYPOTHETICAL central U/mat cell.
            supply = engine.Supplies(core_ao_mm2=hoop['Ao mm2'],core_ph_mm=hoop['ph mm'],
                core_dv_mm=float(shear['dv mm']),core_leg_N_per_mm=hoop['At/s mm2/mm']*hoop['fy MPa'],
                u_ao_mm2=width*height,u_ph_mm=2*(width+height),u_dv_mm=dv,
                u_leg_N_per_mm=math.pi*db*db/4/float(dowel['Spacing_mm'])*min(float(dowel['fy_MPa']),60*6.894757293168),
                slab_closing_N_per_mm=min(closings),bottom_longitudinal_N=bottom,top_longitudinal_N=top,
                top_girder_longitudinal_N=sum(b['force_N'] for b in steel if b['pool']=='top' and b['component']!='slab'),
                top_slab_longitudinal_N=sum(b['force_N'] for b in steel if b['pool']=='top' and b['component']=='slab'),
                diagonal_q_N_per_mm=.25*prep.girder_fc_MPa*float(shear['bw mm'])/(2*(cot+1/cot)),
                contact_width_mm=contact,u_leg_spacing_mm=width,contact_MPa=.85*fc,
                interface_MPa=min(const['K1']*fc,const['K2_MPa']),mu=surface.mu,cot_theta=cot,
                interface_dv_mm=interface_dv)
            actions = {'vu_N':float(source['Vuy'])*1000,'tu_Nmm':float(source['Tu'])*1e6,
                'mu_Nmm':float(source['Mux'])*1e6,'nu_tension_N':-ap.girder_axial_demand_kN(source,local)*1000}
            calculated = engine.calculate(supply,**actions,held_action_intercepts=True,solve_cache=solve_cache)
            # Reconstruct physical-unit balances independently of LP matrices.
            # This verifies the declared model, not the real stress field.
            from concrete_pmm_pro.verification.igird_fullvt48 import audit_witness
            audit_actions={
                'V':dict(vu_N=1000.,tu_Nmm=0.),'T':dict(vu_N=0.,tu_Nmm=1e6),
                'VT':actions,
                'V_fixed_MN':dict(vu_N=1000.,tu_Nmm=0.,mu_Nmm=actions['mu_Nmm'],nu_tension_N=actions['nu_tension_N']),
                'T_fixed_MN':dict(vu_N=0.,tu_Nmm=1e6,mu_Nmm=actions['mu_Nmm'],nu_tension_N=actions['nu_tension_N'])}
            calculated['force_audit']={name:audit_witness(supply,calculated[name],**force)
                for name,force in audit_actions.items()}
            if any(a['status']=='FAIL' for a in calculated['force_audit'].values()):
                raise ValueError('Independent whole-interface force audit failed; capacity is not published.')
            from concrete_pmm_pro.analysis.igird_u_anchorage51 import evaluate as nodal_anchorage
            try:
                node_trace = nodal_anchorage(detail=detail,params=params,
                    slab_thickness_mm=prep.deck_thickness_mm,slab_bottom_y_mm=poly.bounds[3],
                    db_mm=db,spacing_mm=dowel['Spacing_mm'],anchorage=anchor,
                    inventory=steel,calculation=calculated)
            except (ValueError,TypeError,KeyError) as exc:
                node_trace = {'status':'NODAL GEOMETRY INCOMPLETE','reason':str(exc),
                    'accepted_composite_capacity':None,'changes_nominal_resistance':False}
            from concrete_pmm_pro.analysis.igird_interface50 import check as interface_reference
            joint_reference = interface_reference(vu_kN=actions['vu_N']/1000,bvi_mm=contact,
                dv_interface_mm=interface_dv,fc_weaker_MPa=fc,
                avf_mm2_per_m=float(dowel['Avf_mm2_per_m']),fy_MPa=float(dowel['fy_MPa']),
                surface_key=interface['surface_key'],anchor_dimensions_ready=anchor['ready'],
                anchorage_declared=interface['connectors_cross_and_anchored'],
                effective_width_verified=bool(params.get('Be_strength_verified',False)),shear_trace=shear)
            status = 'MODEL REVIEW' if all(calculated[k].get('ready') for k in ('V','T','VT','V_fixed_MN','T_fixed_MN')) else 'MODEL INCOMPLETE'
            entry.update({'Status':status,'calculation':calculated,
                'torsion_reference':ref.trace_columns(source),
                'inventory':steel,'anchorage':anchor,'U geometry':{'a_mm':width,'H_mm':height,'candidate_Ao_mm2':width*height},
                'nodal_anchorage':node_trace,
                'actions':actions,'source_CSI':{k:float(row[k]) for k in ('Nu','Vuy','Vux','Tu','Muy','Mux')},
                'baseline_code_check':{'Vn_kN':shear.get('Vn kN'),'Tn_transverse_kNm':torsion.get('Tn kN-m'),
                    'Threshold status':torsion.get('Threshold status')}, 'physical_I_hoop':hoop,
                'shear_trace':{k:shear.get(k) for k in ('Vc kN','Vs kN','Vn kN','φVn kN','φ','bw mm','dv mm','θ deg','β','Section basis','h mm','Precast h mm','de mm','C-T lever arm mm','Compression f\'c MPa')},
                'section_definition':{'Be_mm':prep.effective_width_mm,'Tslab_mm':prep.deck_thickness_mm,
                    'fc_I_MPa':prep.girder_fc_MPa,'fc_slab_MPa':prep.deck_fc_MPa,'h_I_mm':poly.bounds[3]-poly.bounds[1]},
                'baseline_combined_DC':concurrent.get('Overall D/C value'),
                'detail_status':'U-to-slab closed path and local anchorage nodes UNVERIFIED; 90-degree tension hook check only',
                'continuity_flags_preserved':{face:params.get('deck_long_rebar_'+face+'_continuous_confirmed',False) for face in ('top','bottom')},
                'girder_continuity_flag_preserved':dev.get('bars_continuous_confirmed',False),
                'U force supply per leg N/mm':supply.u_leg_N_per_mm,
                'slab_longitudinal_area_mm2':sum(b['area_mm2'] for b in steel if b['component']=='slab'),
                'slab_longitudinal_force_N':sum(b['force_N'] for b in steel if b['component']=='slab'),
                'interface_reference':joint_reference,
                'interface_geometry':{'tension_steel_y_mm':tension_y,'slab_mid_y_mm':slab_mid_y,
                    'dv_interface_mm':interface_dv,'basis':'AASHTO 5.7.4.5: bottom tension-steel area centroid to slab mid-depth; positive bending only'}})
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            entry['Reason'] = str(exc)
        entries.append(entry)
    result.update(scan.summarize(entries,excluded))
    result['calculate_reuse'] = {'LP':solve_cache.summary(),
        'nominal_fps_unique_states':len(nominal_fps_cache),
        'torsion_source_policy':'One exact station/force torsion result reused for the same row only'}
    # Expensive comparisons are needed for the retained governors only, not
    # for every scan row. Reuse a stored inventory; do not solve while rendering.
    comparisons = {}
    for entry in result['rows']+result['governing_rows']:
        if 'calculation' not in entry: continue
        key = (entry['Girder'],entry['Source input ordinal'])
        if key not in comparisons:
            supply = engine.Supplies(**entry['calculation']['supplies'])
            steel = entry['inventory']
            comparisons[key] = {
                'without_U':engine.calculate(replace(supply,u_leg_N_per_mm=0.,slab_closing_N_per_mm=0.),**entry['actions']),
                'without_slab_longitudinal':engine.calculate(replace(supply,
                    bottom_longitudinal_N=supply.bottom_longitudinal_N-sum(b['force_N'] for b in steel if b['pool']=='bottom' and b['component']=='slab'),
                    top_longitudinal_N=supply.top_girder_longitudinal_N,top_slab_longitudinal_N=0.),**entry['actions'])}
        entry.update(comparisons[key])
    if not result['rows']: result['reason'] = 'No interior source rows to calculate; see excluded physical ends.'
    from concrete_pmm_pro.verification.igird_fullvt48 import design_evidence
    result['design_evidence'] = design_evidence(result)
    return result


def render(result):
    """Read-only with-U/slab nominal model for the optional case-study panel."""
    from .igird_modeltn47 import render as render_primary
    render_primary(result)
