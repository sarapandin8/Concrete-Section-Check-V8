"""Separate native CSI Max/Min views of stored, source-paired ULS results.

Max/Min are source ItemTypes, never force signs. Occurrence sets remain
separate series; no importer, solver, input activation or cache write runs here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import escape
import json
import math
import re
import pandas as pd

from concrete_pmm_pro.io.girder_csi_import import SOURCE_TAG, VERSION, source_info
from concrete_pmm_pro.ui.igird_case_review import (
    FRAME_KEYS, controlling_result, ratio_text, summary_record,
)

DEMAND_VIEW = 'Max / Min — demand / capacity'
UTILIZATION_VIEW = 'Max / Min — utilization'
SOURCE_VIEW = 'Selected source case'
_FAMILY_FIELDS = ('schema', 'source_file', 'case', 'sheet', 'distance_column',
                  'step_number', 'control', 'source_mode', 'kind',
                  'concurrency_confirmed', 'evidence')


@dataclass(frozen=True)
class BoundFamily:
    token: str
    source: dict
    groups: dict[str, tuple[str, ...]]

    @property
    def cases(self):
        return tuple(case for step in ('Max', 'Min') for case in self.groups[step])

    @property
    def option(self):
        return f"CSI LC / {self.source['case']} / {self.source['sheet']} [{self.token[:10]}]"

    @property
    def label(self):
        filename = str(self.source.get('source_file') or 'Imported table')
        if len(filename) > 65:
            filename = filename[:62] + '…'
        return f"{self.source['case']} · {self.source['sheet']} · {filename}"


def csi_bound_families(rows):
    """Qualify complete source series before grouping within one member.

    A mixed/partly untagged series is excluded as a whole. Separate files,
    sheets, LC, distance basis, explicit steps and correspondence controls
    cannot supply each other's bounds. App-column names alone prove nothing.
    """
    if not isinstance(rows, pd.DataFrame) or rows.empty or 'Case Name' not in rows:
        return []
    groups = {}
    for case, series in rows.groupby('Case Name', sort=False):
        identities, metadata = set(), None
        for _, row in series.iterrows():
            note = row.get('Note')
            info = source_info(row) if isinstance(note, str) and SOURCE_TAG in note else None
            if (not isinstance(info, dict)
                    or info.get('schema') not in {VERSION, 'IGIRDER.CSIIMPORT2.auto-detect-v2'}
                    or info.get('step') not in {'Max', 'Min'}
                    or info.get('kind') not in {'ENVELOPE', 'CONCURRENT'}
                    or not all(info.get(k) for k in ('case', 'sheet', 'distance_column', 'kind'))
                    or type(info.get('row')) is not int or info['row'] < 1
                    or type(info.get('occurrence')) is not int or info['occurrence'] < 1):
                identities.add(None)
                continue
            key = json.dumps({k: info.get(k, '') for k in _FAMILY_FIELDS},
                             ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            identities.add((key, info['step'], info['occurrence']))
            metadata = info
        if len(identities) != 1 or None in identities:
            continue
        key, step, _ = next(iter(identities))
        group = groups.setdefault(key, {'source': metadata, 'Max': [], 'Min': []})
        group[step].append(str(case))
    return [BoundFamily(hashlib.sha256(key.encode()).hexdigest()[:16], value['source'],
                        {step: tuple(value[step]) for step in ('Max', 'Min')})
            for key, value in groups.items()]


def family_for_case(families, case):
    matches = [family for family in families if case in family.cases]
    return matches[0] if len(matches) == 1 else None


def select_cases(frame, cases, *, column='Case'):
    if frame is None:
        return None
    if column not in frame:
        return frame.iloc[:0].copy(deep=True)
    return frame.loc[frame[column].astype(str).isin(cases)].copy(deep=True)


def review_choices(rows, cases):
    families = csi_bound_families(rows)
    grouped = {case for family in families for case in family.cases}
    return families, [family.option for family in families] + [case for case in cases if case not in grouped]


def anchor_case(family, frame, check_name):
    control = controlling_result(select_cases(frame, family.cases), check_name)
    return str((control['row'] or {}).get('Case') or family.cases[0])


def choice_label(value, families):
    return next((family.label for family in families if value == family.option), value)


def chart_view(family, *, check_name, key_prefix, state, allow_source=True):
    """Only review-widget state is written; engineering inputs stay untouched."""
    import streamlit as st
    options = ([UTILIZATION_VIEW, SOURCE_VIEW] if check_name == 'Shear + Torsion'
               else [DEMAND_VIEW, UTILIZATION_VIEW, SOURCE_VIEW])
    if not allow_source:
        options.remove(SOURCE_VIEW)
    key = f'{key_prefix}igird_maxmin_{check_name}_view'
    if state.get(key) not in options:
        state[key] = options[0]
    view = st.radio('Chart view', options, horizontal=True, key=key)
    return view


def render_native_workspace(state, rows, result, *, check_name, code_label,
                            key_prefix='detail_', member=''):
    """Native detailed workspace shares the collection/report Max/Min figures."""
    import streamlit as st
    from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY
    frame = result.get(FRAME_KEYS[check_name])
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return False
    families, choices = review_choices(rows, frame['Case'].dropna().astype(str).drop_duplicates())
    if not families:
        return False
    from concrete_pmm_pro.ui.igird_case_review import AUTO_CASE
    key = key_prefix+'igird_maxmin_'+check_name+'_lc'
    options = [AUTO_CASE, *choices]
    if state.get(key) not in options:
        state[key] = AUTO_CASE
    choice = st.selectbox('Load case for Max / Min charts', options, key=key,
                          format_func=lambda value: choice_label(value, families))
    case = (controlling_result(frame, check_name)['row'] or {}).get('Case')
    family = (family_for_case(families, case) if choice == AUTO_CASE else
              next((f for f in families if f.option == choice), None))
    if family is None:
        return False
    view = chart_view(family, check_name=check_name, key_prefix=key_prefix,
                      state=state, allow_source=False)
    figures = make_bound_figures(state, {'rows':rows, 'result':result}, family=family,
        member=member or state.get(ACTIVE_KEY) or family.source['sheet'],
        check_name=check_name, code_label=code_label, view=view)
    render_bound_figures(figures, family=family, key_prefix=key_prefix+check_name)
    return True


def make_bound_figures(state, package, *, family, member, check_name, code_label,
                       view=DEMAND_VIEW):
    """Two figures, each restricted to its actual StepType and stored results."""
    from concrete_pmm_pro.ui import analysis_page as ap, igird_vt_workspace as vt
    from concrete_pmm_pro.visualization.igird_uls_chart_display import add_igird_report_note
    result, all_rows = package['result'], package['rows']
    full_frame = result[FRAME_KEYS[check_name]]
    member_control = controlling_result(full_frame, check_name)
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    global_case = str((member_control['row'] or {}).get('Case', 'Unavailable'))
    global_family = family_for_case(csi_bound_families(all_rows), global_case)
    global_step = next((s for s in ('Max', 'Min') if global_family and global_case in global_family.groups[s]), '')
    global_label = ((str(global_family.source['case'])+' '+global_step) if global_family else global_case)
    if len(global_label) > 45:
        global_label = global_label[:42]+'…'
    figures = {}
    for step in ('Max', 'Min'):
        cases = family.groups[step]
        if not cases:
            figures[step] = None
            continue
        rows = select_cases(all_rows, cases, column='Case Name')
        checked = select_cases(full_frame, cases)
        def pick(key):
            return select_cases(result.get(key), cases)
        utilization = view == UTILIZATION_VIEW or check_name == 'Shear + Torsion'
        if checked.empty and utilization:
            figures[step] = None
            continue
        if utilization and check_name == 'Torsion':
            from concrete_pmm_pro.ui.igird_torsion_utilization import make_torsion_utilization_figure
            fig = make_torsion_utilization_figure(rows, checked,
                diagram=pick('torsion_diagram_capacity_df'), code_label=code_label,
                span_m=span, source_context_df=all_rows)
            meaning = 'Blue: same-source |Tu|/φTn; open markers: original maximum check D/C. × marks unavailable ratios.'
        elif utilization:
            fig = vt.make_overview_figure(rows, checked, check_name=check_name,
                                         code_label=code_label, span_m=span)
            meaning = 'Blue: maximum available original component D/C within this ItemType. Red: limit 1.0; ×/○ retain missing-check status.'
        elif check_name == 'Flexure':
            fig = ap._make_beam_uls_flexure_preview_figure(rows, checked,
                code_label=code_label+' · Final Composite', member_length_m=span,
                source_context_df=all_rows)
            fig = ap._polish_igird_uls_flexure_legend(fig)
            meaning = 'Blue: signed Mux. Red: stored sectional φMn. Composite width, development and interface-shear gates remain required.'
        elif check_name == 'Shear':
            fig = ap._make_beam_uls_shear_capacity_figure(rows, checked,
                code_label=code_label, member_length_m=span, source_context_df=all_rows,
                compact_csi_legend=True, diagram_capacity_df=pick('shear_diagram_capacity_df'),
                boundary_capacity_df=pick('shear_boundary_capacity_df'),
                critical_section_df=pick('shear_critical_section_df'))
            fig.data = tuple(t for t in fig.data if t.name not in {'φVc', 'Critical x'})
            demands = [t for t in fig.data if str(t.name).startswith(('Demand Vuy', 'Vuy '))]
            for number, trace in enumerate(demands, 1):
                trace.name = f'Vu {step} {number}'
            meaning = 'Blue: signed Vu. Red: stored ±φVn paired to each source/station. The negative resistance branch is not the Min demand.'
        else:
            fig = ap._make_beam_uls_torsion_capacity_figure(rows, checked,
                code_label=code_label, member_length_m=span, source_context_df=all_rows,
                diagram_capacity_df=pick('torsion_diagram_capacity_df'),
                boundary_capacity_df=pick('torsion_boundary_capacity_df'))
            have_tn = any(t.name == '±φTn' and any(math.isfinite(float(y)) for y in t.y) for t in fig.data)
            fig.data = tuple(t for t in fig.data if t.name not in
                             ({'±φTcr', '±0.25φTcr'} if have_tn else {'±φTcr'}))
            meaning = ('Blue: signed Tu. Red: stored ±φTn paired to each source/station. The negative resistance branch is not the Min demand.'
                       if have_tn else 'Blue: signed Tu. Purple: investigation threshold. Stored φTn is unavailable; this is not strength acceptance.')
        selected_control = controlling_result(checked, check_name)
        location = (selected_control['row'] or {}).get('Governing x', '—')
        # Legacy capacity builders prioritize their own status/strength row.
        # That may differ from the member review's largest component D/C.
        # A chart-foot diamond locates the original review control without
        # assigning a force/capacity ordinate to a detailing ratio.
        fig.data = tuple(t for t in fig.data if not str(t.name).startswith(('Gov.', 'Governing')))
        marker = None
        try:
            control_x = float(str(location).replace(' m', ''))
        except (TypeError, ValueError):
            control_x = float('nan')
        if math.isfinite(control_x) and selected_control['basis'] != 'NO NUMERIC D/C':
            marker = {'Case':str((selected_control['row'] or {}).get('Case', '')),
                      'x_m':control_x, 'Component':selected_control['component'],
                      'Basis':selected_control['basis'], 'Ratio':ratio_text(selected_control['ratio'])}
            fig.add_annotation(name='igird_maxmin_control', x=control_x, y=.07,
                xref='x', yref='paper', text='◆', showarrow=False,
                font={'size':15,'color':'#0f172a'},
                hovertext=escape(f"Original {marker['Component']} · {marker['Basis']} {marker['Ratio']} @ {location}")+
                          '<br>'+escape(marker['Case'])+'<br>Station marker; no force/capacity ordinate is assigned.')
        fig.layout.annotations = tuple(a for a in fig.layout.annotations if a.name != 'igird_report_note')
        add_igird_report_note(fig, [meaning+' ◆ at foot: control station.',
            f"{step} control ({selected_control['basis']}): {ratio_text(selected_control['ratio'])} @ {location}; {selected_control['failed_rows']} FAIL, {selected_control['review_rows']} REVIEW; {len(checked)} stored rows.",
            f"All LCs: {member_control['failed_rows']} FAIL, {member_control['review_rows']} REVIEW; control {global_label} [{member_control['basis']} {ratio_text(member_control['ratio'])}]. Original gates remain in force."])
        title_check = 'Flexure — Final Composite' if check_name == 'Flexure' else check_name
        measure = 'utilization' if utilization else 'demand / capacity'
        fig.update_layout(title_text=f'Girder: {escape(member)}<br>{title_check} {step} — {measure}<br><sup>Load case: {escape(str(family.source["case"]))} · {escape(str(family.source["sheet"]))} · {escape(code_label)}</sup>',
            meta={**dict(fig.layout.meta or {}), 'igird_maxmin_check': check_name,
                  'igird_maxmin_member': member, 'igird_maxmin_step': step,
                  'igird_maxmin_lc': family.source['case'], 'igird_maxmin_family': family.token,
                  'igird_maxmin_source': dict(family.source), 'igird_maxmin_cases': list(cases),
                  'igird_maxmin_view': view, 'igird_maxmin_stored_rows': len(checked),
                  'igird_maxmin_control_marker': marker,
                  'igird_maxmin_selected_control': summary_record(selected_control),
                  'igird_maxmin_member_control': summary_record(member_control)})
        fig.update_xaxes(range=[0., span])
        figures[step] = fig
    return figures


def render_bound_figures(figures, *, family, key_prefix):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.result_table_display import result_table_for_display
    controls = []
    for step, fig in figures.items():
        st.markdown(f'##### {step} — {family.source["case"]}')
        if fig is None:
            reason = 'No imported source rows' if not family.groups[step] else 'No stored utilization checks'
            st.warning(f'{step} unavailable — {reason} for this LC/source family. No values are inferred from the other bound.')
            continue
        ap._render_beam_uls_browser_plotly_figure(fig, interactive=True)
        meta = dict(fig.layout.meta or {})
        controls.append({'ItemType': step, **meta['igird_maxmin_selected_control']})
        if not meta['igird_maxmin_stored_rows']:
            st.warning(f'{step}: demand only; no stored design checks are available. Recalculate this check in Analysis.')
        missing = meta.get('unavailable_capacity', [])
        if missing:
            st.caption(f'{step}: × marks {len(missing)} unavailable resistance/ratio station(s); see source audit. Missing values remain unavailable.')
        if meta.get('torsion_utilization_audit'):
            from concrete_pmm_pro.ui.igird_torsion_utilization import render_utilization_audit
            render_utilization_audit(fig, key_prefix=key_prefix+'_'+step)
        elif meta.get('overview_missing_ratio_audit'):
            from concrete_pmm_pro.ui.igird_overview_gaps import render_gap_audit
            render_gap_audit(fig, check_name=meta['igird_maxmin_check'], key_prefix=key_prefix+'_'+step)
    st.caption('Max/Min follow the imported CSI ItemType, not the sign of the force. Set 1/set 2 retain separate occurrence rows at a common station. ◆ at the chart foot locates the original controlling component/check; it is not a demand or capacity ordinate. Hover and the stored audit retain full source names. Connecting lines are visual interpolation; no missing force or resistance is filled.')
    if controls:
        with st.expander('Max / Min — stored controls / source family', expanded=False):
            st.dataframe(result_table_for_display(pd.DataFrame(controls)), hide_index=True, use_container_width=True)
            st.caption('Source: '+str(family.source.get('source_file') or 'Imported table')+
                       ' · distance basis: '+str(family.source['distance_column']))


def export_name(check_name, member, family, step=''):
    parts = (check_name, member[:45], str(family.source['case'])[:35], step, family.token[:10])
    return re.sub(r'[^A-Za-z0-9_-]+', '_', '_'.join(parts)).strip('_')
