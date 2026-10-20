from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY, PENDING_KEY
from concrete_pmm_pro.visualization.slab_shell56 import plan_figure,element_envelope,view_column,ALL_CASES
from test_slab_shell56 import model_state

ROOT=Path(__file__).resolve().parents[1]


def test_unresolved_shear_cannot_be_hidden_by_a_larger_passing_numeric_record():
    r=engine.calculate(model_state())
    rows=r['rows'];indices=rows.index[rows['AreaElem']=='1-1']
    rows['Field D/C']=.5;rows['Status']='Preview PASS'
    rows.loc[indices[0],'Field D/C']=.1;rows.loc[indices[0],'Status']='REVIEW'
    selected=element_envelope(r)
    assert selected.loc['1-1','Status']=='REVIEW' and pd.isna(selected.loc['1-1','Map D/C'])
    rows.loc[indices[1],'Field D/C']=1.1;rows.loc[indices[1],'Status']='Preview FAIL'
    selected=element_envelope(r)
    assert selected.loc['1-1','Map D/C']==1.1


def test_plan_retains_full_mesh_true_governing_corner_and_peak_value():
    r=engine.calculate(model_state())
    r['rows']['Field D/C']=.5
    row=r['rows'].iloc[0].name
    r['rows'].loc[row,'Field D/C']=32.5;r['rows'].loc[row,'Status']='Preview FAIL'
    fig=plan_figure(r)
    assert fig.layout.meta['aggregation'].startswith('maximum source corner')
    assert not fig.layout.annotations
    trace=next(t for t in fig.data if t.name.startswith('Gov.'))
    assert trace.x[0]==r['rows'].loc[row,'X (m)'] and trace.y[0]==r['rows'].loc[row,'Y (m)']
    assert '32.500' in trace.name and trace.cliponaxis is False
    scale=next(t for t in fig.data if t.marker.showscale)
    assert float(scale.marker.color[-1])==np.log1p(32.5)
    # Nonzero V now explicitly leaves interaction at REVIEW. Its grey polygon
    # is still part of the complete mesh and must not be mistaken for a hole.
    polygons=[t for t in fig.data if t.name in ('Element envelope','Review / missing')]
    assert sum(np.isfinite(np.asarray(t.x,dtype=float)).sum() for t in polygons)==10  # 2 closed quadrilaterals, five coordinates each


def test_partial_source_is_visible_as_partial_not_an_averaged_complete_map():
    state=model_state()
    state[BANK_KEY].tables['forces']=state[BANK_KEY].tables['forces'].iloc[1:].copy()
    r=engine.calculate(state)
    assert r['incomplete'] and r['coverage']['Missing records'].sum()==1
    selected=element_envelope(r)
    assert selected.loc['1-1','Map incomplete']


def test_actual_calculate_filters_stale_inputs_and_json_restore():
    state=model_state()
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
    for k,v in state.items():app.session_state[k]=deepcopy(v)
    app.session_state['_nav_active_workspace']='Analysis'
    app.session_state['_nav_analysis_subpage']='Slab Reinforcement'
    # REVIEW61 is now an explicitly opened case-study workspace.
    app.session_state['slab_shell55_aashto62_research_open']=True
    def run():
        app.run(timeout=60)
        assert not app.exception,[x.message for x in app.exception]
    with patch.object(engine,'calculate',wraps=engine.calculate) as solver:
        run();assert solver.call_count==0
        button=next(b for b in app.button if b.key=='slab_shell55_strength56_calculate')
        assert not button.disabled
        button.click();run();assert solver.call_count==1
        result=app.session_state[engine.RESULT_KEY]
        summary=result['summary'].copy(deep=True)
        next(s for s in app.selectbox if s.label=='Result to review').set_value('Top longitudinal');run()
        next(s for s in app.selectbox if s.label=='Load case to review').set_value('U1A');run()
        assert solver.call_count==1
        pd.testing.assert_frame_equal(app.session_state[engine.RESULT_KEY]['summary'],summary)
        assert len(app.get('plotly_chart'))==1
        changed=deepcopy(app.session_state['section_parameters'])
        changed['deck_long_rebar_top_spacing_mm']=200
        app.session_state['section_parameters']=changed
        run();assert solver.call_count==1
        assert not app.get('plotly_chart')
        assert any('STALE' in i.value for i in app.info)
        button=next(b for b in app.button if b.key=='slab_shell55_strength56_calculate')
        button.click();run();assert solver.call_count==2
        # Navigation to Loads retains the current result but never invokes the engine.
        next(b for b in app.button if b.key=='slab_shell55_to_loads').click();run()
        assert solver.call_count==2 and app.session_state['_nav_loads_subpage']=='Slab Shell Results'


def test_input_hash_tracks_fc_steel_and_import_selection_but_not_case_view():
    state=model_state();r=engine.calculate(state);state[engine.RESULT_KEY]=r
    assert engine.current(state) is r
    state['slab_shell55_strength56_view']='One-way shear'
    assert engine.current(state) is r
    state[PENDING_KEY]=('new file',)
    assert engine.current(state) is None
    state[PENDING_KEY]=state[BANK_KEY].signature
    state['section_parameters']['deck_fc_MPa']=40
    assert engine.current(state) is None


def test_project_json_keeps_inputs_only_after_slab_calculation():
    from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,apply_project_to_session_state
    from concrete_pmm_pro.core.project import ProjectModel
    state=model_state();state[engine.RESULT_KEY]=engine.calculate(state)
    text=project_to_json(project_from_session_state(state))
    assert engine.RESULT_KEY not in text and 'Equilibrium residual' not in text
    apply_project_to_session_state(ProjectModel(),state)
    assert engine.RESULT_KEY not in state and BANK_KEY not in state
