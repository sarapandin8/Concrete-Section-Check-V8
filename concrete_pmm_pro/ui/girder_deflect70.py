"""Envelope-only CSI Service import, one Calculate and one named stage plot."""
from hashlib import sha256

import pandas as pd
import streamlit as st

from concrete_pmm_pro.io import girder_deflect70 as importer
from concrete_pmm_pro.serviceability import girder_deflect70 as engine
from concrete_pmm_pro.visualization.girder_deflect70 import figure
from concrete_pmm_pro.ui.commercial import render_page_header, render_metric_cards


def _upload():
    uploaded = st.file_uploader('Envelope SLS Girder Deflection (.xlsx)', type=['xlsx'],
        key='girder_deflect70_ui_upload',
        help='Export the SLS envelope with Max and Min at every station. One worksheet per girder, named for that girder. Required: Girder Distance, ItemType, WebTop Vert and the units row. Only WebTop Vert is used.')
    present_key = 'girder_deflect70_upload_was_present'
    if uploaded is not None:
        payload = uploaded.getvalue()
        digest = sha256(payload).hexdigest()
        if digest != st.session_state.get('girder_deflect70_processed_upload'):
            try:
                bank = importer.parse_workbook(payload, uploaded.name)
                st.session_state[importer.BANK_KEY] = bank
                st.session_state.pop(importer.ERROR_KEY, None)
            except (ValueError, TypeError) as exc:
                st.session_state[importer.ERROR_KEY] = str(exc)
            st.session_state['girder_deflect70_processed_upload'] = digest
        st.session_state[present_key] = True
    elif st.session_state.get(present_key):
        for key in [importer.BANK_KEY, importer.ERROR_KEY, 'girder_deflect70_processed_upload']:
            st.session_state.pop(key, None)
        st.session_state[present_key] = False
    if st.session_state.get(importer.ERROR_KEY):
        st.error(st.session_state[importer.ERROR_KEY])
        st.caption('The previous valid input is retained for recovery. It is not used as the current Service result until this upload is replaced or removed.')
    else:
        bank = st.session_state.get(importer.BANK_KEY)
        if bank:
            st.caption(f"{bank['file_name']} · {len(bank['girders'])} girders · "
                + ', '.join(sheet['girder'] for sheet in bank['girders']) + ' · WebTop Vert only')
        else:
            st.caption('Service requires an SLS Max/Min envelope workbook. Transfer / Construction can be calculated before uploading.')


