"""Exercise the actual app.py Analysis routes with a controlled QA model."""
from contextlib import ExitStack
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, 'tests')
import streamlit as st
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import activate_member, ACTIVE_KEY
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from test_igird_casecontrol5 import review_model
from concrete_pmm_pro.ui import igird_uls_report as report
from concrete_pmm_pro.ui.igird_case_review import AUTO_CASE, FRAME_KEYS
import hashlib
import pickle

parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', default='qa/evidence/igird_reportcharts8')
parser.add_argument('--release', default='IGIRDER.REPORTCHARTS8')
args = parser.parse_args()

state = {}
apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
state.update(review_model())
activate_member(state, 'Exterior Girder')
at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=60)
for key, value in state.items():
    at.session_state[key] = deepcopy(value)
at.session_state['_nav_active_workspace'] = 'Analysis'
at.session_state['qa_app_calculations'] = 0
calculate = mr.calculate_member


def counted(*args, **kwargs):
    st.session_state['qa_app_calculations'] += 1
    return calculate(*args, **kwargs)


def ok():
    assert not at.exception, [item.message for item in at.exception]


def element(items, label):
    return next(item for item in items if item.label == label)


records = []
with patch.object(mr, 'calculate_member', counted):
    at.run(); ok()
    element(at.radio, 'Flexure stage').set_value('Final — Composite').run(); ok()
    for check in ('Flexure', 'Shear', 'Torsion', 'Shear + Torsion'):
        element(at.radio, 'ULS check to calculate').set_value(check).run(); ok()
        next(button for button in at.button if button.label.startswith('Calculate ' + check + ' — all')).click().run(); ok()
        before = at.session_state['qa_app_calculations']
        assert before == 2 * (len(records) + 1)
        summary = next(frame.value for frame in at.dataframe if 'Result state' in frame.value)
        assert summary['Result state'].eq('CURRENT').all()
        with ExitStack() as stack:
            for function in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                             '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
                stack.enter_context(patch.object(ap, function, side_effect=AssertionError('Review must not run a solver')))
            for member in ('Exterior Girder', 'Interior Girder 2'):
                element(at.selectbox, 'Load case to review — ' + member).set_value(member + ' / ULS2').run(); ok()
                expander = element(at.expander, 'Stored check rows / source audit — ' + member)
                assert expander.dataframe[0].value['Case'].eq(member + ' / ULS2').all()
                assert at.session_state[ACTIVE_KEY] == 'Exterior Girder'
            assert at.session_state['qa_app_calculations'] == before
            at.toggle(key='igird_compact_details_'+check).set_value(True).run(); ok()
            assert not any(radio.label == 'Girder results view' for radio in at.radio)
            assert any(button.label == ('Calculate Final Composite Flexure' if check == 'Flexure' else 'Calculate '+check)
                       for button in at.button)
            if check == 'Flexure':
                assert element(at.button,'Calculate Interface Shear')
                element(at.button,'Calculate Interface Shear').click().run(); ok()
                assert ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME in at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]
            assert at.session_state['qa_app_calculations'] == before
            at.toggle(key='igird_compact_details_'+check).set_value(False).run(); ok()
        records.append({'check': check, 'current_girders': 2, 'named_case_review_girders': 2,
                        'review_solver_calls': 0, 'design_member_preserved': True, 'detailed_route_preserved': True})

    report_figures=[]
    original_render=ap._render_beam_uls_browser_plotly_figure
    def capture_report(fig,**kwargs):
        if (fig.layout.meta or {}).get('igird_report_check'):
            report_figures.append(fig)
        original_render(fig,**kwargs)
    snapshot_keys=(ACTIVE_KEY,'igird_uls_member_bank','beam_uls_loads_table',mr.CACHE_KEY,ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY)
    snapshots={key:pickle.dumps(at.session_state[key]) for key in snapshot_keys}
    chart_records=[]
    outdir=Path(args.output_dir)
    outdir.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        for function in ('_beam_uls_calculate_selected_check','_beam_uls_flexure_preview_dataframe',
                         '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
            stack.enter_context(patch.object(ap,function,side_effect=AssertionError('Report must not solve')))
        stack.enter_context(patch.object(mr,'calculate_member',side_effect=AssertionError('Report must not calculate members')))
        stack.enter_context(patch.object(ap,'_render_beam_uls_browser_plotly_figure',capture_report))
        at.session_state['_nav_active_workspace']='Report / QA'
        at.run(); ok()
        assert element(at.expander,'I-girder ULS report charts — stored results')
        assert not any(item.label=='Torsion report chart — stored results' for item in at.expander)
        for check,label in report.CHECK_LABELS.items():
            element(at.selectbox,'ULS check for report chart').set_value(label).run(); ok()
            assert set(element(at.selectbox,'Girder for report chart').options)=={'Exterior Girder','Interior Girder 2'}
            for index,member in enumerate(('Exterior Girder','Interior Girder 2')):
                element(at.selectbox,'Girder for report chart').set_value(member).run(); ok()
                element(at.selectbox,'Load case for report chart').set_value(AUTO_CASE).run(); ok()
                auto=report_figures[-1].layout.meta
                assert auto['igird_report_case']==auto['igird_report_member_control']['Controlling load case']
                for suffix in ('ULS1','ULS2'):
                    case=member+' / '+suffix
                    element(at.selectbox,'Load case for report chart').set_value(case).run(); ok()
                    fig=report_figures[-1]
                    assert fig.layout.meta['igird_report_case']==case
                    assert fig.layout.meta['igird_report_check']==check
                    assert fig.layout.meta['igird_report_member']==member
                    assert len(fig.layout.meta['igird_report_note'])==3
                    stored=element(at.expander,'Report chart — load-case ranking / source audit').dataframe[-1].value
                    assert stored['Case'].eq(case).all()
                    name=check.lower().replace(' + ','_').replace(' ','_')+'_'+str(index)+'_'+suffix.lower()
                    fig.write_json(outdir/(name+'.plotly.json'))
                    fig.write_image(outdir/(name+'.png'),width=1440,height=560,scale=1)
                    if check == 'Torsion':
                        element(at.radio,'Torsion report chart view').set_value('Overview — utilization').run(); ok()
                        utilization=report_figures[-1]
                        audit=utilization.layout.meta['torsion_utilization_audit']
                        assert all(row['Case']==case and row['Availability']=='AVAILABLE' for row in audit)
                        assert not any(row['Curve gap'] for row in audit)
                        assert any(row['Threshold status']=='BELOW THRESHOLD' for row in audit)
                        assert any(row['Tu kN-m']==0. and row['Strength utilization |Tu|/phiTn']==0. for row in audit)
                        assert utilization.layout.meta['igird_report_selected_control']==fig.layout.meta['igird_report_selected_control']
                        utilization.write_json(outdir/(name+'_utilization.plotly.json'))
                        utilization.write_image(outdir/(name+'_utilization.png'),width=1440,height=560,scale=1)
                        import pandas as pd
                        pd.DataFrame(audit).to_csv(outdir/(name+'_utilization_audit.csv'),index=False)
                        element(at.button,'Create report chart PNG').click().run(); ok()
                        assert any(item.proto.label=='Download torsion utilization station audit (CSV)' for item in at.get('download_button'))
                        assert any(item.proto.label=='Download report chart PNG' for item in at.get('download_button'))
                        element(at.radio,'Torsion report chart view').set_value('Selected case — demand / capacity').run(); ok()
            element(at.button,'Create report chart PNG').click().run(); ok()
            downloads=at.get('download_button')
            assert any(item.proto.label=='Download report chart PNG' for item in downloads)
            assert any(item.proto.label=='Download selected stored check rows (CSV)' for item in downloads)
            chart_records.append({'check':check,'current_girders':2,'named_case_charts':4,
                'automatic_control':True,'png_creation_and_download_widget':True,
                'selected_csv_download_widget':True,'review_solver_calls':0})
            if check=='Torsion':
                chart_records[-1]['utilization_cases_verified']=4
                chart_records[-1]['utilization_png_and_audit_csv_widgets']=True
        assert at.session_state['qa_app_calculations']==before
        for key,value in snapshots.items():
            assert pickle.dumps(at.session_state[key])==value,key+' changed during report review'
        # A pending member is named explicitly rather than silently represented
        # by another member's current chart.
        bank=deepcopy(at.session_state['igird_uls_member_bank'])
        changed=bank['Girder'].eq('Interior Girder 2')
        bank.loc[changed,'Mux']*=1.5
        at.session_state['igird_uls_member_bank']=bank
        element(at.selectbox,'ULS check for report chart').set_value('Flexure — Final Composite').run(); ok()
        assert element(at.selectbox,'Girder for report chart').options==['Exterior Girder']
        assert any('Interior Girder 2' in item.value and 'No current' in item.value for item in at.warning)
        bank.loc[~changed,'Mux']*=1.5
        at.session_state['igird_uls_member_bank']=bank
        active=deepcopy(at.session_state['beam_uls_loads_table'])
        active.loc[:,'Mux']*=1.5
        at.session_state['beam_uls_loads_table']=active
        at.run(); ok()
        assert not any(item.label=='Create report chart PNG' for item in at.button)
        assert at.session_state[ACTIVE_KEY]=='Exterior Girder'

result = {'release': args.release, 'status': 'PASS', 'entrypoint': 'app.py',
          'scope': 'Hypothetical QA input; full Analysis page routing, not live deployment',
          'streamlit_exceptions': 0, 'checks': records,
          'report_qa_charts': chart_records,'report_state_preserved':True,'pending_and_stale_members_hidden':True}
out = Path(args.output_dir) / 'app_integration.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
