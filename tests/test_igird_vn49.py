"""Vn focus, missing-x regression, safe reuse and accepted-response equivalence."""
from copy import deepcopy
from pathlib import Path
import json
from unittest.mock import patch,MagicMock
import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_flexure_development import SectionEquilibrium
from concrete_pmm_pro.analysis.igird_equilibrium49 import CachedSectionEquilibrium
from concrete_pmm_pro.analysis.igird_station36_steel import strand_ties
from concrete_pmm_pro.analysis import igird_composite_steel45 as engine
from concrete_pmm_pro.core.analysis import AnalysisInput
from concrete_pmm_pro.ui import igird_shear49 as view,igird_composite_steel45 as model
from concrete_pmm_pro.ui.igird_case_review import controlling_result


def fixture():
    return json.loads((Path(__file__).parent/'data/igird_equilibrium49_reference.json').read_text())


def test_optimized_section_matches_148_accepted_geometry_and_steel_responses():
    data=fixture();ai=AnalysisInput.model_validate(data['analysis_input']);contexts={s:SectionEquilibrium(ai,s) for s in (-1.,1.)}
    for row in data['cases']:
        result=contexts[row['sign']].evaluate(row['c_mm'],**row['limits'])
        for key,value in row['expected'].items():assert result[key]==pytest.approx(value,rel=1e-12,abs=1e-6)


def test_exact_response_cache_separates_limits_and_does_not_leak_result_mutation():
    ai=AnalysisInput.model_validate(fixture()['analysis_input']);ctx=CachedSectionEquilibrium(ai,1.);plain=SectionEquilibrium(ai,1.)
    first=ctx.evaluate(100.);first['Pn_N']=0.;first['fps_MPa'][0]=0.
    assert ctx.evaluate(100.)==plain.evaluate(100.)
    assert ctx.evaluate(100.,bar_factors=[0.]*6)==plain.evaluate(100.,bar_factors=[0.]*6)
    assert len(ctx._responses)==2
    for nu in (-200e3,0.,200e3):
        assert ctx.solve(nu)['Mn_Nmm']==pytest.approx(plain.solve(nu)['Mn_Nmm'],rel=1e-12)


def test_pooled_strand_inventory_does_not_require_or_infer_transverse_positions():
    from test_igird_uls6_torsion_general_procedure import _state
    table=_state()['girder_strand_layout_table'];settings={}
    kwargs=dict(x_m=10.,span_m=20.,y_min_mm=0.,depth_mm=1600.,fy_tie_MPa=390.,settings=settings)
    absent=strand_ties(table,require_x_positions=False,**kwargs)
    assert absent and all(r['x_mm'] is None for r in absent)
    assert all(r['spatial_position_verified'] is False for r in absent)
    with pytest.raises(ValueError,match='Explicit strand x'):strand_ties(table,**kwargs)
    known=table.copy();known['Strand x positions mm']=[','.join(str(i*10) for i in range(int(known.iloc[0]['No. Strands'])))]
    explicit=strand_ties(known,**kwargs)
    assert sum(r['capacity_N'] for r in absent)==sum(r['capacity_N'] for r in explicit)


def test_shared_model_reuses_exact_inputs_across_checks_and_rejects_changed_load():
    from test_igird_csiref26 import seed,bound_row
    from test_igird_uls6_torsion_general_procedure import _route
    state=seed();rows=pd.DataFrame([bound_row()]);saved={'enabled':True,'version':engine.VERSION,'rows':[]}
    with patch.object(model,'calculate',return_value=saved) as compute:
        first=model.payload(state,rows,route=_route())
        model.detach_review(state,first,fingerprint='shear')
        assert model.payload(state,rows.copy(),route=_route())[model.KEY] is first[model.KEY]
        assert compute.call_count==1
        changed=rows.copy();changed['Vuy']+=1.
        model.payload(state,changed,route=_route())
        assert compute.call_count==2


def test_capacity_cap_does_not_override_demand_ratio_but_violations_still_govern():
    frame=pd.DataFrame([{'Case':'A','Station type':'LOAD STATION','Governing x':'2 m','Status':'REVIEW',
        'Strength D/C value':.6,'Vn limit D/C':.945},
        {'Case':'B','Station type':'LOAD STATION','Governing x':'3 m','Status':'REVIEW',
        'Strength D/C value':.8,'Vn limit D/C':.945}])
    control=controlling_result(frame,'Shear');assert control['row']['Case']=='B' and control['ratio']==.8
    frame.loc[0,'Vn limit D/C']=1.1
    assert controlling_result(frame,'Shear')['component']=='Vn upper limit'


def snapshot():
    w={'ready':True,'core_V_N':800000.,'U_V_N':200000.,'active_limits':['shared concrete flow budget']}
    calc={'model_Vn_kN':1100.,'model_V_only_actual_MN_kN':1000.,'model_V_only_actual_MN_DC':.5,
        'V_fixed_MN':w,'V':w,'supplies':{'core_dv_mm':1300.}}
    item={'Girder':'I2','Case':'U2A','Source StepType':'Min','Source location type':'Before','Source Excel row':491,
        'x (m)':2.,'actions':{'vu_N':-500000.},'calculation':calc,'Governing action':'V','inventory':[]}
    other={**item,'x (m)':18.,'Governing action':'VT'}
    return {'enabled':True,'rows':[other],'governing_rows':[item,other],
        'coverage':[{'Calculated rows':2,'Interior source rows':2,'Blocked / incomplete rows':0}],
        'station_rows':[{'x (m)':2.,'V-only D/C, actual M/N':.5,'V-only capacity (kN), actual M/N':1000.,'Actions used':{'vu_N':-500000.},'Source Excel row':491},
            {'x (m)':2.,'V-only D/C, actual M/N':.2,'V-only capacity (kN), actual M/N':1200.,'Actions used':{'vu_N':240000.},'Source Excel row':492}],
        'excluded_rows':[{'x (m)':0.},{'x (m)':20.}]}


def test_shear_overview_uses_v_governor_and_paired_values_without_torsion_columns():
    result=snapshot();row=view.summary_row(result,'I2')
    assert row['x (m)']==2. and row['Nominal V D/C']==.5
    assert not any('Tn' in key or 'V–T' in key for key in row)
    picked=view.station_pairs(result);assert len(picked)==1 and picked[0]['Source Excel row']==491
    fig=view.make_shear_figure(result,member='I2')
    assert list(fig.data[0].y)==[500.] and list(fig.data[1].y)==[1000.]
    assert list(fig.layout.xaxis.range)==[0.,20.]
    assert sum(view.contribution_frame(view.governor(result)).iloc[:2]['Allocated V (kN)'])==1000.


def test_missing_shear_results_render_no_empty_capacity_cards():
    with patch('streamlit.info') as info,patch('concrete_pmm_pro.ui.analysis_page._render_analysis_summary_strip') as cards:
        view.render({'station_rows':[]},member='I2')
    assert info.called and not cards.called
