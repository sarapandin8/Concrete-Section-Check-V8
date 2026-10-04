"""Full-app V/T graph and calculate/review checks; no production input is repaired.

The incomplete QA fixture reproduces the supplied source gates. A separate
confirmed-source QA app instance demonstrates numeric plotting after inputs
exist, without passing off its hypothetical cage confirmations as user inputs.
"""
import copy
import json
import math
import os
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
OUT = Path(os.environ.get('CSP_QA_OUT', REPO/'qa/evidence/igird_chart2'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_combined_vt import source_readiness_dataframe
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.girder_csi_import import read_tables, prepare_csi_table
from concrete_pmm_pro.core.models import RebarMaterial


def by_label(elements, label):
    return next(e for e in elements if e.label == label)


def check(at):
    assert not at.exception, [e.message for e in at.exception]


def seed(state):
    at = AppTest.from_file(str(REPO/'app.py'))
    for key,value in state.items():
        at.session_state[key] = copy.deepcopy(value)
    at.session_state['_nav_active_workspace'] = 'Analysis'
    at.run(timeout=30)
    check(at)
    return at


def capture(fig, **kwargs):
    original_render(fig, **kwargs)
    figures[str(fig.layout.title.text)] = copy.deepcopy(fig)


def calculate(at, name):
    by_label(at.radio, 'ULS check to calculate').set_value(name).run(timeout=30)
    check(at)
    by_label(at.button, 'Calculate '+name).click().run(timeout=60)
    check(at)
    return at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name]


def preview(fig, stem, note):
    fig.write_json(OUT/(stem+'.json'))
    pio.write_html(fig, OUT/(stem+'.html'), include_plotlyjs=True, full_html=True,
        config={'displayModeBar':False, 'responsive':True})
    canvas, ax = plt.subplots(figsize=(14.4,5.6),dpi=120)
    for t in fig.data:
        mode = str(t.mode or 'lines')
        x = [float(v) for v in t.x]
        y = [float(v) if v is not None else float('nan') for v in t.y]
        color = t.line.color or t.marker.color or '#0f172a'
        label = t.name if t.showlegend is not False else '_nolegend_'
        if 'lines' in mode:
            dash = {'dash':'--','dot':':','dashdot':'-.'}.get(t.line.dash or 'solid','-')
            marker = ('D' if t.marker.symbol == 'diamond' else 'o') if 'markers' in mode else None
            ax.plot(x,y,color=color,linestyle=dash,linewidth=2,marker=marker,markersize=3,label=label)
        elif 'markers' in mode:
            ax.scatter(x,y,color=color,marker='D',s=36,label=label,zorder=8)
        if 'text' in mode and t.text:
            for xp,yp,text in zip(x,y,t.text):
                if math.isfinite(yp):
                    ax.annotate(str(text),(xp,yp),xytext=(-12 if xp>15 else 8,10),textcoords='offset points',fontsize=7,
                        ha='right' if xp>15 else 'left')
    handles,labels=ax.get_legend_handles_labels()
    assert len(labels)==len(set(labels))
    ax.legend(handles,labels,ncol=min(5,len(labels)),loc='upper center',bbox_to_anchor=(.5,-.19),fontsize=8,frameon=False)
    ax.set_xlim(0,20)
    ax.set_xlabel('Distance from left end of member (m)',fontsize=10)
    ax.set_ylabel('Shear (kN)' if stem.startswith('shear') else 'Torsion (kN-m)',fontsize=10)
    ax.set_title(('Shear Check' if stem.startswith('shear') else 'Torsion Check')+' — Strength ULS\nAASHTO LRFD 9th Edition | Left Exterior Girder | P = 0',loc='left',fontsize=13,pad=14)
    ax.grid(color='#cbd5e1',linewidth=.5)
    ax.spines[['top','right']].set_visible(False)
    canvas.text(.065,.022,note,fontsize=8,color='#334155')
    canvas.subplots_adjust(left=.065,right=.98,top=.82,bottom=.29)
    canvas.savefig(OUT/(stem+'.png'))
    plt.close(canvas)


state = {}
apply_project_to_session_state(project_from_json((REPO/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text()),state)
file = REPO/'qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx'
raw = read_tables(file.read_bytes(),file.name)['Left Exterior Girder'].copy(deep=True)
raw.loc[raw.index[1:],'P'] = 0.0  # In-memory QA input only, consistent with the user's Excel decision.
state['beam_uls_loads_table'] = prepare_csi_table(raw,sheet_name='Left Exterior Girder').frame
figures = {}
original_render = ap._render_beam_uls_browser_plotly_figure
with patch.object(ap,'_render_beam_uls_browser_plotly_figure',side_effect=capture), \
     patch.object(ap,'_render_beam_uls_static_plotly_figure',side_effect=AssertionError('I-Girder Analysis must not rasterize charts')):
    at = seed(state)
    frames = {}
    for name,key in [('Shear','shear_check_df'),('Torsion','torsion_check_df'),('Shear + Torsion','combined_vt_df')]:
        entry = calculate(at,name)
        frames[key] = entry[key].copy(deep=True)
        baseline = os.environ.get('CSP_QA_COMPARE_BASELINE')
        if baseline:
            pd.testing.assert_frame_equal(frames[key],pd.read_pickle(Path(baseline)/(key+'_baseline.pkl')))
        frames[key].to_csv(OUT/(key+'.csv'),index=False)
    shear = next(fig for title,fig in figures.items() if title.startswith('Shear Check'))
    torsion = next(fig for title,fig in figures.items() if title.startswith('Torsion Check'))
    for fig,component in [(shear,'Vuy'),(torsion,'Tu')]:
        names=[t.name for t in fig.data if t.showlegend is not False]
        assert len(names)==len(set(names)) and max(map(len,names)) <= 12
        assert tuple(fig.layout.xaxis.range)==(0,20)
        assert {f'{component} {step} {occ}' for step in ['Max','Min'] for occ in [1,2]} <= {t.name for t in fig.data}
        for trace in fig.data:
            if trace.name.startswith(component+' '):
                case=trace.customdata[0][0]
                original=state['beam_uls_loads_table'].loc[state['beam_uls_loads_table']['Case Name'].eq(case)].sort_values('Station x (m)',kind='stable')
                assert list(trace.x)==original['Station x (m)'].tolist()
                assert list(trace.y)==original[component].tolist()
    assert '±φVn' in [t.name for t in shear.data if t.showlegend is not False]
    assert not any(t.name=='±φTn' for t in torsion.data), 'No torsion cage confirmation may be invented'
    vt=frames['combined_vt_df']
    assert vt['Overall D/C value'].isna().all()
    assert any('Calculation completed:' in e.value for e in at.caption)
    assert any('no finite D/C' in e.value for e in at.info)
    readiness=source_readiness_dataframe(vt)
    assert readiness['Required source / review'].str.contains('SD40').any()
    assert readiness['Required source / review'].str.contains('not selected for torsion').any()
    readiness.to_csv(OUT/'required_inputs.csv',index=False)
    with patch.object(ap,'_beam_uls_calculate_selected_check',side_effect=AssertionError('Review must not solve')):
        at.run(timeout=30)
        check(at)
    for name,key in [('Shear','shear_check_df'),('Torsion','torsion_check_df'),('Shear + Torsion','combined_vt_df')]:
        pd.testing.assert_frame_equal(frames[key],at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name][key])
    # A separate QA instance explicitly supplies hypothetical verified cage and
    # material inputs. This does not change/save the user's model or workbook.
    confirmed=copy.deepcopy(state)
    confirmed['rebar_materials']=[*confirmed['rebar_materials'],RebarMaterial(name='SD40',fy_MPa=390)]
    for row in confirmed['beam_girder_torsion_zone_settings']:
        row.update({'Use for Torsion':True,'Closed Loop':True,'135° Hook':True})
    ready=seed(confirmed)
    ready_frame=calculate(ready,'Shear + Torsion')['combined_vt_df']
    finite=pd.to_numeric(ready_frame['Overall D/C value'],errors='coerce').map(lambda v:pd.notna(v) and math.isfinite(float(v)))
    assert finite.any(), ready_frame['Review reason'].tolist()
    ready_fig=next(fig for title,fig in figures.items() if title.startswith('Combined Shear + Torsion'))
    names=[t.name for t in ready_fig.data if t.showlegend is not False]
    assert len(names)==len(set(names)) and {'Veff D/C','Transverse D/C','Long. D/C','Limit = 1.0'} <= set(names)
    assert not ready_frame['Status'].eq('PASS').any(), 'CSI envelope source must not certify coupled acceptance'
    ready_fig.write_json(OUT/'confirmed_qa_combined_vt.json')
preview(shear,'shear_compact_legend','Native signed Vuy source curves retained; different case-dependent resistances remain. All original row checks are unchanged.')
preview(torsion,'torsion_compact_legend','Native signed Tu source curves retained. No verified torsion cage: phiTn remains unavailable; cracking/investigation references are shown.')
result={'method':'Full app.py Streamlit AppTest; original 80-row source fixture with P=0 in-memory only',
    'streamlit_exceptions':0,'force_coordinates_unchanged':True,'legend_entries_unique':True,'maximum_shear_torsion_label_length':12,
    'full_span':[0,20],'analysis_rasterization_calls':0,'review_solver_calls':0,
    'shear_rows':len(frames['shear_check_df']),'torsion_rows':len(frames['torsion_check_df']),
    'combined_rows':len(vt),'incomplete_combined_finite_dc_rows':0,
    'incomplete_combined_statuses':vt['Status'].value_counts().to_dict(),
    'baseline_all_numeric_and_status_rows_unchanged':bool(os.environ.get('CSP_QA_COMPARE_BASELINE')),
    'missing_material_and_hoop_actions_visible':True,'hypothetical_confirmed_qa_finite_dc_rows':int(finite.sum()),
    'hypothetical_confirmed_qa_changes_user_inputs':False,'native_envelope_coupled_pass_withheld':True,
    'preview_rendering':'Matplotlib using actual production Plotly coordinates; standalone HTML embeds Plotly JS',
    'browser_visual_verification':'NOT COMPLETED; no browser screenshot claim'}
(OUT/'vt_chart_ui_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2),flush=True)
