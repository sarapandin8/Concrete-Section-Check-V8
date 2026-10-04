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
    st.caption('IGIRDER.CSIIMPORT2 · Upload your CSiBridge workbook unchanged. CSI force columns and existing app-column tables are detected automatically. Both Max/Min and every repeated station are retained.')
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
    uploaded = st.file_uploader(UPLOAD_LABEL, type=['xlsx', 'csv'], key=key_prefix+'_import_file',
        help='Automatic detection: Girder Distance / ItemType / P V2 V3 T M2 M3, or Active / Station x (m) / Case Name / Mux Vuy Tu Muy Vux Nu.')
    if uploaded is None:
        return
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
        parsed = prepare_csi_table(raw, sheet_name=source_sheet, case_name=base)
        imported = parsed.frame
        errors.extend(parsed.errors)
        st.markdown('**Source preview — all six force components**')
        st.dataframe(parsed.audit, use_container_width=True, hide_index=True)
        st.caption(f'{len(imported)} rows · Max {parsed.counts.get("Max", 0)} · Min {parsed.counts.get("Min", 0)}. Row sets retain repeated source occurrences; no Before/After face is inferred.')
        st.warning(ENVELOPE_NOTE+' Imported numerical PASS in coupled strength checks is REVIEW until corresponding FEA actions are available.')
        st.caption('P, V2, T and M3 feed the current strength checks. M2 and V3 are retained as reference values. Raw P→Nu is preserved; the solver performs the CSI axial-sign conversion internally.')
        if force_unit != 'kN' or moment_unit != 'kN-m':
            errors.append('CSI import stores kN / kN-m. Select those Force unit and Moment unit values on Loads before applying.')
    else:
        # A saved app table may already contain source tags; retain them and
        # the existing declared axial convention rather than inferring signs.
        imported = prepare_imported_workflow_load_table(raw, APP_COLUMNS)
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
