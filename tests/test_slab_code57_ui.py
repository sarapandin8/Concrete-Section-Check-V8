from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_code57 import FLEXURE_VIEW,MINIMUM_VIEW
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from test_slab_shell56 import model_state

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('membrane_free',[True,False])
def test_code_views_review_existing_calculation_without_steel_change_or_rerun(membrane_free):
    state=model_state()
    if membrane_free:state[BANK_KEY].tables['forces'][['F11','F22','F12']]=0.
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
    for key,value in state.items():app.session_state[key]=deepcopy(value)
    app.session_state['_nav_active_workspace']='Analysis'
    app.session_state['_nav_analysis_subpage']='Slab Reinforcement'
    def run():
        app.run(timeout=60)
        assert not app.exception,[x.message for x in app.exception]
    with patch.object(engine,'calculate',wraps=engine.calculate) as solver:
        run()
        next(b for b in app.button if b.key=='slab_shell55_strength56_calculate').click();run()
        result=app.session_state[engine.RESULT_KEY]
        original=result['summary'].copy(deep=True)
        for view in (FLEXURE_VIEW,MINIMUM_VIEW,'Overall section'):
            next(s for s in app.selectbox if s.label=='Result to review').set_value(view);run()
            assert solver.call_count==1
            assert len(app.get('plotly_chart'))==1
            pd.testing.assert_frame_equal(app.session_state[engine.RESULT_KEY]['summary'],original)
        assert any(e.label=='What controls / All-case check breakdown' for e in app.expander)
        assert any(e.label=='Code flexure / Minimum reinforcement reference' for e in app.expander)
        assert any('Controlling check' in x.value for x in app.markdown)
