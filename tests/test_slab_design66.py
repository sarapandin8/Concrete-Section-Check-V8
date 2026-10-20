"""Candidate spacing is a proposal; actual checks and source vectors stay intact."""
from copy import deepcopy
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_design66 as design, slab_top65 as top, slab_aashto63 as code
from concrete_pmm_pro.analysis.slab_shell56 import SlabSteel
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
from test_slab_shell56 import model_state


def example(v=0., m=0., *, diameter=16., spacing=300., incomplete=False):
    db=np.full(4,diameter);s=np.full(4,spacing)
    steel=SlabSteel(np.pi*db**2/4*1000/s,np.full(4,390.),np.array([64.,64.,48.,48.]),db,s,35.)
    raw=pd.DataFrame({'Thickness (mm)':[350.,350.],'Nx':[0.,0.],'Ny':[0.,0.],
        'Nxy':[0.,0.],'Mx':[m,-m/2],'My':[0.,0.],'Mxy':[0.,0.],'Vx':[v,-v/2],'Vy':[0.,0.],
        'X (m)':[1.,2.],'Y (m)':[.5,.5],'OutputCase':['case A','case B'],
        'StepType':['Max','Min'],'AreaElem':['E','E'],'Joint':['1','2'],INCLUDED:[True,True]})
    checked=code.section_checks(raw,steel)
    for direction,*_ in code.AXES:raw[direction+' local support region']=False
    rows=pd.concat((raw,checked),axis=1)
    parameters={'shear_max_aggregate_mm':20.,'shear_aggregate_confirmed':True}
    result={'rows':rows,'steel':steel,'support_faces':pd.DataFrame(),'incomplete':incomplete,
        'summary':code._summary(rows),'clear_spacing':top.clear_spacing(steel,parameters)}
    result['mat_envelopes']=top.bending_envelopes(result,result['clear_spacing'])
    return result,parameters


def test_proposal_rechecks_changed_tension_mat_and_does_not_fix_concrete_shear_by_fiat():
    actual,p=example(v=300.)
    before=actual['rows'].copy(deep=True)
    proposal=design.propose(actual,p)
    assert proposal['changed'] and proposal['known_rebar_checks_satisfied']
    assert proposal['concrete_shear_has_failures']
    assert proposal['trials']>=2  # at M=0 the smaller physical mat can switch
    assert proposal['native_rechecked']==len(before)
    assert not proposal['applied_to_project'] and not proposal['full_deck_acceptance']
    old=actual['summary'].set_index('Check')
    new=proposal['summary'].set_index('Check')
    assert new.loc['Shear · longitudinal','Max D/C']==pytest.approx(old.loc['Shear · longitudinal','Max D/C'])
    for s in proposal['spacing']:
        assert s<=300. and s>=60.
    pd.testing.assert_frame_equal(actual['rows'],before)
    np.testing.assert_array_equal(actual['steel'].spacing,[300.]*4)


def test_already_sufficient_layout_reuses_current_checks_without_an_extra_solver():
    actual,p=example(v=10.,m=1.)
    with patch.object(code,'section_checks',side_effect=AssertionError('unnecessary section rerun')):
        proposal=design.propose(actual,p)
    assert not proposal['changed'] and proposal['trials']==0
    assert proposal['known_rebar_checks_satisfied']


def test_bar_limit_failure_is_reported_and_unknown_aggregate_never_becomes_pass():
    actual,p=example(v=2000.,diameter=6.,spacing=300.)
    proposal=design.propose(actual,p)
    assert not proposal['known_rebar_checks_satisfied']
    assert proposal['status']=='NO FEASIBLE SPACING FOUND'
    assert proposal['trials']<=design.MAX_TRIALS
    assert np.min(proposal['spacing'])>=50.
    actual,p=example(v=10.)
    actual['clear_spacing']=top.clear_spacing(actual['steel'],{})
    assert design.propose(actual,{})['status']=='REVIEW'


def test_candidate_governor_is_a_single_actual_concurrent_row_and_can_be_rechecked():
    actual,p=example(v=300.,m=60.)
    proposal=design.propose(actual,p)
    source=actual['rows'].set_index(['AreaElem','Joint','OutputCase','StepType'])
    steel=design.with_spacing(actual['steel'],proposal['spacing'])
    for _,r in proposal['governors'].iterrows():
        original=source.loc[(r.AreaElem,r.Joint,r.OutputCase,r.StepType)]
        components=['Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']
        np.testing.assert_array_equal(r[components].to_numpy(float),original[components].to_numpy(float))
        column=code.VIEWS[r.Check][0]
        rechecked=code.section_checks(pd.DataFrame([r]),steel).iloc[0]
        assert r['D/C']==pytest.approx(rechecked[column],rel=1e-12)


def test_local_support_ties_remain_review_and_incomplete_coverage_is_not_filled():
    actual,p=example(v=300.)
    actual['rows'].loc[0,'Longitudinal local support region']=True
    evaluated=design.evaluate(actual,actual['steel'],p)
    summary=evaluated['summary'].set_index('Check')
    assert summary.loc['Flexural shear tie · longitudinal','Status']=='REVIEW'
    actual['incomplete']=True
    evaluated=design.evaluate(actual,actual['steel'],p)
    assert not evaluated['summary'].Status.eq('PASS').any()


def test_load_metadata_reuses_proposal_and_input_changes_invalidate_it():
    state=model_state()
    first=design.calculate(state)
    state[design.RESULT_KEY]=first
    state[top.RESULT_KEY]=first['top65_result']
    assert design.current(state) is first
    top.save_load_basis(state,{'method':'equivalent_udl','ballast_mm':450.})
    assert design.current(state) is None
    with patch.object(design,'propose',side_effect=AssertionError('metadata reran designer')):
        second=design.calculate(state,reuse=first['shear_result'])
    assert second['proposal_reused']
    pd.testing.assert_frame_equal(first['rows'],second['rows'])
    state['section_parameters']['deck_long_rebar_top_spacing_mm']=200.
    assert design.proposal_fingerprint(state)!=first['proposal_fingerprint']


def test_report_keeps_current_and_proposed_checks_separate_and_project_saves_inputs_only():
    state=model_state();result=design.calculate(state)
    state[design.RESULT_KEY]=result
    with patch.object(design,'calculate',side_effect=AssertionError('report reran solver')):
        payload=design.report_zip(result)
    with ZipFile(BytesIO(payload)) as z:
        assert z.testzip() is None
        assert 'Current/Check_Summary.csv' in z.namelist()
        fields=pd.read_csv(BytesIO(z.read('Proposal/Four_Mats.csv'))).columns
        assert 'As proposed (mm²/m)' in fields and 'As current (mm²/m)' in fields
        scope=json.loads(z.read('Proposal/Scope.json'))
        assert not scope['applied_to_project'] and not scope['full_deck_acceptance']
    encoded=project_to_json(project_from_session_state(state))
    assert 'reinforcement_proposal' not in encoded and design.RESULT_KEY not in encoded
    restored={design.RESULT_KEY:{'old':True}}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert design.RESULT_KEY not in restored
