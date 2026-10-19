"""Visible code-result selection and missing-result behavior, no LP shortcut."""
from unittest.mock import patch
import pandas as pd
from concrete_pmm_pro.ui import igird_code52 as view,igird_member_results as members
from concrete_pmm_pro.ui import analysis_page as ap
import pytest


def test_governing_code_member_opens_without_hiding_unresolved_rows():
    names=['Exterior','Interior']
    controls={'Exterior':{'ratio':.9,'failed_rows':0,'review_rows':0},
        'Interior':{'ratio':1.2,'failed_rows':1,'review_rows':0}}
    assert view.default_member(names,controls)=='Interior'
    controls['Interior']={'ratio':float('nan'),'failed_rows':0,'review_rows':2}
    assert view.default_member(names,controls)=='Interior'
    assert view.default_member(names,{})=='Exterior'
    assert view.default_member([],{}) is None


def test_missing_code_results_do_not_trigger_LP_or_silently_return_a_blank_panel():
    from concrete_pmm_pro.ui import igird_composite_steel45 as research
    with patch.object(research,'calculate',side_effect=AssertionError('No LP')),\
         patch.object(members.st,'session_state',{}),patch.object(members.st,'warning') as warning:
        members._render_member_result(member='Interior',result=None,all_rows=pd.DataFrame(),
            control=None,cache={},check_name='Torsion',code_label='AASHTO')
    assert warning.called and 'NOT CALCULATED' in warning.call_args.args[0]


def test_numeric_text_cannot_abort_governing_action_or_VT_result_publication():
    rows=pd.DataFrame({'Case Name':['A','B','C'],'Station x (m)':['0','10','20'],
        'Tu':['12.5','-45.2','not available']},index=[0,0,1])
    before=rows.copy(deep=True)
    result=ap._beam_uls_governing_action(rows,'Tu')
    assert result['case']=='B' and result['demand']==pytest.approx(-45.2)
    assert result['x_m']==10.
    assert ap._beam_uls_torsion_interaction_status(rows)['status']=='warning'
    pd.testing.assert_frame_equal(rows,before)


@pytest.mark.parametrize('values',[[None,'unknown'],['NaN','Infinity','-Infinity'],[True,False]])
def test_invalid_force_values_are_unavailable_not_zero_or_an_infinite_governor(values):
    assert ap._beam_uls_governing_action(pd.DataFrame({'Tu':values}),'Tu') is None


def test_valid_force_with_missing_station_does_not_crash_the_review():
    result=ap._beam_uls_governing_action(pd.DataFrame({'Tu':['-20']}),'Tu')
    assert result['demand']==-20. and result['x_m'] is None
