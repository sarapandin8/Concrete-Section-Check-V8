"""Complete default exports, print fidelity and actionable failure handling."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile
import json

from docx import Document
import pandas as pd
import plotly.graph_objects as go
import pytest

from concrete_pmm_pro.reporting.bg40_data import build_calculation_report, source_signature
from concrete_pmm_pro.reporting.bg40_print import prepare_print_figure
from concrete_pmm_pro.reporting.bg40_word import ReportFigureError
from concrete_pmm_pro.ui.bg40_report import (
    ARTIFACT_KEY, build_complete_artifact, default_metadata, supports_complete_report,
)
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from test_igird_reportcharts8 import calculated_state
from test_word_report_export import _one_pixel_png


@pytest.fixture
def state(calculated_state):
    return deepcopy(calculated_state)


def test_metadata_is_automatic_and_missing_fields_do_not_print_nan():
    meta = default_metadata({'project_name': 'Bridge 1', 'designer': 'Engineer',
        'report_checked_by': float('nan'), 'report_revision': pd.NA,
        'report_date': 'nan'})
    assert meta.project_name == 'Bridge 1'
    assert meta.prepared_by == 'Engineer'
    assert meta.checked_by is None
    assert meta.revision == 'Draft'
    assert meta.report_date and meta.report_date != 'nan'
    edited = default_metadata({'project_name': 'Bridge 1', 'bg40_80_project': 'Report project'})
    assert edited.project_name == 'Report project'


def test_print_figures_preserve_source_values_and_move_notes_outside_bitmap():
    figure = go.Figure(go.Scatter(x=[0, 10, 20], y=[0, 23.456789, 0], name='Vu'))
    figure.update_layout(meta={'igird_report_note': ['Case <b>ULS1</b>', 'D/C 1.03: FAIL'],
        'source_case': 'ULS1'}, annotations=[dict(x=0, y=0, text='long note', name='igird_report_note')])
    before = figure.to_json()
    printed = prepare_print_figure(figure, {'kind': 'uls', 'caption': 'Stored source.'})
    assert list(printed.figure.data[0].y) == [0, 23.456789, 0]
    assert printed.figure.layout.meta['source_case'] == 'ULS1'
    assert 'Case ULS1' in printed.caption and 'D/C 1.03: FAIL' in printed.caption
    assert not printed.figure.layout.annotations
    assert figure.to_json() == before
    section = go.Figure(figure)
    section.update_layout(annotations=[dict(x=.5, y=-.16, xref='paper', yref='paper',
        text='Stored dv=1328.2304076932908 mm; bv=None<br>Zone=Midspan; spacing=200 mm')])
    source = section.to_json()
    presentation = prepare_print_figure(section, {'kind': 'governing_section'})
    assert '1328.2304076932908' in presentation.caption
    assert 'Zone=Midspan; spacing=200 mm' in presentation.caption
    assert 'bv=Not available' in presentation.caption
    assert not presentation.figure.layout.annotations
    assert section.to_json() == source


def test_debonding_and_slab_print_changes_preserve_distances_and_rebar():
    figure = go.Figure(go.Scatter(x=[-10, 10], y=[20, 20], name='Rebar'))
    figure.update_layout(annotations=[dict(text='1000 mm from left', x=1, y=1)],
                        shapes=[dict(type='rect', x0=-20, x1=20, y0=0, y1=40)])
    strand = prepare_print_figure(figure, {'kind': 'debonding'})
    assert '1000 mm from left' in strand.caption
    assert not strand.figure.layout.annotations
    slab = prepare_print_figure(figure, {'kind': 'slab_section'})
    assert slab.figure.layout.shapes[0].layer == 'below'
    assert list(slab.figure.data[0].y) == [20, 20]


def test_complete_default_includes_every_available_figure_equation_and_appendix(state, monkeypatch):
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda figure, **kwargs: (_one_pixel_png(), []))
    # Old session options must not opt the user out of complete reporting.
    state.update(bg40_80_figures=False, report_include_figures=False,
                 report_include_appendices=False, report_max_table_rows=5)
    metadata = default_metadata(state)
    report = build_calculation_report(state, metadata)
    before = source_signature(state, metadata)
    with patch.object(mr, 'calculate_member', side_effect=AssertionError('No report solve')), \
         patch.object(ap, '_beam_uls_calculate_selected_check', side_effect=AssertionError('No report solve')), \
         patch.object(ap, '_girder_full_length_sls_stage_rows', side_effect=AssertionError('No report stress solve')):
        artifact = build_complete_artifact(state, metadata, report)
    doc = Document(BytesIO(artifact['docx']))
    assert len(doc.inline_shapes) == sum(len(c.figures) for c in report.chapters) > 0
    assert doc._element.xpath('.//m:oMath')
    assert 'Appendix A Source Register' in '\n'.join(p.text for p in doc.paragraphs)
    assert all(x['status'] == 'EMBEDDED' for x in artifact['figures'])
    assert source_signature(state, metadata) == before
    with ZipFile(BytesIO(artifact['evidence'])) as archive:
        assert archive.read('Calculation_Report_BG40.docx') == artifact['docx']
        assert len(json.loads(archive.read('Figure_Register.json'))) == len(doc.inline_shapes)
        assert len([n for n in archive.namelist() if n.startswith('tables/')]) == len(report.raw_tables)


def test_complete_download_is_not_created_when_png_export_fails(state, monkeypatch):
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda figure, **kwargs: (None, ['Static renderer unavailable']))
    with pytest.raises(ReportFigureError, match='could not be embedded'):
        build_complete_artifact(state, default_metadata(state))
    assert ARTIFACT_KEY not in state


def test_plain_calculation_notes_are_not_misparsed_as_math(state, monkeypatch):
    from concrete_pmm_pro.reporting.bg40_word import build_bg40_word_report
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda figure, **kwargs: (_one_pixel_png(), []))
    report = build_calculation_report(state)
    doc = Document(BytesIO(build_bg40_word_report(report, state)))
    math = [x.text for x in doc._element.xpath('.//m:t')]
    assert not any('from one physical row/case' in x or '; actual Vu in' in x for x in math)
    assert 'Mu, Nu, Vu, Tu from one physical row/case' in '\n'.join(p.text for p in doc.paragraphs)


def test_complete_export_is_available_for_every_workflow():
    assert supports_complete_report({'section_preset_key': 'parametric_i_girder'})
    assert supports_complete_report({'section_preset_key': 'railway_u_girder'})
    assert supports_complete_report({})


def test_missing_source_labels_print_readably_without_editing_source_data(state):
    from concrete_pmm_pro.reporting.bg40_word import build_bg40_word_report
    rows = state['girder_strand_layout_table']
    rows.loc[rows.index[0], 'Note'] = 'nan'
    before = rows.copy(deep=True)
    report = build_calculation_report(state)
    doc = Document(BytesIO(build_bg40_word_report(report, state, include_figures=False)))
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert 'nan' not in cells
    assert 'Not available' in cells
    assert all(p.paragraph_format.keep_with_next for t in doc.tables for c in t.rows[0].cells for p in c.paragraphs)
    pd.testing.assert_frame_equal(state['girder_strand_layout_table'], before, check_exact=True)


def test_streamlit_failed_export_shows_error_without_a_download(state, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr('concrete_pmm_pro.ui.bg40_report.build_complete_artifact',
                        lambda *args, **kwargs: (_ for _ in ()).throw(ReportFigureError('Required figure failed')))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=120)
    for key, value in state.items():
        app.session_state[key] = value
    app.session_state['_nav_active_workspace'] = 'Report / QA'
    app.run(timeout=120)
    next(x for x in app.button if x.key == 'bg40_80_build').click().run(timeout=120)
    assert not app.exception, [x.message for x in app.exception]
    assert any('complete report could not be created' in x.value for x in app.error)
    assert not [x for x in app.get('download_button') if x.key == 'bg40_80_download']
