"""Actual app.py and supplied XLSX: simple SLS flow and production stress inputs."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import argparse,json,pickle,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io import girder_sls_import as sls
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_to_json,project_from_session_state
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.girder_sls_import import UPLOAD_LABEL
parser=argparse.ArgumentParser();parser.add_argument('--xlsx',required=True);parser.add_argument('--internal',required=True);args=parser.parse_args()
xlsx=Path(args.xlsx).resolve();internal=Path(args.internal).resolve();assert not internal.is_relative_to(ROOT);internal.mkdir(exist_ok=True,parents=True)
class Upload(BytesIO):
    def __init__(self):super().__init__(xlsx.read_bytes());self.name=xlsx.name
expected,errors=sls.parse_files([Upload()]);assert not errors and len(expected)==240
state={};apply_project_to_session_state(project_from_json((ROOT/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()),state)
state['_nav_active_workspace']='Loads'
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120)
for k,v in state.items():at.session_state[k]=deepcopy(v)
def run():
    at.run(timeout=120);assert not at.exception,[e.message for e in at.exception]
def canonical(frame,cols):
    f=pd.DataFrame(frame).copy()
    for col in cols:f[col]=pd.to_numeric(f[col]).astype(float)
    return f.sort_values([c for c in ['Girder','Stage','Case Name','Station x (m)'] if c in f]).reset_index(drop=True)
actions=['Station x (m)','N','Mx','My','Vy','Vx','T'];uls_cols=['Station x (m)','Nu','Mux','Muy','Vuy','Vux','Tu']
records={}
with patch('streamlit.file_uploader',side_effect=lambda label,*a,**k:[Upload()] if label==UPLOAD_LABEL else ([] if k.get('accept_multiple_files') else None)), patch.object(ap,'_girder_full_length_sls_stage_rows',wraps=ap._girder_full_length_sls_stage_rows) as adapter:
    run();assert adapter.call_count==0
    uls_before=deepcopy(at.session_state['beam_uls_loads_table'])
    assert not any(x.label.startswith(('I confirm','All tables')) for x in at.checkbox)
    assert not any('Source basis' in x.label for x in at.text_input)
    next(x for x in at.button if x.label=='Import SLS loads').click();run()
    assert adapter.call_count==0
    bank=deepcopy(at.session_state[sls.BANK_KEY])
    pd.testing.assert_frame_equal(canonical(bank,actions),canonical(expected,actions),check_dtype=False)
    choice=next(x for x in at.selectbox if x.label=='SLS girder');second=choice.options[1];choice.set_value(second);run()
    assert sls.active_member(at.session_state.filtered_state)==second
    buttons={b.key for b in at.button}
    (internal/'loads_seed.pkl').write_bytes(pickle.dumps({k:v for k,v in at.session_state.filtered_state.items() if k not in buttons}))
    next(x for x in at.button if x.label=='Open SLS analysis').click();run()
    assert at.session_state['_nav_active_workspace']=='Analysis' and at.session_state['_nav_analysis_subpage']=='SLS / Stress & Cracking'
    assert adapter.call_count>0
    assert any(x.label=='Service stage diagram load case' for x in at.selectbox)
    summary=pd.DataFrame(at.session_state['result_summary_beam_girder_sls_stage_summary_df'])
    assert summary['Girder'].eq(second).all() and summary['Source scope'].eq('Selected SLS girder and diagram case').all()
    count=adapter.call_count
    for workspace in ['Result Summary','Report / QA']:
        at.session_state['_nav_active_workspace']=workspace;run();assert adapter.call_count==count
    records['summary_report_read_only']=True
    at.session_state['_nav_active_workspace']='Loads';run();assert adapter.call_count==count
    pd.testing.assert_frame_equal(canonical(at.session_state[sls.BANK_KEY],actions),canonical(bank,actions),check_dtype=False)
    pd.testing.assert_frame_equal(canonical(at.session_state['beam_uls_loads_table'],uls_cols),canonical(uls_before,uls_cols),check_dtype=False)
    records['uls_vectors_and_notes_unchanged']=True
    restored={};apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(at.session_state.filtered_state))),restored)
    assert sls.active_member(restored)==second
    pd.testing.assert_frame_equal(canonical(restored[sls.BANK_KEY],actions),canonical(bank,actions),check_dtype=False)
    records['json_member_selection_and_all_rows_preserved']=True
    bases=ap.build_girder_service_stress_basis_options(restored['section_geometry'],restored['section_parameters'],member_type='beam_girder')
    all_adapter_rows=0
    with patch.object(ap.st,'session_state',restored):
        for member in sls.members(bank):
            source=bank.loc[bank.Girder==member].copy();all_adapter_rows+=len(source)
            df=ap._girder_full_length_sls_stage_rows(stage_label='Service stage',load_rows=source.to_dict('records'),basis_options=bases,basis_names=list(bases.bases),span_length_m=20)
            mapped=df.rename(columns={'N (kN)':'N','Mx (kN-m)':'Mx'})
            pd.testing.assert_frame_equal(canonical(mapped,actions[:3])[['Case Name','Station x (m)','N','Mx']],canonical(source,actions[:3])[['Case Name','Station x (m)','N','Mx']],check_dtype=False)
            assert df['Auto Mx (kN-m)'].eq(0).all() and df['Auto Vy (kN)'].eq(0).all() and df['Auto load w (kN/m)'].eq(0).all()
            split=ap._final_service_composite_split_rows(df,bases)
            if not split.empty:assert split['Locked-in Mx (kN-m)'].eq(0).all()
    assert all_adapter_rows==240
    records.update(status='PASS',native_xlsx_rows=240,girders=2,source_vectors_exact=True,production_adapter_rows=all_adapter_rows,
        automatic_dead_load_added=0,loads_workspace_solver_runs=0,confirmation_checkboxes_required=0,streamlit_exceptions=0,
        source_scope='Selected SLS girder and diagram case; not a collection design approval',
        qa_inputs='Hypothetical reinforcement input for software QA only')
out=ROOT/'qa/evidence/igird_slsimport23';out.mkdir(exist_ok=True,parents=True);(out/'app_checks.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
