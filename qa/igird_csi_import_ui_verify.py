"""Production Streamlit UI verification; upload bytes supplied through a controlled fixture."""
import io,json,os,sys,time
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
REPO=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
OUT=Path(os.environ.get('CSP_QA_OUT',REPO/'qa/evidence/igird_csiimport1'))
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(REPO))
from concrete_pmm_pro.ui import analysis_page as ap
class Uploaded(io.BytesIO):
    name='CSiBridge_ULS_Girder_Max_Min.xlsx'
uploaded=Uploaded((REPO/'qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx').read_bytes())
def upload(label,*args,**kwargs):
    return uploaded if label=='Upload CSiBridge girder forces' else None
def assert_ok(at):
    assert not at.exception,[e.message for e in at.exception]
def by_label(elements,label):
    return next(e for e in elements if e.label==label)
with patch('streamlit.file_uploader',side_effect=upload):
    at=AppTest.from_file(str(REPO/'qa/igird_csi_import_runtime.py')).run(timeout=30)
    assert_ok(at)
    sheet=by_label(at.selectbox,'CSiBridge worksheet / girder')
    assert sheet.value=='Left Exterior Girder'
    assert any('80 rows · Max 40 · Min 40' in e.value for e in at.caption)
    sheet.select('Entire Bridge Section').run(timeout=30)
    assert_ok(at)
    assert by_label(at.button,'Replace current rows').disabled
    by_label(at.selectbox,'CSiBridge worksheet / girder').select('Left Exterior Girder').run(timeout=30)
    by_label(at.button,'Replace current rows').click().run(timeout=30)
    assert_ok(at)
    assert len(at.session_state['beam_uls_loads_table'])==80
    assert by_label(at.button,'Append imported rows').disabled
    # Legacy mode continues to offer its prior native app-column import.
    by_label(at.radio,'Import table format').set_value('App columns (legacy)').run(timeout=30)
    assert_ok(at)
    assert any('Bridge Beam/Girder ULS station-load import' in e.value for e in at.markdown)
    by_label(at.radio,'Import table format').set_value('CSiBridge girder forces').run(timeout=30)
    assert_ok(at)
    by_label(at.radio,'Workspace').set_value('Analysis').run(timeout=30)
    assert_ok(at)
    by_label(at.radio,'Flexure stage').set_value('Final — Composite').run(timeout=30)
    assert_ok(at)
    # Streamlit tabs render both stage bodies. Click the actual Final button.
    start=time.perf_counter()
    by_label(at.button,'Calculate Final Composite Flexure').click().run(timeout=60)
    elapsed=time.perf_counter()-start
    assert_ok(at)
    cache=at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]
    entry=cache['Flexure — Final Composite']
    frame=entry['flexure_preview_df']
    assert len(frame)==80 and frame['Case'].nunique()==4
    assert 'PASS' not in set(frame['Status'])
    assert entry['negative_mux_rows_excluded']==0
    assert entry['negative_mux_rows_screened']==1
    dashboard=ap._igird_composite_flexure_dashboard_state(at.session_state.filtered_state)
    assert dashboard[0]=='FAIL' and 'current' in dashboard[1],dashboard
    assert any('simultaneous Mu/Nu/Vu/Tu is not established by this table' in e.value for e in at.warning)
    assert any('Strand families — actual stress and force used' in e.value for e in at.markdown)
    records=[]
    for _,r in frame.iterrows():
        records.append({k:(None if not isinstance(r.get(k),(str,list,dict)) and __import__('pandas').isna(r.get(k)) else r.get(k))
            for k in ['Case','Station x (m)','Source ItemType','Demand kN-m','Nu input kN','Nu kN','φMn kN-m','Status','Numerical status','Source coupling']})
    (OUT/'final_flexure_80rows.json').write_text(json.dumps(records,indent=2,allow_nan=True))
    frame.drop(columns=['Strand development trace','Ordinary bar development trace'],errors='ignore').to_csv(OUT/'final_flexure_80rows.csv',index=False)
    result={'method':'Streamlit AppTest with fixture upload bytes; no browser rendering claim',
        'selected_girder':'Left Exterior Girder','source_rows':80,'Max':40,'Min':40,
        'wrong_scope_blocked':True,'replace_applied':True,'duplicate_append_blocked':True,
        'legacy_mode_renders':True,'final_rows':len(frame),'negative_rows_screened':1,
        'final_flexure_button_seconds':elapsed,'status_counts':frame['Status'].value_counts().to_dict(),
        'streamlit_exceptions':0,'stored_trace_visible':True,
        'dashboard_reads_current_result':True,
        'browser_verification':'BLOCKED: local Chrome executables are truncated and fail before launching; network download timed out.'}
    (OUT/'ui_result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
