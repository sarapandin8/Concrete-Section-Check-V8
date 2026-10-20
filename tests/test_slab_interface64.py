"""Read-only member ownership, numeric minimum checks and stale-result guards."""
from copy import deepcopy
from unittest.mock import patch
import pandas as pd
import pytest
from concrete_pmm_pro.ui import analysis_page as ap,igird_flexure_workspace as fw,igird_member_results as members
from concrete_pmm_pro.ui.slab_interface64 import linked_results
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY,ACTIVE_KEY
from test_igird_membercharts3 import model


def stored(state,name,*,strength=.4,minimum=.7,status='PASS'):
    rows=members.member_inputs(state)[name]
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    settings=ap._igird_interface_shear_settings_from_state(state)
    key=ap._igird_interface_shear_hash(state,ap._igird_interface_source_dataframe(rows),settings=settings,strength_route=route)
    frame=pd.DataFrame({'Strength D/C':[strength], 'Minimum Avf D/C':[minimum],'Status':[status]})
    state.setdefault(fw.CACHE_KEY,{})[name]={'version':fw.VERSION,'hashes':{'interface':key},
        'bundle':{'interface':{'result_version':ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION,
            'interface_status':'PASS','interface_shear_df':frame}}}


def test_reads_all_owned_current_rows_without_running_or_mutating_a_solver():
    state=model()
    for name in members.member_inputs(state):stored(state,name)
    before=deepcopy(state)
    with patch.object(ap,'_igird_interface_shear_dataframe',side_effect=AssertionError('solver ran')), \
            patch.object(members,'calculate_member',side_effect=AssertionError('flexure ran')):
        result=linked_results(state)
    assert result['status']=='PASS' and result['members']==2
    assert result['rows']['Max D/C'].eq(.7).all()
    pd.testing.assert_frame_equal(state[BANK_KEY],before[BANK_KEY])
    for n in state[fw.CACHE_KEY]:
        pd.testing.assert_frame_equal(state[fw.CACHE_KEY][n]['bundle']['interface']['interface_shear_df'],
            before[fw.CACHE_KEY][n]['bundle']['interface']['interface_shear_df'])


@pytest.mark.parametrize('status,minimum,expected',[('FAIL',.7,'FAIL'),('REVIEW',.7,'REVIEW'),('PASS',1.3,'FAIL'),('PASS',float('nan'),'REVIEW')])
def test_row_status_and_minimum_ratio_override_cached_green_headline(status,minimum,expected):
    state=model();name=next(iter(members.member_inputs(state)))
    stored(state,name,status=status,minimum=minimum)
    table=linked_results(state)['rows'].set_index('Girder')
    assert table.loc[name,'Interface status']==expected
    assert table.iloc[1]['Interface status']=='NOT CALCULATED'


@pytest.mark.parametrize('changed',['load','section','settings','version'])
def test_input_changes_and_wrong_versions_cannot_reuse_current_pass(changed):
    state=model();name=next(iter(members.member_inputs(state)));stored(state,name)
    if changed=='load':state[BANK_KEY].loc[0,'Vuy']+=10
    elif changed=='section':state['section_parameters']['Tslab_mm']+=10
    elif changed=='settings':
        settings=ap._igird_interface_shear_settings_from_state(state)
        state['beam_girder_interface_shear_settings']={**settings,'connectors_cross_and_anchored':not settings['connectors_cross_and_anchored']}
    else:state[fw.CACHE_KEY][name]['bundle']['interface']['result_version']='older'
    row=linked_results(state)['rows'].set_index('Girder').loc[name]
    assert row['Interface status']=='STALE' and pd.isna(row['Max D/C'])


def test_active_edited_loads_override_bank_and_legacy_cache_stays_owned():
    state=model();name,rows=next(iter(members.member_inputs(state).items()));stored(state,name)
    state[ACTIVE_KEY]=name;state['beam_uls_loads_table']=rows.copy()
    assert linked_results(state)['rows'].iloc[0]['Interface status']=='PASS'
    state['beam_uls_loads_table'].loc[rows.index[0],'Vuy']+=10
    assert linked_results(state)['rows'].iloc[0]['Interface status']=='STALE'
    # A valid legacy result is scoped to the active member only.
    state['beam_uls_loads_table']=rows.copy()
    saved=state.pop(fw.CACHE_KEY)[name]
    payload=saved['bundle']['interface'];payload['input_hash']=saved['hashes']['interface']
    state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]={ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME:payload}
    result=linked_results(state)
    assert result['rows'].iloc[0]['Interface status']=='PASS'
    assert result['rows'].iloc[1]['Interface status']=='NOT CALCULATED'


def test_missing_numeric_minimum_and_missing_member_never_imply_bridge_wide_pass():
    state=model();name=next(iter(members.member_inputs(state)));stored(state,name)
    del state[fw.CACHE_KEY][name]['bundle']['interface']['interface_shear_df']['Minimum Avf D/C']
    r=linked_results(state)
    assert r['status']=='REVIEW' and r['rows'].iloc[0]['Interface status']=='REVIEW'
    empty=linked_results({})
    assert empty['status']=='REVIEW' and empty['members']==0
