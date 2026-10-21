"""Independent LL criterion, source gaps, stage scope and stored-result tests."""
from copy import deepcopy
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.serviceability import girder_deflect69 as engine
from concrete_pmm_pro.visualization.girder_deflect69 import figure
from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state


def source_curves(up=100., existing_live=0.):
    x=np.linspace(0,20,21)
    records=[]
    for stage,name,peak in [('Transfer stage','Deflection @ Transfer',120.),
        ('Construction stage','Deflection @ Erection / CIP pour',110.),
        ('Service stage','Deflection on Completion',up),
        ('Service stage','Final Service Sustained Deflection',up),
        ('Service stage','Final Service Sust. + LL Deflection',up)]:
        for station in x:
            records.append({'Stage':stage,'Curve':name,'Station x (m)':station,
                'Deflection (mm)':peak*4*(station/20)*(1-station/20),
                'Service LL w (kN/m)':existing_live,'E used (MPa)':30000.,'Composite Ix (mm^4)':1e12})
    return pd.DataFrame(records)


def state(**config):
    return {engine.SETTINGS_KEY:{'profile':'rail_project',**config}}


def test_large_net_upward_camber_cannot_cancel_failing_live_load_increment():
    s=state(live_udl_kN_m=200.)
    result=engine.calculate(s,source_curves(),20.)
    ll=result['summary'].loc[lambda f:f.Check.eq('LL+IM increment')].iloc[0]
    expected=5*200.*20000.**4/(384*30000.*1e12)
    assert ll['Demand (mm)']==pytest.approx(expected)
    assert ll['Limit (mm)']==pytest.approx(20000/1500)
    assert ll.Utilization==pytest.approx(expected/(20000/1500))
    assert ll.Status=='Preview FAIL' and result['status']=='Preview FAIL'
    loaded=result['curves'].loc[lambda f:f.Curve.eq('Net with LL+IM')]
    assert loaded['Deflection (mm)'].min()>=0
    assert not result['full_deflection_acceptance']


def test_no_live_component_is_review_not_zero_deflection_pass_and_no_duplicate_service_curves():
    result=engine.calculate(state(),source_curves(up=9.912),20.)
    ll=result['summary'].loc[lambda f:f.Check.eq('LL+IM increment')].iloc[0]
    assert not result['live_available'] and ll.Status=='REVIEW'
    assert np.isnan(ll.Utilization) and np.isnan(ll['Demand (mm)'])
    assert result['curves'].loc[lambda f:f.Stage.eq('Service stage')].Curve.nunique()==1
    assert result['status']=='REVIEW REQUIRED'
    assert result['summary'].loc[lambda f:f.Check.eq('Long-term / full response'),'Status'].iloc[0]=='REVIEW'


@pytest.mark.parametrize('length,expected',[(20.,13.3333333333),(60.,30.)])
def test_railway_criterion_uses_more_restrictive_limit_and_is_not_labelled_aashto(length,expected):
    limit,label,basis=engine.criterion(engine.settings(state()),length)
    assert limit==pytest.approx(expected)
    assert 'Project railway' in basis and 'not an AASHTO' in basis


def test_aashto_highway_ratio_and_optional_stage_criteria_do_not_leak_between_stages():
    s=state(profile='aashto_vehicle',live_udl_kN_m=20.,transfer_limit_mm=130.,construction_limit_mm=105.)
    result=engine.calculate(s,source_curves(),20.)
    assert result['limit_mm']==25. and '2.5.2.6.2' in result['limit_basis']
    summary=result['summary'].iloc[:3]
    assert summary.iloc[0].Status=='Preview PASS'
    assert summary.iloc[1].Status=='Preview FAIL'
    assert np.isnan(summary.iloc[2]['Limit (mm)'])
    assert summary.iloc[2].Status=='REVIEW'
    fig=figure(result,'Transfer stage')
    levels=[float(t.y[0]) for t in fig.data if str(t.name).startswith('Project ±')]
    assert levels==[-130.,130.]
    assert not any('LL limit' in str(t.name) for t in fig.data)


def test_existing_building_live_load_is_reused_without_second_multiplier_and_zero_declaration_is_not_required():
    generated=engine.calculate(state(),source_curves(existing_live=50.),20.)
    supplied=engine.calculate(state(live_udl_kN_m=50.),source_curves(),20.)
    np.testing.assert_allclose(generated['curves']['Deflection (mm)'],supplied['curves']['Deflection (mm)'])
    zero=engine.calculate(state(live_udl_kN_m=0.),source_curves(),20.)
    ll=zero['summary'].loc[lambda f:f.Check.eq('LL+IM increment')].iloc[0]
    assert ll.Status=='NOT REQUIRED' and zero['status']=='REVIEW REQUIRED'
    assert not zero['curves'].Curve.eq('Net with LL+IM').any()


