"""Shared BG40 presentation with workflow-owned, stored Analysis evidence.

Input preparation may validate a source fingerprint. No strength, stress,
prestress-loss or displacement solver is called by this report adapter.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
import math
import re
import pandas as pd

from .bg40_data import Calculation, CalculationReport, Chapter, display, fields_table, plain, _status, _source_rows, _json_signature
from .report_models import ReportMetadata

VERSION = 'REPORT.ALL82'
LABELS = {'i_girder':'Precast I-Girder', 'column':'Column Pier Wall Pylon',
    'building_beam':'Building Beam Girder', 'bridge_beam':'Bridge Beam Girder',
    'railway_u':'Railway U-Girder', 'crossbeam':'Portal Frame Crossbeam'}
CB_RESULTS = {
    'Flexure':'crossbeam_analysis1a_uls_flexure_result',
    'Shear':'crossbeam_analysis2_uls_shear_result',
    'Torsion':'crossbeam_analysis3_uls_torsion_result',
    'Shear + Torsion':'crossbeam_analysis4c2_uls_combined_vt_result',
    'At Transfer':'crossbeam_sls1a_transfer_stress_result',
    'At Final Service':'crossbeam_sls1b_service_stress_result',
    'Transfer deflection':'crossbeam_sls2_transfer_camber_result',
    'Service deflection':'crossbeam_sls2_final_service_deflection_result',
    'Deflection':'crossbeam_sls2_deflection_camber_result'}
VIEW = re.compile(r'(?:^|_)(?:selected|selection|tab|view|preview|notice|widget|editor|timing)(?:_|$)')
DIAGNOSTIC = re.compile(r'diagnostic|debug|advanced_qa|independent_qa|linear_mesh|contact_mesh|incremental_contact')


def workflow_key(state):
    mode = state.get('analysis_mode_settings')
    kind = mode.get('member_type') if isinstance(mode,dict) else getattr(mode,'member_type',None)
    if kind == 'portal_frame_crossbeam': return 'crossbeam'
    if kind == 'building_beam_girder': return 'building_beam'
    if state.get('section_preset_key') == 'parametric_i_girder' and kind not in {'column_pier_pmm','general_section'}: return 'i_girder'
    if kind == 'beam_girder': return 'railway_u' if state.get('section_preset_key') == 'railway_u_girder' else 'bridge_beam'
    return 'column'


def obj(value):
    if is_dataclass(value): return asdict(value)
    if hasattr(value,'model_dump'): return value.model_dump()
    return value


def frame(value):
    if isinstance(value,pd.DataFrame): return value.copy(deep=True)
    value = obj(value)
    if isinstance(value,dict) and isinstance(value.get('rows'),list): value = value['rows']
    if isinstance(value,(tuple,list)): return pd.DataFrame([obj(x) for x in value if isinstance(obj(x),dict)])
    return pd.DataFrame()


def scalars(value):
    return {k:v for k,v in value.items() if isinstance(v,(str,int,float,bool))
        and not (isinstance(v,float) and not math.isfinite(v))
        and not (isinstance(v,str) and v.strip().lower() in {'','-','nan','none','<na>'})}


def numeric(row,*keys):
    for key in keys:
        try: value = float(row.get(key))
        except (ValueError,TypeError): continue
        if math.isfinite(value): return value
    return None


def input_snapshot(state):
    from concrete_pmm_pro.state.dirty_state import INPUT_GROUP_KEYS
    keys = {k for values in INPUT_GROUP_KEYS.values() for k in values}
    keys.update(('rebars','prestress_elements','section_dimensions','project_metadata',
        'serviceability_settings','custom_stress_check_points','analysis_accuracy_preset'))
    for key in state:
        name = str(key)
        if not name.startswith(('crossbeam_','girder_','beam_','building_','railway_','column_','section_','slab_','rebar_','prestress_')): continue
        if VIEW.search(name) or DIAGNOSTIC.search(name) or any(x in name for x in ('_result','_summary','_fingerprint','_input_hash','_cache')): continue
        keys.add(key)
    return {k:plain(obj(state.get(k))) for k in sorted(keys) if state.get(k) is not None and not DIAGNOSTIC.search(k)}


def stored_sources(state):
    keys = {'rc_pmm_result','pmm_result','rc_demand_capacity_result','demand_capacity_summary','dc_summary',
        'serviceability_summary','crack_classification_summary','_beam_girder_uls_manual_calculation_cache',*CB_RESULTS.values()}
    for key in state:
        name = str(key)
        if VIEW.search(name) or DIAGNOSTIC.search(name): continue
        if name.startswith(('result_summary_beam_girder_','column_pier_','slab_shell55_','girder_deflect',
                            'girder_prestress_code_loss_','girder_prestress_refined_loss_')): keys.add(key)
        if name.startswith('crossbeam_') and ('result' in name or 'input_hash' in name): keys.add(key)
    return {k:state.get(k) for k in sorted(keys) if state.get(k) is not None and not (
        k == 'crossbeam_ptloss4a_time_dependent_result_v1' and isinstance(state[k],dict) and not state[k].get('adoptable'))}


def universal_signature(state,metadata=None,include_figures=True,include_appendices=True):
    from .bg40_print import PRESENTATION_VERSION
    bindings = ('_perf_last_analysis_input_hash','rc_pmm_result_input_hash','rc_demand_capacity_input_hash',
        'rc_demand_capacity_pmm_result_hash','serviceability_summary_hash','analysis_input_hash',
        'result_summary_beam_girder_sls_cache_hash')
    payload = {'version':VERSION,'presentation':PRESENTATION_VERSION,'workflow':workflow_key(state),
        'metadata':plain(metadata),'figures':include_figures,'appendices':include_appendices,
        'inputs':input_snapshot(state),'bindings':{k:state.get(k) for k in bindings},
        'results':{k:plain(obj(v)) for k,v in stored_sources(state).items()}}
    return _json_signature(payload,default=str)


def currency(state):
    from concrete_pmm_pro.state.dirty_state import LAST_ANALYSIS_HASH_KEY,project_input_hash
    previous = state.get(LAST_ANALYSIS_HASH_KEY)
    return ('CURRENT' if previous == project_input_hash(state) else 'STALE') if previous else 'UNVERIFIED'


def table(report,chapter,name,value,source,*,columns=None,show=True):
    data = frame(value)
    if data.empty: return data
    report.raw_tables[name] = data.copy(deep=True)
    cols = [k for k in (columns or list(data)) if k in data]
    if columns is None: cols = [k for k in cols if not any(isinstance(v,(dict,list,tuple)) for v in data[k])]
    if show and cols: chapter.table(name,data[cols],source)
    return data


def figure(chapter,title,plot,**kwargs):
    chapter.figures.append({'kind':'workflow82','plot':plot,'title':title,
        'caption':'Stored source values retain their original case, station and engineering scope.',**kwargs})


def governing(data):
    if data.empty: return {}
    # Preserve the source's explicit exclusion of diagram-only member ends.
    # Such rows retain their place in station tables and evidence, but cannot
    # replace a physical calculation with a page of undefined capacities.
    statuses=data.get('Status',pd.Series('',index=data.index)).astype(str).str.upper()
    station_type=data.get('Station type',pd.Series('',index=data.index)).astype(str).str.upper()
    notes=data.get('Notes',pd.Series('',index=data.index)).astype(str)
    excluded=statuses.eq('SECTION BOUNDARY') | (station_type.eq('DIAGRAM BOUNDARY') & notes.str.contains('excluded from governing',case=False,regex=False))
    data=data.loc[~excluded]
    if data.empty: return {}
    ratio_columns = [k for k in data if any(s in str(k).lower() for s in ('d/c','utilization','dcr'))]
    def rank(row):
        status = str(row.get('Status',row.get('status',''))).upper()
        return (3 if 'FAIL' in status else 2 if 'BLOCK' in status else 1 if 'REVIEW' in status else 0,
                max((abs(numeric(row,k) or 0.) for k in ratio_columns),default=0.))
    return max(data.to_dict('records'),key=rank)


def control(report,label,status,row,source,basis=''):
    item = pd.DataFrame([{'Check':label,'Status':status,
        'Case':row.get('Case') or row.get('Case Name') or row.get('combo_name') or '-',
        'Station / Point':row.get('Station s (m)',row.get('Station x (m)',row.get('Governing x',row.get('point_name','-')))),
        'D/C':numeric(row,'Overall D/C value','Governing D/C value','Utilization value','D/C value','Utilization','utilization','dcr'),
        'Code basis':basis,'Source':source}])
    report.controls = item if report.controls.empty else pd.concat([report.controls,item],ignore_index=True)


def equations(chapter,row,label,basis):
    check=str(row.get('Check') or label).lower()
    for expression,demands,capacities in (
        ('D/C = |Mu| / φMn',('Demand kN-m','M3 kN-m'),('φMn kN-m','Capacity kN-m')),
        ('D/C = |Vu| / φVn',('Abs demand kN','Demand kN','V2 kN'),('φVn kN','phiVn kN')),
        ('D/C = |Tu| / φTn',('Abs demand kN-m','Demand kN-m','T kN-m'),('phiTn kN-m','φTn kN-m')),
        ('D/C = section limit demand / resistance',('Section limit lhs MPa',),('Section limit rhs MPa',))):
        if 'Mu' in expression and ('torsion' in check or 'shear' in check): continue
        if 'Vu' in expression and 'torsion' in check and 'shear' not in check: continue
        if 'Tu' in expression and 'shear' in check and 'torsion' not in check: continue
        demand,resistance = numeric(row,*demands),numeric(row,*capacities)
        if demand is not None and resistance is not None and resistance > 0:
            chapter.calculations.append(Calculation(label+' | Stored resistance check',expression,
                f'|Demand|={display(abs(demand))}; Capacity={display(resistance)}',
                'Resistance ratio='+display(abs(demand)/resistance)+'; Source governing utilization='+
                display(numeric(row,'Overall D/C value','Governing D/C value','Utilization value','D/C value'))+
                '; Stored status: '+str(row.get('Status','REVIEW')),basis))
            break
    phi = numeric(row,'φ value','φ','phi')
    for nominal,factored,symbol,unit in ((('Mn nominal kN-m',),('φMn kN-m','Capacity kN-m'),'Mn','kN·m'),
        (('Vn kN',),('φVn kN','phiVn kN'),'Vn','kN'),(('Tn kN-m',),('φTn kN-m','phiTn kN-m'),'Tn','kN·m')):
        n,r = numeric(row,*nominal),numeric(row,*factored)
        if phi is not None and n is not None and r is not None:
            chapter.calculations.append(Calculation(label+' | Resistance factor','φ'+symbol+' = φ × adopted '+symbol,
                f'φ={display(phi)}; {symbol}={display(n)} {unit}','Stored φ'+symbol+'='+display(r)+' '+unit,basis))
    for title,needs,provided,ratio,unit in (
        ('Combined transverse reinforcement',('Governing transverse req mm2/mm','(Av+2At)/s adopted req mm2/mm'),
         ('Provided Av+2At per s mm2/mm','(Av+2At)/s provided mm2/mm'),'Transverse D/C value','mm2/mm'),
        ('Longitudinal reinforcement',('Al V+T req mm2','Al adopted req mm2'),('Al provided mm2',),'Longitudinal D/C value','mm2')):
        need,supply = numeric(row,*needs),numeric(row,*provided)
        if need is not None and supply is not None and supply > 0:
            chapter.calculations.append(Calculation(label+' | '+title,'Component utilization = adopted required reinforcement / provided reinforcement',
                f'Required={display(need)} {unit}; Provided={display(supply)} {unit}',
                'Stored component utilization='+display(row.get(ratio))+'; Overall source status='+str(row.get('Status','REVIEW')),basis))
    stress,limit = numeric(row,'Stress MPa'),numeric(row,'Limit MPa')
    if stress is not None and limit is not None:
        criterion = str(row.get('Criterion') or 'Source stress criterion')
        chapter.calculations.append(Calculation(label+' | '+criterion,'σ = σstored',
            f'σ={display(stress)} MPa; Limit={display(limit)} MPa',str(row.get('Status','REVIEW'))+'; '+criterion,basis))
    demand,limit = numeric(row,'Max downward deflection mm','Demand mm'),numeric(row,'Limit mm')
    if demand is not None and limit is not None and limit > 0:
        chapter.calculations.append(Calculation(label+' | Displacement check','Utilization = δdown / δlimit',
            f'Demand={display(demand)} mm; Limit={display(limit)} mm','Stored status: '+str(row.get('Status','REVIEW')),basis))


VISIBLE = ['Check','Case','Case Name','Governing x','Station s (m)','Station x (m)','Section ID','Section face','Fiber','Status',
    'Demand','Capacity','Capacity / Limit','Demand kN-m','Capacity kN-m','Abs demand kN','Demand kN','φVn kN','phiVn kN','phiTn kN-m',
    'Utilization','Utilization value','D/C value','Overall D/C value','Governing D/C value','Stress D/C value','Transverse D/C value','Longitudinal D/C value',
    'Stress MPa','Compression limit MPa','Tension limit MPa','Stage','Region','Span length m','Max upward camber mm','Max downward deflection mm','Limit mm']


def base(state,metadata,key):
    from concrete_pmm_pro.core.design_code import workflow_project_code_label_from_session
    titles = ['Design Criteria Design Loads and Load Combinations','Structural System and Analysis Model','Section Properties',
        'Reinforcement Prestress and Losses','Analysis Results',
        'ULS Axial and Biaxial Flexural Design' if key == 'column' else 'ULS Flexural Design',
        'ULS Shear and Torsion Design','SLS Stress and Cracking','Deflection and Camber','Scope and Required Actions']
    report = CalculationReport(metadata=metadata or ReportMetadata(project_name=state.get('project_name')),
        code=workflow_project_code_label_from_session(state),chapters=[Chapter(i+1,t) for i,t in enumerate(titles)],
        sources=pd.DataFrame(),controls=pd.DataFrame(),signature='',status='REVIEW',warnings=[],
        workflow_key=key,workflow_label=LABELS[key])
    report.input_snapshot = input_snapshot(state)
    report.chapters[0].table('Design criteria',fields_table({'Workflow':LABELS[key],'Design code':report.code,
        'Section':state.get('section_preset_name') or state.get('section_preset_key'),
        'Internal units':'mm, MPa, N, N-mm','Source action units':'Retained from each source table'}),'Project setup')
    for name in ('concrete_material','concrete_materials','rebar_materials','prestress_materials'):
        data = obj(state.get(name))
        if isinstance(data,dict): report.chapters[0].table(name.replace('_',' '),fields_table(scalars(data)),name)
        else: table(report,report.chapters[0],name,data,name)
    for name in ('analysis_mode_settings','analysis_settings','beam_girder_system_settings','girder_prestress_system_settings','railway_u_girder_stage_settings'):
        value = obj(state.get(name))
        if isinstance(value,dict): report.chapters[1].table(name.replace('_',' '),fields_table(value),name)
    for name in ('load_cases','column_uls_loads_table','column_sls_loads_table','beam_uls_loads_table','beam_sls_loads_table','crossbeam_uls_loads_table','crossbeam_sls_loads_table'):
        source=name+' | actions: kN and kN·m; station: m' if name.endswith('_loads_table') else name
        data = table(report,report.chapters[4],name.replace('_',' '),state.get(name),source)
        if name.endswith('_loads_table') and not data.empty:
            source_rows=_source_rows(data,LABELS[key])
            for record in source_rows:
                if record.get('File')=='Manual input': record['File']='Project input (import identity not recorded)'
            report.sources = pd.concat([report.sources,pd.DataFrame(source_rows)],ignore_index=True)
    for name in ('rebars','prestress_elements','rebar_table','prestress_table','girder_strand_layout_table','girder_prestress_force_states_table',
                 'girder_prestress_code_loss_summary_table','girder_prestress_code_loss_result_table','girder_prestress_refined_loss_interval_table'):
        data = table(report,report.chapters[3],name.replace('_',' '),state.get(name),name)
        if not data.empty and 'loss' in name: report.chapters[3].notes.append('Recorded prestress-loss audit: input currency is unverified; confirm its source assumptions before issue.')
    geometry = state.get('section_geometry')
    if geometry is not None:
        from concrete_pmm_pro.core.models import SectionGeometry
        from concrete_pmm_pro.geometry.summary import summarize_geometry
        g = SectionGeometry.model_validate(geometry) if isinstance(geometry,dict) else geometry
        p = summarize_geometry(g)
        report.chapters[2].table('Gross section properties',fields_table({'Area A (mm2)':p.area_mm2,
            'Centroid x (mm)':p.centroid_x_mm,'Centroid y (mm)':p.centroid_y_mm,'Ix (mm4)':p.ix_nmm4,'Iy (mm4)':p.iy_nmm4}),'Current section polygon')
        figure(report.chapters[2],'Section geometry and reinforcement','section')
    report.chapters[2].table('Section dimensions',fields_table(state.get('section_parameters') or {}),'Section Builder')
    if key in {'building_beam','bridge_beam','railway_u'}:
        from .bg40_figures import span
        if span(state): figure(report.chapters[1],'Member longitudinal reference','system',caption='Current member reference length. Support restraints are not inferred.')
    for chapter in report.chapters[:5]: chapter.status = 'INPUT DATA' if chapter.tables or chapter.figures else 'NOT CALCULATED'
    report.chapters[9].notes.append('The report preserves the source code edition, case correspondence and acceptance scope. Only stored Analysis results are used; missing checks are not calculated during export.')
    return report


def serviceability(report,state,stale):
    summary = state.get('serviceability_summary')
    if summary is None: return
    chapter = report.chapters[7]
    binding=state.get('serviceability_summary_hash')
    if binding and not stale:
        try:
            from concrete_pmm_pro.analysis.runtime import serviceability_input_hash
            from concrete_pmm_pro.analysis.preflight import _analysis_settings_from_session_state
            from concrete_pmm_pro.core.analysis import AnalysisInput
            from concrete_pmm_pro.core.reinforcement_system import effective_rebars_for_analysis,effective_prestress_for_analysis
            from concrete_pmm_pro.serviceability.models import ServiceabilitySettings
            settings=_analysis_settings_from_session_state(state)
            model=AnalysisInput(section_geometry=state.get('section_geometry'),concrete_material=state.get('concrete_material'),
                rebar_materials=list(state.get('rebar_materials') or []),prestress_materials=list(state.get('prestress_materials') or []),
                rebars=effective_rebars_for_analysis(list(state.get('rebars') or []),state,settings),
                prestress_elements=effective_prestress_for_analysis(list(state.get('prestress_elements') or []),state,settings),
                load_cases=list(state.get('load_cases') or []),settings=settings)
            criteria=state.get('serviceability_settings') or ServiceabilitySettings()
            criteria=ServiceabilitySettings.model_validate(criteria) if isinstance(criteria,dict) else criteria
            stale=binding!=serviceability_input_hash(model,criteria,list(state.get('custom_stress_check_points') or []),bool(state.get('include_default_stress_check_points',True)))
        except (ValueError,TypeError,KeyError,AttributeError): stale=True
    if stale:
        chapter.status = 'STALE'; chapter.notes.append('Stored section service stresses are stale and excluded.'); return
    value = obj(summary)
    rows = frame(value.get('stress_results',[]) if isinstance(value,dict) else [])
    data = table(report,chapter,'Section service stress results',rows,'serviceability_summary')
    report.stored_results['serviceability_summary'] = plain(summary)
    chapter.status = str(value.get('overall_status','REVIEW'))
    chapter.notes.extend(str(x) for x in [*(value.get('warnings') or []),*(value.get('info') or [])])
    settings = obj(value.get('settings'))
    if isinstance(settings,dict): chapter.table('Stored serviceability criteria',fields_table(scalars(settings)),'serviceability_summary.settings')
    for row in data.to_dict('records'):
        if row.get('include_in_governing') is False: continue
        limit = numeric(row,'limit_MPa')
        formula = 'σtotal = σexternal + σprestress'
        if limit is not None and limit > 0: formula += '; utilization = |σtotal| / applicable stress limit'
        chapter.calculations.append(Calculation(str(row.get('combo_name'))+' | '+str(row.get('point_name')),formula,
            'σexternal='+display(row.get('external_stress_MPa'))+' MPa; σprestress='+display(row.get('prestress_stress_MPa'))+' MPa; limit='+display(row.get('limit_MPa'))+' MPa',
            'σtotal='+display(row.get('total_stress_MPa',row.get('stress_MPa')))+' MPa; utilization='+display(row.get('utilization'))+'; '+str(row.get('status','REVIEW')),
            report.code+' | stored serviceability limits'))
    if not data.empty: figure(chapter,'Section service stress by case and check point','stress_points',data=plain(data.to_dict('records')))


def column(report,state,stale):
    strength,shear = report.chapters[5:7]
    pmm = state.get('rc_pmm_result') or state.get('pmm_result')
    dc = state.get('rc_demand_capacity_result') or state.get('demand_capacity_summary') or state.get('dc_summary')
    binding=state.get('rc_pmm_result_input_hash')
    if binding and not stale:
        from concrete_pmm_pro.analysis.preflight import build_analysis_input_from_session_state
        from concrete_pmm_pro.analysis.runtime import analysis_input_hash,demand_capacity_input_hash
        try:
            model=build_analysis_input_from_session_state(state)
            stale=model is None or binding!=analysis_input_hash(model,state.get('analysis_accuracy_preset') or 'Standard')
            dc_binding=state.get('rc_demand_capacity_input_hash') or state.get('rc_demand_capacity_result_hash')
            if dc_binding and dc is not None:
                stale=stale or dc_binding!=demand_capacity_input_hash(binding,list(state.get('load_cases') or []))
        except (ValueError,TypeError,KeyError,AttributeError): stale=True
    if stale and (pmm is not None or dc is not None):
        strength.status='STALE'; strength.notes.append('Stored PMM results are stale and excluded. Recalculate for the current model.')
    else:
        if pmm is not None and getattr(pmm,'points',None):
            from concrete_pmm_pro.analysis.result_models import pmm_result_to_display_dataframe
            report.raw_tables['PMM full point cloud']=pmm_result_to_display_dataframe(pmm)
            strength.status='REVIEW'
            strength.notes.append('The diagram plots stored factored PMM points. No new capacity surface is solved or interpolated during export.')
            figure(strength,'Stored PMM factored interaction points','pmm')
        if dc is not None:
            value=obj(dc)
            data=table(report,strength,'PMM demand capacity results',value.get('results',[]),'Stored PMM demand capacity summary')
            for row in data.to_dict('records'):
                label=str(row.get('combo_name','ULS case'))
                strength.calculations.append(Calculation(label+' | Directional PMM demand capacity','D/C = Mu / φMn at Pu',
                    'Mu='+display((numeric(row,'Mu_Nmm') or 0.)/1e6)+' kN·m; φMn='+display(None if row.get('capacity_phiMn_Nmm') is None else row['capacity_phiMn_Nmm']/1e6)+' kN·m; Pu='+display((numeric(row,'Pu_N') or 0.)/1e3)+' kN',
                    'D/C='+display(row.get('dcr'))+'; '+str(row.get('status','REVIEW')),report.code+' | stored method: '+str(row.get('capacity_method'))))
                control(report,'PMM '+label,row.get('status','REVIEW'),row,'rc_demand_capacity_result',report.code)
            strength.status=str(value.get('overall_status','REVIEW'))
            if not data.empty: figure(strength,'PMM utilization by load case','utilization',data=plain(data.to_dict('records')))
        for value in (pmm,dc):
            if value is not None:
                strength.notes.extend(str(x) for x in getattr(value,'warnings',[]))
                strength.notes.extend(str(x) for x in getattr(value,'info',[]))
    if not stale:
        from .column_pier_vt_report import build_column_pier_vt_report_package
        package=build_column_pier_vt_report_package(state)
        if package.available:
            for name,data in package.tables().items(): table(report,shear,name.replace('_',' '),data,name)
            shear.status=_status(package.audit.get('Status',pd.Series(['REVIEW'])).tolist())
            shear.notes.extend(package.warnings)
            for row in package.audit.to_dict('records'):
                basis=str(row.get('Code basis') or report.code)
                control(report,'Column V+T '+str(row.get('Direction','')),row.get('Status','REVIEW'),row,'column_pier_combined_vt_result_df',basis)
                equations(shear,row,str(row.get('Case'))+' | '+str(row.get('Direction')),basis)
            from .workflow_figures import plottable
            if plottable(package.audit): figure(shear,'Column shear and torsion utilization','utilization',data=plain(package.audit.to_dict('records')))
    serviceability(report,state,stale)


def beam(report,state,stale):
    from concrete_pmm_pro.ui import analysis_page as ap
    from .workflow_figures import beam_plottable,plottable
    cache=state.get('_beam_girder_uls_manual_calculation_cache') or {}
    frames={'Flexure':'flexure_preview_df','Shear':'shear_check_df','Torsion':'torsion_check_df','Shear + Torsion':'combined_vt_df'}
    for check,key in frames.items():
        entry=cache.get(check)
        if not isinstance(entry,dict): continue
        chapter=report.chapters[5 if check=='Flexure' else 6]
        current=not stale
        if current and entry.get('input_hash'):
            try:
                active=ap._active_beam_uls_demand_dataframe_from_session(state)
                route=ap._beam_uls_strength_route_from_state(state,is_bridge=report.workflow_key!='building_beam',is_building=report.workflow_key=='building_beam')
                current=entry['input_hash']==ap._beam_uls_check_input_hash(state,active,strength_route=route,check_name=check)
            except (ValueError,TypeError,KeyError,AttributeError): current=False
        if not current:
            chapter.status='STALE'; chapter.notes.append(check+': stored results are stale and excluded.')
            control(report,check,'STALE',{},key,report.code); continue
        data=table(report,chapter,check+' full station results',entry.get(key),key,columns=VISIBLE)
        if data.empty: continue
        casekey=next((k for k in ('Case','Case Name') if k in data),None)
        groups=data.groupby(casekey,dropna=False,sort=False) if casekey else [('',data)]
        for case,rows in groups:
            row=governing(rows); label=check+(' | '+str(case) if case else '')
            chapter.table(label+' governing calculation values',fields_table(scalars(row)),key)
            equations(chapter,row,label,str(row.get('Code basis') or report.code))
        status=_status(data.get('Status',pd.Series(['REVIEW'])).tolist())
        chapter.status=status if chapter.status=='NOT CALCULATED' else _status([chapter.status,status])
        control(report,check,status,governing(data),key,report.code)
        if beam_plottable(data): figure(chapter,check+' demand capacity and utilization','beam',data=plain(data.to_dict('records')),plot_check=check)
        for name,values in entry.items():
            if name.endswith('messages') and isinstance(values,(list,tuple)): chapter.notes.extend(str(x) for x in values if x)
    serviceability(report,state,stale)
    for name in ('result_summary_beam_girder_sls_stage_summary_df','result_summary_beam_girder_sls_demand_detail_df'):
        data=frame(state.get(name))
        if data.empty: continue
        chapter=report.chapters[7]
        if stale: chapter.status='STALE'; continue
        table(report,chapter,name.replace('_',' '),data,name)
        stage_status=_status(data.get('Status',data.get('Decision',pd.Series(['REVIEW']))).tolist())
        chapter.status=stage_status if chapter.status=='NOT CALCULATED' else _status([chapter.status,stage_status])
        chapter.notes.append('The legacy staged handoff contains stored governing points; a complete station history is not reconstructed during export.')
        for row in data.to_dict('records'):
            if numeric(row,'Actual stress (MPa)') is not None:
                chapter.calculations.append(Calculation(str(row.get('Stage'))+' | '+str(row.get('Case Name')),
                    'Utilization = actual stress / matching signed stress limit',
                    'Actual stress='+display(row.get('Actual stress (MPa)'))+' MPa; Limit='+display(row.get('Limit stress (MPa)'))+' MPa',
                    'Utilization='+display(row.get('Utilization'))+'; '+str(row.get('Status')),str(row.get('Limit profile') or report.code)))
        if plottable(data): figure(chapter,'Stored staged SLS governing points','utilization',data=plain(data.to_dict('records')))


def crossbeam_binding(state,label,result):
    from concrete_pmm_pro.analysis.crossbeam_uls import build_crossbeam_uls_flexure_preparation
    from concrete_pmm_pro.analysis.crossbeam_uls_shear import build_crossbeam_uls_shear_preparation
    from concrete_pmm_pro.analysis.crossbeam_uls_torsion import build_crossbeam_uls_torsion_preparation
    from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import build_crossbeam_uls_combined_vt_preparation
    from concrete_pmm_pro.analysis.crossbeam_sls_transfer import build_crossbeam_transfer_stress_preparation,build_crossbeam_service_stress_preparation
    from concrete_pmm_pro.analysis.crossbeam_sls_deflection import build_crossbeam_deflection_preparation,build_crossbeam_deflection_stage_preparation,TRANSFER_STAGE,FINAL_SERVICE_STAGE
    builders={'Flexure':build_crossbeam_uls_flexure_preparation,'Shear':build_crossbeam_uls_shear_preparation,
        'Torsion':build_crossbeam_uls_torsion_preparation,'Shear + Torsion':build_crossbeam_uls_combined_vt_preparation,
        'At Transfer':build_crossbeam_transfer_stress_preparation,'At Final Service':build_crossbeam_service_stress_preparation,
        'Deflection':build_crossbeam_deflection_preparation,'Transfer deflection':lambda s:build_crossbeam_deflection_stage_preparation(s,TRANSFER_STAGE),
        'Service deflection':lambda s:build_crossbeam_deflection_stage_preparation(s,FINAL_SERVICE_STAGE)}
    fingerprint=result.get('input_fingerprint') or result.get('fingerprint')
    if not fingerprint: return 'UNVERIFIED'
    try:
        preparation=builders[label](state)
        return 'CURRENT' if preparation.ready and preparation.fingerprint==fingerprint else 'STALE'
    except (ValueError,TypeError,KeyError,AttributeError): return 'STALE'


def crossbeam(report,state,stale):
    method=str(state.get('crossbeam_ptloss3b1_construction_method') or 'Precast Segmental')
    for name,value in input_snapshot(state).items():
        if not name.startswith('crossbeam_'): continue
        chapter=report.chapters[3] if any(x in name for x in ('rb','tr1','tendon','ptloss')) else report.chapters[1]
        if isinstance(value,(list,dict)):
            data=frame(value)
            if not data.empty: table(report,chapter,name.replace('_',' '),data,name)
            elif isinstance(value,dict): chapter.table(name.replace('_',' '),fields_table(scalars(value)),name)
    for label,key in CB_RESULTS.items():
        value=state.get(key)
        if not isinstance(value,dict): continue
        chapter=report.chapters[8 if 'deflection' in label.lower() else 7 if label.startswith('At ') else 5 if label=='Flexure' else 6]
        method_stored=value.get('construction_method'); credit=str(value.get('flexure_credit_basis') or '')
        if method_stored is None and credit: method_stored='Precast Segmental' if 'TENDON-ONLY' in credit else 'Cast-in-Place' if 'SECTION REBAR' in credit else None
        binding=crossbeam_binding(state,label,value)
        if stale or (method_stored is not None and method_stored!=method) or binding=='STALE':
            chapter.status='STALE'; chapter.notes.append(label+': stored results are stale or belong to another construction type and are excluded.')
            control(report,label,'STALE',{},key,report.code); continue
        if binding=='UNVERIFIED': chapter.notes.append(label+': input currency requires review because no source fingerprint is recorded.')
        status=str(value.get('status') or 'REVIEW'); basis=str(value.get('code_basis') or report.code)
        rows=value.get('rows',value.get('results',value.get('checks',value.get('span_rows',[]))))
        data=table(report,chapter,label+' station results',rows,key,columns=VISIBLE)
        row=value.get('governing_row') or governing(data)
        chapter.table(label+' governing calculation values',fields_table(scalars(row)),key)
        equations(chapter,row,label,str(row.get('Code basis') or basis))
        control(report,label,status,row,key,basis)
        chapter.status=status if chapter.status=='NOT CALCULATED' else _status([chapter.status,status])
        chapter.notes.extend(str(x) for x in [value.get('scope'),*(value.get('warnings') or []),*(value.get('errors') or [])] if x)
        for name,values in value.items():
            if name not in {'rows','results','checks','governing_row'} and isinstance(values,(list,pd.DataFrame)):
                table(report,chapter,label+' '+name.replace('_',' '),values,key,show=name in {'required_actions','joint_review_rows'})
        chart_data=frame(value.get('response_rows')) if 'deflection' in label.lower() else data
        if 'Case' in chart_data:
            for case,group in chart_data.groupby('Case',dropna=False,sort=False):
                stages=group.Stage.drop_duplicates().tolist() if 'Stage' in group else [None]
                for stage in stages:
                    components=('stress','transverse','longitudinal') if label=='Shear + Torsion' else (None,)
                    for component in components:
                        title=label+' | '+str(case)+(' | '+component.title() if component else '')
                        figure(chapter,title,'crossbeam',source_key=key,plot_check=label,case=str(case),stage=stage,component=component)
    definitions=state.get('crossbeam_seclib1_definitions') or []
    if definitions:
        from concrete_pmm_pro.crossbeam.section_library import section_property_records
        table(report,report.chapters[2],'Crossbeam section properties',section_property_records(definitions),'Crossbeam source section library')
        for definition in definitions: figure(report.chapters[2],'Section '+str(definition.get('Section ID')),'crossbeam_section',definition=plain(definition))
    if state.get('crossbeam_ui1_length_m') and state.get('crossbeam_ui1_segment_layout_rows'):
        figure(report.chapters[1],'Crossbeam zones and column references','crossbeam_system',caption='Source section layout and column references. Geometry is not a solved frame response.')
    for key in ('crossbeam_ptloss_lightweight_es_result_v1','crossbeam_ptloss4a_time_dependent_result_v1'):
        value=state.get(key)
        if not isinstance(value,dict): continue
        chapter=report.chapters[3]
        if stale or (value.get('construction_method') and value['construction_method']!=method):
            chapter.notes.append('Recorded prestress-loss evidence is stale or belongs to another construction type and is excluded.'); continue
        if 'time_dependent' in key and not value.get('adoptable'):
            chapter.notes.append('Time-dependent loss final adoption is blocked in the source. Diagnostic time-step output is excluded.'); continue
        chapter.status='REVIEW'; chapter.notes.append('Recorded prestress-loss evidence requires input-currency and adoption review. Source status: '+str(value.get('status','REVIEW')))
        chapter.table('Recorded prestress-loss basis',fields_table(scalars(value)),key+' | currency unverified')
        for name,rows in value.items():
            if isinstance(rows,(list,pd.DataFrame)) and not DIAGNOSTIC.search(name):
                table(report,chapter,'Recorded loss '+name.replace('_',' '),rows,key,show=name in {'after_es_station_rows','summary_rows'})


def additional_stored(report,state,stale):
    from concrete_pmm_pro.serviceability import girder_deflect70 as deflect
    if state.get(deflect.RESULT_KEY) is not None:
        chapter=report.chapters[8]; result=None if stale else deflect.current(state)
        if result is None: chapter.status='STALE'; chapter.notes.append('Stored girder deflection is stale and excluded.')
        else:
            chapter.status=str(result.get('status','REVIEW'))
            chapter.notes.extend(str(result.get(k)) for k in ('limit_label','limit_basis','scope') if result.get(k))
            for key in ('summary','curves','source_audit','service_audit'): table(report,chapter,'Deflection '+key,result.get(key),deflect.RESULT_KEY,show=key=='summary')
            for row in frame(result.get('summary')).to_dict('records'):
                chapter.calculations.append(Calculation(str(row.get('Stage'))+' | '+str(row.get('Girder','')),
                    'Utilization = |deflection| / applicable limit','Demand='+display(row.get('Demand (mm)'))+' mm; Limit='+display(row.get('Limit (mm)'))+' mm',
                    'Utilization='+display(row.get('Utilization'))+'; '+str(row.get('Status')),str(row.get('Basis'))))
            for stage in frame(result.get('summary')).get('Stage',pd.Series(dtype=str)).drop_duplicates():
                for name in result.get('girders',[]) if stage=='Service stage' else [None]:
                    figure(chapter,'Deflection | '+str(stage)+(' | '+name if name else ''),'deflection82',stage=stage,girder=name,caption='Stored deflection curves. '+str(result.get('limit_basis','')))
    from concrete_pmm_pro.analysis import slab_review68 as deck
    if state.get(deck.RESULT_KEY) is not None:
        chapter=report.chapters[9]; chapter.title='Deck Slab Review Scope and Required Actions'; result=None if stale else deck.current(state)
        if result is None: chapter.status='STALE'; chapter.notes.append('Stored deck/slab results are stale and excluded.')
        else:
            chapter.status='FAIL' if 'FAIL' in str(result.get('status')).upper() else 'REVIEW'
            for key in ('summary','mat_envelopes','coverage','exclusion_counts'): table(report,chapter,'Deck '+key.replace('_',' '),result.get(key),result['version'])
            table(report,chapter,'Deck full native check rows',result.get('rows'),result['version'],show=False)
            chapter.notes.append('Deck component indices and the local normal-shear index do not certify full deck or physical-perimeter punching acceptance.')
            chapter.figures.append({'kind':'slab_section','title':'Deck section and reinforcement mats'})
            for view in deck.VIEWS:
                for kind in ('slab_plan','slab_profile'): chapter.figures.append({'kind':kind,'view':view,'title':view+(' | plan' if kind=='slab_plan' else ' | station profile')})
            if result.get('punching_screen78'): chapter.figures.append({'kind':'punching','title':'Local punching index with source thickness'})


def build_workflow_report(state,metadata=None):
    key=workflow_key(state)
    if key=='i_girder':
        from .bg40_data import build_calculation_report
        return build_calculation_report(state,metadata)
    report=base(state,metadata,key); current=currency(state); stale=current=='STALE'
    if current=='UNVERIFIED': report.warnings.append('Legacy stored results have no project-wide current-input binding. Source values require engineering review; the report does not certify their currency.')
    if key=='column': column(report,state,stale)
    elif key=='crossbeam': crossbeam(report,state,stale)
    else: beam(report,state,stale)
    additional_stored(report,state,stale)
    if key=='column' and report.chapters[8].status=='NOT CALCULATED':
        report.chapters[8].status='NOT APPLICABLE'
        report.chapters[8].notes.append('The PMM section workflow has no member-deflection result. Global stability, second-order response and member deflection require a separate structural model.')
    actions=[{'Chapter':c.number,'Check':c.title,'Status':c.status,'Required action':
        'Run the missing Analysis check or document project applicability.' if c.status=='NOT CALCULATED' else
        'Recalculate for current inputs.' if c.status=='STALE' else 'Review the source gate and calculation scope before issue.'}
        for c in report.chapters[5:9] if c.status not in {'PASS','Preview PASS','NOT APPLICABLE','BELOW THRESHOLD'}]
    report.chapters[9].table('Required engineering actions',actions,'Stored chapter statuses')
    if report.chapters[9].status=='NOT CALCULATED': report.chapters[9].status='REVIEW' if actions else 'SCOPE REVIEW'
    for chapter in report.chapters:
        if chapter.status=='NOT CALCULATED' and chapter.tables: chapter.status='INPUT DATA'
        chapter.notes=list(dict.fromkeys(chapter.notes))
        for i,item in enumerate(chapter.tables,1):
            # A reader must still identify the physical row in every wide-table
            # panel. Preserve case plus station, direction, stage or fiber.
            groups=(('Case','Case Name','combo_name'),('Stage',),
                ('Station s (m)','Station x (m)','Governing x','Direction','Dir','point_name','Fiber'))
            identities=[next((k for k in group if k in item.data),None) for group in groups]
            item.data.attrs['report_repeat_columns']=[k for k in identities if k]
            report.raw_tables.setdefault(f'Chapter {chapter.number} table {i} {item.title}',item.data.copy(deep=True))
    report.stored_results={k:plain(obj(v)) for k,v in stored_sources(state).items()}
    report.status='STALE' if stale else _status([c.status for c in report.chapters[5:10] if c.status!='NOT APPLICABLE'])
    report.signature=universal_signature(state,report.metadata)
    return report
