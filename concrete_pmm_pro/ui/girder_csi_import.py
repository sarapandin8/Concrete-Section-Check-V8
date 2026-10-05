"""One ULS upload entry point; detect CSI or app columns before mapping any forces."""
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from concrete_pmm_pro.io.girder_csi_import import (
    APP_COLUMNS, CSI_COLUMNS, ENVELOPE_NOTE, append_errors, girder_ranking,
    is_app_table, is_csi_table, prepare_csi_table, read_tables,
)
from concrete_pmm_pro.analysis.girder_axial_convention import (
    CSI_TENSION_POSITIVE, SETTINGS_KEY, axial_convention,
)

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'assets/templates/Bridge_Beam_ULS_CSiBridge_Template.xlsx'
UPLOAD_LABEL = 'Upload Bridge Beam/Girder ULS station-load import'


def _downloads(key_prefix):
    units = ['m', 'm', '', 'KN', 'KN', 'KN', 'KN-m', 'KN-m', 'KN-m']
    sample = pd.DataFrame(
        [units, *[[x, x, step, *[''] * 6] for x in (0, 5, 10, 15, 20) for step in ('Max', 'Min')]],
        columns=CSI_COLUMNS,
    )
    cols = st.columns(2)
    with cols[0]:
        if TEMPLATE_PATH.is_file():
            st.download_button('Download Excel template', TEMPLATE_PATH.read_bytes(), file_name=TEMPLATE_PATH.name,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True, key=key_prefix+'_csi_xlsx')
    with cols[1]:
        st.download_button('Download CSV template', sample.to_csv(index=False).encode('utf-8-sig'),
            file_name='Bridge_Beam_ULS_CSiBridge_Template.csv', mime='text/csv', use_container_width=True, key=key_prefix+'_csi_csv')


