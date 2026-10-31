"""Default complete calculation report; only stored evidence, no analysis command."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging

import pandas as pd
import streamlit as st

from concrete_pmm_pro.reporting.bg40_data import (
    build_report_figure, source_signature,
)
from concrete_pmm_pro.reporting.workflow_reports import build_workflow_report, workflow_key, LABELS
from concrete_pmm_pro.reporting.bg40_word import build_bg40_word_report, build_evidence_zip
from concrete_pmm_pro.reporting.report_models import ReportMetadata

ARTIFACT_KEY = '_bg40_report82_artifact'
ERROR_KEY = '_bg40_report82_error'
LOGGER = logging.getLogger(__name__)


def supports_complete_report(state):
    return workflow_key(state) in LABELS


def _text(value, default=''):
    if value is None or value is pd.NA:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    text = str(value).strip()
    return default if text.lower() in {'', 'nan', 'none', '<na>'} else text


def default_metadata(state):
    """Use project details automatically; optional edits do not require a form."""
    def value(widget, *keys, default=''):
        if widget in state:
            return _text(state.get(widget), default)
        return next((_text(state.get(k)) for k in keys if _text(state.get(k))), default)
    today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    return ReportMetadata(
        report_title=value('bg40_80_title', 'report_title', default='Structural Design Calculation'),
        project_name=value('bg40_80_project', 'project_name') or None,
        prepared_by=value('bg40_80_prepared', 'report_prepared_by', 'designer') or None,
        checked_by=value('bg40_80_checked', 'report_checked_by') or None,
        revision=value('bg40_80_revision', 'report_revision', default='Draft'),
        report_date=value('bg40_80_date', 'report_date', default=today),
        organization=_text(state.get('organization')) or None,
        project_number=_text(state.get('project_number')) or None,
        note=_text(state.get('report_note')) or None,
    )


def artifact_is_current(state, metadata, *, include_figures=True, include_appendices=True):
    saved = state.get(ARTIFACT_KEY)
    return bool(isinstance(saved, dict) and saved.get('signature') == source_signature(
        state, metadata, include_figures, include_appendices))


def build_complete_artifact(state, metadata, report=None):
    """The same full export is used by the UI, with no per-content switches."""
    report = report or build_workflow_report(state, metadata)
    docx = build_bg40_word_report(report, state, include_figures=True,
                                  include_appendices=True, require_all_figures=True)
    signature = source_signature(state, metadata)
    if signature != report.signature:
        raise ValueError('Report inputs changed during export. Build the current report again.')
    return {'signature': signature, 'docx': docx,
            'evidence': build_evidence_zip(report, docx),
            'figures': list(report.figure_audit), 'status': report.status,
            'chapters': len(report.chapters)}


def _report_details(state):
    metadata = default_metadata(state)
    with st.expander('Report details — optional', expanded=False):
        st.caption('Project details are filled automatically. These edits affect the report only.')
        st.text_input('Report title', value=metadata.report_title, key='bg40_80_title')
        st.text_input('Project name', value=metadata.project_name or '', key='bg40_80_project')
        a, b, c = st.columns(3)
        a.text_input('Prepared by', value=metadata.prepared_by or '', key='bg40_80_prepared')
        b.text_input('Checked by', value=metadata.checked_by or '', key='bg40_80_checked')
        c.text_input('Revision', value=metadata.revision, key='bg40_80_revision')
        st.text_input('Report date', value=metadata.report_date or '', key='bg40_80_date')
    return default_metadata(state)


def _render_preview(report, state, metadata):
    panel = st.expander('Report preview and source evidence', expanded=False,
        key='bg40_83_preview_open', on_change='rerun')
    if not panel.open:
        return
    with panel:
        try:
            report = report or build_workflow_report(state, metadata)
        except Exception as exc:
            LOGGER.exception('BG40 report preview failed')
            st.error('Report preview could not be loaded: ' + str(exc))
            return
        st.caption('Every available chapter, calculation, figure and source appendix is included automatically.')
        if report.warnings:
            for warning in report.warnings:
                st.warning(warning)
        st.dataframe(pd.DataFrame([{'Chapter': c.number, 'Title': c.title,
            'Status': c.status, 'Figures': len(c.figures)} for c in report.chapters]),
            hide_index=True, width='stretch')
        index = st.selectbox('Chapter to preview', list(range(len(report.chapters))),
            format_func=lambda i: f'{i+1}. {report.chapters[i].title}', key='bg40_80_chapter')
        chapter = report.chapters[index]
        st.markdown(f'#### Chapter {chapter.number} {chapter.title}')
        for note in chapter.notes:
            st.write(note)
        for table in chapter.tables:
            st.markdown('**' + table.title + '**')
            st.caption('Source: ' + table.source)
            if len(table.data) > 200:
                st.caption(f'Preview: first 200 of {len(table.data):,} rows. The complete Word report and source evidence retain all rows.')
            st.dataframe(table.data.head(200), hide_index=True, width='stretch')
        for calc in chapter.calculations:
            st.markdown('**' + calc.title + '**')
            st.caption('Reference: ' + calc.reference)
            st.text(calc.formula)
            if calc.substitution:
                st.text(calc.substitution)
            st.write('Result: ' + calc.result)
        if chapter.figures:
            which = st.selectbox('Figure to preview', list(range(len(chapter.figures))),
                format_func=lambda i: chapter.figures[i]['title'], key='bg40_80_figure_' + str(index))
            if st.button('Show stored report figure', key='bg40_80_show_figure'):
                figure = build_report_figure(state, chapter.figures[which])
                if figure is not None:
                    st.plotly_chart(figure, width='stretch', key='bg40_80_chart')


def render(state):
    if not supports_complete_report(state):
        return
    st.markdown('## Calculation Report')
    st.caption('BG40 R10 Word format · all chapters, equations, figures and source appendices included automatically.')
    metadata = _report_details(state)
    st.caption('Stored Analysis results are checked when creating the report. Opening this page does not build the document or its charts.')
    st.warning('Report export does not confirm engineering acceptance. FAIL, REVIEW, STALE, missing checks and source scope limitations are retained; missing checks are not calculated here.')
    report = None
    try:
        current = artifact_is_current(state, metadata)
    except Exception as exc:
        LOGGER.exception('BG40 report currency check failed')
        state[ERROR_KEY] = str(exc)
        current = False
    label = 'Rebuild complete Word report' if current else 'Create complete Word report'
    if st.button(label, type='secondary' if current else 'primary',
                 width='stretch', key='bg40_80_build'):
        # Release the previous export before allocating a replacement. Never
        # retain a failed replacement as an apparently complete download.
        state.pop(ARTIFACT_KEY, None)
        current = False
        try:
            with st.spinner('Preparing the complete report and all figures…'):
                report = build_workflow_report(state, metadata)
                state[ARTIFACT_KEY] = build_complete_artifact(state, metadata, report)
            state.pop(ERROR_KEY, None)
            current = True
        except Exception as exc:
            LOGGER.exception('BG40 complete report export failed')
            state[ERROR_KEY] = str(exc)
    if state.get(ERROR_KEY):
        st.error('The complete report could not be created. Retry after resolving the export error below. '
                 'A report with missing figures is not offered as a complete download.')
        with st.expander('Export error details', expanded=False):
            st.text(state[ERROR_KEY])
    if current:
        saved = state[ARTIFACT_KEY]
        st.download_button('Download complete Word report (.docx)', saved['docx'],
            file_name='Concrete_Section_Pro_Calculation_Report_BG40.docx',
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            key='bg40_80_download', type='primary', width='stretch', on_click='ignore')
        st.caption(f"Complete Word file prepared · {len(saved['figures'])} figures embedded · BG40 R10 layout.")
        st.caption('Engineering status: ' + saved['status'])
        with st.expander('Additional download — source evidence', expanded=False):
            st.download_button('Download report and source evidence (.zip)', saved['evidence'],
                file_name='Concrete_Section_Pro_Report_Evidence_BG40.zip',
                mime='application/zip', key='bg40_80_evidence', width='stretch', on_click='ignore')
    elif state.get(ARTIFACT_KEY):
        st.warning('STALE — report inputs, stored results or report details changed. Create the complete Word report again before downloading.')
    _render_preview(report, state, metadata)
