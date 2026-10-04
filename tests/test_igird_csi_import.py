"""Native source fidelity, concurrency gates, and real 80-row flexure regression."""
from pathlib import Path
import pandas as pd
import pytest

from concrete_pmm_pro.io.girder_csi_import import (
    APP_COLUMNS, CSI_COLUMNS, FORCE_MAP, append_errors, apply_source_gate,
    girder_ranking, prepare_csi_table, read_tables, source_info,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json,
)
from concrete_pmm_pro.analysis.girder_axial_convention import SETTINGS_KEY, CSI_TENSION_POSITIVE
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _route

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def tables():
    file=ROOT/'qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx'
    return read_tables(file.read_bytes(),file.name)

@pytest.fixture(scope='module')
def left(tables):
    return prepare_csi_table(tables['Left Exterior Girder'],sheet_name='Left Exterior Girder')

def test_actual_workbook_selects_individual_critical_flexure_member(tables):
    assert len(tables)==19
    ranking=girder_ranking(tables)
    assert len(ranking)==6
    assert ranking.iloc[0]['Girder']=='Left Exterior Girder'
    assert ranking.iloc[0]['|M3| kN-m']==pytest.approx(7184.6936)
    assert ranking.loc[ranking['|V2| kN'].idxmax(),'Girder']=='Interior Girder 4'
    assert ranking.loc[ranking['|T| kN-m'].idxmax(),'Girder']=='Interior Girder 2'
    assert all(ranking['Rows']==80)

def test_all_source_rows_components_signs_and_repeated_stations_are_exact(tables,left):
    raw=tables['Left Exterior Girder'].iloc[1:] # skip original units row
    assert not left.errors and left.counts=={'Max':40,'Min':40}
    assert list(left.frame.columns)==APP_COLUMNS and len(left.frame)==len(raw)==80
    assert left.frame['Station x (m)'].nunique()==21
    assert len(left.frame.loc[left.frame['Station x (m)'].eq(1)])==4
    assert not left.frame.duplicated(['Case Name','Station x (m)']).any()
    assert left.frame['Case Name'].nunique()==4
    for source,target in FORCE_MAP.items():
        assert left.frame[target].tolist()==raw[source].astype(float).tolist()
    assert left.frame['Station x (m)'].tolist()==raw['Girder Distance'].astype(float).tolist()
    assert [source_info(row)['row'] for _,row in left.frame.iterrows()]==list(range(3,83))
    assert left.frame.iloc[0]['Nu']==575.159 and left.frame.iloc[1]['Nu']==-918.561

def table_with_units(*,length='m',force='KN',moment='KN-m',values=None):
    return pd.DataFrame([[length,length,'',force,force,force,moment,moment,moment],
        [10,2,'Min',*(values or [1,2,3,4,5,6])]],columns=CSI_COLUMNS)

@pytest.mark.parametrize('length,force,moment,x,p,m',[
    ('mm','N','N-mm',.002,.001,6e-6),('m','KN','KN-m',2,1,6),
    ('ft','kip','kip-ft',.6096,4.4482216152605,6*1.3558179483314),
    ('m','tonf','tonf-m',2,9.80665,6*9.80665),
])
def test_declared_units_are_normalized_and_girder_distance_preferred(length,force,moment,x,p,m):
    r=prepare_csi_table(table_with_units(length=length,force=force,moment=moment),sheet_name='G')
    assert not r.errors
    row=r.frame.iloc[0]
    assert row['Station x (m)']==pytest.approx(x)
    assert row['Nu']==pytest.approx(p) and row['Mux']==pytest.approx(m)
    assert source_info(row)['layout_distance']=='10'

@pytest.mark.parametrize('bad', ['',None,float('nan'),float('inf'),'not a force',True])
def test_invalid_component_is_never_filled_with_zero_or_silently_dropped(bad):
    table=table_with_units();table.loc[1,'V2']=bad
    r=prepare_csi_table(table,sheet_name='G')
    assert r.errors and r.frame.empty

def test_unknown_units_and_missing_identity_are_validation_errors():
    assert prepare_csi_table(table_with_units(force='kg'),sheet_name='G').errors
    assert prepare_csi_table(table_with_units(),sheet_name='G',case_name=' ').errors
    table=table_with_units();table.loc[1,'ItemType']='abs maximum'
    assert prepare_csi_table(table,sheet_name='G').errors

def test_native_csv_and_legacy_headers_are_read_without_forcing_first_sheet(left):
    native=table_with_units().to_csv(index=False).encode('utf-8-sig')
    assert not prepare_csi_table(read_tables(native,'girder.csv')['CSV'],sheet_name='Left Exterior Girder').errors
    old=left.frame.iloc[:2].to_csv(index=False).encode('utf-8')
    assert list(read_tables(old,'app.csv')['CSV'].columns)==APP_COLUMNS

def test_append_rejects_duplicate_paths_and_mixed_axial_conventions(left):
    current=left.frame.copy(deep=True)
    assert append_errors(current,left.frame,current_is_csi=True)
    distinct=left.frame.copy(deep=True);distinct['Case Name']='Other '+distinct['Case Name']
    assert not append_errors(current,distinct,current_is_csi=True)
    assert append_errors(current,distinct,current_is_csi=False)
    current['Nu']=0
    assert not append_errors(current,distinct,current_is_csi=False)

