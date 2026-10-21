"""Local-transfer scope, verified material credit and read-only review evidence."""
from copy import deepcopy
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_aashto63 as code, slab_review68 as review
from concrete_pmm_pro.analysis import slab_design66 as design
from concrete_pmm_pro.analysis.slab_aashto63_sections import in_support
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json, project_from_json, apply_project_to_session_state
from concrete_pmm_pro.reporting.slab_top65 import summary_rows
from concrete_pmm_pro.analysis import slab_top65 as top
from test_slab_aashto63 import vector
from test_slab_connections59 import connected_state
from test_slab_shell56 import steel


def test_general_procedure_uses_verified_aggregate_hand_equation_but_simplified_unchanged():
    actions=vector(Nx=120.,Mx=20.,Vx=70.)
    default=code.section_checks(actions,steel())
    confirmed=code.section_checks(actions,steel(),aggregate_mm=20.)
    a=default.iloc[0];b=confirmed.iloc[0]
    assert b['Longitudinal procedure'].endswith('general')
    sx=b['Longitudinal sx (mm)']
    sxe=np.clip(sx*1.38/(20/25.4+.63),304.8,2032.)
    eps=b['Longitudinal strain used']
    beta=4.8/(1+750*eps)*51/(39+sxe/25.4)
    assert b['Longitudinal sxe (mm)']==pytest.approx(sxe)
    assert b['Longitudinal beta']==pytest.approx(beta)
    assert b['Longitudinal shear D/C'] < a['Longitudinal shear D/C']
    assert b['Transverse procedure'].endswith('simplified')
    assert b['Transverse shear D/C']==a['Transverse shear D/C']
    assert b['Transverse tie D/C']==a['Transverse tie D/C']


@pytest.mark.parametrize('invalid',[None,True,-1.,101.,float('nan'),float('inf'),'unknown'])
def test_unverified_value_earns_no_credit_and_invalid_verified_value_blocks(invalid):
    assert code.aggregate_from_parameters({'shear_max_aggregate_mm':invalid})==0.
    with pytest.raises(ValueError):
        code.aggregate_from_parameters({'shear_max_aggregate_mm':invalid,'shear_aggregate_confirmed':True})


def test_finite_reaction_patch_reviews_both_directions_without_new_source_exclusions():
    state=connected_state()
    original=code.calculate(state)
    # A wider physical contact puts retained y=1 corners inside it; forces
    # and the unchanged source CL masks do not determine this geometry scope.
    state['section_parameters']['B1_mm']=2400.
    result=code.calculate(state)
    pd.testing.assert_frame_equal(original['rows'][[INCLUDED,*review.ACTIONS]],result['rows'][[INCLUDED,*review.ACTIONS]])
    local=in_support(result['rows'][['X (m)','Y (m)']].to_numpy(),result['supports'])&result['rows'][INCLUDED]
    assert local.any()
    for direction in ('Longitudinal','Transverse'):
        assert result['rows'].loc[local,direction+' local support region'].all()
        for kind in ('shear','tie'):
            assert result['rows'].loc[local,direction+' '+kind+' D/C'].isna().all()
            assert result['rows'].loc[local,direction+' '+kind+' status'].eq('REVIEW').all()
            assert result['rows'].loc[local,direction+' '+kind+' native D/C'].notna().all()
    assert result['rows'].loc[local,'Longitudinal N–M D/C'].notna().all()
    assert result['status']=='REVIEW REQUIRED'


def test_audit_does_not_apply_max_moment_limit_or_dv_shift_from_udl_metadata():
    state=connected_state()
    state['section_parameters']['B1_mm']=2400.
    review.save_load_basis(state,{'method':'equivalent_udl','ballast_mm':300.,'track_width_m':2.,'nominal_pressure_kpa':64.22})
    result=review.calculate(state)
    audit=result['code_review']
    unresolved=audit['eligibility'].loc[lambda f:f.Article.isin(['5.7.3.5','5.7.3.2'])]
    assert unresolved.Assessment.eq('NOT ESTABLISHED').all()
    assert not unresolved.Applied.any()
    assert audit['exceptions_applied']==0 and not audit['full_deck_acceptance']
    assert not audit['source_actions_changed'] and audit['new_source_exclusions']==0
    local=audit['governing_vectors'].loc[lambda f:f.Region.eq('Local transfer')]
    assert len(local) and local['Review status'].eq('REVIEW').all()
    ties=local.loc[local.Check.eq('tie')]
    expected=ties[['M term (kN/m)','N term (kN/m)','V term (kN/m)']].sum(axis=1).clip(lower=0.)
    np.testing.assert_allclose(expected,ties['Tie demand (kN/m)'])
    pd.testing.assert_frame_equal(result['summary'],result['design66_result']['summary'])
    assert not audit['section_cuts'].get('Status',pd.Series(dtype=str)).eq('PASS').any()


def test_review_report_is_read_only_and_project_has_no_persisted_review_results():
    state=connected_state()
    result=review.calculate(state)
    state[review.RESULT_KEY]=result
    assert review.current(state) is result
    before=result['rows'].copy(deep=True)
    with patch.object(review,'calculate',side_effect=AssertionError('rerun')),patch.object(design,'calculate',side_effect=AssertionError('rerun')):
        payload=review.report_zip(result)
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
        assert 'Review68/Selected_Section_Cuts.csv' in archive.namelist()
        scope=json.loads(archive.read('Review68/Scope.json'))
        assert scope['exceptions_applied']==0 and not scope['full_deck_acceptance']
    pd.testing.assert_frame_equal(before,result['rows'])
    encoded=project_to_json(project_from_session_state(state))
    assert review.RESULT_KEY not in encoded and 'code_review' not in encoded
    restored={review.RESULT_KEY:result}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert review.RESULT_KEY not in restored
    state['section_parameters']['deck_long_rebar_top_spacing_mm']=175.
    assert review.current(state) is None


def test_global_summary_and_report_keep_local_indices_without_replacing_applied_results():
    state=connected_state()
    state['section_parameters']['B1_mm']=2400.
    result=review.calculate(state)
    state[top.RESULT_KEY]=result['top65_result']
    with patch.object(review,'calculate',side_effect=AssertionError('rerun')):
        rows=summary_rows(state)
        local=[r for r in rows if r['Check'].startswith('Local transfer index')]
        assert len(local)==4 and all(r['Status']=='REVIEW' for r in local)
        assert all(r['D/C / Util.'] is not None for r in local)
        payload=review.report_zip(result)
    with ZipFile(BytesIO(payload)) as archive:
        assert 'Current/Local_Transfer_Review.csv' in archive.namelist()
        assert 'Review68/Local_and_Sectional_Governing_Vectors.csv' in archive.namelist()
    pd.testing.assert_frame_equal(result['summary'],result['top65_result']['summary'])
