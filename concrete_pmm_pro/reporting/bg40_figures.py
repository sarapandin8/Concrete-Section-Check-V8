"""Read-only engineering figures for the BG40 calculation chapters."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from concrete_pmm_pro.core.models import SectionGeometry, Rebar, PrestressElement, DimensionItem
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability

COLORS = ['#1565c0', '#008577', '#b45309', '#7c3aed', '#c62828', '#475569']


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def finish(fig, title, *, height=650):
    fig.update_layout(template='plotly_white', width=1200, height=height,
        title={'text': title, 'x': .5, 'xanchor': 'center'},
        font={'family': 'Arial', 'size': 22}, margin={'l': 100, 'r': 100, 't': 90, 'b': 110},
        legend={'orientation': 'h', 'y': -.17, 'x': .5, 'xanchor': 'center','font':{'size':20}})
    fig.update_xaxes(tickfont={'size':20}, title_font={'size':22}, automargin=True)
    fig.update_yaxes(tickfont={'size':20}, title_font={'size':22}, automargin=True)
    for annotation in fig.layout.annotations:
        annotation.font.size = 20
    return apply_global_plot_readability(fig)


def span(state):
    for key in ('beam_girder_system_settings', 'girder_prestress_system_settings'):
        value = number((state.get(key) or {}).get('span_length_m'))
        if value is not None and value > 0:
            return value
    return None


def core_geometry(state, row=None):
    from concrete_pmm_pro.analysis import igird_end_sections as ends
    raw = state.get('section_geometry')
    g = SectionGeometry.model_validate(raw) if isinstance(raw, dict) else raw
    if not isinstance(g, SectionGeometry):
        return None
    x = number((row or {}).get('Station x (m)'))
    if x is None:
        x = number(str((row or {}).get('Governing x', '')).replace(' m', ''))
    if row and x is not None and ends.enabled(state):
        g, _ = ends.section_at(g, ends.profile(state, g, span(state)), x)
    return g


def section(state, *, composite=False, row=None):
    from concrete_pmm_pro.visualization.section_plot import create_section_preview
    from concrete_pmm_pro.analysis.igird_composite_flexure import _composite_geometry
    from concrete_pmm_pro.geometry.summary import summarize_geometry
    g = core_geometry(state, row)
    if g is None:
        return None
    core = g
    p = state.get('section_parameters') or {}
    be = number((row or {}).get('_report_Be_mm')) or number(p.get('Be_effective_mm', p.get('Be_mm')))
    t = number((row or {}).get('_report_Tslab_mm')) or number(p.get('Tslab_mm'))
    if composite and be and t and be > 0 and t > 0:
        g = _composite_geometry(g, be_mm=be, tslab_mm=t)
    bars = [Rebar.model_validate(b) if isinstance(b, dict) else b for b in (state.get('rebars') or [])]
    ps = [PrestressElement.model_validate(b) if isinstance(b, dict) else b for b in (state.get('prestress_elements') or [])]
    dimensions = [DimensionItem.model_validate(d) if isinstance(d, dict) else d
                  for d in (state.get('section_dimensions') or [])] if not row and not composite else []
    fig = create_section_preview(g, dimensions=dimensions, rebars=bars, prestress_elements=ps)
    table = state.get('girder_strand_layout_table')
    if not ps and table is not None:
        from concrete_pmm_pro.ui.prestress_page import _girder_strand_point_layout_dataframe
        points = _girder_strand_point_layout_dataframe(pd.DataFrame(table), core)
        if not points.empty:
            fig.add_trace(go.Scatter(x=points['x_mm'], y=points['y_mm_abs'], mode='markers',
                name='Strand layout', marker={'color':'#1565c0','size':6,'symbol':'circle-open'}))
    props = summarize_geometry(g)
    x0, x1, y0, y1 = props.x_min_mm, props.x_max_mm, props.y_min_mm, props.y_max_mm
    width, height = x1-x0, y1-y0
    fig.add_annotation(x=x1, y=(y0+y1)/2, text=f'h={height:g} mm', showarrow=False,
                       xshift=40, textangle=-90, bgcolor='white')
    fig.add_annotation(x=(x0+x1)/2, y=y0, text=f'B={width:g} mm', showarrow=False,
                       yshift=-35, bgcolor='white')
    if composite and g is not core:
        top = max(v.y for v in core.outer_polygon)
        fig.add_hline(y=top, line_dash='dot', line_color='#008577')
        fig.add_annotation(x=x1, y=top+t/2, text=f'Deck t={t:g} mm; Be={be:g} mm',
                           showarrow=False, xanchor='right', bgcolor='white')
    fig.update_layout(meta={'source': 'Current Section Builder geometry and reinforcement',
                            'geometry_only': True, 'composite': composite})
    return finish(fig, 'Composite section' if composite else 'Precast section', height=780)


def system(state):
    length = span(state)
    if not length or length <= 0:
        return None
    f = go.Figure()
    f.add_trace(go.Scatter(x=[0, length], y=[0, 0], mode='lines+markers',
        line={'width': 14, 'color': '#64748b'}, marker={'size': 9}, name='Girder reference line'))
    f.add_annotation(x=length/2, y=.25, text=f'Span L = {length:g} m', showarrow=False)
    f.add_annotation(x=0, y=-.22, text='x=0 reference', showarrow=False)
    f.add_annotation(x=length, y=-.22, text='x=L reference', showarrow=False)
    f.update_xaxes(title='Distance x (m)', range=[-length*.06, length*1.06])
    f.update_yaxes(visible=False, range=[-.6, .6])
    f.update_layout(meta={'source': 'System settings', 'support_restraints_inferred': False})
    return finish(f, 'Girder longitudinal reference schematic', height=360)


def actions(state, member):
    from concrete_pmm_pro.ui.igird_uls_report import report_member_inputs
    rows = report_member_inputs(state).get(member)
    if rows is None or rows.empty:
        return None
    cases = rows['Case Name'].dropna().astype(str).drop_duplicates().tolist()
    if len(cases) > 6:
        chosen = []
        for col in ('Mux','Vuy','Tu','Nu'):
            if col in rows:
                values = pd.to_numeric(rows[col], errors='coerce').abs()
                if values.notna().any():
                    case = str(rows.loc[values.idxmax(), 'Case Name'])
                    if case not in chosen:
                        chosen.append(case)
        cases = chosen
    f = make_subplots(rows=2, cols=2, subplot_titles=['M3 / Mux', 'V2 / Vuy', 'T / Tu', 'P / Nu input'])
    fields = [('Mux', 'kN·m'), ('Vuy', 'kN'), ('Tu', 'kN·m'), ('Nu', 'kN')]
    for i, (field, unit) in enumerate(fields):
        rr, cc = i//2+1, i%2+1
        for j, name in enumerate(cases):
            selected = rows.loc[rows['Case Name'].astype(str).eq(name)].sort_values('Station x (m)')
            if field not in selected:
                continue
            f.add_trace(go.Scatter(x=selected['Station x (m)'], y=selected[field],
                mode='lines+markers', name=f'C{j+1}', legendgroup=f'C{j+1}', showlegend=i==0,
                line={'color': COLORS[j%len(COLORS)], 'width': 2.2}, marker={'size': 4},
                customdata=[name]*len(selected), hovertemplate='%{customdata}<br>x=%{x} m<br>value=%{y}<extra></extra>',
                connectgaps=False), row=rr, col=cc)
        f.update_xaxes(title='x (m)', row=rr, col=cc)
        f.update_yaxes(title=unit, row=rr, col=cc)
    f.update_layout(meta={'member': member, 'source_cases': {f'C{i+1}': n for i,n in enumerate(cases)},
        'selection': 'All cases up to six; otherwise original cases governing absolute force components',
        'combined_vector_created': False})
    return finish(f, 'Imported ULS actions | ' + member, height=850)


def governing_section(state, spec):
    from concrete_pmm_pro.ui.igird_uls_report import current_check_packages
    from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS, controlling_result
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon
    from shapely.geometry import box
    package = current_check_packages(state, spec['check']).get(spec['member'])
    if not package:
        return None
    row = controlling_result(package['result'][FRAME_KEYS[spec['check']]], spec['check'])['row'] or {}
    row = {**row, '_report_Be_mm':package['result'].get('Be_mm'),
           '_report_Tslab_mm':package['result'].get('Tslab_mm')}
    composite = 'COMPOSITE' in str(row.get('Section basis', '')).upper()
    f = section(state, composite=composite, row=row)
    if f is None:
        return None
    core = core_geometry(state, row)
    if spec['check'] == 'Flexure':
        g = core
        p = state.get('section_parameters') or {}
        if composite:
            from concrete_pmm_pro.analysis.igird_composite_flexure import _composite_geometry
            be = number(package['result'].get('Be_mm', p.get('Be_mm')))
            t = number(package['result'].get('Tslab_mm', p.get('Tslab_mm')))
            if be and t:
                g = _composite_geometry(core, be_mm=be, tslab_mm=t)
        poly = to_shapely_polygon(g)
        x0,y0,x1,y1 = poly.bounds
        depth = number(row.get('Stress block a mm'))
        c = number(row.get('Neutral axis c mm'))
        top_compression = 'top' not in str(row.get('Tension face', 'Bottom')).lower()
        if depth is not None and depth >= 0:
            region = poly.intersection(box(x0, y1-depth, x1, y1) if top_compression else box(x0,y0,x1,y0+depth))
            if not region.is_empty and region.geom_type == 'Polygon':
                x,y = region.exterior.xy
                f.add_trace(go.Scatter(x=list(x),y=list(y),fill='toself',mode='lines',
                    fillcolor='rgba(198,40,40,.30)',line={'color':'#c62828'},name=f'a={depth:.1f} mm'))
        if c is not None:
            na = y1-c if top_compression else y0+c
            if y0 <= na <= y1:
                f.add_hline(y=na,line_dash='dash',line_color='#c62828')
        annotation = f"Stored c={c} mm; a={depth} mm; Cc={row.get('Cc kN')} kN<br>Strand force={row.get('Strand force kN')} kN; φMn={row.get('φMn kN-m')} kN·m"
    else:
        annotation = f"Stored dv={row.get('dv mm')} mm; bv={row.get('bw mm')} mm<br>Zone={row.get('Zone')}; stirrup={row.get('Stirrup')}; spacing={row.get('Spacing mm')} mm"
        if spec['check'] in {'Torsion','Shear + Torsion'}:
            offset = number(row.get('Hoop offset mm'))
            if offset is None:
                p = state.get('beam_girder_torsion_settings') or {}
                cover = number(p.get('clear_cover_mm'))
                import re
                diameter = re.search(r'(?:DB|RB|D)?\s*(\d+(?:\.\d+)?)', str(row.get('Stirrup','')))
                if cover is not None and diameter:
                    offset = cover+float(diameter.group(1))/2
            if offset is not None:
                inset = to_shapely_polygon(core).buffer(-offset,join_style=2)
                if inset.geom_type == 'Polygon' and not inset.is_empty:
                    x,y = inset.exterior.xy
                    f.add_trace(go.Scatter(x=list(x),y=list(y),mode='lines',
                        line={'color':'#b45309','width':3,'dash':'dash'},name='Closed hoop centreline'))
            annotation += f"<br>Stored Ao={row.get('Ao mm2')} mm²; ph={row.get('ph mm')} mm"
    f.add_annotation(x=.5,y=-.16,xref='paper',yref='paper',text=annotation,showarrow=False,
                     font={'size':13},bgcolor='white')
    f.update_layout(title_text=spec['member']+' | '+spec['check']+' | x='+str(row.get('Governing x')),
        margin={'b':150},meta={'source_case':row.get('Case'),'station':row.get('Governing x'),
        'check':spec['check'],'stored_values':True,'strength_recalculated':False})
    return f


def stress_section(state, spec):
    from concrete_pmm_pro.ui.igird_sls53_results import current, controlling
    result = current(state)
    if not result:
        return None
    entry = result['stages'][spec['stage']]
    row = controlling(entry['checks'])
    case = entry['cases'][str(row['Case Name'])]
    x = row.get('Station x (m)')
    raw = case['raw'].loc[case['raw']['Station x (m)'].eq(x)]
    if raw.empty:
        return None
    core = core_geometry(state)
    if core is None:
        return None
    ymin,ymax = min(p.y for p in core.outer_polygon),max(p.y for p in core.outer_polygon)
    f = go.Figure()
    split = case.get('split',pd.DataFrame())
    if not split.empty:
        subset = split.loc[split['Station x (m)'].eq(x)]
        for i,(component,group) in enumerate(subset.groupby('Concrete component',sort=False)):
            group = group.sort_values('y from bottom (mm)')
            f.add_trace(go.Scatter(x=group['Total stress (MPa)'],y=group['y from bottom (mm)'],
                mode='lines+markers+text',text=[f'{v:.3f}' for v in group['Total stress (MPa)']],
                textposition='middle right',name=component,line={'color':COLORS[i]}))
    else:
        r = raw.iloc[0]
        values = [r['Bottom total (MPa)'],r['Top total (MPa)']]
        f.add_trace(go.Scatter(x=values,y=[0,ymax-ymin],mode='lines+markers+text',
            text=[f'{v:.3f}' for v in values],textposition='middle right',name='Precast beam'))
    f.add_vline(x=0,line_dash='dash',line_color='#475569')
    f.update_xaxes(title='Stored total stress (MPa); compression negative')
    f.update_yaxes(title='Height from precast bottom (mm)')
    f.update_layout(meta={'source_case':row['Case Name'],'station_m':x,'stage':spec['stage'],
        'stress_recalculated':False})
    return finish(f, spec['stage']+f" | {row['Case Name']} | stress through depth at x={x:g} m",height=650)


def slab_section(state):
    from concrete_pmm_pro.analysis.slab_review68 import current
    from concrete_pmm_pro.analysis.slab_shell56 import GROUPS
    r = current(state)
    if not r:
        return None
    sample = (r.get('punching_screen78') or {}).get('governing') or r['rows'].iloc[0].to_dict()
    h = number(sample.get('Thickness (mm)'))
    if not h or h <= 0:
        return None
    steel = r['steel']
    f = go.Figure()
    f.add_shape(type='rect',x0=0,x1=1000,y0=0,y1=h,fillcolor='#eef2f7',line={'color':'#475569'})
    for i,label in enumerate(GROUPS):
        y = h-steel.centre[i] if label.startswith('Top') else steel.centre[i]
        f.add_trace(go.Scatter(x=[100,900],y=[y,y],mode='lines+markers',
            name=f'{label} D{steel.diameter[i]:g}@{steel.spacing[i]:g}',
            line={'color':COLORS[i],'width':3},marker={'size':6}))
    f.update_xaxes(title='Representative 1000 mm design strip',range=[-50,1050])
    f.update_yaxes(title='Depth coordinate (mm)',range=[-h*.25,h*1.2])
    f.update_layout(meta={'geometry_schematic':True,'thickness_mm':h,
        'sample_xy_m':[sample.get('X (m)'),sample.get('Y (m)')],'design_recalculated':False})
    return finish(f,f"Deck section and four mats | actual h={h:g} mm",height=600)


def extra_figure(state, spec):
    kind = spec['kind']
    if kind == 'system':
        return system(state)
    if kind == 'composite_section':
        return section(state,composite=True)
    if kind == 'governing_section':
        return governing_section(state,spec)
    if kind == 'actions':
        return actions(state,spec['member'])
    if kind == 'debonding':
        from concrete_pmm_pro.ui.prestress_page import _plot_girder_longitudinal_debonding_layout
        return _plot_girder_longitudinal_debonding_layout(pd.DataFrame(state['girder_strand_layout_table']),
                                                        span(state),one_side_schematic=False)
    if kind == 'stress_section':
        return stress_section(state,spec)
    if kind == 'slab_section':
        return slab_section(state)
    if kind == 'prestress_audit':
        data = pd.DataFrame(state.get(spec['key']))
        values = pd.to_numeric(data[spec['column']], errors='coerce')
        labels = next((data[c].astype(str) for c in data if c != spec['column']
                       and pd.to_numeric(data[c],errors='coerce').isna().any()),
                      pd.Series([str(i+1) for i in range(len(data))]))
        f = go.Figure(go.Bar(x=labels,y=values,name=spec['column'],marker_color=COLORS[0]))
        f.update_yaxes(title=spec['column'])
        f.update_xaxes(title='Original stage / group')
        return finish(f,spec['title'],height=560)
    if kind in {'track_plan','punching_perimeters'}:
        from concrete_pmm_pro.analysis.slab_review68 import current
        r = current(state)
        if not r:
            return None
        if kind == 'track_plan':
            from concrete_pmm_pro.visualization.slab_track77 import figure
        else:
            from concrete_pmm_pro.visualization.slab_punching64 import figure
        return figure(r)
    if kind in {'slab_plan','slab_profile'}:
        from concrete_pmm_pro.analysis import slab_review68 as engine
        from concrete_pmm_pro.visualization import slab_top65 as charts
        r = engine.current(state)
        if not r:
            return None
        adapted = engine.map_adapter(r,spec['view'])
        return charts.plan(r,adapted,spec['view']) if kind == 'slab_plan' else charts.profile(adapted,spec['view'])
    return None


def add_figures(report, state):
    from concrete_pmm_pro.ui.igird_uls_report import current_check_packages,report_member_inputs
    from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS,controlling_result
    from concrete_pmm_pro.analysis import slab_review68 as slab
    from concrete_pmm_pro.ui.igird_sls53_results import current as current_sls
    c2,c3,c5,c6,c7,c8,c10 = [report.chapters[i] for i in [1,2,4,5,6,7,9]]
    c4 = report.chapters[3]
    import re
    for key in ('girder_prestress_force_states_table','girder_prestress_code_loss_summary_table'):
        data = pd.DataFrame(state.get(key)) if state.get(key) is not None else pd.DataFrame()
        for column in data:
            if (re.search(r'pe|prestress|force|loss|Δfp|fpe|stress',str(column),re.I)
                    and data[column].dtype != bool
                    and pd.to_numeric(data[column],errors='coerce').notna().any()):
                c4.figures.append({'kind':'prestress_audit','key':key,'column':column,
                    'title':'Recorded prestress | '+str(column),
                    'caption':'Stored force-state / loss-audit values. Historical loss input binding remains REVIEW.'})
    if span(state):
        c2.figures.append({'kind':'system','title':'Longitudinal reference schematic',
            'caption':'System inputs; schematic only. Source FEA support restraints are not inferred.'})
    strands = pd.DataFrame(state.get('girder_strand_layout_table')) if state.get('girder_strand_layout_table') is not None else pd.DataFrame()
    if not strands.empty and span(state):
        c2.figures.append({'kind':'debonding','title':'Strand groups and longitudinal debonding',
            'caption':'Original strand groups, bond lengths and cut-end reference; no effective-force recalculation.'})
    if (state.get('section_parameters') or {}).get('composite_enabled'):
        c3.figures.append({'kind':'composite_section','title':'Composite section and effective deck strip',
            'caption':'Current effective width, slab thickness and reinforcement inputs; dimensions in mm.'})
    for member in report_member_inputs(state):
        c5.figures.append({'kind':'actions','member':member,'title':'Imported action diagrams | '+member,
            'caption':'Signed source actions remain attached to their original cases. No new V–T vector is assembled.'})
    for check in FRAME_KEYS:
        for member,package in current_check_packages(state,check).items():
            row = controlling_result(package['result'][FRAME_KEYS[check]],check)['row'] or {}
            label = f"{member} | {check} | {row.get('Case','')} | x={row.get('Governing x','')}"
            chapter = c6 if check=='Flexure' else c7
            chapter.figures.append({'kind':'governing_section','check':check,'member':member,
                'title':f"{member} | {check} | governing section",'after_label':label,
                'caption':f"Case {row.get('Case')}; x={row.get('Governing x')}. Section geometry and stored design quantities; no new strength solution."})
    stress = current_sls(state)
    if stress:
        for stage in stress['stages']:
            c8.figures.append({'kind':'stress_section','stage':stage,
                'title':stage+' stress distribution through depth',
                'caption':'Stored governing section stresses; piecewise material values retained for the composite section.'})
    if slab.current(state):
        r = slab.current(state)
        c10.figures.insert(0,{'kind':'slab_section','title':'Deck section and four reinforcement mats',
            'caption':'Actual thickness at the governing local-index sample. Mat dimensions are source inputs; this is a geometry schematic.'})
        for view in slab.VIEWS:
            for kind in ('slab_plan','slab_profile'):
                c10.figures.append({'kind':kind,'view':view,'title':view+(' | plan' if kind=='slab_plan' else ' | station profile'),
                    'caption':'Current retained shell results with original exclusions and source gates; component indices do not certify full deck acceptance.'})
        if (r.get('track_distribution') or {}).get('deck_bounds_local') is not None:
            c10.figures.append({'kind':'track_plan','title':'Track strips and slab load-path geometry',
                'caption':'Recorded distribution assumption and support contacts only; not an inferred punching exemption.'})
        if (r.get('punching') or {}).get('areas'):
            c10.figures.append({'kind':'punching_perimeters','title':'Recorded loaded areas and candidate critical perimeters',
                'caption':'Only configured physical loaded areas and stored perimeter results are shown; original REVIEW gates retained.'})
    return report

