"""A4 calculation report in the supplied BG40 chapter and calculation style."""
from __future__ import annotations

from dataclasses import asdict
from io import BytesIO, TextIOWrapper
import json
import posixpath
import re
from shutil import copyfileobj
import textwrap
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from lxml import etree

from .bg40_data import CalculationReport, build_report_figure, display, source_signature, VERSION, REFERENCE
from .figure_export import plotly_figure_to_png_bytes, static_image_export_session
from .bg40_print import prepare_print_figure
from . import bg40_template as reference


class ReportFigureError(ValueError):
    """A complete report cannot be offered with missing required figures."""


def _xml(parent, tag, **attrs):
    element = OxmlElement(tag)
    for name, value in attrs.items():
        element.set(qn(name.replace('__', ':')), str(value))
    parent.append(element)
    return element


def _field(paragraph, instruction):
    return _xml(paragraph._p, 'w:fldSimple', w__instr=instruction)


def _defaults(doc, report):
    # The supplied Word document owns these settings. Do not recreate styles.
    _xml(doc.settings._element, 'w:updateFields', w__val='true')
    reference.update_header(doc, report)


def _para(doc, text, *, bold=False, role='body'):
    p = doc.add_paragraph()
    p.add_run(str(text))
    reference.paragraph_format(p, role)
    if bold:
        for run in p.runs:
            run.bold = True
    p.paragraph_format.widow_control = True
    return p


def _cell_text(cell, value, *, header=False):
    cell.text = display(value)
    reference.cell_format(cell, header)


def _column_groups(columns, repeat_columns=None):
    if len(columns) <= 7:
        return [columns]
    if repeat_columns:
        identity = [c for c in repeat_columns if c in columns][:3]
        others = [c for c in columns if c not in identity]
        size = max(2, 7-len(identity))
        return [[*identity, *others[i:i+size]] for i in range(0,len(others),size)]
    # Repeat source identity when wider audit schemas need another panel.
    preferred = ['Case', 'Case Name', 'Stage', 'Girder', 'Group ID', 'ID', 'Parameter', 'Mat']
    identity = next((c for c in preferred if c in columns), columns[0])
    others = [c for c in columns if c != identity]
    return [[identity, *others[i:i+5]] for i in range(0, len(others), 5)]


def _table(doc, data, title, source):
    if data.empty:
        return
    for panel, columns in enumerate(_column_groups(list(data.columns), data.attrs.get('report_repeat_columns')), 1):
        caption = title + (f' part {panel}' if len(data.columns) > 7 else '')
        p = _para(doc, caption, bold=True)
        p.paragraph_format.keep_with_next = True
        table = doc.add_table(rows=1, cols=len(columns))
        reference.table_properties(table)
        table.autofit = False
        weights = []
        for col in columns:
            lengths = [len(display(x)) for x in data[col].tolist()]
            weight = min(3.4, max(.8, (max([len(str(col)), *lengths]) ** .5) / 4))
            if str(col).lower() in {'status', 'd/c', 'unit'}:
                weight = 1.
            weights.append(weight)
        section = doc.sections[0]
        available = section.page_width - section.left_margin - section.right_margin
        widths = [int(available * w / sum(weights)) for w in weights]
        for col, width in zip(table.columns, widths):
            col.width = width
        header = table.rows[0]
        _xml(header._tr.get_or_add_trPr(), 'w:tblHeader')
        for cell, col, width in zip(header.cells, columns, widths):
            cell.width = width
            _cell_text(cell, str(col), header=True)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True
            cell.width = width
        for values in data[columns].itertuples(index=False, name=None):
            row = table.add_row()
            _xml(row._tr.get_or_add_trPr(), 'w:cantSplit')
            for cell, value, width in zip(row.cells, values, widths):
                _cell_text(cell, value)
                cell.width = width
        if source:
            p = _para(doc, 'Source: ' + source)
            p.paragraph_format.space_after = Pt(9)
            for r in p.runs:
                r.italic = True


