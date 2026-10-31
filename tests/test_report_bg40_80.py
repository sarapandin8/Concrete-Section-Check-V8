"""Source fidelity, read-only reports, stale exports and Word structure."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json
from zipfile import ZipFile
from unittest.mock import patch

from docx import Document
from docx.oxml.ns import qn
import pandas as pd
import pytest

from concrete_pmm_pro.reporting.bg40_data import (
    CHAPTERS, build_calculation_report, build_report_figure, source_signature,
)
from concrete_pmm_pro.reporting.bg40_word import build_bg40_word_report, build_evidence_zip
from concrete_pmm_pro.reporting.report_models import ReportMetadata
from concrete_pmm_pro.ui.bg40_report import ARTIFACT_KEY, artifact_is_current
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from test_igird_reportcharts8 import calculated_state


@pytest.fixture
def state(calculated_state):
    return deepcopy(calculated_state)


def text(document):
    body = [p.text for p in document.paragraphs]
    body.extend(c.text for t in document.tables for row in t.rows for c in row.cells)
    return '\n'.join(body)


def test_report_follows_reference_chapters_but_uses_active_values(state):
    r = build_calculation_report(state)
    assert [c.title for c in r.chapters] == list(CHAPTERS)
    assert r.chapters[0].tables[1].data.query("Parameter == 'fc_MPa'").Value.tolist() == ['45', '35']
    assert len(r.controls) == 8
    assert set(r.controls.Check) == {'Flexure','Shear','Torsion','Shear + Torsion'}
    assert not r.sources.empty
    assert r.chapters[7].status == 'NOT CALCULATED'
    assert r.status != 'PASS'
    for c in (r.chapters[5], r.chapters[6]):
        assert c.calculations
        assert all(x.reference for x in c.calculations)
    assert any('bonded' in n for n in r.chapters[5].notes)


def test_every_uls_input_and_result_cell_kept_without_new_envelopes(state):
    before = deepcopy(state)
    r = build_calculation_report(state)
    for member, checks in state[mr.CACHE_KEY].items():
        for check, entry in checks.items():
            from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS
            pd.testing.assert_frame_equal(r.raw_tables[check+' '+member], entry['result'][FRAME_KEYS[check]])
    assert source_signature(state) == source_signature(before)
    pd.testing.assert_frame_equal(state['beam_uls_loads_table'], before['beam_uls_loads_table'])


def test_report_does_not_call_solvers_or_activate_members(state):
    with patch.object(mr, 'calculate_member', side_effect=AssertionError('No report solve')), \
         patch.object(ap, '_beam_uls_calculate_selected_check', side_effect=AssertionError('No report solve')), \
         patch.object(ap, '_girder_full_length_sls_stage_rows', side_effect=AssertionError('No report stress solve')):
        r = build_calculation_report(state)
        for c in r.chapters:
            for spec in c.figures:
                assert build_report_figure(state, spec) is not None
        assert build_bg40_word_report(r, state, include_figures=False).startswith(b'PK')


def test_stale_member_results_are_excluded_not_relabelled_as_passing(state):
    state['section_parameters']['deck_fc_MPa'] = 42.
    r = build_calculation_report(state)
    assert all(c.status == 'NOT CALCULATED' for c in r.chapters[5:7])
    assert r.controls.Status.eq('NOT CALCULATED').all()
    assert not any(k.startswith('Flexure ') for k in r.raw_tables)


def test_report_controls_preserve_failure_and_source_blocks(state):
    target = state[mr.CACHE_KEY]['Exterior Girder']['Shear + Torsion']['result']['combined_vt_df']
    target.loc[target.index[0], 'Status'] = 'SOURCE BLOCKED'
    target.loc[target.index[-1], 'Status'] = 'FAIL'
    r = build_calculation_report(state)
    assert r.status == 'FAIL'
    assert r.controls.query("Member == 'Exterior Girder' and Check == 'Shear + Torsion'").Status.iloc[0] == 'FAIL'


def test_artifact_expires_after_input_result_and_metadata_changes(state):
    meta = ReportMetadata(project_name='Bridge')
    state[ARTIFACT_KEY] = {'signature': source_signature(state, meta, False, True)}
    assert artifact_is_current(state, meta, include_figures=False)
    assert not artifact_is_current(state, replace(meta, revision='R1'), include_figures=False)
    assert not artifact_is_current(state, meta, include_figures=True)
    state['some_navigation_view'] = 'other'
    assert artifact_is_current(state, meta, include_figures=False)
    state[mr.CACHE_KEY]['Exterior Girder']['Shear']['result']['shear_check_df'].loc[0, 'Status'] = 'SOURCE BLOCKED'
    assert not artifact_is_current(state, meta, include_figures=False)
    state[ARTIFACT_KEY]['signature'] = source_signature(state, meta, False, True)
    state['section_parameters']['deck_long_rebar_top_diameter_mm'] = 28.
    assert not artifact_is_current(state, meta, include_figures=False)


def test_word_has_native_equations_chapters_page_fields_and_repeating_tables(state):
    r = build_calculation_report(state)
    doc = Document(BytesIO(build_bg40_word_report(r, state, include_figures=False)))
    assert doc.sections[0].page_width.mm == pytest.approx(210, abs=.1)
    assert len([p for p in doc.paragraphs if p.style.name == 'Heading 1' and p.text.startswith('Chapter')]) == 10
    assert doc._element.findall('.//' + qn('m:oMath'))
    assert all(t.rows[0]._tr.find('.//' + qn('w:tblHeader')) is not None for t in doc.tables)
    assert 'BG40_Final_Complete_R10.docx' in text(doc)
    assert 'critical-perimeter' in text(doc).lower()
    from concrete_pmm_pro.reporting.bg40_template import document as template_document
    assert doc.sections[0].footer._element.xml == template_document().sections[0].footer._element.xml
    assert 'PAGEREF' in doc._element.xml


def test_archive_contains_all_source_rows_and_full_precision(state):
    r = build_calculation_report(state)
    data = build_evidence_zip(r, build_bg40_word_report(r, state, include_figures=False))
    with ZipFile(BytesIO(data)) as archive:
        p = json.loads(archive.read('Provenance.json'))
        assert p['solver_recalculation'] is False and p['full_punching_acceptance'] is False
        assert len([n for n in archive.namelist() if n.startswith('tables/')]) == len(r.raw_tables)
        assert pd.read_csv(BytesIO(archive.read('Source_Register.csv'))).shape[0] == len(r.sources)


def test_empty_project_has_no_invented_bg40_design_values():
    r = build_calculation_report({})
    assert r.status == 'REVIEW'
    assert not r.chapters[5].calculations
    assert r.chapters[5].status == 'NOT CALCULATED'
    assert r.sources.empty


def test_streamlit_report_build_and_stale_download_guard(state, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    from test_word_report_export import _one_pixel_png
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda figure, **kwargs: (_one_pixel_png(), []))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=120)
    for key, value in state.items():
        app.session_state[key] = value
    app.session_state['_nav_active_workspace'] = 'Report / QA'
    # Previous optional selections cannot disable the new complete default.
    app.session_state['bg40_80_figures'] = False
    app.run(timeout=120)
    assert not app.exception, [x.message for x in app.exception]
    next(b for b in app.button if b.key == 'bg40_80_build').click()
    with patch.object(mr, 'calculate_member', side_effect=AssertionError('No report solve')):
        app.run(timeout=120)
    assert not app.exception, [x.message for x in app.exception]
    assert app.session_state[ARTIFACT_KEY]['docx'].startswith(b'PK')
    assert not app.checkbox
    assert not any('Build Draft Word Report' == x.label for x in app.button)
    assert len([x for x in app.get('download_button') if x.key == 'bg40_80_download']) == 1
    next(x for x in app.text_input if x.key == 'bg40_80_revision').set_value('R9')
    app.run(timeout=120)
    assert not app.exception
    assert not [x for x in app.get('download_button') if x.key == 'bg40_80_download']
    assert any('STALE' in x.value and 'report' in x.value for x in app.warning)


def test_word_export_rejects_old_report_package_after_input_edit(state):
    r = build_calculation_report(state)
    state['section_parameters']['deck_fc_MPa'] = 50.
    with pytest.raises(ValueError, match='stale'):
        build_bg40_word_report(r, state, include_figures=False)


def test_current_sls_uses_stored_numeric_stress_and_stale_results_are_hidden(state):
    from concrete_pmm_pro.ui import igird_sls53_results as sls
    signature = sls.fingerprint(state)
    raw = pd.DataFrame({'Station x (m)': [0., 10., 20.], 'Case Name': ['S1']*3,
        'Top total (MPa)': [-3., -4., -3.], 'Bottom total (MPa)': [-2., 1., -2.]})
    check = {'Stage': 'Service stage', 'Case Name': 'S1', 'Controls': 'Tension',
        'Demand': 'Tension', 'Station x (m)': 10., 'Actual stress (MPa)': 1.,
        'Limit stress (MPa)': 2., 'Utilization': .5, 'Status': 'Preview PASS',
        'Limit profile source': 'Project verified stress criterion'}
    case = {'raw': raw, 'split': pd.DataFrame(), 'checks': [check],
        'limits': {'Precast beam': {'compression': 20., 'tension': [2., 2.], 'x': [0.,20.]}}}
    result = {'signature': signature, 'checks': [check], 'summary': [check],
        'member': 'SLS Girder', 'span_m': 20., 'code_label': 'Project code',
        'stages': {'Service stage': {'checks': [check], 'profile': 'Project criterion', 'cases': {'S1': case}}}}
    state[sls.RUNTIME_KEY] = result
    r = build_calculation_report(state)
    assert r.chapters[7].status == 'Preview PASS'
    assert 'σ=1 MPa' in r.chapters[7].calculations[0].substitution
    pd.testing.assert_frame_equal(r.raw_tables['SLS Service stage S1'], raw)
    state['girder_code_loss_fci_mpa'] = 12.
    stale = build_calculation_report(state)
    assert stale.chapters[7].status == 'STALE'
    assert not stale.chapters[7].calculations


def test_punching_local_index_never_becomes_perimeter_acceptance():
    from test_slab_punch76_auto import state as slab_state
    from concrete_pmm_pro.analysis import slab_review68 as slab
    s = slab_state()
    s[slab.RESULT_KEY] = slab.calculate(s)
    r = build_calculation_report(s)
    c = r.chapters[9]
    assert c.status == 'REVIEW'
    assert c.calculations and 'REVIEW' in c.calculations[-1].result
    assert 'Local index' in c.calculations[-1].formula
    assert 'Punching local source rows' in r.raw_tables
    assert any(f['kind'] == 'punching' for f in c.figures)
    for figure in c.figures:
        assert build_report_figure(s, figure) is not None
    assert not r.sources.empty
    s['section_parameters']['deck_fc_MPa'] = 55.
    assert build_calculation_report(s).chapters[9].status == 'STALE'


def test_original_word_styles_theme_and_margins_are_preserved(state):
    from pathlib import Path
    from concrete_pmm_pro.reporting.bg40_template import ROOT
    r = build_calculation_report(state)
    content = build_bg40_word_report(r,state,include_figures=False)
    with ZipFile(BytesIO(content)) as output, ZipFile(ROOT/'BG40_R10_Template.docx') as source:
        assert output.read('word/styles.xml') == source.read('word/styles.xml')
        assert output.read('word/theme/theme1.xml') == source.read('word/theme/theme1.xml')
    doc, template = Document(BytesIO(content)), Document(ROOT/'BG40_R10_Template.docx')
    for field in ('page_width','page_height','left_margin','right_margin','top_margin','bottom_margin','header_distance','footer_distance'):
        assert getattr(doc.sections[0],field) == getattr(template.sections[0],field)
    assert doc.paragraphs[0].text == 'TABLE OF CONTENTS'
    assert 'Track Doubling Project (Khon Kaen' not in text(doc)
    first = next(p for p in doc.paragraphs if p.text.startswith('Chapter 1 ') and p.style.name=='Heading 1')
    assert first.style.font.size == template.styles['Heading 1'].font.size


def test_each_design_part_has_source_graphs_and_necessary_sections(state):
    before = source_signature(state)
    r = build_calculation_report(state)
    assert {f['kind'] for f in r.chapters[1].figures} == {'system','debonding'}
    assert {f['kind'] for f in r.chapters[2].figures} == {'section','composite_section'}
    assert len([f for f in r.chapters[4].figures if f['kind']=='actions']) == 2
    for index in (5,6):
        assert any(f['kind']=='uls' for f in r.chapters[index].figures)
        assert any(f['kind']=='governing_section' for f in r.chapters[index].figures)
        for spec in r.chapters[index].figures:
            fig = build_report_figure(state,spec)
            assert fig is not None
            if spec['kind']=='governing_section':
                assert fig.layout.meta['strength_recalculated'] is False
    assert source_signature(state) == before


def test_all_embedded_graphs_are_registered_and_exported_with_report(state,monkeypatch):
    from test_word_report_export import _one_pixel_png
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda figure, **kwargs:(_one_pixel_png(),[]))
    r = build_calculation_report(state)
    content = build_bg40_word_report(r,state)
    assert len(Document(BytesIO(content)).inline_shapes) == sum(len(c.figures) for c in r.chapters)
    assert all(f['status']=='EMBEDDED' for f in r.figure_audit)
    for chapter in {f['chapter'] for f in r.figure_audit}:
        numbers = [int(f['number'].split('.')[1]) for f in r.figure_audit if f['chapter']==chapter]
        assert numbers == list(range(1,len(numbers)+1))
    with ZipFile(BytesIO(build_evidence_zip(r,content))) as output:
        register = json.loads(output.read('Figure_Register.json'))
        assert len([n for n in output.namelist() if n.startswith('figures/')]) == len(register)
        assert 'ProjectInputSnapshot.json' in output.namelist()



