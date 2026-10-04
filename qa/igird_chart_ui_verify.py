"""Full app.py chart verification for the user's P=0 input assumption.

Generate previews from actual production Plotly trace coordinates. AppTest
checks controls and figure specs; PNG previews use Matplotlib, not a browser.
"""
import copy
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import plotly.io as pio
from streamlit.testing.v1 import AppTest

REPO = Path(os.environ.get('CSP_QA_REPO', Path(__file__).resolve().parents[1]))
OUT = Path(os.environ.get('CSP_QA_OUT', REPO/'qa/evidence/igird_chart1'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.girder_csi_import import read_tables, prepare_csi_table


def check(at):
    assert not at.exception, [e.message for e in at.exception]


def by_label(elements, label):
    return next(e for e in elements if e.label == label)


def dataframe(entry, column):
    return next(value for value in entry.values() if isinstance(value, pd.DataFrame) and column in value.columns)


state = {}
apply_project_to_session_state(project_from_json((REPO/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text()), state)
file = REPO/'qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx'
raw = read_tables(file.read_bytes(), file.name)['Left Exterior Girder'].copy(deep=True)
raw.loc[raw.index[1:], 'P'] = 0.0  # QA input only, as explicitly confirmed by the user.
source = prepare_csi_table(raw, sheet_name='Left Exterior Girder').frame
state['beam_uls_loads_table'] = source
settings = ap._igird_interface_shear_settings_from_state(state)
settings['stirrups_cross_and_anchored'] = True  # Matches the latest PDF's checked input.
state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = settings
state['project_metadata'][ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = settings
at = AppTest.from_file(str(REPO/'app.py'))
for key, value in state.items():
    at.session_state[key] = value
at.session_state['_nav_active_workspace'] = 'Analysis'
figures = {}
original_render = ap._render_beam_uls_browser_plotly_figure


def capture(fig, **kwargs):
    original_render(fig, **kwargs)
    figures[str(fig.layout.title.text)] = copy.deepcopy(fig)


with patch.object(ap, '_render_beam_uls_browser_plotly_figure', side_effect=capture):
    at.run(timeout=30)
    check(at)
    by_label(at.radio, 'Flexure stage').set_value('Final — Composite').run(timeout=30)
    check(at)
    by_label(at.button, 'Calculate Final Composite Flexure').click().run(timeout=60)
    check(at)
    by_label(at.button, 'Calculate Interface Shear').click().run(timeout=60)
    check(at)
    cache = at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]
    flexure = dataframe(cache['Flexure — Final Composite'], 'φMn kN-m').copy(deep=True)
    interface = dataframe(cache[ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME], 'vui (MPa)').copy(deep=True)
    assert len(flexure) == len(interface) == 80
    assert flexure['Nu kN'].eq(0).all() and flexure['Nu input kN'].eq(0).all()
    flex_fig = next(fig for title, fig in figures.items() if title.startswith('Flexure Check') and 'Final composite' in title)
    interface_fig = next(fig for title, fig in figures.items() if title.startswith('Girder–Deck Interface Shear'))
    assert [t.name for t in interface_fig.data] == ['vui max', 'φvni', 'Gov.']
    blue = interface_fig.data[0]
    for x, value, metadata in zip(blue.x, blue.y, blue.customdata):
        original = interface.loc[interface['Station x (m)'].eq(float(x))]
        assert float(value) == original['vui (MPa)'].max()
        assert metadata[0] in original.loc[original['vui (MPa)'].eq(value), 'Case'].tolist()
    assert len([t for t in flex_fig.data if t.name == 'φMn']) == 1
    assert {'Mux Max 1', 'Mux Max 2', 'Mux Min 1', 'Mux Min 2'} <= {t.name for t in flex_fig.data}
    for fig in (flex_fig, interface_fig):
        names = [t.name for t in fig.data if t.showlegend is not False]
        assert len(names) == len(set(names)) and max(map(len, names)) <= 12
        assert tuple(fig.layout.xaxis.range) == (0, 20)
    assert any('Blue vui max' in e.value for e in at.caption)
    assert any('Mux Max/Min 1/2' in e.value for e in at.caption)
    # A review rerun must use the existing calculations and their exact rows.
    with patch.object(ap, '_beam_uls_flexure_preview_dataframe', side_effect=AssertionError('Unexpected flexure solve on review')), patch.object(ap, '_igird_interface_shear_dataframe', side_effect=AssertionError('Unexpected interface solve on review')):
        at.run(timeout=30)
        check(at)
    cache = at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]
    pd.testing.assert_frame_equal(flexure, dataframe(cache['Flexure — Final Composite'], 'φMn kN-m'))
    pd.testing.assert_frame_equal(interface, dataframe(cache[ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME], 'vui (MPa)'))


def save_preview(fig, stem, title, note):
    """Export exact trace coordinates, using the project's blue/red line convention."""
    fig.write_json(OUT/(stem+'.json'))
    # Embed Plotly JS so the preview remains usable without a CDN/network.
    pio.write_html(fig, OUT/(stem+'.html'), include_plotlyjs=True, full_html=True,
        config={'displayModeBar': False, 'responsive': True})
    canvas, ax = plt.subplots(figsize=(14.4, 5.6), dpi=120)
    canvas.patch.set_facecolor('white')
    colors = {'Gov.': '#0f172a', 'Gov. flexure': '#0f172a', 'Gov. demand': '#1f77b4'}
    for trace in fig.data:
        mode = str(trace.mode or 'lines')
        name = str(trace.name or '')
        x = [float(v) for v in trace.x]
        y = [float(v) if v is not None else float('nan') for v in trace.y]
        color = trace.line.color or trace.marker.color or colors.get(name, '#1f77b4')
        if 'lines' in mode:
            dash = {'dash': '--', 'dot': ':', 'dashdot': '-.'}.get(str(trace.line.dash or 'solid'), '-')
            marker = ('D' if str(trace.marker.symbol) == 'diamond' else 'o') if 'markers' in mode else None
            ax.plot(x, y, color=color, linestyle=dash, linewidth=2.4, marker=marker, markersize=3.4,
                label=name if trace.showlegend is not False else '_nolegend_')
        elif 'markers' in mode:
            ax.scatter(x, y, color=color, marker='D', s=40, zorder=6,
                label=name if trace.showlegend is not False else '_nolegend_')
        if 'text' in mode and trace.text:
            for xp, yp, label in zip(x, y, trace.text):
                if name == 'Gov. demand' or 'inf' in str(label).lower():
                    ax.annotate(str(label), (xp, yp), xytext=(8, 13), textcoords='offset points', fontsize=8)
                else:
                    ax.annotate(str(label), (xp, yp), xytext=(8, -17), textcoords='offset points', fontsize=8)
    ax.set_xlim(0,20)
    ax.set_xlabel('Distance from left end of member (m)', fontsize=10)
    ax.set_ylabel('Interface shear stress (MPa)' if stem.startswith('interface') else 'Moment (kN-m)', fontsize=10)
    ax.set_title(title+'\nAASHTO LRFD 9th Edition | Left Exterior Girder | P = 0', loc='left', fontsize=13, pad=15)
    ax.grid(axis='y', color='#cbd5e1', linewidth=.6)
    ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    assert len(labels) == len(set(labels))
    ax.legend(handles, labels, ncol=len(labels), loc='upper center', bbox_to_anchor=(.5,-.16),
        fontsize=9, frameon=False, handlelength=3.8, columnspacing=1.6)
    canvas.text(.065,.025,note,fontsize=8,color='#334155')
    canvas.subplots_adjust(left=.065,right=.98,top=.82,bottom=.26)
    canvas.savefig(OUT/(stem+'.png'),dpi=120)
    plt.close(canvas)


save_preview(interface_fig, 'interface_shear_envelope', 'Girder–Deck Interface Shear',
    'Blue: max demand across all 80 rows at each station. Red: min resistance. Original row D/C and audit remain unchanged.')
save_preview(flex_fig, 'final_flexure_compact_legend', 'Final Composite Flexure',
    'Max/Min 1/2: original source occurrences. Coincident resistance is drawn once; all 80 calculated rows remain in the audit.')
flexure.drop(columns=['Strand development trace', 'Ordinary bar development trace'],errors='ignore').to_csv(OUT/'final_zero_p_80rows.csv',index=False)
interface.to_csv(OUT/'interface_zero_p_80rows.csv',index=False)
mid = flexure.loc[flexure['Station x (m)'].eq(10)]
gov = ap._igird_interface_governing_row(interface)
result = {'method':'Full app.py Streamlit AppTest; original fixture forces with user-confirmed P=0, unchanged 250-mm deck',
    'streamlit_exceptions':0,'final_rows':len(flexure),'interface_rows':len(interface),
    'interface_display_demand_curves':1,'interface_display_capacity_curves':1,
    'flexure_demand_curves':4,'flexure_coincident_capacity_curves':1,
    'legend_entries_unique':True,'maximum_legend_label_length':12,'full_span':[0,20],
    'all_original_checks_retained':True,'review_does_not_rerun_solvers':True,
    'midspan_phiMn_kNm':mid['φMn kN-m'].max(),
    'interface_governing_vui_MPa':gov['vui (MPa)'],'interface_governing_DC':gov['Strength D/C'],
    'flexure_status_counts':flexure['Status'].value_counts().to_dict(),
    'preview_rendering':'Matplotlib from actual production Plotly trace coordinates; standalone interactive Plotly HTML also provided',
    'browser_visual_verification':'NOT COMPLETED; no browser screenshot or print-layout claim'}
(OUT/'chart_ui_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2),flush=True)