def _equation(doc, text):
    """Native editable Word math, wrapped into physically bounded lines."""
    if not text:
        return
    # Prose such as "from" and "in" is parsed as math syntax by Word/PDF
    # converters. Keep those source explanations as ordinary readable text.
    if 'from one physical row/case' in text or text.strip() == 'lower bound':
        _para(doc, text)
        return
    if '; actual Vu in' in text:
        expression, explanation = text.split('; ', 1)
        _equation(doc, expression)
        _para(doc, explanation)
        return
    prototype = doc.add_paragraph()
    reference.paragraph_format(prototype, 'equation')
    section = doc.sections[0]
    available = (section.page_width-section.left_margin-section.right_margin
                 - (prototype.paragraph_format.left_indent or 0)
                 - (prototype.paragraph_format.right_indent or 0)) / 12700
    doc.element.body.remove(prototype._p)
    # Respect the original equation indentation; wrap to its actual text width.
    width = max(24, int(available/8.0))
    for line in textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False):
        p = doc.add_paragraph()
        reference.paragraph_format(p, 'equation')
        p.paragraph_format.keep_with_next = True
        math = _xml(p._p, 'm:oMath')
        run = _xml(math, 'm:r')
        props = _xml(run, 'm:rPr')
        _xml(props, 'm:sty', m__val='p')
        t = _xml(run, 'm:t')
        t.text = line


def _bookmark(heading, number):
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'), str(number))
    start.set(qn('w:name'), f'bg40_chapter_{number}')
    end = OxmlElement('w:bookmarkEnd')
    end.set(qn('w:id'), str(number))
    heading._p.insert(0, start)
    heading._p.append(end)


def build_bg40_word_report(report: CalculationReport, state, *, include_figures=True,
                          include_appendices=True, require_all_figures=True, progress=None):
    with static_image_export_session():
        return _build_bg40_word_report(report, state, include_figures=include_figures,
            include_appendices=include_appendices, require_all_figures=require_all_figures,
            progress=progress)


