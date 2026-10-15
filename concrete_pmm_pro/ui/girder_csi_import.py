"""One ULS upload entry point; detect CSI or app columns before mapping any forces."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from concrete_pmm_pro.io.girder_csi_import import (
    APP_COLUMNS, CSI_COLUMNS, ENVELOPE_NOTE, append_errors, girder_ranking,
    is_app_table, is_csi_table, is_native_bridge_table, prepare_csi_table, read_tables, split_member_tables,
)
from concrete_pmm_pro.analysis.girder_axial_convention import (
    CSI_TENSION_POSITIVE, SETTINGS_KEY, axial_convention,
)

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'assets/templates/Bridge_Beam_ULS_CSiBridge_Template.xlsx'
UPLOAD_LABEL = 'Upload Bridge Beam/Girder ULS station-load import'
SOURCE_LABELS = ['CSI Correspondence', 'Static case / explicit step', 'Envelope / unverified']
SOURCE_MODES = ['correspondence', 'static', 'unverified']


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
    st.markdown('**Import ULS loads**')
    from concrete_pmm_pro.ui.csi_force_reference import render_settings
    render_settings(key_prefix=key_prefix + '_csi_reference')
    st.caption('File → Force source → Import loads. Girders and load cases are assigned automatically.')
    uploaded = st.file_uploader(UPLOAD_LABEL, type=['xlsx', 'csv'], key=key_prefix+'_import_file', accept_multiple_files=True,
        help='Native BridgeObj / SectCutNum / Girder / Distance / LocType / OutputCase / CaseType / StepType / P V2 V3 T M2 M3, individual girder sheets, or app-column tables. All worksheets are inspected.')
    files = uploaded if isinstance(uploaded, list) else ([uploaded] if uploaded else [])
    source_contract = None
    if files:
        signature = _upload_signature(files)
        source_contract = _source_controls(key_prefix+'_source_'+signature[:12],
            default_mode=_saved_source_mode(files))
    with st.expander('More import options', expanded=False):
        advanced = st.checkbox('Advanced import settings', key=key_prefix+'_advanced_import',
            help='Optional worksheet/member mapping, append and downloads. The normal import needs none of these settings.')
    if uploaded:
        mode, confirmed, evidence = source_contract
        staged = None if advanced else _native_preview(files, source_mode=mode,
            concurrency_confirmed=confirmed, evidence=evidence)
        if staged is not None:
            _render_simple_native_import(staged, files, state_key=state_key, editor_key=editor_key,
                key_prefix=key_prefix, force_unit=force_unit, moment_unit=moment_unit)
        else:
            if not advanced:
                st.info('This file needs worksheet/member mapping. Check the detected names below, then import.')
            _render_batch(files, state_key=state_key, editor_key=editor_key, key_prefix=key_prefix,
                force_unit=force_unit, moment_unit=moment_unit, source_contract=source_contract)
    receipt = st.session_state.get(key_prefix+'_import_receipt')
    _render_saved_source_readiness()
    with st.expander('Templates and column mapping', expanded=False):
        if receipt:
            st.caption('Last successful import: '+receipt)
        st.dataframe(pd.DataFrame([
            ['Distance','Station x (m)'],['M3','Mux'],['V2','Vuy'],['T','Tu'],
            ['P','Nu (raw CSI P)'],['M2','Muy'],['V3','Vux'],
        ],columns=['CSiBridge','App']),hide_index=True,use_container_width=True)
        _downloads(key_prefix)
        st.caption('Keep the original title, headers, units row, Girder, OutputCase, StepType and LocType. Max/Min remains envelope screening until simultaneous actions are verified.')


def _upload_signature(files):
    identity = sorted((f.name,hashlib.sha256(f.getvalue()).hexdigest()) for f in files)
    return hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()


def _source_declaration(mode):
    """Record the engineer's explicit source choice without required free text."""
    if mode not in {'correspondence', 'static'}:
        return mode, False, ''
    basis = ('CSI Correspondence' if mode == 'correspondence' else 'Static case / explicit step')
    return mode, True, ('Engineer declaration through force-source selection and Import loads: '
        + basis + '; each row contains simultaneous factored ULS actions for its girder '
        'and section face. Raw CSI P signs are retained. This is an engineer declaration, '
        'not automatic verification of the CSI export.')


