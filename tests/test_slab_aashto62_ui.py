from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_shear64 as code,slab_aashto63 as base,slab_punching64 as punching
from concrete_pmm_pro.analysis import slab_shell56 as research
from concrete_pmm_pro.io.project_io import apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from concrete_pmm_pro.core.project import ProjectModel
from test_slab_shell56 import model_state

ROOT=Path(__file__).resolve().parents[1]


def seed(app):
    for key,value in model_state().items():
        app.session_state[key]=deepcopy(value)
    app.session_state['_nav_active_workspace']='Analysis'
    app.session_state['_nav_analysis_subpage']='Slab Reinforcement'


def test_actual_app_default_calculates_once_no_research_solver_and_keeps_all_views():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60);seed(app)
    def run():
        app.run(timeout=60)
        assert not app.exception,[e.message for e in app.exception]
    with patch.object(code,'calculate',wraps=code.calculate) as solver, patch.object(research,'calculate',side_effect=AssertionError('legacy ran')):
        run();assert solver.call_count==0
        assert not any(b.key=='slab_shell55_strength56_calculate' for b in app.button)
        next(b for b in app.button if b.key=='slab_shell55_aashto62_calculate').click();run()
        assert solver.call_count==1 and len(app.get('plotly_chart'))==1
        before=app.session_state[code.RESULT_KEY]['summary'].copy(deep=True)
        for view in code.VIEWS:
            group='One-way shear' if view.startswith(('Shear ·','Flexural shear tie ·')) else 'Reinforcement'
            next(r for r in app.radio if r.key=='slab_shell55_shear64_group').set_value(group);run()
            next(s for s in app.selectbox if s.key=='slab_shell55_aashto62_view').set_value(view);run()
            assert len(app.get('plotly_chart'))==1
        next(s for s in app.selectbox if s.key=='slab_shell55_aashto62_case').set_value('U1A');run()
        assert solver.call_count==1
        pd.testing.assert_frame_equal(before,app.session_state[code.RESULT_KEY]['summary'])
        assert 'slab_shell55_aashto62_csv_payload' not in app.session_state
        changed=deepcopy(app.session_state['section_parameters'])
        changed['deck_long_rebar_top_spacing_mm']=200
        app.session_state['section_parameters']=changed
        run()
        assert len(app.get('plotly_chart'))==0 and solver.call_count==1
        assert any('STALE' in text.value for text in app.info)


def test_new_project_transaction_clears_code_results_and_research_is_explicit():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60);seed(app)
    app.run(timeout=60)
    next(c for c in app.checkbox if c.key=='slab_shell55_aashto62_research_open').check()
    app.run(timeout=60)
    assert not app.exception
    assert any(b.key=='slab_shell55_strength56_calculate' for b in app.button)
    state=model_state();state[code.RESULT_KEY]=code.calculate(state)
    apply_project_to_session_state(ProjectModel(),state)
    assert code.RESULT_KEY not in state and BANK_KEY not in state


def test_punching_apply_form_keeps_navigation_and_reuses_oneway_base():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60);seed(app)
    with patch.object(base,'calculate',wraps=base.calculate) as solver:
        app.run()
        app.button(key='slab_shell55_aashto62_calculate').click().run()
        assert solver.call_count==1
        app.radio(key='slab_shell55_shear64_group').set_value('Punching shear').run()
        assert not app.exception and len(app.get('plotly_chart'))==1
        assert app.session_state[code.RESULT_KEY]['punching']['status']=='NOT CALCULATED'
        app.session_state['slab_shell55_punch64_editor']={'edited_rows':{},'deleted_rows':[],
            'added_rows':[dict(zip(punching.COLUMNS,['P1',.5,.5,200.,200.,10.]))]}
        next(b for b in app.button if b.label=='Apply load areas').click().run()
        assert not app.exception,[e.message for e in app.exception]
        assert punching.config({'project_metadata':app.session_state['project_metadata']})[0]['Area']=='P1'
        assert app.session_state['_nav_analysis_subpage']=='Slab Reinforcement'
        assert len(app.get('plotly_chart'))==0
        app.button(key='slab_shell55_aashto62_calculate').click().run()
        assert not app.exception,[e.message for e in app.exception]
        assert solver.call_count==1 and app.session_state[code.RESULT_KEY]['base_reused']
        assert len(app.get('plotly_chart'))==1