def render(*, build_curves, span_m):
    code_label = str(st.session_state.get('project_code_edition') or st.session_state.get('code_edition') or 'Project criterion')
    render_page_header('SLS Deflection / Camber', code_label + ' · individual girder results',
        icon='δ', kicker='Analysis / Serviceability', badge=engine.VERSION, accent='blue')
    _upload()
    config = engine.settings(st.session_state)
    with st.form('girder_deflect70_calculation'):
        with st.expander('Deflection criteria', expanded=False):
            st.selectbox('Service deflection criterion', list(engine.PROFILES),
                index=list(engine.PROFILES).index(config['profile']), format_func=engine.PROFILES.get,
                key='girder_deflect70_ui_profile')
            custom = st.number_input('Custom SLS envelope limit (mm)', min_value=.001, value=config['custom_limit_mm'],
                placeholder='Only for custom criterion', key='girder_deflect70_ui_custom')
            a, b = st.columns(2)
            with a:
                transfer = st.number_input('Transfer |δ| tolerance (mm)', min_value=.001, value=config['transfer_limit_mm'],
                    placeholder='Optional project tolerance', key='girder_deflect70_ui_transfer')
            with b:
                construction = st.number_input('Construction |δ| tolerance (mm)', min_value=.001, value=config['construction_limit_mm'],
                    placeholder='Optional project tolerance', key='girder_deflect70_ui_construction')
            st.caption('Railway min(L/1500, 30 mm) is a project envelope criterion requiring owner confirmation. A highway or LL-only criterion remains reference-only because this export does not identify the load-combination definition.')
        run = st.form_submit_button('Calculate deflection / camber', type='primary', width='stretch', key='girder_deflect70_calculate')
    if run:
        st.session_state[engine.SETTINGS_KEY] = {'profile': st.session_state['girder_deflect70_ui_profile'],
            'custom_limit_mm': custom, 'transfer_limit_mm': transfer, 'construction_limit_mm': construction}
        try:
            with st.spinner('Calculating precast stages and checking imported Service envelopes…'):
                result = engine.calculate(st.session_state, build_curves(), span_m)
            st.session_state[engine.RESULT_KEY] = result
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY, None)
            st.error('Deflection calculation unavailable: ' + str(exc))
    result = engine.current(st.session_state)
    if result is None:
        st.info('STALE — source or model inputs changed; Calculate again.' if engine.RESULT_KEY in st.session_state
            else 'NOT CALCULATED — press Calculate deflection / camber.')
        return
    stage = st.radio('Stage', engine.STAGES, horizontal=True, key='girder_deflect70_ui_stage')
    service = stage == 'Service stage'
    girder = None
    if service and result['girders']:
        key = 'girder_deflect70_ui_girder'
        if st.session_state.get(key) not in result['girders']:
            st.session_state[key] = result['girders'][0]
        girder = st.selectbox('Service girder', result['girders'], key=key)
    selected = result['summary'].loc[result['summary'].Stage.eq(stage)]
    selected = selected.loc[selected.Girder.eq(girder)] if girder else selected.iloc[:1]
    row = selected.iloc[0]
    render_metric_cards([
        {'title': 'Selected result', 'value': girder or ('No imported girder' if service else 'Single I-girder'),
            'detail': 'CSI WebTop Vert · SLS envelope' if service else 'Current section model · calculated', 'status': 'info'},
        {'title': 'Maximum |δ|', 'value': f"{row['Demand (mm)']:.3f} mm" if pd.notna(row['Demand (mm)']) else 'Unavailable',
            'detail': f"x={row['x (m)']:.5f} m · {row.Branch}" if pd.notna(row['x (m)']) else 'Import SLS envelope', 'status': 'info'},
        {'title': 'Selected check', 'value': row.Status,
            'detail': f'D/C {row.Utilization:.3f}' if pd.notna(row.Utilization) else 'No applicable numeric check',
            'status': 'danger' if row.Status == 'Preview FAIL' else 'ready' if row.Status == 'Preview PASS' else 'warning'},
        {'title': 'Full SLS scope', 'value': result['status'], 'detail': 'Component results and source coverage remain distinct',
            'status': 'danger' if result['status'] == 'Preview FAIL' else 'warning'},
    ])
    with st.container(key='girder_deflect70_plot'):
        st.plotly_chart(figure(result, stage, girder), width='stretch', key='girder_deflect70_chart')
    if service:
        st.caption('WebTop Vert is used as exported, with source signs retained and length units converted to mm. Envelope Max/Min are pointwise bounds. No app camber, LL, impact factor, bearing-chord correction or additional creep is applied.')
        if not result['service_available']:
            st.warning('Service has no current imported SLS girder envelope. No generated Service curve is substituted.')
    else:
        st.caption('Calculated deflection / camber of one precast I-girder in the current section model; positive = upward. Original Transfer/Construction equations are retained. Constant EI and equivalent midspan Pe remain an elastic preview.')
    st.dataframe(result['summary'][['Stage', 'Girder', 'Check', 'Branch', 'Demand (mm)', 'Limit (mm)', 'Utilization', 'Status']],
        hide_index=True, width='stretch', column_config={c: st.column_config.NumberColumn(format='%.3f')
            for c in ['Demand (mm)', 'Limit (mm)', 'Utilization']})
    with st.expander('Calculation trace / Equations / Source audit', expanded=False):
        st.write('Service: δmm = WebTop Vert × source length-unit factor × 1000. Demand = max(|Envelope Max|, |Envelope Min|) over exported stations. D/C = demand / selected applicable project limit.')
        st.write(result['limit_basis'])
        st.caption('Worksheet names identify the girders. The illustrated export has no load-case name or combination definition; no case name, LL-only attribution or long-term coverage is invented.')
        st.dataframe(result['service_audit'], hide_index=True, width='stretch')
        st.caption('Calculated Transfer / Construction source:')
        st.dataframe(result['source_audit'], hide_index=True, width='stretch')
        st.download_button('Download deflection audit', engine.report_zip(result),
            file_name='SLS_DEFLECT70_Audit.zip', mime='application/zip', key='girder_deflect70_download')