def _saved_source_mode(files):
    """Restore a choice only for the same saved source file, never for new bytes."""
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
    from concrete_pmm_pro.io.girder_csi_import import source_info
    from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed
    bank = pd.DataFrame(st.session_state.get(BANK_KEY, []))
    if bank.empty:
        return 'unverified'
    choices = set()
    for uploaded in files:
        digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
        name = uploaded.name+' ['+digest[:8]+']'
        matching = [source_info(row) for _, row in bank.iterrows()
            if (source_info(row) or {}).get('source_file') == name]
        if not matching or not all(concurrent_source_allowed(info) for info in matching):
            return 'unverified'
        choices.update(info['source_mode'] for info in matching)
    return next(iter(choices)) if len(choices) == 1 else 'unverified'


def _render_simple_native_import(staged, files, *, state_key, editor_key, key_prefix,
                                 force_unit, moment_unit):
    """One explicit commit; changing a dropdown or revisiting never changes loads."""
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
    from concrete_pmm_pro.io.girder_csi_import import source_info
    imported, parse_issues = staged
    issues = list(parse_issues)
    if force_unit != 'kN' or moment_unit != 'kN-m':
        issues.append('Set load units to kN / kN-m before importing.')
    if not imported.empty:
        cases = {source_info(row).get('case') for _, row in imported.iterrows()}
        st.caption(f'{len(imported)} rows · {imported.Girder.nunique()} girders · '
            f'{len(cases)} load cases. Import loads replaces the current load collection.')
    for issue in issues:
        st.error(issue)
    if st.button('Import loads', type='primary', disabled=bool(issues) or imported.empty,
                 key=key_prefix+'_simple_import'):
        _commit_import(imported, current=pd.DataFrame(st.session_state.get(BANK_KEY, [])),
            append=False, state_key=state_key, editor_key=editor_key, key_prefix=key_prefix,
            file_names=[f.name for f in files])
        st.session_state[key_prefix+'_auto_import_signature'] = _upload_signature(files)
        st.rerun()
    with st.expander('Preview source rows', expanded=False):
        st.dataframe(imported[['Girder','Station x (m)','Case Name','Mux','Vuy','Tu','Muy','Vux','Nu']],
            hide_index=True, use_container_width=True)


def _native_source_identity(row):
    """Identify an original file row without treating its force sign as proof."""
    from concrete_pmm_pro.io.girder_csi_import import source_info
    info = source_info(row) or {}
    digest = info.get('source_sha256')
    if not digest:
        return None
    return (digest, info.get('source_file'), info.get('sheet'), info.get('row'),
            info.get('bridge_object'), info.get('girder'), info.get('case'),
            info.get('step'), info.get('location_type'), info.get('occurrence'))


def _native_upload_already_stored(imported, bank):
    """A reread of the same file must preserve the committed source contract.

    Row identities come from the actual saved load bank, so this also works
    after loading a Project JSON without the session-only upload signature.
    No contract is transferred to a new file or a missing source row.
    """
    if imported.empty or bank.empty:
        return False
    expected = [_native_source_identity(row) for _, row in imported.iterrows()]
    saved = {_native_source_identity(row) for _, row in bank.iterrows()}
    return all(identity is not None and identity in saved for identity in expected)


def saved_source_readiness(bank):
    """Expose what Analysis will actually consume, not uncommitted controls."""
    from concrete_pmm_pro.io.girder_csi_import import source_info
    from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed
    records = []
    if bank.empty or 'Girder' not in bank:
        return pd.DataFrame()
    for member, rows in bank.groupby('Girder', sort=False):
        allowed = rows.apply(lambda row: concurrent_source_allowed(source_info(row)), axis=1)
        records.append({'Girder': member, 'Saved rows': len(rows),
            'Concurrent rows ready for V+T': int(allowed.sum()),
            'Source-blocked rows': int((~allowed).sum())})
    return pd.DataFrame(records)


def _render_saved_source_readiness():
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
    readiness = saved_source_readiness(pd.DataFrame(st.session_state.get(BANK_KEY, [])))
    if readiness.empty:
        return
    st.markdown('**Imported loads**')
    st.dataframe(readiness.rename(columns={'Saved rows':'Rows',
        'Concurrent rows ready for V+T':'Concurrent', 'Source-blocked rows':'Unverified'}),
        hide_index=True, use_container_width=True)
    blocked = int(readiness['Source-blocked rows'].sum())
    if blocked:
        st.warning(f'{blocked} rows have unverified concurrency. For V+T, select the matching '
            'Correspondence or Static source and press Import loads.')
    else:
        st.success('Concurrent source saved. Go to Analysis → Calculate Shear + Torsion.')