def _build_bg40_word_report(report, state, *, include_figures,
                           include_appendices, require_all_figures, progress):
    def notify(message, fraction):
        if progress is not None:
            progress(message, fraction)
    notify('Checking stored report sources', .10)
    if report.signature != source_signature(state, report.metadata):
        raise ValueError('Report evidence is stale. Build the current report package before export.')
    doc = reference.document()
    _defaults(doc, report)
    doc.core_properties.title = report.metadata.report_title
    doc.core_properties.subject = report.metadata.project_name or ''
    doc.core_properties.author = report.metadata.prepared_by or ''
    report.figure_audit.clear()
    figure_counts = {}
    total_figures = sum(len(ch.figures) for ch in report.chapters) if include_figures else 0

    def unavailable(item, reason):
        item['reason'] = reason
        if require_all_figures:
            raise ReportFigureError('1 required report figure(s) could not be embedded. '
                f"Figure {item['number']} {item['title']}: {reason}")
        _para(doc, 'Figure not embedded: ' + item['title'] + '. ' + reason)

    def emit_figure(chapter, index, spec):
        figure_counts[chapter.number] = figure_counts.get(chapter.number, 0) + 1
        number = f'{chapter.number}.{figure_counts[chapter.number]}'
        item = {'chapter': chapter.number, 'number': number,
                'title': spec['title'], 'spec': spec, 'status': 'UNAVAILABLE'}
        report.figure_audit.append(item)
        notify(f"Creating figure {len(report.figure_audit)}/{total_figures}: {spec['title']}",
               .15 + .65 * (len(report.figure_audit)-1)/max(1,total_figures))
        try:
            figure = build_report_figure(state, spec)
        except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError) as exc:
            unavailable(item, str(exc))
            return
        if figure is None:
            unavailable(item, 'Source figure unavailable for the current input context')
            return
        presentation = prepare_print_figure(figure, spec)
        data, warnings = plotly_figure_to_png_bytes(presentation.figure, timeout_seconds=60.)
        if data:
            p = doc.add_paragraph()
            reference.paragraph_format(p)
            # Inline drawings need a full line box even when the source body
            # text uses slightly less than single spacing.
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.keep_with_next = True
            section = doc.sections[0]
            p.add_run().add_picture(BytesIO(data), width=section.page_width-section.left_margin-section.right_margin)
            title = _para(doc, f'Figure {number} {spec["title"]}')
            title.paragraph_format.keep_with_next = bool(presentation.caption)
            meta = dict(figure.layout.meta or {})
            if presentation.caption:
                caption = _para(doc, presentation.caption)
                if spec.get('kind') == 'workflow82' and meta.get('source_cases'):
                    caption.paragraph_format.keep_together = True
                    caption.paragraph_format.keep_with_next = bool(meta.get('source_cases'))
            item.update(status='EMBEDDED', context=meta, caption=presentation.caption)
            if meta.get('source_cases'):
                _para(doc, '; '.join(f'{k}: {v}' for k,v in meta['source_cases'].items()))
        else:
            unavailable(item, ' '.join(warnings) or 'PNG renderer returned no image')
    _para(doc, 'TABLE OF CONTENTS', role='toc')
    for ch in report.chapters:
        notify(f'Writing chapter {ch.number}: {ch.title}',
               .15 + .65 * len(report.figure_audit)/max(1,total_figures))
        p = doc.add_paragraph()
        p.style = doc.styles['Heading 2']
        link = _xml(p._p, 'w:hyperlink', w__anchor=f'bg40_chapter_{ch.number}')
        run = _xml(link, 'w:r')
        _xml(run, 'w:t').text = f'Chapter {ch.number}  {ch.title}'
        p.add_run('   ')
        _field(p, f'PAGEREF bg40_chapter_{ch.number} \\h')
    _para(doc, report.metadata.report_title, bold=True)
    _para(doc, report.metadata.project_name or 'Project name not recorded')
    _para(doc, f"Revision {report.metadata.revision} | {report.metadata.report_date or 'Date not recorded'}")
    _para(doc, f"Prepared by: {report.metadata.prepared_by or 'Not recorded'} | Checked by: {report.metadata.checked_by or 'Not recorded'}")
    _para(doc, 'Design code: ' + report.code + ' | Report status: ' + report.status)
    if report.metadata.note:
        _para(doc, report.metadata.note)
    if report.workflow_key == 'i_girder':
        doc.add_page_break()
    reference.heading(doc, 'Governing Check Summary', 1)
    _table(doc, report.controls, 'Stored governing checks', 'Stored Analysis cases and source acceptance gates')
    for warning in report.warnings:
        _para(doc, warning)
    for ch in report.chapters:
        if report.workflow_key == 'i_girder':
            doc.add_page_break()
        heading = reference.heading(doc, f'Chapter {ch.number} {ch.title}', 1)
        _bookmark(heading, ch.number)
        _para(doc, 'Chapter status: ' + ch.status, bold=True)
        for text in ch.notes:
            _para(doc, text)
        if not ch.tables and not ch.calculations and ch.status not in {'NOT APPLICABLE', 'SCOPE REVIEW'}:
            _para(doc, 'No current stored calculation is available for this chapter. Run the corresponding Analysis check before reporting its result.')
        for table in ch.tables:
            _table(doc, table.data, table.title, table.source)
        if ch.calculations:
            reference.heading(doc, f'{ch.number} Calculation Details', 2)
        emitted = set()
        for calculation_index, calc in enumerate(ch.calculations):
            p = _para(doc, calc.title, bold=True)
            p.paragraph_format.keep_with_next = True
            p = _para(doc, 'Reference: ' + calc.reference)
            p.paragraph_format.keep_with_next = True
            _equation(doc, calc.formula)
            _equation(doc, calc.substitution)
            _para(doc, 'Result: ' + calc.result, bold=True)
            following = ch.calculations[calculation_index+1].title if calculation_index+1 < len(ch.calculations) else ''
            if include_figures:
                for index, spec in enumerate(ch.figures, 1):
                    label = spec.get('after_label')
                    if label and calc.title.startswith(label) and not following.startswith(label):
                        emit_figure(ch, index, spec)
                        emitted.add(index)
        if include_figures:
            for i, spec in enumerate(ch.figures, 1):
                if i not in emitted:
                    emit_figure(ch, i, spec)
    if include_appendices:
        if report.workflow_key == 'i_girder':
            doc.add_page_break()
        reference.heading(doc, 'Appendix A Source Register', 1)
        _para(doc, 'Complete row identities and full precision result tables are included in the companion evidence ZIP. The register below groups the imported files and worksheets.')
        cols = ['File', 'Sheet', 'Source SHA256', 'Coupling']
        if not report.sources.empty:
            _table(doc, report.sources[cols].drop_duplicates(), 'Imported source files', 'Original import metadata')
        else:
            _para(doc, 'No imported source identity is recorded. Input values require source-document review.')
        reference.heading(doc, 'Appendix B Calculation Provenance', 1)
        _para(doc, 'Layout reference: ' + REFERENCE)
        _para(doc, 'Report version: ' + VERSION)
        _para(doc, 'Stored result signature: ' + report.signature)
        _para(doc, 'Design code references and project criteria are shown beside the actual stored calculations. Reference example values have not been copied into the design.')
        if report.figure_audit:
            import pandas as pd
            reference.heading(doc, 'Appendix C Figure Register', 1)
            _table(doc, pd.DataFrame([{'Figure':f['number'],'Title':f['title'],
                'Status':f['status'],'Source context':str((f.get('context') or {}).get('source_case','')),
                'Note':f.get('reason','')} for f in report.figure_audit]),
                'Calculation figures', '')
    missing = [f for f in report.figure_audit if f['status'] != 'EMBEDDED']
    if include_figures and require_all_figures and missing:
        names = '; '.join(f"Figure {f['number']} {f['title']}: {f.get('reason', 'source figure unavailable')}"
                         for f in missing)
        raise ReportFigureError(f'{len(missing)} required report figure(s) could not be embedded. {names}')
    output = BytesIO()
    notify('Saving the complete Word document', .83)
    doc.save(output)
    return output.getvalue()