def test_source_gate_retains_failure_and_numerical_evidence_without_changing_inputs(left):
    source=left.frame.iloc[:2].copy(deep=True);before=source.copy(deep=True)
    result=pd.DataFrame([{'Case':r['Case Name'],'Status':status,'Strength status':'PASS',
        'Stress status':'PASS','Transverse status':'PASS','Longitudinal status':'PASS','D/C value':dc,'Notes':'Calculated'}
        for (_,r),status,dc in zip(source.iterrows(),['PASS','FAIL'],[.5,1.2])])
    gated=apply_source_gate(result,source)
    assert gated['Status'].tolist()==['REVIEW','FAIL']
    assert gated['D/C value'].tolist()==[.5,1.2]
    assert all(gated['Strength status']=='REVIEW')
    assert all(gated['Source coupling']=='ENVELOPE — REVIEW')
    pd.testing.assert_frame_equal(source,before)
    pd.testing.assert_frame_equal(apply_source_gate(result,source.assign(Note='Legacy')),result)

def test_json_roundtrip_keeps_all_rows_and_source_metadata(left):
    state=ready_state();state['beam_uls_loads_table']=left.frame.copy(deep=True)
    state[SETTINGS_KEY]={'input_sign':CSI_TENSION_POSITIVE}
    project=project_from_session_state(state)
    restored={}
    apply_project_to_session_state(project_from_json(project_to_json(project)),restored)
    active=ap._active_beam_uls_demand_dataframe_from_session(restored)
    for column in ['Mux','Vuy','Tu','Muy','Vux','Nu','Station x (m)','Note','Case Name']:
        assert active[column].tolist()==left.frame[column].tolist()

def test_real_left_max_min_flexure_checks_every_row_and_retains_nu(left):
    state={}
    apply_project_to_session_state(project_from_json((ROOT/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text()),state)
    source=left.frame.copy(deep=True);before=source.copy(deep=True)
    _,composite,_=ap._beam_uls_final_composite_preparation(state)
    frame,_=ap._beam_uls_flexure_preview_dataframe(composite,source,strength_route=_route(),
        prestress_force_stage='final',full_span_capacity=True,use_aashto_solver=True,apply_girder_development=True)
    assert len(frame)==80 and frame['Case'].nunique()==4
    expected=source.sort_values(['Case Name','Station x (m)'],kind='stable')
    assert frame['Nu input kN'].tolist()==expected['Nu'].tolist()
    assert frame['Nu kN'].tolist()==(-expected['Nu']).tolist()
    assert frame['Demand kN-m'].tolist()==expected['Mux'].tolist()
    assert set(frame['Status'])<= {'REVIEW','FAIL'}
    assert len(frame.loc[frame['Station x (m)'].isin([0,20])])==4
    valid=frame.loc[frame['Force residual N'].notna()]
    assert (valid['φPn kN']-valid['Nu kN']).abs().max()<.000021
    assert all(frame['Source coupling']=='ENVELOPE — REVIEW')
    pd.testing.assert_frame_equal(source,before)

@pytest.mark.parametrize('producer', [ap._beam_uls_shear_check_dataframe,ap._beam_uls_torsion_check_dataframe,ap._beam_uls_combined_vt_check_dataframe])
def test_real_strength_producers_apply_source_gate_to_original_and_supplemental_rows(left,producer):
    state=ready_state();state[SETTINGS_KEY]={'input_sign':CSI_TENSION_POSITIVE}
    source=left.frame.iloc[2:4].copy(deep=True) # Max and Min, x=1
    frame=producer(state,source,strength_route=_route())
    assert not frame.empty and set(source['Case Name'])<=set(frame['Case'])
    assert all(frame['Source coupling']=='ENVELOPE — REVIEW')
    assert 'PASS' not in set(frame['Status'])

def test_contract_change_invalidates_cached_acceptance(left,monkeypatch):
    state=ready_state();state[SETTINGS_KEY]={'input_sign':CSI_TENSION_POSITIVE}
    first=ap._beam_uls_cache_input_hash(state,left.frame,strength_route=_route())
    monkeypatch.setattr(ap,'GIRDER_CSI_IMPORT_VERSION','changed-source-contract')
    assert first!=ap._beam_uls_cache_input_hash(state,left.frame,strength_route=_route())

def test_downloadable_template_has_native_headers_units_and_blank_force_inputs():
    file=ROOT/'assets/templates/Bridge_Beam_ULS_CSiBridge_Template.xlsx'
    tables=read_tables(file.read_bytes(),file.name)
    assert 'Left Exterior Girder' in tables
    first=tables['Left Exterior Girder']
    assert list(first.columns[:9])==CSI_COLUMNS
    assert first.iloc[0]['P']=='KN' and first.iloc[0]['M3']=='KN-m'
    result=prepare_csi_table(first,sheet_name='Left Exterior Girder')
    assert result.errors and result.frame.empty # Blank forces are not plausible zeros.