def _native_preview(files, *, source_mode='unverified', concurrency_confirmed=False, evidence=''):
    """Validate all native files first; never publish a partial import."""
    from concrete_pmm_pro.ui.loads_page import _workflow_table_result
    frames, issues, seen = [], [], set()
    for uploaded in files:
        payload = uploaded.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if digest in seen:
            issues.append('Duplicate file contents: '+uploaded.name)
            continue
        seen.add(digest)
        try:
            tables = read_tables(payload,uploaded.name)
        except Exception as exc:
            issues.append(uploaded.name+': '+str(exc))
            continue
        eligible = {n:t for n,t in tables.items() if is_native_bridge_table(t) or is_csi_table(t) or is_app_table(t)}
        if not eligible or not all(is_native_bridge_table(t) for t in eligible.values()):
            return None
        for sheet, table in eligible.items():
            groups = split_member_tables(table,sheet_name=sheet)
            if not groups:
                issues.append(uploaded.name+': no physical member rows')
            for group in groups:
                parsed = prepare_csi_table(group.frame,sheet_name=sheet,
                    source_name=uploaded.name+' ['+digest[:8]+']', source_mode=source_mode,
                    concurrency_confirmed=concurrency_confirmed, evidence=evidence)
                issues.extend(parsed.errors)
                frame = parsed.frame.copy()
                frame['Case Name'] = group.name+' / '+frame['Case Name'].astype(str)
                frame['Girder'] = group.name
                frames.append(frame)
    imported = pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=['Girder',*APP_COLUMNS])
    valid = _workflow_table_result(imported,table_name='ULS import',
        numeric_columns=['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu'],
        unique_key_columns=['Girder','Case Name','Station x (m)'])
    return imported, [*issues,*valid.errors]


def _commit_import(imported, *, current, append, state_key, editor_key, key_prefix, file_names):
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, merge_bank, activate_member
    from concrete_pmm_pro.ui.loads_page import _sync_workflow_load_tables_metadata
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.io.csi_force_reference import bind_reference, configured_profile
    imported = bind_reference(imported, configured_profile(st.session_state))
    bank = merge_bank(current,imported,append=append)
    st.session_state[BANK_KEY] = bank
    activate_member(st.session_state,str(imported.iloc[0]['Girder']),state_key=state_key,editor_key=editor_key)
    st.session_state.pop(key_prefix+'_active_girder_choice',None)
    cfg = {'input_sign':CSI_TENSION_POSITIVE}
    st.session_state[SETTINGS_KEY] = cfg
    metadata = dict(st.session_state.get('project_metadata') or {})
    metadata[SETTINGS_KEY] = cfg
    st.session_state['project_metadata'] = metadata
    st.session_state.pop('igird_axial_input_sign',None)
    st.session_state.pop(mr.CACHE_KEY,None)
    st.session_state.pop(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,None)
    st.session_state[key_prefix+'_import_receipt'] = (
        ', '.join(file_names)+f' — {len(imported)} rows imported; {bank.Girder.nunique()} girders / {len(bank)} rows stored'
        + ('; added to collection' if append else '; replaced previous ULS collection'))
    _sync_workflow_load_tables_metadata()


