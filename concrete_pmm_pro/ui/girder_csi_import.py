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
    st.markdown('**Upload ULS loads — assigned to each girder automatically**')
    st.caption('A valid CSiBridge Bridge Object Girder Forces file replaces the previous ULS load collection immediately. Every girder receives its own rows. No Apply button is needed.')
    uploaded = st.file_uploader(UPLOAD_LABEL, type=['xlsx', 'csv'], key=key_prefix+'_import_file', accept_multiple_files=True,
        help='Native BridgeObj / SectCutNum / Girder / Distance / LocType / OutputCase / CaseType / StepType / P V2 V3 T M2 M3, individual girder sheets, or app-column tables. All worksheets are inspected.')
    advanced = st.checkbox('Advanced import settings', key=key_prefix+'_advanced_import',
        help='Choose worksheets, rename members, append loads or document verified Correspondence. Original native exports need none of these settings.')
    if uploaded:
        files = uploaded if isinstance(uploaded, list) else [uploaded]
        staged = None if advanced else _native_preview(files)
        if staged is not None:
            _apply_native_upload(staged, files, state_key=state_key, editor_key=editor_key,
                key_prefix=key_prefix, force_unit=force_unit, moment_unit=moment_unit)
        else:
            st.caption('This format uses explicit import settings. Native Bridge Object Girder Forces exports are applied automatically.')
            _render_batch(files, state_key=state_key, editor_key=editor_key, key_prefix=key_prefix,
                force_unit=force_unit, moment_unit=moment_unit)
    receipt = st.session_state.get(key_prefix+'_import_receipt')
    if receipt:
        st.success('Last successful import: '+receipt)
        st.caption('Analysis calculates every imported girder separately. Use Calculate to update results. Section and reinforcement settings remain the current shared model.')
    with st.expander('Templates and column mapping', expanded=False):
        st.dataframe(pd.DataFrame([
            ['Distance','Station x (m)'],['M3','Mux'],['V2','Vuy'],['T','Tu'],
            ['P','Nu (raw CSI P)'],['M2','Muy'],['V3','Vux'],
        ],columns=['CSiBridge','App']),hide_index=True,use_container_width=True)
        _downloads(key_prefix)
        st.caption('Keep the original title, headers, units row, Girder, OutputCase, StepType and LocType. Max/Min remains envelope screening until simultaneous actions are verified.')


def _upload_signature(files):
    identity = sorted((f.name,hashlib.sha256(f.getvalue()).hexdigest()) for f in files)
    return hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()


def _native_preview(files):
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
                    source_name=uploaded.name+' ['+digest[:8]+']')
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
    if signature != st.session_state.get(key_prefix+'_auto_import_signature'):
        _commit_import(imported,current=pd.DataFrame(st.session_state.get(BANK_KEY,[])),append=False,
            state_key=state_key,editor_key=editor_key,key_prefix=key_prefix,file_names=[f.name for f in files])
        st.session_state[key_prefix+'_auto_import_signature'] = signature
        st.rerun()
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
    frames, audits, issues, identities = [], [], [], set()
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
            eligible = {n:t for n,t in tables.items() if is_csi_table(t) or is_native_bridge_table(t) or is_app_table(t)}
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
    sign_confirmed = st.checkbox('All tables use raw CSI P signs: tension positive, compression negative', key=key_prefix+'_batch_sign')
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
    disabled = bool(issues) or imported.empty or not same_member or not sign_confirmed
    left, right = st.columns(2)
    with left:
        replace = st.button('Replace entire girder collection', type='primary', disabled=disabled, key=key_prefix+'_replace_import')
    with right:
        append = st.button('Add tables to girder collection', disabled=disabled or bool(append_issues), key=key_prefix+'_append_import')
    if replace or append:
        _commit_import(imported,current=current,append=append,state_key=state_key,editor_key=editor_key,
            key_prefix=key_prefix,file_names=[f.name for f in uploaded])
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
    st.markdown('#### Imported girders — loads stored separately')
    st.dataframe(bank.groupby('Girder', sort=False).agg(Rows=('Case Name','size'), Vector_series=('Case Name','nunique')).reset_index(), hide_index=True, use_container_width=True)
    selected = st.selectbox('Girder shown in the load table', names, index=names.index(active), key=key_prefix+'_active_girder_choice')
    if selected != active:
        save_active(st.session_state, state_key=state_key)
        activate_member(st.session_state, selected, state_key=state_key, editor_key=editor_key)
        _sync_workflow_load_tables_metadata()
        st.rerun()
    st.info(f'Load table and selected-member Summary / Report: {active}. Analysis can calculate all {len(names)} imported girders, each using only its own loads. No additional load assignment is required.')
    st.caption('Each girder uses the current shared section, reinforcement, prestress and support model. Native uploads replace the ULS collection automatically. Append and verified-source settings are available under Advanced import settings.')
