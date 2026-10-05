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
    st.caption('IGIRDER.MULTIGIRDER2 · Upload multiple workbooks/CSVs and select multiple girder worksheets. All cases are retained separately for each girder. CSI force columns and existing app-column tables are detected automatically. Both Max/Min and every repeated station are retained.')
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
    files = uploaded if isinstance(uploaded, list) else [uploaded]
    return _render_batch(files, state_key=state_key, editor_key=editor_key, key_prefix=key_prefix,
        force_unit=force_unit, moment_unit=moment_unit)


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
    st.info('Import a collection of girders and factored ULS cases. Assign the same physical girder name across files for the same member. Analysis uses only the selected girder and its complete case set.')
    same_member = st.checkbox('I confirm member names identify physical girders consistently across files, with the same station origin for each member', key=key_prefix+'_same_member')
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
            selected = st.multiselect('Worksheets to import', choices, default=preferred or choices[:1], key=key+'_sheets')
            base = st.text_input('Factored ULS combination name (if OutputCase is absent)', value=Path(uploaded_file.name).stem, key=key+'_case')
            mode, confirmed, evidence = _source_controls(key)
            if not selected:
                issues.append(uploaded_file.name+': select at least one worksheet')
            for sheet in selected:
                raw = eligible[sheet]
                member = st.text_input('Physical girder / member name — '+sheet, value=sheet if sheet != 'CSV' else Path(uploaded_file.name).stem, key=key+'_member_'+sheet).strip()
                if not member:
                    issues.append(uploaded_file.name+': physical girder name is required')
                    continue
                source_name = uploaded_file.name+' ['+digest[:8]+']'
                if is_csi_table(raw):
                    if sheet != 'CSV' and 'girder' not in sheet.casefold():
                        issues.append(uploaded_file.name+': select an individual Girder worksheet')
                        continue
                    parsed = prepare_csi_table(raw, sheet_name=member if sheet == 'CSV' else sheet, case_name=base,
                        source_name=source_name, source_mode=mode, concurrency_confirmed=confirmed, evidence=evidence)
                    issues.extend(parsed.errors)
                    frame = parsed.frame.copy()
                    frame['Case Name'] = member+' / '+frame['Case Name'].astype(str)
                    frame['Girder'] = member
                    frames.append(frame)
                else:
                    frame = prepare_imported_workflow_load_table(raw, APP_COLUMNS)
                    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
                    frame = tag_app_source(frame,source_name=source_name,sheet_name=sheet,
                        source_mode=mode,concurrency_confirmed=confirmed,evidence=evidence)
                    frame['Case Name'] = source_name+' / '+sheet+' / '+frame['Case Name'].astype(str)
                    frame['Case Name'] = member+' / '+frame['Case Name'].astype(str)
                    frame['Girder'] = member
                    frames.append(frame)
    imported = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=['Girder', *APP_COLUMNS])
    if force_unit != 'kN' or moment_unit != 'kN-m':
        issues.append('Batch import requires kN / kN-m units.')
    # CSI raw-P convention is a batch contract, including app-column tables.
    sign_confirmed = st.checkbox('All tables use raw CSI P signs: tension positive, compression negative', key=key_prefix+'_batch_sign')
    valid = _workflow_table_result(imported, table_name='Multi-table ULS import',
        numeric_columns=['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu'], unique_key_columns=['Girder','Case Name','Station x (m)'])
    issues.extend(valid.errors)
    st.dataframe(imported, use_container_width=True, hide_index=True)
    st.caption(f'{len(uploaded)} files · {len(imported)} retained rows · {imported["Case Name"].nunique()} separate vector series')
    for issue in issues:
        st.error(issue)
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, merge_bank, save_active, activate_member
    save_active(st.session_state)
    current = pd.DataFrame(st.session_state.get(BANK_KEY, []))
    if current.empty:
        previous = pd.DataFrame(st.session_state.get(state_key, []), columns=APP_COLUMNS)
        if not previous.empty:
            from concrete_pmm_pro.io.girder_csi_import import source_info
            source_members = {source_info(row).get('sheet') for _, row in previous.iterrows() if source_info(row)}
            source_members.discard(None)
            previous_member = st.text_input('Existing current table — girder name to retain when adding tables',
                value=next(iter(source_members)) if len(source_members) == 1 else 'Existing girder', key=key_prefix+'_legacy_member').strip()
            previous['Girder'] = previous_member
            current = previous
            st.caption('Add tables retains the existing current table under this member name. Replace entire girder collection discards it.')
    append_issues = []
    if not current.empty:
        if current['Girder'].astype(str).str.strip().eq('').any():
            append_issues.append('Assign a name to the existing current table.')
        try:
            merge_bank(current, imported, append=True)
        except ValueError as exc:
            append_issues.append(str(exc))
        if axial_convention(st.session_state)['input_sign'] != CSI_TENSION_POSITIVE:
            append_issues.append('Existing collection uses a different axial convention.')
    for issue in append_issues:
        st.caption('Append unavailable: '+issue)
    disabled = bool(issues) or imported.empty or not same_member or not sign_confirmed
    left, right = st.columns(2)
    with left:
        replace = st.button('Replace entire girder collection', type='primary', disabled=disabled, key=key_prefix+'_replace_import')
    with right:
        append = st.button('Add tables to girder collection', disabled=disabled or bool(append_issues), key=key_prefix+'_append_import')
    if replace or append:
        bank = merge_bank(current, imported, append=append)
        st.session_state[BANK_KEY] = bank
        activate_member(st.session_state, str(imported.iloc[0]['Girder']), state_key=state_key, editor_key=editor_key)
        st.session_state.pop(key_prefix+'_active_girder_choice', None)
        cfg = {'input_sign':CSI_TENSION_POSITIVE}
        st.session_state[SETTINGS_KEY] = cfg
        metadata = dict(st.session_state.get('project_metadata') or {})
        metadata[SETTINGS_KEY] = cfg
        st.session_state['project_metadata'] = metadata
        st.session_state.pop('igird_axial_input_sign',None)
        _sync_workflow_load_tables_metadata()
        st.rerun()


def render_member_collection(*, state_key, editor_key, key_prefix):
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, ACTIVE_KEY, members, save_active, activate_member
    from concrete_pmm_pro.ui.loads_page import _sync_workflow_load_tables_metadata
    bank = pd.DataFrame(st.session_state.get(BANK_KEY, []))
    names = members(bank)
    if not names:
        return
    save_active(st.session_state, state_key=state_key)
    active = st.session_state.get(ACTIVE_KEY)
    if active not in names:
        active = names[0]
        activate_member(st.session_state, active, state_key=state_key, editor_key=editor_key)
    st.markdown('#### Imported girder collection — select member for Analysis')
    st.dataframe(bank.groupby('Girder', sort=False).agg(Rows=('Case Name','size'), Vector_series=('Case Name','nunique')).reset_index(), hide_index=True, use_container_width=True)
    selected = st.selectbox('Girder to design', names, index=names.index(active), key=key_prefix+'_active_girder_choice')
    if st.button('Use this girder — all imported load cases', key=key_prefix+'_activate_member'):
        save_active(st.session_state, state_key=state_key)
        activate_member(st.session_state, selected, state_key=state_key, editor_key=editor_key)
        _sync_workflow_load_tables_metadata()
        st.rerun()
    st.info(f'Analysis member: {active}. All its active load cases are checked against the current section, reinforcement, prestress and support settings. Verify those settings for this member before calculating.')
    st.caption('Replace entire girder collection replaces all stored girders. Add tables retains existing members/cases. Changing the member requires recalculation; previous results must be reviewed for their case names.')
