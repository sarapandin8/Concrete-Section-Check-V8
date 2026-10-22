"""Independent unit conversion, bound proof, source guards and production UI."""
from copy import deepcopy
from io import BytesIO
import json
import math
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_punching78 as bound, slab_top65 as top, slab_review68 as active
from concrete_pmm_pro.analysis import slab_aashto63 as sections
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io import slab_shell_import as source
from concrete_pmm_pro.visualization.slab_punching78 import figure
from test_slab_punch76_auto import state, app


def uniform_state():
    s = state()
    s[source.BANK_KEY].tables['thickness'][[f'Thick{i}' for i in range(1, 5)]] = .35
    source._validate(s[source.BANK_KEY])
    return s


@pytest.fixture
def base():
    b = sections.calculate(uniform_state())
    b['rows'][['Vx', 'Vy']] = [3., 4.]
    return b


def test_si_resistance_matches_independent_us_calculation_and_aspect_ratio_limit():
    stress, dv, r = bound.unit_resistance(35., [350.], 64.)
    dv_in = max(.9*(350-64)/25.4, .72*350/25.4)
    # 12 in of perimeter = one foot. kip/ft -> kN/m.
    independent = .9*.063*math.sqrt(35/6.894757293)*12*dv_in*4.4482216152605/.3048
    assert dv[0] == pytest.approx(257.4)
    assert r[0] == pytest.approx(independent, rel=2e-10)
    for beta in (1., 2., 3., 10., 1000., 1e12):
        assert min(.063+.126/beta, .126) >= .063


def test_static_vector_norm_and_rotation_are_invariant_without_force_scaling(base):
    before = base['rows'].copy(deep=True)
    a = bound.calculate(base)
    assert a['status'] == 'PASS (sufficient)'
    assert a['rows']['Q bound (kN/m)'].eq(5.).all()
    angle = .59
    q = np.array([3., 4.])@np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])
    base['rows'][['Vx', 'Vy']] = q
    b = bound.calculate(base)
    assert b['max_dc'] == pytest.approx(a['max_dc'])
    base['rows'] = before
    bound.calculate(base)
    pd.testing.assert_frame_equal(base['rows'], before, check_exact=True)


def test_step_bound_handles_opposite_component_extrema_without_cancellation(base):
    f = base['rows']
    f.loc[f.StepType.eq('Max'), ['Vx', 'Vy']] = [30., 4.]
    f.loc[f.StepType.eq('Min'), ['Vx', 'Vy']] = [-3., -40.]
    r = bound.calculate(base)
    assert r['rows']['Q bound (kN/m)'].eq(50.).all()
    assert len(r['rows']) == len(f)//2


def test_analytical_radial_field_and_all_cut_normals_obey_the_sufficient_bound():
    # Q=(a*x,b*y). Net force through any rectangle is (a+b)*area.
    a, b = 13., 19.
    for width, height in ((.2, .4), (1., .5), (.8, 1.4)):
        qmax = math.hypot(a*width/2, b*height/2)
        vu = (a+b)*width*height
        perimeter = 2*(width+height)
        assert vu <= qmax*perimeter+1e-12
        for theta in np.linspace(0., 2*math.pi, 501):
            normal = [math.cos(theta), math.sin(theta)]
            assert abs(np.dot([a*width/2, b*height/2], normal)) <= qmax+1e-12


def test_an_exceeded_sufficient_bound_is_review_never_an_actual_failure(base):
    base['rows'][['Vx', 'Vy']] = [10000., 10000.]
    r = bound.calculate(base)
    assert r['status'] == 'REVIEW' and r['max_dc'] > 1
    assert not r['rows'].Status.eq('FAIL').any()


@pytest.mark.parametrize('mode', ['missing_step', 'missing_corner_case', 'nonfinite', 'duplicate'])
def test_incomplete_sources_cannot_create_a_sufficient_pass(base, mode):
    f = base['rows']
    if mode == 'missing_step':
        base['rows'] = f.drop(f.index[0])
    elif mode == 'missing_corner_case':
        row = f.iloc[0]
        base['rows'] = f.loc[~(f.AreaElem.eq(row.AreaElem)&f.Joint.eq(row.Joint)&f.OutputCase.eq(row.OutputCase))]
    elif mode == 'nonfinite':
        f.loc[f.index[0], 'Vx'] = np.nan
    else:
        base['rows'] = pd.concat((f, f.iloc[[0]]), ignore_index=True)
    r = bound.calculate(base)
    assert r['source_incomplete'] and r['status'] == 'REVIEW'


def test_omitted_sources_and_support_contacts_have_no_nominal_dc(base):
    row = base['rows'].iloc[0]
    mask = base['rows'].Joint.eq(row.Joint)&base['rows'].AreaElem.eq(row.AreaElem)
    base['rows'].loc[mask, INCLUDED] = False
    base['rows'].loc[mask, ['Vx', 'Vy']] = 1e8
    r = bound.calculate(base)
    assert r['rows'].loc[r['rows'].Joint.eq(row.Joint)&r['rows'].AreaElem.eq(row.AreaElem), 'Local D/C'].isna().all()
    assert r['max_dc'] < 1
    adapted = bound.map_adapter(base, r)
    assert adapted['rows'].loc[adapted['rows'].AreaElem.eq(row.AreaElem), 'Source incomplete'].all()
    base['supports'] = [{'a': np.array([0., 0.]), 'b': np.array([2., 0.]), 'half_width': .1,
        'unit': np.array([1., 0.]), 'normal': np.array([0., 1.]), 'length': 2.}]
    r = bound.calculate(base)
    assert r['rows'].loc[r['rows']['Support contact'], 'Local D/C'].isna().all()