def render_import(*, state_key, editor_key, key_prefix, force_unit, moment_unit):
    from concrete_pmm_pro.ui.loads_page import (
        _sync_workflow_load_tables_metadata, _workflow_table_result, prepare_imported_workflow_load_table,
    )

    st.markdown('**ULS Excel / CSV import — automatic format detection**')
    st.caption('IGIRDER.MULTICASE1 · Upload one or multiple workbooks/CSVs for the same physical girder. CSI force columns and existing app-column tables are detected automatically. Both Max/Min and every repeated station are retained.')
    st.dataframe(pd.DataFrame([
        ['Girder Distance', 'Station x (m)', 'm', 'Position'],
        ['M3', 'Mux', 'kN-m', 'Flexure'],
        ['V2', 'Vuy', 'kN', 'Shear'],
        ['T', 'Tu', 'kN-m', 'Torsion'],
        ['P', 'Nu (raw CSI P)', 'kN', 'Axial action'],
        ['M2', 'Muy', 'kN-m', 'Reference only'],
        ['V3', 'Vux', 'kN', 'Reference only'],
    ], columns=['CSiBridge', 'App', 'Import units', 'Use']), use_container_width=True, hide_index=True)
    _downloads(key_prefix)
    st.caption('The supplied Left Exterior workbook can be uploaded directly; no header changes, deleted units row or force-sign edits are required. Blank template force cells must be filled before importing a new template.')
    # Reuse the original app-column uploader key. A previous format-radio
    # selection can no longer route a native workbook to the wrong parser.
    uploaded = st.file_uploader(UPLOAD_LABEL, type=['xlsx', 'csv'], key=key_prefix+'_import_file', accept_multiple_files=True,
        help='Automatic detection: Girder Distance / ItemType / P V2 V3 T M2 M3, or Active / Station x (m) / Case Name / Mux Vuy Tu Muy Vux Nu.')
    if not uploaded:
        return
    if isinstance(uploaded, list):
        if len(uploaded) > 1:
            return _render_batch(uploaded, state_key=state_key, editor_key=editor_key, key_prefix=key_prefix,
                force_unit=force_unit, moment_unit=moment_unit)
        uploaded = uploaded[0]
    try:
        tables = read_tables(uploaded.getvalue(), uploaded.name)
    except Exception as exc:
        st.error(f'Could not read ULS workbook: {exc}')
        return
    eligible = {name: table for name, table in tables.items() if is_csi_table(table) or is_app_table(table)}
    if not eligible:
        st.error('No supported ULS header found. CSI tables need a distance column and all six components P, V2, V3, T, M2, M3; app tables need Case Name, Station x (m) and force columns.')
        return
    ranking = girder_ranking(eligible)
    if not ranking.empty:
        st.markdown('**Individual girder demand comparison — uploaded worksheets**')
        st.dataframe(ranking, use_container_width=True, hide_index=True)
        best = str(ranking.iloc[0]['Girder'])
        if len(ranking) > 1:
            shear = ranking.loc[ranking['|V2| kN'].idxmax(), 'Girder']
            torsion = ranking.loc[ranking['|T| kN-m'].idxmax(), 'Girder']
            st.info(f'Default flexure demand: {best} (largest |M3|). Largest |V2|: {shear}; largest |T|: {torsion}. This ranks uploaded demands, not member capacity ratios.')
        else:
            st.caption('This workbook contains one individual girder; no comparison with unprovided girders is made.')
    else:
        best = next(iter(eligible))
    sheets = list(eligible)
    fingerprint = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    selected = st.selectbox('CSiBridge worksheet / girder', sheets, index=sheets.index(best), key=key_prefix+'_csi_sheet_'+fingerprint)
    raw = eligible[selected]
    native = is_csi_table(raw)
    st.info('Detected format: '+('CSiBridge native girder forces (P, V2, V3, T, M2, M3)' if native else 'App station-load columns (existing format)'))
    errors = []
    if native:
        source_sheet = selected
        if selected == 'CSV':
            source_sheet = st.text_input('CSV girder / member name', value='Left Exterior Girder', key=key_prefix+'_csi_csv_member')
        individual = ('girder' in selected.casefold() or (selected == 'CSV' and bool(source_sheet.strip())
            and any(str(c).strip().casefold() == 'girder distance' for c in raw.columns)))
        if not individual:
            errors.append('Select an individual Girder worksheet. Entire Bridge Section, Beam-only and Slab-only forces cannot be applied as I-Girder section demand.')
        base = st.text_input('FEA case / envelope name', value='ENV_ULS', key=key_prefix+'_csi_case',
            help='If OutputCase is absent, this label identifies the factored FEA envelope. A row-set suffix preserves source occurrence order; it is not another load combination.')
        mode, confirmed, evidence = _source_controls(key_prefix+'_source_'+fingerprint)
        parsed = prepare_csi_table(raw, sheet_name=source_sheet, case_name=base,
            source_mode=mode, concurrency_confirmed=confirmed, evidence=evidence)
        imported = parsed.frame
        errors.extend(parsed.errors)
        st.markdown('**Source preview — all six force components**')
        st.dataframe(parsed.audit, use_container_width=True, hide_index=True)
        st.caption(f'{len(imported)} rows · Max {parsed.counts.get("Max", 0)} · Min {parsed.counts.get("Min", 0)}. Row sets retain repeated source occurrences; no Before/After face is inferred.')
        if mode != 'unverified' and confirmed and evidence.strip():
            st.caption('Concurrent vectors are accepted only under the recorded source declaration; Max/Min rows remain bounds unless CSI Correspondence is declared.')
        else:
            st.warning(ENVELOPE_NOTE+' Imported numerical PASS in coupled strength checks is REVIEW until corresponding FEA actions are available.')
        st.caption('P, V2, T and M3 feed the current strength checks. M2 and V3 are retained as reference values. Raw P→Nu is preserved; the solver performs the CSI axial-sign conversion internally.')
        if force_unit != 'kN' or moment_unit != 'kN-m':
            errors.append('CSI import stores kN / kN-m. Select those Force unit and Moment unit values on Loads before applying.')
    else:
        # A saved app table may already contain source tags; retain them and
        # the existing declared axial convention rather than inferring signs.
        imported = prepare_imported_workflow_load_table(raw, APP_COLUMNS)
        mode, confirmed, evidence = _source_controls(key_prefix+'_source_'+fingerprint)
        from concrete_pmm_pro.io.girder_csi_import import tag_app_source
        imported = tag_app_source(imported,source_name=uploaded.name,sheet_name=selected,
            source_mode=mode,concurrency_confirmed=confirmed,evidence=evidence)
        st.caption(f'{len(imported)} app station rows detected. Existing force values, source notes and Nu convention are retained.')
    st.markdown('**Import Preview — values sent to Analysis**')
    st.dataframe(imported, use_container_width=True, hide_index=True)
    valid = _workflow_table_result(imported, table_name='Girder ULS import',
        numeric_columns=['Station x (m)', 'Mux', 'Vuy', 'Tu', 'Muy', 'Vux', 'Nu'], unique_key_columns=['Case Name', 'Station x (m)'])
    errors.extend(valid.errors)
    for error in errors:
        st.error(error)
    disabled = bool(errors) or imported.empty
    if not disabled:
        st.success('Validation passed. Every source row and all six force components are retained.')
    current = pd.DataFrame(st.session_state.get(state_key, []), columns=APP_COLUMNS)
    current['Station x (m)'] = pd.to_numeric(current['Station x (m)'], errors='coerce')
    append_issues = append_errors(current, imported, current_is_csi=(not native or axial_convention(st.session_state)['input_sign'] == CSI_TENSION_POSITIVE))
    for issue in append_issues:
        st.caption('Append unavailable: '+issue)
    cols = st.columns(2)
    with cols[0]:
        replace = st.button('Replace current rows', type='primary', use_container_width=True, disabled=disabled, key=key_prefix+'_replace_import')
    with cols[1]:
        append = st.button('Append imported rows', use_container_width=True, disabled=disabled or bool(append_issues), key=key_prefix+'_append_import')
    if replace or append:
        st.session_state[state_key] = pd.concat([current, imported], ignore_index=True) if append else imported.copy(deep=True)
        st.session_state.pop(editor_key, None)
        if native:
            cfg = {'input_sign': CSI_TENSION_POSITIVE}
            st.session_state[SETTINGS_KEY] = cfg
            metadata = dict(st.session_state.get('project_metadata') or {})
            metadata[SETTINGS_KEY] = cfg
            st.session_state['project_metadata'] = metadata
            st.session_state.pop('igird_axial_input_sign', None)
        _sync_workflow_load_tables_metadata()
        st.rerun()