def _apply_native_upload(staged, files, *, state_key, editor_key, key_prefix, force_unit, moment_unit):
    from concrete_pmm_pro.io.girder_csi_import import source_info
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
    imported, parse_issues = staged
    issues = list(parse_issues)
    if force_unit != 'kN' or moment_unit != 'kN-m':
        issues.append('Set app units to kN / kN-m before importing.')
    if issues or imported.empty:
        st.error('Upload not applied. The previous ULS loads are still in use.')
        for issue in issues: st.error(issue)
        return
    signature = _upload_signature(files)
    bank = pd.DataFrame(st.session_state.get(BANK_KEY, []))
    already_stored = _native_upload_already_stored(imported, bank)
    if signature != st.session_state.get(key_prefix+'_auto_import_signature') and not already_stored:
        _commit_import(imported,current=pd.DataFrame(st.session_state.get(BANK_KEY,[])),append=False,
            state_key=state_key,editor_key=editor_key,key_prefix=key_prefix,file_names=[f.name for f in files])
        st.session_state[key_prefix+'_auto_import_signature'] = signature
        st.rerun()
    # Advanced import, project loading and widget cleanup must never reapply an
    # unverified preview over the saved correspondence rows for this file.
    st.session_state[key_prefix+'_auto_import_signature'] = signature
    st.markdown('**Loads assigned by Girder**')
    summaries = []
    for member,frame in imported.groupby('Girder',sort=False):
        cases = list(dict.fromkeys(source_info(r)['case'] for _,r in frame.iterrows()))
        summaries.append({'Girder':member,'Load cases':', '.join(cases),'Rows':len(frame),
            'Start (m)':frame['Station x (m)'].min(),'End (m)':frame['Station x (m)'].max()})
    st.dataframe(pd.DataFrame(summaries),hide_index=True,use_container_width=True)
    st.caption('All cases, Max/Min, Before/After and all six force components are retained. P maps to Nu with raw CSI signs. Go to Analysis and Calculate; importing loads does not run a solver.')
    with st.expander('Uploaded source rows',expanded=False):
        st.dataframe(imported[['Girder','Station x (m)','Case Name','Mux','Vuy','Tu','Muy','Vux','Nu']],
            hide_index=True,use_container_width=True)
        st.caption('This is the uploaded source. Subsequent load-table edits are retained; reviewing this file does not import it again.')


def _source_controls(key, *, default_mode='unverified'):
    label = st.radio('Force source', SOURCE_LABELS, horizontal=True,
        index=SOURCE_MODES.index(default_mode), key=key+'_mode',
        help='Correspondence: simultaneous moving-load actions. Static: one explicit case/step. Envelope: simultaneous actions are not established.')
    mode = SOURCE_MODES[SOURCE_LABELS.index(label)]
    if mode == 'unverified':
        st.caption('Envelope bounds can be reviewed; V+T needs simultaneous actions.')
    else:
        st.caption('Import loads records your declaration that each row contains simultaneous factored '
            'actions for the same girder and section. Raw CSI P signs are kept.')
    return _source_declaration(mode)