def test_remote_thin_region_does_not_reduce_resistance_at_a_thicker_point(base):
    before = bound.calculate(base)
    g = base['geometry'].corners.iloc[0]
    mask = base['rows'].AreaElem.eq(g.AreaElem)&base['rows'].Joint.eq(g.Joint)
    base['rows'].loc[mask, ['Vx','Vy']] = 0.
    base['rows'].loc[mask, 'Thickness (mm)'] = 200.
    base['geometry'].corners.loc[base['geometry'].corners.index[0], 'Thickness (mm)'] = 200.
    r = bound.calculate(base)
    assert r['minimum_thickness_mm'] == 200
    local = r['rows'].loc[r['rows'].AreaElem.eq(g.AreaElem)&r['rows'].Joint.eq(g.Joint)]
    others = r['rows'].loc[~(r['rows'].AreaElem.eq(g.AreaElem)&r['rows'].Joint.eq(g.Joint))]
    assert local['dv (mm)'].eq(144.).all()
    np.testing.assert_allclose(others['dv (mm)'], 257.4)
    assert r['max_dc'] == pytest.approx(before['max_dc'])
    assert r['status']=='REVIEW' and not r['global_minimum_depth_applied']
    assert r['governing']['Thickness (mm)'] == 350.
    area = next(iter(base['geometry'].parent_axes))
    base['geometry'].parent_axes[area]['up'] = [.01, 0., np.sqrt(1-.01**2)]
    assert bound.calculate(base)['geometry_issues']
    with pytest.raises(ValueError):
        bound.unit_resistance(110., [350.], 64.)


def test_production_calculation_preserves_all_existing_mechanics_and_report_is_readonly():
    s = uniform_state()
    result = active.calculate(s)
    b = result['base_result']
    for name in ('rows', 'summary', 'support_faces', 'exclusion_counts'):
        pd.testing.assert_frame_equal(result[name], b[name], check_exact=True)
    assert result['punching_screen78']['evaluated_records'] > 0
    before = result['punching_screen78']['rows'].copy(deep=True)
    with patch.object(bound, 'calculate', side_effect=AssertionError('Report ran mechanics')):
        payload = active.report_zip(result)
    with ZipFile(BytesIO(payload)) as z:
        name = next(n for n in z.namelist() if n.endswith('Punching79/Basis.json'))
        saved = json.loads(z.read(name))
        assert saved['source_actions_multiplier'] == 1
        assert not saved['physical_perimeter_inferred'] and not saved['full_deck_acceptance']
    pd.testing.assert_frame_equal(before, result['punching_screen78']['rows'], check_exact=True)


def test_actual_app_one_calculate_shows_dc_map_and_filter_does_not_rerun():
    test = app(uniform_state())
    assert not test.exception
    assert any('existing CSiBridge shear forces' in x.value for x in test.info)
    assert not next(e for e in test.expander if 'areas · optional' in e.label).proto.expanded
    with patch.object(active, 'calculate', wraps=active.calculate) as solver:
        test.button(key='slab_shell55_aashto62_calculate').click().run(timeout=60)
        assert not test.exception and solver.call_count == 1
        assert len(test.get('plotly_chart')) == 1
        result = test.session_state[active.RESULT_KEY]
        assert result['punching_screen78']['max_dc'] >= 0
        test.selectbox(key='slab_shell55_punch78_case').set_value('U1A').run()
        assert not test.exception and solver.call_count == 1
        test.button(key='slab_shell55_punch76_oneway').click().run()
        assert not test.exception and solver.call_count == 1
        assert test.session_state['slab_shell55_shear64_group'] == 'One-way shear'


def test_shared_plan_contains_numeric_scale_and_actual_governing_location():
    r = active.calculate(uniform_state())
    fig = figure(r)
    assert any(t.name == 'D/C scale' for t in fig.data)
    assert 'actual thickness' in fig.layout.title.text
    governor = r['punching_screen78']['governing']
    marker = next(t for t in fig.data if str(t.name).startswith('Gov. local'))
    assert marker.x[0] == governor['X (m)'] and marker.y[0] == governor['Y (m)']
    assert fig.layout.meta['bound_not_actual_perimeter_ratio']


def test_result_summary_uses_the_same_stored_bound_and_never_recalculates():
    from concrete_pmm_pro.reporting.slab_top65 import summary_rows
    s = uniform_state()
    r = top.calculate(s)
    s[top.RESULT_KEY] = r
    with patch.object(bound, 'calculate', side_effect=AssertionError('Summary ran mechanics')):
        rows = summary_rows(s)
    row = next(x for x in rows if x['Check'] == 'Punching local normal-shear index')
    assert row['D/C / Util.'] == r['punching_screen78']['max_dc']
    assert row['Status'] == r['punching_screen78']['status']
    assert 'kN/m' in row['Demand'] and 'kN/m' in row['Capacity / Limit']