@pytest.mark.parametrize('key,value',[('profile','invented'),('live_udl_kN_m',-1.),('live_udl_kN_m',True),
    ('custom_limit_mm',float('nan')),('transfer_limit_mm',0.),('construction_limit_mm',float('inf'))])
def test_invalid_settings_block_instead_of_silently_defaulting(key,value):
    with pytest.raises(ValueError):engine.calculate(state(**{key:value}),source_curves(),20.)


def test_custom_or_review_without_a_limit_cannot_give_pass_and_source_coverage_is_not_fabricated():
    result=engine.calculate(state(profile='custom',live_udl_kN_m=5.),source_curves(),20.)
    assert result['summary'].loc[lambda f:f.Check.eq('LL+IM increment'),'Status'].iloc[0]=='REVIEW'
    bad=source_curves().loc[lambda f:f['Station x (m)']>0]
    with pytest.raises(ValueError,match='whole member'):engine.calculate(state(),bad,20.)
    bad=source_curves();bad.loc[0,'Deflection (mm)']=np.nan
    with pytest.raises(ValueError,match='finite'):engine.calculate(state(),bad,20.)


def test_chart_limit_negative_full_span_and_missing_source_annotation_with_short_legends():
    result=engine.calculate(state(),source_curves(),20.)
    fig=figure(result,'Service stage')
    line=next(t for t in fig.data if str(t.name).startswith('LL limit'))
    assert list(line.x)==[0,20.] and list(line.y)==pytest.approx([-20000/1500]*2)
    assert list(fig.layout.xaxis.range)==[0,20.]
    assert fig.layout.legend.orientation=='h'
    assert all(t.connectgaps is False for t in fig.data if t.mode=='lines+markers')
    assert any('source missing' in a.text for a in fig.layout.annotations)
    assert all(len(str(t.name))<32 for t in fig.data)
    assert not any('limit' in str(t.name).lower() for t in figure(result,'Construction stage').data)


def test_reports_and_summary_do_not_rerun_and_input_changes_invalidate_result():
    s=state(live_udl_kN_m=20.)
    result=engine.calculate(s,source_curves(),20.)
    s[engine.RESULT_KEY]=result
    source=result['curves'].copy(deep=True)
    with patch.object(engine,'calculate',side_effect=AssertionError('rerun')):
        assert len(engine.summary_rows(s))==5
        payload=engine.report_zip(result)
    with ZipFile(BytesIO(payload)) as z:
        assert z.testzip() is None
        assert not json.loads(z.read('Scope.json'))['full_deflection_acceptance']
    pd.testing.assert_frame_equal(result['curves'],source)
    s['section_parameters']={'Ebeam_MPa':35000.}
    assert engine.current(s) is None and engine.summary_rows(s)[0]['Status']=='STALE'


def test_new_settings_round_trip_but_runtime_result_and_widget_state_are_cleared():
    s=state(live_udl_kN_m=20.,construction_limit_mm=25.)
    s[engine.RESULT_KEY]=engine.calculate(s,source_curves(),20.)
    encoded=project_to_json(project_from_session_state(s))
    assert engine.RESULT_KEY not in encoded
    restored={engine.RESULT_KEY:{'old':True},'girder_deflect69_ui_stage':'Service stage'}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert engine.RESULT_KEY not in restored and 'girder_deflect69_ui_stage' not in restored
    assert engine.settings(restored)==engine.settings(s)


def test_result_summary_recognizes_stored_deflection_without_certifying_sls_or_rerunning():
    import app
    from concrete_pmm_pro.core.analysis import AnalysisModeSettings
    s=state(live_udl_kN_m=20.)
    s['analysis_mode_settings']=AnalysisModeSettings(member_type='beam_girder',analysis_workflow='bridge_beam_girder')
    # Match the app's normal workflow initialization before storing a result.
    app._results_governing_rows(s)
    s[engine.RESULT_KEY]=engine.calculate(s,source_curves(),20.)
    with patch.object(engine,'calculate',side_effect=AssertionError('rerun')):
        rows=app._results_governing_rows(s)
        assert len([r for r in rows if r['Module']=='SLS Deflection'])==5
        assert app._results_sls_available(s)
        assert not app._results_sls_complete_for_report(s)
        cards=app._results_sls_summary_cards(s)
        assert any(c['value']=='REVIEW REQUIRED' for c in cards)
