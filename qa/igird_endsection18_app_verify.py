"""Actual app.py input, native force, manual calculation and review verification."""
import argparse,json,pickle,sys
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.analysis.igird_end_sections import SETTINGS_KEY
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_from_session_state,project_to_json
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.io.girder_csi_import import source_info,FORCE_MAP
from concrete_pmm_pro.ui import analysis_page as ap,igird_member_results as mr
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--internal',required=True);args=parser.parse_args()
internal=Path(args.internal).resolve();assert not internal.is_relative_to(ROOT);internal.mkdir(parents=True,exist_ok=True)
state={};apply_project_to_session_state(project_from_json(Path(args.project).read_text()),state);state['_nav_active_workspace']='Loads'
class Upload(BytesIO):
    def __init__(self,data,name):super().__init__(data);self.name=name
fixture=ROOT/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
files=[Upload(fixture.read_bytes(),'ULS_Girder Force uploaded to app.xlsx')]
def uploader(label,*a,**kw):return files if label==UPLOAD_LABEL else ([] if kw.get('accept_multiple_files') else None)
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=240)
for k,v in state.items():at.session_state[k]=deepcopy(v)
def run():at.run(timeout=240);assert not at.exception,[e.message for e in at.exception]
def number(label,value):next(n for n in at.number_input if n.label==label).set_value(value);run()
def canonical(frame):
    frame=frame.copy(deep=True)
    for col in ['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu']:frame[col]=pd.to_numeric(frame[col]).astype(float)
    return frame
def seed(name):
    buttons={b.key for b in at.button};(internal/name).write_bytes(pickle.dumps({k:v for k,v in at.session_state.filtered_state.items() if k not in buttons}))
