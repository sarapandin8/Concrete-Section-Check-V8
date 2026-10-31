"""Hypothetical examples calculated with production Analysis commands."""
from __future__ import annotations
import argparse
from pathlib import Path
import pickle
import pandas as pd
from concrete_pmm_pro.core.analysis import AnalysisInput,AnalysisModeSettings
from concrete_pmm_pro.core.models import LoadCase
from concrete_pmm_pro.analysis.pmm_solver import run_rc_pmm_solver
from concrete_pmm_pro.analysis.capacity_check import check_uls_demands_against_rc_pmm
from concrete_pmm_pro.serviceability import run_gross_section_sls_stress_check,ServiceabilitySettings
from concrete_pmm_pro.reporting.workflow_reports import build_workflow_report
from concrete_pmm_pro.reporting.report_models import ReportMetadata
from concrete_pmm_pro.state.dirty_state import mark_analysis_current
from concrete_pmm_pro.ui import analysis_page as ap


def column():
    from tests.test_rc_pmm_solver import _sample_analysis_input
    model=_sample_analysis_input()
    model.load_cases.append(LoadCase(name='SLS sample',Pu_N=700000,Mux_Nmm=70000000,Muy_Nmm=30000000,load_type='SLS'))
    state={k:getattr(model,k) for k in ('section_geometry','concrete_material','rebar_materials','rebars','prestress_elements','load_cases')}
    state.update(analysis_mode_settings=AnalysisModeSettings(member_type='column_pier_pmm'),section_preset_key='rectangle',analysis_settings=model.settings)
    state['rc_pmm_result']=run_rc_pmm_solver(model)
    state['rc_demand_capacity_result']=check_uls_demands_against_rc_pmm(state['rc_pmm_result'],model.load_cases)
    state['serviceability_summary']=run_gross_section_sls_stress_check(model,ServiceabilitySettings(enabled=True))
    state['column_uls_loads_table']=pd.DataFrame([{'Active':True,'Case Name':'ULS-01','Pu':1000.,'Mux':100.,'Muy':50.,'Vux':80.,'Vuy':40.,'Tu':15.,'Note':'Hypothetical coupled ULS vector'}])
    state['column_pier_transverse_reinforcement_table']=pd.DataFrame([{'Active':True,'Zone':'Control section','x_start_m':0.,'x_end_m':0.,'Bar Size':'DB12','Diameter_mm':12.,'Legs':2,'Spacing_mm':150.,'fy_MPa':400.,'Note':'Closed control section hoop'}])
    state['column_pier_transverse_reinforcement_settings']={'closed_tie_layout':'Closed ties / hoops','torsion_core_basis':'Auto from section and tie offset','tie_center_offset_mm':40.}
    state['column_pier_combined_vt_result_df']=ap._column_pier_combined_vt_check_dataframe(state,model)
    state['column_pier_combined_vt_screen_df']=ap._column_pier_combined_vt_screen_dataframe(state['column_pier_combined_vt_result_df'])
    return state


def beam(kind):
    from tests.test_beam_uls_vt_below_threshold_al_not_required import _below_threshold_state
    state=_below_threshold_state()
    if kind=='railway_u':
        from tests.test_report_railway_u_girder1 import _session_state
        state.update(_session_state()); state['rebars']=[]
    state.update(analysis_mode_settings=AnalysisModeSettings(member_type='building_beam_girder' if kind=='building_beam' else 'beam_girder'),
        section_preset_key='railway_u_girder' if kind=='railway_u' else 'rectangle')
    state['beam_uls_loads_table']=pd.DataFrame([{'Active':True,'Station x (m)':x,'Case Name':case,'Mux':m,'Vuy':v,'Tu':t,'Muy':0.,'Vux':0.,'Nu':0.,'Note':'Hypothetical simultaneous static vector'}
        for case,t in [('ULS sample A',20.),('ULS sample B',35.)] for x,m,v in [(0.,0.,100.),(5.,150.,20.),(10.,0.,-100.)]])
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=kind!='building_beam',is_building=kind=='building_beam')
    active=ap._active_beam_uls_demand_dataframe_from_session(state); cache={}
    for check in ('Flexure','Shear','Torsion','Shear + Torsion'):
        result=ap._beam_uls_calculate_selected_check(state,active,selected_check=check,strength_route=route)
        cache[check]={'input_hash':ap._beam_uls_check_input_hash(state,active,strength_route=route,check_name=check),**result}
    state['_beam_girder_uls_manual_calculation_cache']=cache
    sls=LoadCase(name='SLS sample',Pu_N=0.,Mux_Nmm=70000000,load_type='SLS')
    state['load_cases']=[sls]
    model=AnalysisInput(section_geometry=state['section_geometry'],concrete_material=state['concrete_material'],
        rebar_materials=state['rebar_materials'],rebars=state['rebars'],prestress_elements=[],load_cases=[sls])
    state['serviceability_summary']=run_gross_section_sls_stress_check(model,ServiceabilitySettings(enabled=True))
    return state


