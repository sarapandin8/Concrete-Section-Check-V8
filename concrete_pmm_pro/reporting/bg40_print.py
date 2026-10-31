"""Print presentation shared by the complete BG40 Word export.

Only layout changes belong here. Trace values, source identity and engineering
acceptance remain owned by the stored Analysis results.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re

import plotly.graph_objects as go


PRESENTATION_VERSION = 'Original-R10.complete-print.82.3'


@dataclass(frozen=True)
class PrintFigure:
    figure: go.Figure
    caption: str


def _plain_note(value):
    text = re.sub(r'<br\s*/?>', ' ', str(value), flags=re.IGNORECASE)
    text = re.sub(r'</?(?:b|i|span|sup)(?:\s[^>]*)?>', '', text)
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
    if kind == 'workflow82':
        if spec.get('plot')=='crossbeam':
            for trace in printed.data:
                if not isinstance(trace,go.Scatter) or 'text' not in str(trace.mode) or trace.x is None: continue
                axis=getattr(printed.layout,'xaxis'+str(trace.xaxis or 'x')[1:])
                bounds=axis.range
                if not bounds or len(bounds)!=2: continue
                positions=list(trace.textposition) if isinstance(trace.textposition,(tuple,list)) else [trace.textposition or 'middle center']*len(trace.x)
                for i,x in enumerate(trace.x):
                    if not isinstance(x,(int,float)): continue
                    if x<=float(bounds[0])+1e-9: positions[i]=str(positions[i]).replace('left','right').replace('center','right')
                    elif x>=float(bounds[1])-1e-9: positions[i]=str(positions[i]).replace('right','left').replace('center','left')
                trace.textposition=positions
        notes,retained=[],[]
        for annotation in printed.layout.annotations:
            if annotation.xref=='paper' and annotation.yref=='paper' and annotation.y is not None and annotation.y<0:
                notes.append(_plain_note(annotation.text))
            else:
                if spec.get('plot')=='crossbeam' and annotation.xref in {'x','x2','x3'}:
                    axis=getattr(printed.layout,'xaxis'+annotation.xref[1:])
                    bounds=axis.range
                    if bounds and len(bounds)==2 and isinstance(annotation.x,(int,float)):
                        if annotation.x<=float(bounds[0])+1e-9:
                            annotation.xanchor='left'; annotation.xshift=6; annotation.align='left'
                        elif annotation.x>=float(bounds[1])-1e-9:
                            annotation.xanchor='right'; annotation.xshift=-6; annotation.align='right'
                annotation.font.size=max(16,min(20,annotation.font.size or 18)); retained.append(annotation)
        printed.layout.annotations=tuple(retained)
        original_title=_plain_note(printed.layout.title.text or '')
        if original_title and original_title!=spec['title'] and spec.get('plot')=='crossbeam': notes.insert(0,original_title)
        caption=' '.join([caption,*notes]).strip()
        entries=sum(t.showlegend is not False and bool(t.name) for t in printed.data) if printed.layout.showlegend is not False else 0
        bottom=max(175,90+math.ceil(entries/2)*30)
        printed.update_layout(width=1200,height=600+bottom,font={'size':20},
            title={'text':spec['title'],'font':{'size':24},'x':.5,'xanchor':'center'},
            margin={'l':105,'r':80,'t':100,'b':bottom},
            legend={'font':{'size':18},'orientation':'h','y':-.15,'yanchor':'top','x':.5,
                    'xanchor':'center','entrywidth':440,'entrywidthmode':'pixels'})
        printed.update_xaxes(tickfont_size=20,title_font_size=22,automargin=True)
        printed.update_yaxes(tickfont_size=20,title_font_size=22,automargin=True)
    return PrintFigure(printed, caption)