records={};original_calculator=mr.calculate_member
with patch('streamlit.file_uploader',side_effect=uploader),patch.object(mr,'calculate_member',wraps=mr.calculate_member) as calculate:
    run();bank=deepcopy(at.session_state[BANK_KEY]);assert len(bank)==640
    at.session_state['_nav_active_workspace']='Sections';run()
    checkbox=next(c for c in at.checkbox if c.label=='Enable solid precast end sections');assert not checkbox.value;checkbox.check();run()
    cfg=at.session_state['section_parameters'][SETTINGS_KEY]
    assert cfg['left_solid_m']==cfg['right_solid_m']==1.5 and cfg['left_taper_m']==cfg['right_taper_m']==.25 and cfg['width_mm']==600
    number('Left solid length (m)',2);number('Right solid length (m)',1)
    assert at.session_state['section_parameters'][SETTINGS_KEY]['left_solid_m']==2
    number('Left solid length (m)',1.5);number('Right solid length (m)',1.5)
    next(s for s in at.slider if s.label=='Preview section at Loads x (m)').set_value(1.625);run()
    assert any('LEFT TAPER' in c.value and '400 mm' in c.value for c in at.caption)
    number('Left solid length (m)',19);assert any('overlap' in e.value for e in at.error);number('Left solid length (m)',1.5)
    assert calculate.call_count==0
    saved=project_to_json(project_from_session_state(at.session_state.filtered_state));restored={};apply_project_to_session_state(project_from_json(saved),restored)
    assert restored['section_parameters'][SETTINGS_KEY]==at.session_state['section_parameters'][SETTINGS_KEY] and len(restored[BANK_KEY])==640
    assert '_igird_endsection_local_x' not in saved and '_igird_shearcomp_runtime' not in saved
    records['builder_inputs_preview_overlap_and_json_roundtrip']=True;seed('builder_seed.pkl')
    at.session_state['_nav_active_workspace']='Analysis';run()
    next(r for r in at.radio if r.label=='ULS check to calculate').set_value('Shear + Torsion');run();assert calculate.call_count==0
    next(b for b in at.button if b.label.startswith('Calculate Shear + Torsion — all')).click();run();assert calculate.call_count==2
    seed('calculated_seed.pkl');pd.testing.assert_frame_equal(canonical(at.session_state[BANK_KEY]),canonical(bank),check_dtype=False)
    inputs=mr.member_inputs(at.session_state.filtered_state);summaries=[]
    for member,entry in at.session_state[mr.CACHE_KEY].items():
        result=entry['Shear + Torsion']['result'];assert not result.get('error'),result.get('error');frame=result['combined_vt_df'];source=inputs[member]
        assert len(frame)==320 and frame['Section region'].eq('LEFT SOLID END').any() and frame['Section region'].eq('RIGHT SOLID END').any()
        for _,r in frame.iterrows():
            x=float(r['Governing x'].replace(' m',''));src=source[source['Case Name'].eq(r.Case)&source['Station x (m)'].sub(x).abs().lt(1e-7)].iloc[0]
            info=source_info(src);assert info['girder']==member.split(' / ',1)[1]
            assert all(float(src[target])==float(info['raw_fields'][field]) for field,target in FORCE_MAP.items())
            for key,col in [('Source Mux kN-m','Mux'),('Source Vuy kN','Vuy'),('Source Tu kN-m','Tu'),('Source Nu kN','Nu')]:assert float(r[key])==float(src[col])
        for key in ['shear_diagram_capacity_df','torsion_diagram_capacity_df']:
            d=result[key];assert d['Governing x'].eq('1.625 m').any();sample=d[d['Governing x'].eq('1.625 m')].iloc[0]
            assert sample['Section region']=='LEFT TAPER' and sample['Diagram only'] and pd.isna(sample['D/C value'])
        baseline=deepcopy(at.session_state.filtered_state);baseline['section_parameters'][SETTINGS_KEY]['enabled']=False
        route=ap.beam_girder_uls_strength_route(is_bridge=True,is_building=False,project_design_code='AASHTO LRFD',code_edition='AASHTO LRFD 9th Edition')
        old=original_calculator(baseline,source,check_name='Shear + Torsion',route=route)['combined_vt_df']
        joined=frame.merge(old,on=['Case','Governing x'],suffixes=('_end','_uniform'));body=joined[joined['Section region'].eq('I SECTION')]
        for col in ['Stress D/C value','Transverse D/C value','Longitudinal D/C value','Spacing D/C']:
            assert (pd.to_numeric(body[col+'_end'])-pd.to_numeric(body[col+'_uniform'])).abs().dropna().max()<1e-10
        summaries.append({'member':member,'rows':len(frame),'regions':frame['Section region'].value_counts().to_dict(),
            'maximum_numeric_dc':float(frame['Overall D/C value'].max()),'uniform_maximum_numeric_dc':float(old['Overall D/C value'].max()),
            'statuses':frame.Status.value_counts().to_dict(),'body_numerically_unchanged':True})
    records['native_two_girders_640_rows_all_six_actions_preserved']=True;records['member_results']=summaries
    cache=pickle.dumps(at.session_state[mr.CACHE_KEY])
    for page in ['Result Summary','Report / QA']:
        at.session_state['_nav_active_workspace']=page;run();assert calculate.call_count==2 and pickle.dumps(at.session_state[mr.CACHE_KEY])==cache
    records['summary_report_do_not_recalculate']=True
    at.session_state['_nav_active_workspace']='Sections';run();number('Left solid length (m)',1.6)
    at.session_state['_nav_active_workspace']='Analysis';run();next(r for r in at.radio if r.label=='ULS check to calculate').set_value('Shear + Torsion');run()
    assert calculate.call_count==2 and any('STALE' in str(d.value) for d in at.dataframe)
    records['profile_edit_invalidates_results_without_auto_calculation']=True;records['manual_ui_member_calculations']=2
out=ROOT/'qa/evidence/igird_endsection18';out.mkdir(parents=True,exist_ok=True);(out/'app_checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2),flush=True)
