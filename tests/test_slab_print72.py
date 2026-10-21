"""Physical location and print-export checks, independent of D/C magnitude."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.visualization import slab_print72 as printing
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
from concrete_pmm_pro.visualization.slab_shell56 import _color_scale
from concrete_pmm_pro.visualization import slab_top65 as plots
from concrete_pmm_pro.analysis import slab_top65 as engine
from test_slab_endzone60 import end_state


def context(reference='centerline', angle=0., shift=(0., 0.)):
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    shift = np.asarray(shift)
    def point(xy): return np.asarray(xy)@rotation.T+shift
    direction = rotation[:, 0]
    lines = [dict(Connection='Girder', ID=f'CSI-{i}',
        **dict(zip(['X1 (m)', 'Y1 (m)', 'X2 (m)', 'Y2 (m)'],
                   np.concatenate((point([0., y]), point([20., y]))))))
        for i, y in enumerate([3.7, 2.5, 1.3, -1.3, -2.5, -3.7], 1)]
    polygon = np.column_stack((point([[0, -5.5], [20, -5.5], [20, 5.5], [0, 5.5]]), np.zeros(4)))
    geometry = SimpleNamespace(elements={'E': polygon}, parent_axes={'A': {'long': np.r_[direction, 0.]}})
    return {'geometry': geometry, 'connections': {'lines': pd.DataFrame(lines),
        'end_zones': {'active': True, 'reference': reference, 'longitudinal': direction.tolist(),
            'origin_s_m': float(shift@direction),
            'zones': [{'Side': 'Left', 'From station (m)': 0., 'To station (m)': .4},
                      {'Side': 'Right', 'From station (m)': 19.6, 'To station (m)': 20.}]}}}


def test_girder_labels_follow_native_order_and_bearings_are_actual_intersections():
    source = context()
    before = source['connections']['lines'].copy(deep=True)
    refs = printing.references(source)
    assert [g['label'] for g in refs['girders']] == [f'G{i}' for i in range(1, 7)]
    np.testing.assert_array_equal([g['a'][1] for g in refs['girders']], [3.7, 2.5, 1.3, -1.3, -2.5, -3.7])
    assert [b['station_m'] for b in refs['bearings']] == [.4, 19.6]
    assert [len(b['points']) for b in refs['bearings']] == [6, 6]
    for b in refs['bearings']:
        np.testing.assert_allclose(np.asarray(b['points'])[:, 0], b['station_m'])
    pd.testing.assert_frame_equal(before, source['connections']['lines'])


def test_rotated_translated_layout_preserves_native_coordinates_and_station_datum():
    angle=.4; shift=np.array([17., -8.]); source=context(angle=angle, shift=shift)
    direction=np.array([np.cos(angle),np.sin(angle)])
    for bearing in printing.references(source)['bearings']:
        np.testing.assert_allclose((np.asarray(bearing['points'])-shift)@direction, bearing['station_m'], atol=1e-12)


def test_unconfirmed_bearings_and_missing_girders_are_not_replaced_by_guessed_geometry():
    source=context();source['connections']['end_zones']['active']=False
    source['connections']['lines']=source['connections']['lines'].iloc[:0]
    refs=printing.references(source)
    assert not refs['girders'] and not refs['bearings']


def test_bearing_face_reference_is_never_labelled_centerline_and_segments_are_not_extended():
    source=context(reference='inside_face')
    source['connections']['lines'].loc[0, 'X1 (m)']=1.
    refs=printing.references(source)
    assert len(refs['bearings'][0]['points'])==5 and len(refs['bearings'][1]['points'])==6
    assert all('inside face' in b['label'] and 'CL' not in b['label'] for b in refs['bearings'])


def test_global_readability_cannot_thicken_context_or_remove_print_references():
    import plotly.graph_objects as go
    fig=printing.add_plan_references(go.Figure(),context())
    for _ in range(2): apply_global_plot_readability(fig)
    assert len([a for a in fig.layout.annotations if a.name.startswith('slab-girder-')])==6
    assert fig.layout.meta['bearing_stations_m']==[.4,19.6]
    assert not fig.layout.meta['bearing_symbols_are_footprints']
    line=next(t for t in fig.data if t.name=='I-girder CL')
    assert line.line.width==1.15
    assert printing.export_config()['toImageButtonOptions']['format']=='svg'
    assert fig.layout.paper_bgcolor=='#ffffff'


def test_profile_labels_locations_without_treating_girder_y_as_a_dc_value():
    source=context()
    import plotly.graph_objects as go
    fig=printing.add_profile_references(go.Figure(),source)
    assert [s.x0 for s in fig.layout.shapes]==[.4,19.6]
    assert all(s.yref=='paper' for s in fig.layout.shapes)
    key=next(a for a in fig.layout.annotations if a.name=='slab-girder-key')
    assert 'G1 Y=+3.70 m' in key.text and 'G6 Y=-3.70 m' in key.text
    assert not fig.data  # no invented D/C series for a girder location


def test_actual_plan_and_profile_preserve_stored_result_values_and_missingness():
    result=engine.calculate(end_state())
    before=result['rows'].copy(deep=True)
    adapted=engine.map_adapter(result,'Direct N–M · transverse')
    envelope=plots.station_envelope(adapted)[0].copy(deep=True)
    plan=plots.plan(result,adapted,'Direct N–M · transverse')
    profile=plots.profile(adapted,'Direct N–M · transverse')
    assert plan.layout.meta['slab_print_version']==printing.VERSION
    assert profile.layout.meta['slab_print_version']==printing.VERSION
    pd.testing.assert_frame_equal(envelope,plots.station_envelope(adapted)[0])
    pd.testing.assert_frame_equal(before,result['rows'])


def test_soft_palette_retains_the_unclipped_logarithmic_dc_scale_and_failure_boundary():
    top,colors=_color_scale(32.5)
    assert top==pytest.approx(np.log1p(32.5))
    boundary=np.log(2)/top
    assert [boundary,printing.LIMIT_FILL] in colors
    assert colors[0]==[0,printing.SAFE_FILL] and colors[-1]==[1,printing.HIGH_FILL]
