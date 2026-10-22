"""Automatic project-input review without inventing local loads or exemptions."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_punching76 as automatic, slab_punching64 as punching
from concrete_pmm_pro.analysis import slab_top65 as top, slab_review68 as active
from concrete_pmm_pro.io import slab_shell_import as source
from concrete_pmm_pro.io.project_io import (apply_project_to_session_state, project_from_json,
    project_from_session_state, project_to_json)
from test_slab_punching64 import area
from test_slab_shell56 import model_state
from test_slab_top65_ui import clean

ROOT=Path(__file__).resolve().parents[1]


def state(method='equivalent_udl',areas=None):
    s=model_state()
    top.save_load_basis(s,{'method':method,'track_width_m':2.,'ballast_mm':300.})
    if areas is not None:
        s['project_metadata'][punching.CONFIG_KEY]={'version':1,'areas':areas}
        s[source.BANK_KEY].tables['thickness'][[f'Thick{i}' for i in range(1,5)]]=.35
        source._validate(s[source.BANK_KEY])
    return s


def review(s,**kwargs):
    basis=top.load_basis(s)
    return automatic.assessment(punching.config(s),basis,top.basis_status(s,basis),**kwargs)


def app(s):
    test=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
    for key,value in s.items():test.session_state[key]=deepcopy(value)
    test.session_state['_nav_active_workspace']='Analysis'
    test.session_state['_nav_analysis_subpage']='Slab Reinforcement'
    test.session_state['slab_shell55_shear64_group']='Punching shear'
    clean(test)
    return test


def test_matched_continuous_udl_is_identified_without_creating_areas_or_a_punching_pass():
    s=state();before=deepcopy(s['project_metadata']);r=review(s,check_status='PASS')
    assert r['route']=='continuous_udl' and r['area_count']==0
    assert r['track_width_m']==2 and r['ballast_mm']==300
    assert r['local_check_status']=='NOT CALCULATED'
    assert not r['code_exemption'] and not r['full_deck_acceptance']
    assert not r['footprint_inferred_from_shell_results']
    assert s['project_metadata']==before


@pytest.mark.parametrize('status',['SOURCE CHANGED','NOT RECORDED'])
def test_unmatched_basis_never_becomes_a_source_matched_automatic_model(status):
    r=automatic.assessment([],top.load_basis(state()),status)
    assert r['route']=='udl_basis_unmatched' and r['source_status']==status
    assert r['local_check_status']=='NOT CALCULATED' and not r['code_exemption']


def test_unspecified_import_cannot_infer_a_footprint_from_default_train_dimensions():
    r=review(state('imported'))
    assert r['route']=='footprint_missing' and r['area_count']==0
    assert not r['footprint_inferred_from_shell_results']


@pytest.mark.parametrize('method',['imported','equivalent_udl'])
def test_saved_physical_areas_take_priority_and_reuse_the_actual_calculated_status(method):
    s=state(method,[area(x=.5,y=.5,l=200,b=200,vu=10)])
    r=review(s,check_status='REVIEW')
    assert r['route']=='saved_areas' and r['area_count']==1
    assert r['local_check_status']=='REVIEW' and not r['code_exemption']


def test_automatic_route_survives_project_json_without_new_geometry_inputs():
    s=state();encoded=project_to_json(project_from_session_state(s));loaded={}
    apply_project_to_session_state(project_from_json(encoded),loaded)
    assert review(s)==review(loaded)
    assert punching.config(loaded)==[]


def test_actual_app_uses_recorded_udl_and_keeps_optional_area_table_folded():
    s=state();before=deepcopy(s['project_metadata'])
    with patch.object(active,'calculate',side_effect=AssertionError('View ran a solver')):
        test=app(s)
    assert any('existing CSiBridge shear forces' in x.value for x in test.info)
    assert any('No new load-area inputs' in x.value for x in test.info)
    assert any('local D/C below 1' in x.value for x in test.caption)
    editor=next(x for x in test.expander if x.label=='Punching load / reaction areas · optional')
    assert not editor.proto.expanded
    assert test.session_state['project_metadata']==before


def test_calculate_udl_requires_no_area_apply_and_oneway_navigation_reuses_results():
    s=state();original=s[source.BANK_KEY].tables['forces'].copy(deep=True)
    test=app(s)
    with patch.object(active,'calculate',wraps=active.calculate) as solver:
        test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
        assert solver.call_count==1
        result=test.session_state[active.RESULT_KEY]
        assert result['punching']['status']=='NOT CALCULATED' and result['punching']['areas']==[]
        assert result['status']!='PASS' and len(test.get('plotly_chart'))==1
        assert result['punching_screen78']['evaluated_records']>0
        test.button(key='slab_shell55_punch76_oneway').click();clean(test)
        assert test.session_state['slab_shell55_shear64_group']=='One-way shear'
        assert len(test.get('plotly_chart'))==1 and solver.call_count==1
    pd.testing.assert_frame_equal(original,test.session_state[source.BANK_KEY].tables['forces'],check_exact=True)


def test_changing_load_model_in_existing_calculation_form_updates_auto_review_immediately():
    test=app(state('imported'))
    assert any('existing CSiBridge shear forces' in x.value for x in test.info)
    test.selectbox(key='slab_shell55_top65_method').set_value('equivalent_udl')
    test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
    assert any('existing CSiBridge shear forces' in x.value for x in test.info)
    assert not any('Physical footprint not supplied' in x.value for x in test.info)
    assert any('SOURCE MATCHED' in x.value for x in test.caption)


def test_project_with_saved_area_calculates_without_retyping_or_pressing_apply():
    s=state(areas=[area(x=.5,y=.5,l=200,b=200,vu=10)])
    loaded={};apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(s))),loaded)
    test=app(loaded)
    assert punching.config({'project_metadata':test.session_state['project_metadata']})
    test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
    result=test.session_state[active.RESULT_KEY]['punching']
    assert len(result['rows'])==1 and np.isfinite(result['rows']['D/C']).all()
    assert result['rows'].iloc[0]['Vu (kN)']==10 and len(test.get('plotly_chart'))==2


def test_compact_report_records_the_same_snapshot_scope_without_running_mechanics():
    s=state();result=active.calculate(s);before=result['rows'].copy(deep=True)
    # A subsequently changed UI state cannot change a report of this result.
    top.save_load_basis(s,{'method':'imported'})
    with patch.object(active,'calculate',side_effect=AssertionError('report solved')), \
         patch.object(punching,'calculate',side_effect=AssertionError('report solved')):
        payload=active.report_zip(result)
    with ZipFile(BytesIO(payload)) as z:
        names=[n for n in z.namelist() if n.endswith('Punching_Automatic_Review.json')]
        assert len(names)==1
        r=json.loads(z.read(names[0]))
        assert r['route']=='actual_thickness_local_index' and r['source_status']=='SOURCE MATCHED'
        assert r['physical_perimeter_check_status']=='NOT CALCULATED' and not r['code_exemption']
        assert r['local_check_status']==result['punching_screen78']['status']
    pd.testing.assert_frame_equal(before,result['rows'],check_exact=True)
