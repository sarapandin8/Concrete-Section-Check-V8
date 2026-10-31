"""The supplied Word file owns the page, theme, paragraph and table formats."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn

ROOT = Path(__file__).parent/'templates'


@lru_cache(maxsize=1)
def formats():
    return json.loads((ROOT/'BG40_R10_Formats.json').read_text(encoding='utf-8'))


def document():
    return Document(ROOT/'BG40_R10_Template.docx')


def paragraph_format(paragraph, role='body'):
    spec = formats()[role]
    if paragraph._p.pPr is not None:
        paragraph._p.remove(paragraph._p.pPr)
    if spec.get('pPr'):
        props = parse_xml(spec['pPr'])
        for section in list(props.iter(qn('w:sectPr'))):
            section.getparent().remove(section)
        paragraph._p.insert(0, props)
    for run in paragraph.runs:
        if run._r.rPr is not None:
            run._r.remove(run._r.rPr)
        if spec.get('rPr'):
            run._r.insert(0, parse_xml(spec['rPr']))
    return paragraph


def heading(doc, text, level=1):
    return paragraph_format(doc.add_heading(text, level), 'heading'+str(level))


def table_properties(table):
    old = table._tbl.tblPr
    table._tbl.remove(old)
    table._tbl.insert(0, parse_xml(formats()['table_properties']))


def cell_format(cell, header=False):
    key = 'table_header' if header else 'table_body'
    old = cell._tc.tcPr
    if old is not None:
        cell._tc.remove(old)
    cell._tc.insert(0, parse_xml(formats()[key+'_cell']))
    for p in cell.paragraphs:
        paragraph_format(p, key)


def update_header(doc, report):
    # Keep original header paragraph/run formatting, tab stops and border.
    # Replace only the source project's identifying text.
    for section in doc.sections:
        for index, p in enumerate(section.header.paragraphs):
            content = ('STRUCTURAL DESIGN CALCULATION \t\t   |  IG  |  Precast I-Girder'
                       if index == 0 else '\t\t' + (report.metadata.project_name or 'Project name not recorded'))
            exemplar = next((deepcopy(r._r.rPr) for r in p.runs
                             if r.text.strip() and r._r.rPr is not None), None)
            for child in list(p._p):
                if child.tag != qn('w:pPr'):
                    p._p.remove(child)
            run = p.add_run(content)
            if exemplar is not None:
                run._r.insert(0, exemplar)

