"""Punching Apply: real editor transactions, visible feedback and fresh results."""
from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pytest

from concrete_pmm_pro.analysis import slab_punching64 as punching, slab_review68 as active
from concrete_pmm_pro.io import slab_shell_import as source
from concrete_pmm_pro.io.project_io import (apply_project_to_session_state, project_from_json,
    project_from_session_state, project_to_json)
from test_slab_punching64 import area
from test_slab_top65_ui import app, clean


def workspace(areas=None):
    test=app()
    # Explicit QA geometry: uniform thickness allows an isolated area to have a
    # qualified numeric check. The product never fills these dimensions itself.
    package=test.session_state[source.BANK_KEY]
    package.tables['thickness'][[f'Thick{i}' for i in range(1,5)]]=.35
    source._validate(package)
    if areas is not None:
        metadata=deepcopy(test.session_state['project_metadata'])
        metadata[punching.CONFIG_KEY]={'version':1,'areas':areas}
        test.session_state['project_metadata']=metadata
    test.session_state['slab_shell55_shear64_group']='Punching shear'
    clean(test)
    return test


def editor_key(test):
    revision=test.session_state.filtered_state.get('slab_shell55_punch75_editor_revision',0)
    return 'slab_shell55_punch64_editor'+(f'_{revision}' if revision else '')


def edit(test, *, row=None, added=None, deleted=None):
    test.session_state[editor_key(test)]={'edited_rows':{0:row} if row else {},
        'added_rows':added or [],'deleted_rows':deleted or []}


def apply(test):
    next(b for b in test.button if b.label=='Apply load areas').click()
    clean(test)


def definitions(test):
    return punching.config(test.session_state.filtered_state)


def test_blank_apply_displays_actionable_warning_without_saving_or_calculating():
    test=workspace()
    before=deepcopy(test.session_state['project_metadata'])
    with patch.object(active,'calculate',side_effect=AssertionError('Apply ran the structural solver')):
        apply(test)
    assert test.session_state['project_metadata']==before
    assert definitions(test)==[]
    assert any('No load areas applied' in item.value and 'X/Y (m)' in item.value for item in test.warning)
    assert not any('Applied 0' in item.value for item in test.success)


@pytest.mark.parametrize('vu',[None,10.])
def test_fill_first_row_apply_reports_success_and_calculate_produces_numeric_punching(vu):
    test=workspace()
    definition=area(x=.5,y=.5,l=200.,b=200.,vu=vu)
    edit(test,row=definition)
    with patch.object(active,'calculate',wraps=active.calculate) as solver:
        apply(test)
        assert solver.call_count==0
        assert definitions(test)==[definition]
        assert any('Applied 1 load area.' in item.value for item in test.success)
        for _ in range(2):clean(test)
        assert definitions(test)==[definition]
        test.button(key='slab_shell55_aashto62_calculate').click()
        clean(test)
        assert solver.call_count==1
        result=test.session_state[active.RESULT_KEY]['punching']
        assert len(result['rows'])==(4 if vu is None else 1)
        assert np.isfinite(result['rows']['D/C']).all()
        assert set(result['rows'].Area)=={'P1'} and len(test.get('plotly_chart'))==2
        assert test.session_state[active.RESULT_KEY]['punching_screen78']['evaluated_records']>0
        if vu is not None:assert result['rows']['Vu (kN)'].eq(vu).all()


def test_anonymous_area_name_is_assigned_only_after_real_dimensions_are_entered():
    test=workspace()
    row=area(x=.5,y=.5,l=200.,b=200.,vu=None)
    row['Area']=None
    edit(test,row=row)
    apply(test)
    assert definitions(test)==[{**row,'Area':'P1'}]


@pytest.mark.parametrize('fault',['missing dimension','nonpositive dimension','duplicate name'])
def test_invalid_draft_does_not_replace_previously_applied_definitions(fault):
    original=area(x=.5,y=.5,l=200.,b=200.,vu=10.)
    test=workspace([original])
    if fault=='missing dimension':edit(test,row={'B (mm)':None})
    elif fault=='nonpositive dimension':edit(test,row={'L (mm)':-1.})
    else:edit(test,added=[area(x=1.5,y=.5,l=200.,b=200.,vu=10.)])
    apply(test)
    assert test.error and definitions(test)==[original]
    assert not any('Applied' in item.value for item in test.success)


def test_added_and_deleted_rows_are_not_replayed_against_the_newly_saved_table():
    test=workspace()
    first=area(x=.5,y=.5,l=200.,b=200.,vu=10.)
    second=area(x=1.5,y=.5,l=200.,b=200.,vu=10.,name='P2')
    edit(test,row=first,added=[second])
    apply(test)
    assert definitions(test)==[first,second]
    assert any('Applied 2 load areas.' in item.value for item in test.success)
    clean(test)
    assert definitions(test)==[first,second]
    edit(test,deleted=[0])
    apply(test)
    assert definitions(test)==[second]
    clean(test)
    assert definitions(test)==[second]


def test_removing_all_previously_saved_rows_clears_inputs_and_old_results_are_not_current():
    original=area(x=.5,y=.5,l=200.,b=200.,vu=10.)
    test=workspace([original])
    test.button(key='slab_shell55_aashto62_calculate').click()
    clean(test)
    assert active.current(test.session_state.filtered_state) is not None
    edit(test,deleted=[0])
    apply(test)
    assert definitions(test)==[]
    assert any('Load areas cleared' in item.value for item in test.info)
    assert active.current(test.session_state.filtered_state) is None
    assert not test.get('plotly_chart')


def test_applied_areas_survive_project_json_but_form_drafts_and_notices_do_not_leak():
    test=workspace()
    original=area(x=.5,y=.5,l=200.,b=200.,vu=None)
    edit(test,row=original)
    apply(test)
    encoded=project_to_json(project_from_session_state(test.session_state.filtered_state))
    state={'slab_shell55_punch75_notice':{'old':True},
        'slab_shell55_punch75_editor_revision':99,'slab_shell55_punch64_editor_99':{'old':True}}
    apply_project_to_session_state(project_from_json(encoded),state)
    assert punching.config(state)==[original]
    assert not any('punch75' in str(k) or 'punch64_editor' in str(k) for k in state)