def _source_controls(key):
    label = st.selectbox('Force-vector source', ['Envelope / unverified', 'Static combination / explicit step', 'CSI Correspondence'], key=key+'_mode')
    mode = {'Envelope / unverified':'unverified', 'Static combination / explicit step':'static', 'CSI Correspondence':'correspondence'}[label]
    confirmed = False
    evidence = ''
    if mode != 'unverified':
        confirmed = st.checkbox('I confirm each row contains simultaneous factored ULS actions for this girder', key=key+'_confirmed')
        evidence = st.text_input('Source basis / export setting / combination definition', key=key+'_evidence',
            help='Record the CSI combination/step or Correspondence export setting. A file name or Max/Min label alone is not proof.')
    return mode, confirmed, evidence


def _render_batch(uploaded, *, state_key, editor_key, key_prefix, force_unit, moment_unit):
    from concrete_pmm_pro.ui.loads_page import (_sync_workflow_load_tables_metadata, _workflow_table_result,
        prepare_imported_workflow_load_table)
    frames, issues, identities = [], [], set()
    st.info('Select the same physical girder in each file. Each case/step/vector is checked separately; components are never enveloped together by the importer. Inputs must already be factored ULS combinations.')
    same_member = st.checkbox('All selected tables belong to the same physical girder and station origin', key=key_prefix+'_same_member')
    for number, uploaded_file in enumerate(uploaded):
        payload = uploaded_file.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if digest in identities:
            issues.append('Duplicate uploaded contents: '+uploaded_file.name)
            continue
        identities.add(digest)
        key = key_prefix+'_batch_'+digest[:12]
        with st.expander(f'{number+1}. {uploaded_file.name}', expanded=True):
            try:
                tables = read_tables(payload, uploaded_file.name)
            except Exception as exc:
                issues.append(uploaded_file.name+': '+str(exc))
                continue
            eligible = {n:t for n,t in tables.items() if is_csi_table(t) or is_app_table(t)}
            if not eligible:
                issues.append(uploaded_file.name+': no supported table')
                continue
            choices = list(eligible)
            preferred = [n for n in choices if 'girder' in n.casefold()]
            selected = st.multiselect('Worksheets to import', choices, default=preferred[:1] or choices[:1], key=key+'_sheets')
            base = st.text_input('Factored ULS combination name (if OutputCase is absent)', value=Path(uploaded_file.name).stem, key=key+'_case')
            member = st.text_input('Physical girder / member name', value='Left Exterior Girder', key=key+'_member')
            mode, confirmed, evidence = _source_controls(key)
            if not selected:
                issues.append(uploaded_file.name+': select at least one worksheet')
            for sheet in selected:
                raw = eligible[sheet]
                source_name = uploaded_file.name+' ['+digest[:8]+']'
                if is_csi_table(raw):
                    if sheet != 'CSV' and 'girder' not in sheet.casefold():
                        issues.append(uploaded_file.name+': select an individual Girder worksheet')
                        continue
                    parsed = prepare_csi_table(raw, sheet_name=member if sheet == 'CSV' else sheet, case_name=base,
                        source_name=source_name, source_mode=mode, concurrency_confirmed=confirmed, evidence=evidence)
                    issues.extend(parsed.errors)
                    frames.append(parsed.frame)
                else:
                    frame = prepare_imported_workflow_load_table(raw, APP_COLUMNS)
                    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
                    frame = tag_app_source(frame,source_name=source_name,sheet_name=sheet,
                        source_mode=mode,concurrency_confirmed=confirmed,evidence=evidence)
                    frame['Case Name'] = source_name+' / '+sheet+' / '+frame['Case Name'].astype(str)
                    frames.append(frame)
    imported = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=APP_COLUMNS)
    if force_unit != 'kN' or moment_unit != 'kN-m':
        issues.append('Batch import requires kN / kN-m units.')
    # CSI raw-P convention is a batch contract, including app-column tables.
    sign_confirmed = st.checkbox('All tables use raw CSI P signs: tension positive, compression negative', key=key_prefix+'_batch_sign')
    valid = _workflow_table_result(imported, table_name='Multi-table ULS import',
        numeric_columns=['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu'], unique_key_columns=['Case Name','Station x (m)'])
    issues.extend(valid.errors)
    st.dataframe(imported, use_container_width=True, hide_index=True)
    st.caption(f'{len(uploaded)} files · {len(imported)} retained rows · {imported["Case Name"].nunique()} separate vector series')
    for issue in issues:
        st.error(issue)
    current = pd.DataFrame(st.session_state.get(state_key, []), columns=APP_COLUMNS)
    append_issues = append_errors(current, imported, current_is_csi=axial_convention(st.session_state)['input_sign'] == CSI_TENSION_POSITIVE)
    disabled = bool(issues) or imported.empty or not same_member or not sign_confirmed
    left, right = st.columns(2)
    with left:
        replace = st.button('Replace current rows', type='primary', disabled=disabled, key=key_prefix+'_replace_import')
    with right:
        append = st.button('Append imported rows', disabled=disabled or bool(append_issues), key=key_prefix+'_append_import')
    if replace or append:
        st.session_state[state_key] = pd.concat([current,imported],ignore_index=True) if append else imported.copy(deep=True)
        st.session_state.pop(editor_key,None)
        cfg = {'input_sign':CSI_TENSION_POSITIVE}
        st.session_state[SETTINGS_KEY] = cfg
        metadata = dict(st.session_state.get('project_metadata') or {})
        metadata[SETTINGS_KEY] = cfg
        st.session_state['project_metadata'] = metadata
        st.session_state.pop('igird_axial_input_sign',None)
        _sync_workflow_load_tables_metadata()
        st.rerun()