def _write_json(archive, name, value, **options):
    with archive.open(name, 'w') as stream:
        with TextIOWrapper(stream, encoding='utf-8', newline='') as text:
            text.writelines(json.JSONEncoder(ensure_ascii=False, indent=2, **options).iterencode(value))


def _write_csv(archive, name, data):
    with archive.open(name, 'w') as stream:
        with TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
            data.to_csv(text, index=False, chunksize=1000)


def _embedded_image_paths(document):
    """Read inline picture identities without constructing a second Word DOM."""
    with document.open('word/_rels/document.xml.rels') as stream:
        relations = etree.parse(stream)
    targets = {node.get('Id'): posixpath.normpath(posixpath.join('word', node.get('Target')))
               for node in relations.getroot()
               if node.get('Target') and node.get('TargetMode') != 'External'}
    inline_tag = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline'
    blip_tag = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
    embed_key = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
    with document.open('word/document.xml') as stream:
        # Clear complete paragraphs/tables too; clearing only pictures would
        # still accumulate all of the document's text and table nodes.
        for _, node in etree.iterparse(stream, events=('end',)):
            if node.tag == inline_tag:
                blip = next(node.iter(blip_tag), None)
                if blip is not None:
                    yield targets[blip.get(embed_key)]
            if node.tag in {inline_tag, qn('w:p'), qn('w:tr')}:
                node.clear()
                while node.getprevious() is not None:
                    del node.getparent()[0]


def build_evidence_zip(report, docx_bytes, *, progress=None):
    def notify(message, fraction):
        if progress is not None:
            progress(message, fraction)
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        notify('Packaging the Word report and source snapshots', 0.)
        archive.writestr('Calculation_Report_BG40.docx', docx_bytes)
        _write_csv(archive, 'Source_Register.csv', report.sources)
        _write_csv(archive, 'Governing_Checks.csv', report.controls)
        _write_json(archive, 'ProjectInputSnapshot.json', report.input_snapshot)
        if report.stored_results:
            _write_json(archive, 'StoredResultSnapshot.json', report.stored_results, default=str)
        _write_json(archive, 'Figure_Register.json', report.figure_audit, default=str)
        # Extract the exact embedded images, retaining chapter/figure identity.
        embedded = [x for x in report.figure_audit if x['status'] == 'EMBEDDED']
        notify('Copying the exact embedded report figures', .35)
        with ZipFile(BytesIO(docx_bytes)) as document:
            images = iter(_embedded_image_paths(document))
            for item in embedded:
                target = next(images, None)
                if target is None:
                    raise ValueError('Figure evidence does not match the complete Word report')
                with document.open(target) as source, archive.open(
                        'figures/Figure_' + item['number'].replace('.', '_') + '.png', 'w') as destination:
                    copyfileobj(source, destination, length=65536)
            if next(images, None) is not None:
                raise ValueError('Word report contains an unregistered inline figure')
        for i, (name, data) in enumerate(report.raw_tables.items(), 1):
            notify(f'Packaging source table {i}/{len(report.raw_tables)}',
                   .45 + .45*(i-1)/max(1,len(report.raw_tables)))
            safe = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')[:115]
            _write_csv(archive, f'tables/{i:03d}_{safe}.csv', data)
        _write_json(archive, 'Calculations.json', [
            {'chapter': c.number, 'title': c.title, 'status': c.status,
             'calculations': [asdict(x) for x in c.calculations]} for c in report.chapters],
            )
        _write_json(archive, 'Provenance.json', {'version': VERSION,
            'layout_reference': REFERENCE, 'design_code': report.code, 'workflow': report.workflow_key,
            'status': report.status, 'signature': report.signature,
            'warnings': report.warnings, 'solver_recalculation': False,
            'full_punching_acceptance': False})
    notify('Source evidence package prepared', 1.)
    return output.getvalue()
