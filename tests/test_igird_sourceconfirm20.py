"""Committed CSI correspondence survives automatic rereads and project load."""
from io import BytesIO
from pathlib import Path
from copy import deepcopy
import pandas as pd
from concrete_pmm_pro.io.girder_csi_import import prepare_csi_table,read_tables,source_info,split_member_tables
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY,activate_member
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_to_json,project_from_session_state
from concrete_pmm_pro.ui.girder_csi_import import _native_preview,_native_upload_already_stored,saved_source_readiness
from concrete_pmm_pro.ui.igird_member_results import member_inputs
from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed
FILE=Path(__file__).resolve().parents[1]/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
class Upload(BytesIO):
    def __init__(self,data,name):super().__init__(data);self.name=name

def imports():
    upload=Upload(FILE.read_bytes(),'native.xlsx')
    unverified,errors=_native_preview([upload]);assert not errors
    tables=read_tables(upload.getvalue(),upload.name)
    frames=[]
    for sheet,table in tables.items():
        if sheet!='Bridge Object Girder Forces':continue
        for group in split_member_tables(table,sheet_name=sheet):
            import hashlib
            parsed=prepare_csi_table(group.frame,sheet_name=sheet,
                source_name=upload.name+' ['+hashlib.sha256(upload.getvalue()).hexdigest()[:8]+']',
                source_mode='correspondence',concurrency_confirmed=True,
                evidence='User confirms simultaneous factored CSI correspondence vectors')
            frame=parsed.frame.copy();frame['Case Name']=group.name+' / '+frame['Case Name'];frame['Girder']=group.name
            frames.append(frame)
    return unverified,pd.concat(frames,ignore_index=True)

def test_same_native_upload_preserves_saved_contract_and_user_edits():
    preview,committed=imports();before=deepcopy(committed)
    assert _native_upload_already_stored(preview,committed)
    committed.loc[0,'Mux']=123. # Existing user edits are not an implicit reimport.
    committed.loc[0,'Active']=False
    assert _native_upload_already_stored(preview,committed)
    assert preview.Note.ne(committed.Note).all()
    assert before.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).all()

def test_different_file_or_incomplete_source_is_not_reused():
    preview,committed=imports()
    assert not _native_upload_already_stored(preview,committed.iloc[1:])
    assert not _native_upload_already_stored(preview,pd.DataFrame())
    changed=preview.copy();changed.loc[0,'Note']=changed.loc[0,'Note'].replace('native.xlsx','different.xlsx')
    assert not _native_upload_already_stored(changed,committed)
    changed=preview.copy();changed.loc[0,'Note']=''
    assert not _native_upload_already_stored(changed,committed)

def test_persisted_project_retains_proof_without_session_upload_flags():
    preview,committed=imports();state={}
    # Use the accepted input-only QA model; no calculation result persistence.
    model=Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()
    apply_project_to_session_state(project_from_json(model),state)
    state[BANK_KEY]=committed;activate_member(state,committed.iloc[0].Girder)
    saved=project_to_json(project_from_session_state(state));restored={}
    apply_project_to_session_state(project_from_json(saved),restored)
    assert _native_upload_already_stored(preview,pd.DataFrame(restored[BANK_KEY]))
    inputs=member_inputs(restored);assert len(inputs)==2
    assert sum(len(rows) for rows in inputs.values())==640
    assert all(rows.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).all() for rows in inputs.values())

def test_display_reports_saved_eligibility_not_the_preview():
    preview,committed=imports()
    good=saved_source_readiness(committed);bad=saved_source_readiness(preview)
    assert good['Concurrent rows ready for V+T'].sum()==640 and good['Source-blocked rows'].sum()==0
    assert bad['Concurrent rows ready for V+T'].sum()==0 and bad['Source-blocked rows'].sum()==640

def test_verified_native_rows_reach_real_vt_solver():
    from test_igird_uls7_concurrent_vt import ready_state
    from test_igird_uls6_torsion_general_procedure import _route
    from concrete_pmm_pro.ui.igird_combined_vt import check_dataframe
    from concrete_pmm_pro.analysis.girder_axial_convention import SETTINGS_KEY,CSI_TENSION_POSITIVE
    _,committed=imports()
    state=ready_state();state[SETTINGS_KEY]={'input_sign':CSI_TENSION_POSITIVE}
    # Native evidence plus accepted hypothetical reinforcement. This verifies
    # execution of the real engine, not acceptance of the user's bridge.
    rows=committed.loc[committed['Station x (m)'].eq(10.)].copy()
    result=check_dataframe(state,rows,strength_route=_route())
    assert len(result)==len(rows)
    assert not result.Status.eq('SOURCE BLOCKED').any()
    assert result['Transverse D/C value'].notna().any()
    assert result['Source coupling'].eq('CONCURRENT — DECLARED').all()
