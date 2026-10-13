"""End-dimension workflow, legacy coordinates, reviewed status and live span changes."""
from copy import deepcopy
import math

import pandas as pd
import pytest

try:
    from streamlit.testing.v1 import AppTest
except (ImportError, TypeError):
    AppTest = None

from concrete_pmm_pro.analysis import igird_end_sections as ends
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json,
    project_from_session_state, project_to_json,
)
from concrete_pmm_pro.ui import analysis_page as ap, igird_station_section as station
from test_igird_endsection18 import model, demand, _route

SCRIPT = '''
import streamlit as st
from concrete_pmm_pro.ui.igird_end_sections import render_inputs
page=st.radio('Page',['Sections','Analysis'])
if page=='Sections':
    render_inputs(st.session_state['section_parameters'], st.session_state['section_geometry'])
'''


def run(at):
    at.run(timeout=30)
    assert not at.exception, [e.message for e in at.exception]


def app(settings=None):
    at = AppTest.from_string(SCRIPT)
    state = model()
    # UI inputs are intentionally unreviewed; tests do not assert real drawing proof.
    state['section_parameters'][ends.SETTINGS_KEY].update({
        'hoop_confirmed': False, 'load_reference_confirmed': False,
        'd_region_confirmed': False, **(settings or {}),
    })
    for key, value in state.items():
        at.session_state[key] = deepcopy(value)
    run(at)
    return at


def number(at, label, value):
    next(x for x in at.number_input if x.label == label).set_value(value)
    run(at)


def checkbox(at, label):
    return next(x for x in at.checkbox if x.label == label)


def config(at):
    return at.session_state['section_parameters'][ends.SETTINGS_KEY]


@pytest.mark.skipif(AppTest is None, reason='Preload real Streamlit for UI tests')
def test_default_three_dimensions_mirror_and_preview_without_review_confirmations():
    at = app()
    assert checkbox(at, 'Same dimensions at both ends').value
    assert config(at)['coordinate_mode'] == 'span'
    assert not any('physical end x' in x.label for x in at.number_input)
    assert {'Solid length at each end (m)', 'Transition length at each end (m)',
            'Solid-end width (mm)'}.issubset({x.label for x in at.number_input})
    assert not any(config(at)[k] for k in ('hoop_confirmed', 'load_reference_confirmed', 'd_region_confirmed'))
    number(at, 'Solid length at each end (m)', 2.0)
    number(at, 'Transition length at each end (m)', .5)
    assert config(at)['left_solid_m'] == config(at)['right_solid_m'] == 2.0
    assert config(at)['left_taper_m'] == config(at)['right_taper_m'] == .5
    next(x for x in at.slider if x.label == 'Preview section at Loads x (m)').set_value(2.25)
    run(at)
    assert any('LEFT TAPER' in x.value and '400 mm' in x.value for x in at.caption)
    r = ap._beam_uls_shear_result_for_row(at.session_state.filtered_state, demand(1), strength_route=_route())
    assert math.isfinite(r['φVn kN']) and r['End section acceptance'] == 'REVIEW'


@pytest.mark.skipif(AppTest is None, reason='Preload real Streamlit for UI tests')
def test_asymmetric_legacy_dimensions_remain_independent_across_navigation_and_json():
    at = app({'left_solid_m': 2.0, 'right_solid_m': 1.0,
              'left_taper_m': .25, 'right_taper_m': .5,
              'left_end_x_m': .025, 'right_end_x_m': 19.975})
    assert not checkbox(at, 'Same dimensions at both ends').value
    assert not checkbox(at, 'Use full Loads span for girder ends').value
    number(at, 'Right solid length (m)', 1.2)
    saved = dict(config(at))
    at.radio[0].set_value('Analysis'); run(at)
    at.radio[0].set_value('Sections'); run(at)
    assert config(at) == saved
    serialized = project_to_json(project_from_session_state(at.session_state.filtered_state))
    restored = {}
    apply_project_to_session_state(project_from_json(serialized), restored)
    assert restored['section_parameters'][ends.SETTINGS_KEY] == saved
    assert ends.cut_ends(restored['section_parameters'], 20) == (.025, 19.975)
    assert station.strand_families(restored, restored['girder_strand_layout_table'],
        y_min_mm=-750, span_m=20, stage='final', settings={})[0].left_bond_start_m == pytest.approx(.025)


