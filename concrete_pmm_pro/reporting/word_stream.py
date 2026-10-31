"""Spool the Word body and table rows without retaining a full document DOM."""
from contextvars import ContextVar
from io import BytesIO
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from docx.oxml.ns import qn
from lxml import etree

_ACTIVE = ContextVar('calculation_word_body', default=None)


def active_body(doc):
    body = _ACTIVE.get()
    return body if body is not None and body.doc is doc else None


class StreamingWordBody:
    """Keep the original python-docx package/styles/relations and stream its body.

    Finished paragraphs and rows are immutable and can leave the DOM. Images,
    headers, numbering, native equations, bookmarks and section formats remain
    the original package's objects. Only word/document.xml is spooled to disk.
    """
    def __init__(self, doc, *, progress=None):
        self.doc = doc
        self.finished = False
        self.drawing_id = max((int(v) for v in doc.element.xpath('.//@id') if v.isdigit()), default=0)
        self.progress = progress

    def table_progress(self, title, count, total):
        if self.progress is not None:
            self.progress(f'Writing source table: {title} ({count:,}/{total:,} rows)')

    def next_drawing_id(self):
        # python-docx otherwise scans only the remaining body. Earlier inline
        # pictures have already been spooled, so preserve document-wide IDs.
        self.drawing_id += 1
        return self.drawing_id

    def __enter__(self):
        self.directory = TemporaryDirectory(prefix='calculation-word-')
        self.xml_path = Path(self.directory.name)/'document.xml'
        self.file = etree.xmlfile(str(self.xml_path), encoding='UTF-8')
        self.writer = self.file.__enter__()
        self.writer.write_declaration(standalone=True)
        element = self.doc.element
        self.document = self.writer.element(element.tag, dict(element.attrib), nsmap=element.nsmap)
        self.document.__enter__()
        self.body = self.writer.element(element.body.tag, dict(element.body.attrib))
        self.body.__enter__()
        self.token = _ACTIVE.set(self)
        return self

    def flush(self, *, before=None):
        for node in list(self.doc.element.body):
            if node is before:
                break
            if node.tag != qn('w:sectPr'):
                self.doc.element.body.remove(node)
                etree.cleanup_namespaces(node)
                self.writer.write(node)

    def write_table(self, table, rows):
        """Write the exact formatted header/grid and one immutable row at a time."""
        element = table._tbl
        self.flush(before=element)
        with self.writer.element(element.tag, dict(element.attrib)):
            for child in list(element):
                element.remove(child)
                etree.cleanup_namespaces(child)
                self.writer.write(child)
            for row in rows:
                etree.cleanup_namespaces(row)
                self.writer.write(row)
        self.doc.element.body.remove(element)

    def finish(self):
        if self.finished:
            return
        self.flush()
        section = self.doc.element.body.sectPr
        if section is not None:
            self.writer.write(section)
        self.body.__exit__(None, None, None)
        self.document.__exit__(None, None, None)
        self.file.__exit__(None, None, None)
        self.finished = True

    def save(self):
        self.finish()
        skeleton = Path(self.directory.name)/'package.docx'
        self.doc.save(skeleton)
        output = BytesIO()
        with ZipFile(skeleton) as source, ZipFile(output, 'w', ZIP_DEFLATED) as destination:
            for info in source.infolist():
                if info.filename == 'word/document.xml':
                    with self.xml_path.open('rb') as data, destination.open(info, 'w') as target:
                        copyfileobj(data, target, length=65536)
                else:
                    with source.open(info) as data, destination.open(info, 'w') as target:
                        copyfileobj(data, target, length=65536)
        return output.getvalue()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.finish()
        finally:
            _ACTIVE.reset(self.token)
            self.directory.cleanup()
