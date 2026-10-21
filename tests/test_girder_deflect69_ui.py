"""One calculation, view-only stage changes, and visible source qualification."""
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.serviceability import girder_deflect69 as engine


def test_one_command_stage_navigation_and_report_are_read_only():
    code='''import streamlit as st
from concrete_pmm_pro.ui.girder_deflect69 import render
from test_girder_deflect69 import source_curves
render(build_curves=source_curves,span_m=20.)
'''
    app=AppTest.from_string(code,default_timeout=60)
    with patch.object(engine,'calculate',wraps=engine.calculate) as solver:
        app.run()
        assert not app.exception and solver.call_count==0
        assert len([b for b in app.button if b.label=='Calculate deflection / camber'])==1
        app.button(key='girder_deflect69_calculate').click().run()
        assert not app.exception,[e.message for e in app.exception]
        assert solver.call_count==1
        assert len(app.get('plotly_chart'))==1
        assert any('no live-load component' in item.value for item in app.warning)
        for stage in ['Construction stage','Service stage','Transfer stage']:
            app.radio(key='girder_deflect69_ui_stage').set_value(stage).run()
            assert not app.exception,[e.message for e in app.exception]
            assert len(app.get('plotly_chart'))==1 and solver.call_count==1
        assert app.session_state[engine.RESULT_KEY]['status']=='REVIEW REQUIRED'