@pytest.mark.skipif(AppTest is None, reason='Preload real Streamlit for UI tests')
def test_simple_and_independent_modes_switch_without_reentering_dimensions():
    at = app()
    number(at, 'Solid length at each end (m)', 1.8)
    checkbox(at, 'Same dimensions at both ends').uncheck(); run(at)
    assert config(at)['left_solid_m'] == config(at)['right_solid_m'] == 1.8
    number(at, 'Right solid length (m)', 1.0)
    assert config(at)['left_solid_m'] == 1.8 and config(at)['right_solid_m'] == 1.0
    checkbox(at, 'Same dimensions at both ends').check(); run(at)
    assert config(at)['left_solid_m'] == config(at)['right_solid_m'] == 1.8


@pytest.mark.skipif(AppTest is None, reason='Preload real Streamlit for UI tests')
def test_invalid_old_coordinates_are_exposed_and_repaired_only_by_explicit_action():
    at = app({'left_end_x_m': 0.0, 'right_end_x_m': 0.0})
    assert at.error and config(at)['coordinate_mode'] == 'custom'
    assert config(at)['right_end_x_m'] == 0.0
    next(x for x in at.button if x.label == 'Use Loads span for girder ends').click(); run(at)
    assert not at.error and config(at)['coordinate_mode'] == 'span'
    assert ends.cut_ends(at.session_state['section_parameters'], 20) == (0.0, 20.0)


@pytest.mark.skipif(AppTest is None, reason='Preload real Streamlit for UI tests')
def test_automatic_coordinates_follow_setup_span_and_custom_ones_do_not():
    at = app()
    at.session_state[ap.BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = {'span_length_m': 22.0}
    run(at)
    assert config(at)['right_end_x_m'] == 22.0 and not at.error
    checkbox(at, 'Use full Loads span for girder ends').uncheck(); run(at)
    number(at, 'Left physical end x in Loads (m)', .025)
    number(at, 'Right physical end x in Loads (m)', 21.975)
    at.session_state[ap.BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = {'span_length_m': 24.0}
    run(at)
    assert (config(at)['left_end_x_m'], config(at)['right_end_x_m']) == (.025, 21.975)


def test_automatic_mode_resolves_current_span_before_section_ui_or_after_json_reload():
    state = model(coordinate_mode='span', left_end_x_m=0.0, right_end_x_m=20.0)
    state[ap.BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = {'span_length_m': 22.0}
    local = station.at_station(state, 21.0)
    assert local[station.TRACE_KEY]['Section region'] == 'RIGHT SOLID END'
    assert local[station.TRACE_KEY]['Physical girder length (m)'] == 22.0
    restored = {}
    apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(state))), restored)
    assert ends.cut_ends(restored['section_parameters'], 22.0) == (0.0, 22.0)
    before = ap._beam_uls_check_input_hash(state, pd.DataFrame([demand(10)]), strength_route=_route(), check_name='Shear')
    state[ap.BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = {'span_length_m': 24.0}
    after = ap._beam_uls_check_input_hash(state, pd.DataFrame([demand(10)]), strength_route=_route(), check_name='Shear')
    assert before != after


def test_explicit_same_geometry_retains_all_strength_values_and_unreviewed_flags():
    legacy = model(hoop_confirmed=False, d_region_confirmed=False, load_reference_confirmed=False)
    simple = deepcopy(legacy)
    simple['section_parameters'][ends.SETTINGS_KEY].update({
        'coordinate_mode': 'span', 'same_ends': True, 'left_end_x_m': 0.0, 'right_end_x_m': 20.0,
    })
    for x in (1.0, 1.625, 10.0, 18.375, 19.0):
        for check in (ap._beam_uls_shear_result_for_row, ap._beam_uls_igird_torsion_result_for_row):
            pd.testing.assert_frame_equal(
                pd.DataFrame([check(legacy, demand(x), strength_route=_route())]),
                pd.DataFrame([check(simple, demand(x), strength_route=_route())]),
            )
    source = pd.DataFrame([demand(1.0), demand(10.0), demand(19.0)])
    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
    source = tag_app_source(source, source_name='ENDSIMPLE22 hypothetical static QA', sheet_name='QA',
        source_mode='static', concurrency_confirmed=True,
        evidence='Hypothetical simultaneous static action vectors; no CSI export proof claimed')
    pd.testing.assert_frame_equal(
        ap._beam_uls_combined_vt_check_dataframe(legacy, source, strength_route=_route()),
        ap._beam_uls_combined_vt_check_dataframe(simple, source, strength_route=_route()),
    )
