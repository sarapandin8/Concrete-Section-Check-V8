"""Print presentation shared by the complete BG40 Word export.

Only layout changes belong here. Trace values, source identity and engineering
acceptance remain owned by the stored Analysis results.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re

import plotly.graph_objects as go


PRESENTATION_VERSION = 'Original-R10.complete-print.81.1'


@dataclass(frozen=True)
class PrintFigure:
    figure: go.Figure
    caption: str


def _plain_note(value):
    text = re.sub(r'<br\s*/?>', ' ', str(value), flags=re.IGNORECASE)
    text = re.sub(r'</?(?:b|i|span)(?:\s[^>]*)?>', '', text)
    return re.sub(r'\bNone\b|\bnan\b|<NA>', 'Not available', text)


def prepare_print_figure(figure, spec):
    """Return an independent print layout without changing the source figure."""
    printed = go.Figure(deepcopy(figure.to_dict()))
    caption = str(spec.get('caption') or '').strip()
    kind = spec.get('kind')
    if kind == 'uls':
        # These audit notes must remain readable at an A4 text-column width.
        # Keep their full text as native Word captions, outside the bitmap.
        notes = (printed.layout.meta or {}).get('igird_report_note') or []
        caption = ' '.join([caption, *(_plain_note(x) for x in notes)]).strip()
        printed.layout.annotations = tuple(
            a for a in printed.layout.annotations if a.name != 'igird_report_note')
        printed.update_layout(width=1200, height=650, font={'size': 22},
            title_font_size=24, margin={'l': 100, 'r': 55, 't': 150, 'b': 145},
            legend={'font': {'size': 20}, 'y': -.22})
        printed.update_xaxes(tickfont_size=20, title_font_size=22)
        printed.update_yaxes(tickfont_size=20, title_font_size=22)
    elif kind == 'governing_section':
        # Stored section audit text otherwise overlaps the legend and becomes
        # too small in print. Preserve it at normal Word caption size instead.
        notes, retained = [], []
        for annotation in printed.layout.annotations:
            if (annotation.xref == 'paper' and annotation.yref == 'paper'
                    and annotation.y is not None and annotation.y < 0
                    and str(annotation.text).startswith('Stored ')):
                notes.append(_plain_note(annotation.text))
            else:
                retained.append(annotation)
        printed.layout.annotations = tuple(retained)
        caption = ' '.join([caption, *notes]).strip()
        if notes:
            printed.update_layout(height=max(450, (printed.layout.height or 650)-70),
                                  margin={'b': 80})
    elif kind == 'debonding':
        distances, retained = [], []
        for annotation in printed.layout.annotations:
            if 'mm from ' in str(annotation.text):
                distances.append(_plain_note(annotation.text))
            else:
                annotation.font.size = 16
                retained.append(annotation)
        printed.layout.annotations = tuple(retained)
        if distances:
            caption = (caption + ' Debond length references: ' + ', '.join(distances) + '.').strip()
        printed.update_layout(width=1200, height=650, font={'size': 18},
            title={'font': {'size': 24}, 'x': .5, 'y': .98},
            margin={'l': 215, 'r': 245, 't': 135, 'b': 105},
            legend={'font': {'size': 18}, 'y': 1.10, 'yanchor': 'bottom'})
        printed.update_xaxes(tickfont_size=18, title_font_size=20)
        printed.update_yaxes(tickfont_size=16, title_font_size=20)
    elif kind == 'slab_section':
        # The concrete fill must not obscure the reinforcement markers.
        for shape in printed.layout.shapes:
            shape.layer = 'below'
        printed.update_layout(height=660, margin={'b': 150},
            legend={'font': {'size': 18}, 'orientation': 'h', 'entrywidth': 460,
                    'entrywidthmode': 'pixels', 'y': -.18, 'x': .5, 'xanchor': 'center'})
    return PrintFigure(printed, caption)
