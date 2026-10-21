"""Single-command import workflow and view-only girder/stage navigation."""
from io import BytesIO
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io import girder_deflect70 as importer
from concrete_pmm_pro.serviceability import girder_deflect70 as engine
from test_girder_deflect70 import FIXTURE


def app_code():
    return '''from concrete_pmm_pro.ui.girder_deflect70 import render
from test_girder_deflect69 import source_curves
render(build_curves=source_curves,span_m=20.)
'''


def upload(payload=None):
    f = BytesIO(FIXTURE.read_bytes() if payload is None else payload)
    f.name = 'SLS deflection.xlsx'
    return f


def test_upload_two_girders_one_calculate_and_view_changes_do_not_rerun():
    with patch('concrete_pmm_pro.ui.girder_deflect70.st.file_uploader',return_value=upload()), \
         patch.object(engine,'calculate',wraps=engine.calculate) as solver:
        app = AppTest.from_string(app_code(),default_timeout=60).run()
        assert not app.exception and solver.call_count == 0
        app.button(key='girder_deflect70_calculate').click().run()
        assert not app.exception,[e.message for e in app.exception]
        assert solver.call_count == 1 and len(app.get('plotly_chart')) == 1
        app.radio(key='girder_deflect70_ui_stage').set_value('Service stage').run()
        app.selectbox(key='girder_deflect70_ui_girder').set_value('Interior Girder 2').run()
        assert not app.exception,[e.message for e in app.exception]
        assert solver.call_count == 1 and len(app.get('plotly_chart')) == 1
        assert app.session_state[engine.RESULT_KEY]['girders'] == ['Left Exterior Girder','Interior Girder 2']
        assert not any('Service LL+IM per girder' in n.label for n in app.number_input)


def test_failed_replacement_is_visible_and_clear_x_removes_the_input_bank():
    app = AppTest.from_string(app_code(),default_timeout=60)
    with patch('concrete_pmm_pro.ui.girder_deflect70.st.file_uploader',return_value=upload()):
        app.run();app.button(key='girder_deflect70_calculate').click().run()
    original = app.session_state[importer.BANK_KEY]
    with patch('concrete_pmm_pro.ui.girder_deflect70.st.file_uploader',return_value=upload(b'bad zip')):
        app.run()
        assert not app.exception and app.error
        assert app.session_state[importer.BANK_KEY] == original
        assert engine.current(app.session_state.filtered_state) is None
        app.button(key='girder_deflect70_calculate').click().run()
        assert not app.session_state[engine.RESULT_KEY]['service_available']
    with patch('concrete_pmm_pro.ui.girder_deflect70.st.file_uploader',return_value=None):
        app.run()
        assert not app.exception and importer.BANK_KEY not in app.session_state.filtered_state
        assert importer.ERROR_KEY not in app.session_state.filtered_state
