"""Trace fidelity and actionable incomplete-source presentation for native CSI V/T."""
import math

import pandas as pd
import plotly.graph_objects as go

from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_combined_vt import source_readiness_dataframe
from concrete_pmm_pro.visualization.igird_uls_chart_display import (
    compact_csi_demand_labels, compact_reference_paths,
)


def native_rows():
    return pd.DataFrame([{'Station x (m)':x, 'Case Name':f'ENV_ULS / Left Exterior Girder / {step} / set {occ}',
        'Vuy':factor*(x-1)*100, 'Tu':factor*(x-1)*20}
        for step,occ,factor in [('Max',1,1),('Max',2,.9),('Min',1,-1),('Min',2,-.8)] for x in [0,1,2]])


def test_csi_shear_and_torsion_labels_preserve_signed_coordinates_and_source_hover():
    active = native_rows()
    for component, unit in [('Vuy','kN'), ('Tu','kN-m')]:
        fig = ap._make_beam_uls_demand_figure(active, column=component, title='check', y_label=unit)
        original = {t.name:(list(t.x),list(t.y)) for t in fig.data if t.name.startswith('Demand '+component)}
        compact_csi_demand_labels(fig, component=component, unit=unit)
        assert {f'{component} {step} {occ}' for step in ['Max','Min'] for occ in [1,2]} <= {t.name for t in fig.data}
        for trace in fig.data:
            if trace.name.startswith(component+' '):
                case = trace.customdata[0][0]
                assert (list(trace.x),list(trace.y)) == original['Demand '+component+' — '+case]
                assert unit in trace.hovertemplate and trace.line.color == ap._BEAM_ULS_DEMAND_LINE_STYLE['color']
                assert trace.line.dash == ('dot' if '/ Min /' in case else 'solid')


def test_reference_cleanup_keeps_different_resistance_paths_and_both_signs():
    paths = [(100,200), (100,200), (110,210), (-100,-200), (-100,-200), (-110,-210)]
    fig = go.Figure([go.Scatter(x=[0,20],y=p,name='φVn' if p[0]>0 else '-φVn') for p in paths])
    compact_reference_paths(fig, {'φVn':'±φVn','-φVn':'±φVn'})
    assert {tuple(t.y) for t in fig.data} == set(paths)
    assert len(fig.data) == 4
    assert sum(t.showlegend for t in fig.data) == 1


def test_a_missing_resistance_gap_is_never_merged_into_a_finite_path():
    fig = go.Figure([go.Scatter(x=[0,10,20],y=[100,200,100],name='±φTn'),
        go.Scatter(x=[0,10,20],y=[100,float('nan'),100],name='±φTn')])
    compact_reference_paths(fig, {'±φTn':'±φTn'})
    assert len(fig.data) == 2 and math.isnan(fig.data[1].y[1])
    assert all(t.connectgaps is False for t in fig.data)


def test_first_available_torsion_reference_is_visible_even_when_first_case_has_no_capacity():
    active = native_rows()
    rows = []
    for index,source in active.iterrows():
        rows.append({'Case':source['Case Name'], 'Governing x':str(source['Station x (m)'])+' m',
            'φTn kN-m':float('nan') if index<3 else 100, 'φTcr kN-m':80, 'Threshold kN-m':20,
            'Status':'LAYOUT REQUIRED','Abs demand kN-m':abs(source['Tu']),'D/C value':float('nan')})
    fig = ap._make_beam_uls_torsion_capacity_figure(active,pd.DataFrame(rows),code_label='AASHTO LRFD 9th Edition')
    names = [t.name for t in fig.data if t.showlegend is not False]
    assert '±φTn' in names and len(names) == len(set(names))
    assert len([t for t in fig.data if t.name == '±φTcr']) == 2


def test_incomplete_sources_show_material_and_zone_actions_without_altering_results():
    df = pd.DataFrame([
        {'Case':'Max 1','Governing x':'1.000 m','Status':'DATA REQUIRED','Review reason':"Provided transverse zone 'Z1' is not selected for torsion.",'Overall D/C value':float('nan')},
        {'Case':'Min 1','Governing x':'1.000 m','Status':'DATA REQUIRED','Review reason':"Provided transverse zone 'Z1' is not selected for torsion.",'Overall D/C value':float('nan')},
        {'Case':'Max 1','Governing x':'10.000 m','Status':'REVIEW','Review reason':'Longitudinal material SD40 is unresolved.','Overall D/C value':float('nan')},
        {'Case':'Max 1','Governing x':'12.000 m','Status':'FAIL','Review reason':'strength failure','Overall D/C value':2.0},
    ])
    before = df.copy(deep=True)
    readiness = source_readiness_dataframe(df)
    assert len(readiness) == 2
    zone = readiness.loc[readiness['Required source / review'].str.contains('Z1')].iloc[0]
    material = readiness.loc[readiness['Required source / review'].str.contains('SD40')].iloc[0]
    assert zone['Check rows'] == 2 and zone['Stations'] == '1.000 m'
    assert 'Transverse Rebar' in zone['Input location'] and '135° Hook' in zone['Required action']
    assert 'Complete missing longitudinal materials' in material['Input location'] and 'verified fy' in material['Required action']
    pd.testing.assert_frame_equal(df,before)


def test_multiple_native_members_with_the_same_bound_have_distinct_short_labels():
    fig = go.Figure([go.Scatter(x=[0],y=[10],name='Demand Tu — ENV / '+member+' / Max / set 1') for member in ['Left','Right']])
    compact_csi_demand_labels(fig, component='Tu', unit='kN-m')
    assert [t.name for t in fig.data] == ['Tu Max C1','Tu Max C2']
    assert fig.data[0].customdata[0] != fig.data[1].customdata[0]


def test_native_reference_actions_are_not_listed_as_missing_primary_inputs():
    df = pd.DataFrame([{'Status':'DATA REQUIRED','Source ItemType':'Max','Governing x':'1.000 m',
        'Review reason':"Muy requires biaxial review outside the route.; Vux requires biaxial review outside the route.; Provided transverse zone 'Z1' is not selected for torsion."}])
    before = df.copy(deep=True)
    readiness = source_readiness_dataframe(df)
    assert len(readiness) == 1 and 'Z1' in readiness.iloc[0]['Required source / review']
    pd.testing.assert_frame_equal(df,before)