def _render_batch(uploaded, *, state_key, editor_key, key_prefix, force_unit, moment_unit,
                  source_contract=None):
    from concrete_pmm_pro.ui.loads_page import (_sync_workflow_load_tables_metadata, _workflow_table_result,
        prepare_imported_workflow_load_table)
    frames, audits, issues, identities = [], [], [], set()
    st.caption('Optional worksheet/member mapping. Keep the same name and station origin for the same physical girder across files.')
    per_file = st.checkbox('Different force sources by file', key=key_prefix+'_per_file_sources')
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
            eligible = {n:t for n,t in tables.items() if is_csi_table(t) or is_native_bridge_table(t) or is_app_table(t)}
            if not eligible:
                issues.append(uploaded_file.name+': no supported table')
                continue
            choices = list(eligible)
            preferred = [n for n in choices if 'girder' in n.casefold()]
            selected = st.multiselect('Worksheets to import', choices, default=preferred or choices[:1], key=key+'_sheets')
            base = st.text_input('Factored ULS combination name (if OutputCase is absent)', value=Path(uploaded_file.name).stem, key=key+'_case')
            mode, confirmed, evidence = (_source_controls(key) if per_file or source_contract is None
                else source_contract)
            if not selected:
                issues.append(uploaded_file.name+': select at least one worksheet')
            assigned_members = {}
            for sheet in selected:
                groups = split_member_tables(eligible[sheet], sheet_name=sheet)
                if not groups:
                    issues.append(uploaded_file.name+': '+sheet+' has no physical member rows')
                if len(groups) > 1:
                    st.caption(f'{sheet}: {len(groups)} physical girders detected. Every source row is retained in its own member table.')
                for group_number, group in enumerate(groups):
                    raw = group.frame
                    default_name = group.name if group.girder or sheet != 'CSV' else Path(uploaded_file.name).stem
                    member = st.text_input('Physical girder / member name — '+group.name,
                        value=default_name, key=key+'_member_'+sheet+'_'+str(group_number)).strip()
                    if not member:
                        issues.append(uploaded_file.name+': physical girder name is required')
                        continue
                    identity = (sheet, group.bridge_object, group.girder)
                    canonical_member = member.casefold()
                    if canonical_member in assigned_members and assigned_members[canonical_member] != identity:
                        issues.append(uploaded_file.name+': distinct source members cannot share the same physical member name: '+member)
                    assigned_members[canonical_member] = identity
                    source_name = uploaded_file.name+' ['+digest[:8]+']'
                    if is_csi_table(raw) or is_native_bridge_table(raw):
                        if not group.girder and sheet != 'CSV' and 'girder' not in sheet.casefold():
                            issues.append(uploaded_file.name+': select an individual Girder worksheet or a table with a Girder column')
                            continue
                        parsed = prepare_csi_table(raw, sheet_name=sheet, case_name=base,
                            source_name=source_name, source_mode=mode, concurrency_confirmed=confirmed, evidence=evidence)
                        issues.extend(parsed.errors)
                        frame = parsed.frame.copy()
                        frame['Case Name'] = member+' / '+frame['Case Name'].astype(str)
                        frame['Girder'] = member
                        frames.append(frame)
                        audit = parsed.audit.copy()
                        if not audit.empty:
                            audit['Physical member'] = member
                            audit['Case Name'] = member+' / '+audit['Case Name'].astype(str)
                            audits.append(audit)
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
    st.caption('Import keeps raw CSI P: positive tension, negative compression. App-column files must use the same sign convention.')
    valid = _workflow_table_result(imported, table_name='Multi-table ULS import',
        numeric_columns=['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu'], unique_key_columns=['Girder','Case Name','Station x (m)'])
    issues.extend(valid.errors)
    preview_columns = ['Girder','Station x (m)','Case Name','Mux','Vuy','Tu','Muy','Vux','Nu']
    st.dataframe(imported[preview_columns], use_container_width=True, hide_index=True)
    st.caption(f'{len(uploaded)} file{"s" if len(uploaded)!=1 else ""} · {len(imported)} retained rows · {imported["Case Name"].nunique()} separate vector series')
    if not imported.empty:
        st.dataframe(imported.groupby('Girder', sort=False).agg(
            Rows=('Case Name','size'), Vector_series=('Case Name','nunique'),
            Start_m=('Station x (m)','min'), End_m=('Station x (m)','max')).reset_index().rename(
                columns={'Vector_series':'Vector series','Start_m':'Start (m)','End_m':'End (m)'}),
            use_container_width=True, hide_index=True)
    audit_frame = pd.concat(audits, ignore_index=True) if audits else pd.DataFrame()
    if not audit_frame.empty:
        with st.expander('Source rows / units — Before/After and original CSI fields'):
            st.dataframe(audit_frame, use_container_width=True, hide_index=True)
            st.caption('Original CSI columns and raw signs are retained alongside normalized m / kN / kN-m values. Max/Min bounds remain envelope screening unless concurrency is established from the source export.')
    if not issues and not imported.empty:
        downloads = st.columns(2)
        with downloads[0]:
            st.download_button('Download all-member app CSV', imported.to_csv(index=False).encode('utf-8-sig'),
                file_name='CSiBridge_ULS_CSIIMPORT14_all_girders.csv', mime='text/csv',
                use_container_width=True, key=key_prefix+'_normalized_csv')
        if not audit_frame.empty:
            with downloads[1]:
                st.download_button('Download original-row audit CSV', audit_frame.to_csv(index=False).encode('utf-8-sig'),
                    file_name='CSiBridge_ULS_CSIIMPORT14_source_audit.csv', mime='text/csv',
                    use_container_width=True, key=key_prefix+'_source_audit_csv')
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
    disabled = bool(issues) or imported.empty
    left, right = st.columns(2)
    with left:
        replace = st.button('Replace entire girder collection', type='primary', disabled=disabled, key=key_prefix+'_replace_import')
    with right:
        append = st.button('Add tables to girder collection', disabled=disabled or bool(append_issues), key=key_prefix+'_append_import')
    if replace or append:
        _commit_import(imported,current=current,append=append,state_key=state_key,editor_key=editor_key,
            key_prefix=key_prefix,file_names=[f.name for f in uploaded])
        st.session_state[key_prefix+'_auto_import_signature'] = _upload_signature(uploaded)
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
    selected = st.selectbox('Girder shown in the load table', names, index=names.index(active), key=key_prefix+'_active_girder_choice')
    if selected != active:
        save_active(st.session_state, state_key=state_key)
        activate_member(st.session_state, selected, state_key=state_key, editor_key=editor_key)
        _sync_workflow_load_tables_metadata()
        st.rerun()
    st.caption(f'Load table / Summary / Report: {active}. Analysis can calculate all {len(names)} girders separately. Section and reinforcement inputs are shared.')