def crossbeam(segmental=False):
    from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state
    from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state
    from tests.test_crossbeam_analysis4c7d13_result_summary_integration import _store_all_crossbeam_uls
    from tests.test_crossbeam_sls1a_transfer_stress import _transfer_row,_service_row
    from concrete_pmm_pro.analysis import crossbeam_sls_transfer as sls
    state=_store_all_crossbeam_uls(_mixed_30m_state()[0] if segmental else _cip_ready_state())
    length=float(state['crossbeam_ui1_length_m'])
    stations=sorted({0.,length,*(float(x.get('x_end_m',x.get('s_end (m)',length))) for x in state['crossbeam_ui1_segment_layout_rows'])})
    state['crossbeam_sls_loads_table']=[_transfer_row(x,p=5000.,m3=200.) for x in stations]+[_service_row(x,p=4000.,m3=300.) for x in stations]
    for prepare,run,key,hash_key in (
        (sls.build_crossbeam_transfer_stress_preparation,sls.run_crossbeam_transfer_stress,sls.CROSSBEAM_TRANSFER_RESULT_KEY,sls.CROSSBEAM_TRANSFER_RESULT_HASH_KEY),
        (sls.build_crossbeam_service_stress_preparation,sls.run_crossbeam_service_stress,sls.CROSSBEAM_SERVICE_RESULT_KEY,sls.CROSSBEAM_SERVICE_RESULT_HASH_KEY)):
        prep=prepare(state)
        if not prep.ready: raise ValueError(prep.errors)
        state[key]=run(prep); state[hash_key]=prep.fingerprint
    if not segmental:
        from tests.test_crossbeam_analysis4c7d27_stage_isolated_deflection_workspace import _state
        from concrete_pmm_pro.analysis import crossbeam_sls_deflection as d
        data=_state()
        for key in (d.CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,'crossbeam_sls_deflection_limit_basis','crossbeam_sls_deflection_overhang_limit_basis'): state[key]=data[key]
        for stage,key,hash_key in ((d.TRANSFER_STAGE,d.CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_KEY,d.CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_HASH_KEY),
            (d.FINAL_SERVICE_STAGE,d.CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_KEY,d.CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_HASH_KEY)):
            prep=d.build_crossbeam_deflection_stage_preparation(state,stage)
            if not prep.ready: raise ValueError(prep.errors)
            state[key]=d.run_crossbeam_deflection_camber(prep); state[hash_key]=prep.fingerprint
    return state


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',required=True,type=Path); parser.add_argument('--only'); args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    builders={'column':column,'building_beam':lambda:beam('building_beam'),'bridge_beam':lambda:beam('bridge_beam'),
        'railway_u':lambda:beam('railway_u'),'crossbeam_cip':crossbeam,'crossbeam_segmental':lambda:crossbeam(True)}
    for name,builder in builders.items():
        if args.only and args.only!=name: continue
        print('Calculating hypothetical example:',name,flush=True); state=builder()
        state['project_name']='SAMPLE '+name.replace('_',' ').title()
        meta=ReportMetadata(report_title='SAMPLE '+name.replace('_',' ').title()+' Calculation Report',project_name=state['project_name'],
            prepared_by='Concrete Section Pro demonstration',revision='SAMPLE',report_date='31 October 2026',
            note='DEMONSTRATION ONLY. Hypothetical production-kernel examples illustrate application output. Not checked for project issue. All actual FAIL, REVIEW and missing-result states are retained.')
        mark_analysis_current(state,workspace='QA production Analysis commands')
        report=build_workflow_report(state,meta)
        with (args.out/(name+'.pkl')).open('wb') as output: pickle.dump((state,report),output)
        print(name,report.status,'figures',sum(len(c.figures) for c in report.chapters),'calculations',sum(len(c.calculations) for c in report.chapters),flush=True)


if __name__=='__main__': main()
