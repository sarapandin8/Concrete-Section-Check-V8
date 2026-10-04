"""Native CSI member worksheet selection, preview, and reversible Loads apply."""
from pathlib import Path
import pandas as pd
import streamlit as st

from concrete_pmm_pro.io.girder_csi_import import (
    CSI_COLUMNS, ENVELOPE_NOTE, append_errors, girder_ranking, is_csi_table,
    prepare_csi_table, read_tables,
)
from concrete_pmm_pro.analysis.girder_axial_convention import (
    CSI_TENSION_POSITIVE, SETTINGS_KEY, axial_convention,
)

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / 'assets/templates/Bridge_Beam_ULS_CSiBridge_Template.xlsx'

def render_import(*, state_key, editor_key, key_prefix, force_unit, moment_unit):
    from concrete_pmm_pro.ui.loads_page import _sync_workflow_load_tables_metadata, _workflow_table_result

    st.markdown('**CSiBridge girder ULS import — Max / Min**')
    st.caption('Select an individual girder worksheet. Each original row is retained, including repeated stations and both Max and Min. Forces are normalized to kN and kN-m; all signs are preserved.')
    mapping=pd.DataFrame([
        ['Girder Distance','Station x (m)','m'],['M3','Mux','kN-m'],['V2','Vuy','kN'],
        ['T','Tu','kN-m'],['M2','Muy','kN-m'],['V3','Vux','kN'],['P','Nu (raw CSI P)','kN'],
    ],columns=['CSiBridge','App','Import units'])
    st.dataframe(mapping,use_container_width=True,hide_index=True)
    units=['m','m','','KN','KN','KN','KN-m','KN-m','KN-m']
    sample=pd.DataFrame([units,*[[x,x,step,*['']*6] for x in (0,5,10,15,20) for step in ('Max','Min')]],columns=CSI_COLUMNS)
    downloads=st.columns(2)
    with downloads[0]:
        if TEMPLATE_PATH.is_file():
            st.download_button('Download Excel template',TEMPLATE_PATH.read_bytes(),file_name=TEMPLATE_PATH.name,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key=key_prefix+'_csi_xlsx')
    with downloads[1]:
        st.download_button('Download CSV template',sample.to_csv(index=False).encode('utf-8-sig'),
            file_name='Bridge_Beam_ULS_CSiBridge_Template.csv',mime='text/csv',use_container_width=True,key=key_prefix+'_csi_csv')
    st.caption('The template contains a units row and example stations for a 20 m girder. Replace stations with the real export and fill all six components, including explicit zeros. Native multi-sheet CSiBridge exports can be uploaded directly.')
    uploaded=st.file_uploader('Upload CSiBridge girder forces',type=['xlsx','csv'],key=key_prefix+'_csi_file')
    if uploaded is None:
        return
    try:
        tables=read_tables(uploaded.getvalue(),uploaded.name)
    except Exception as exc:
        st.error(f'Could not read CSI tables: {exc}')
        return
    eligible={name:table for name,table in tables.items() if is_csi_table(table)}
    if not eligible:
        st.error('No native CSI force table found. For the existing Active / Case Name / Mux format, select App columns (legacy).')
        return
    ranking=girder_ranking(eligible)
    if not ranking.empty:
        st.markdown('**Individual girder demand comparison — both Max and Min**')
        st.dataframe(ranking,use_container_width=True,hide_index=True)
        best=str(ranking.iloc[0]['Girder'])
        shear=ranking.loc[ranking['|V2| kN'].idxmax(),'Girder']
        torsion=ranking.loc[ranking['|T| kN-m'].idxmax(),'Girder']
        st.info(f'Default for flexure: {best} (largest |M3|). Largest |V2|: {shear}; largest |T|: {torsion}. This is demand ranking; it does not compare section capacity or certify one girder as critical for every check.')
    else:
        best=next(iter(eligible))
    sheets=list(eligible)
    # A new upload resets the selection to its critical individual girder.
    import hashlib
    fingerprint=hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    selected=st.selectbox('CSiBridge worksheet / girder',sheets,index=sheets.index(best),key=key_prefix+'_csi_sheet_'+fingerprint)
    source_sheet=selected
    if selected=='CSV':
        source_sheet=st.text_input('CSV girder / member name',value='Left Exterior Girder',key=key_prefix+'_csi_csv_member')
    individual=('girder' in selected.casefold() or (selected=='CSV' and bool(source_sheet.strip())
        and any(str(c).strip().casefold()=='girder distance' for c in eligible[selected].columns)))
    if not individual:
        st.error('Select an individual Girder worksheet for the I-Girder section check. Entire Bridge Section, Beam-only and Slab-only forces are not the same section demand.')
    base=st.text_input('FEA case / envelope name',value='ENV_ULS',key=key_prefix+'_csi_case',help='The supplied table has no OutputCase column. Enter the actual factored FEA combination or envelope name; a row-set suffix is source occurrence order, not an FEA load case.')
    parsed=prepare_csi_table(eligible[selected],sheet_name=source_sheet,case_name=base)
    st.markdown('**Source preview — mapped without combining rows**')
    st.dataframe(parsed.audit,use_container_width=True,hide_index=True)
    st.caption(f'{len(parsed.frame)} rows · Max {parsed.counts.get("Max",0)} · Min {parsed.counts.get("Min",0)}. Row set 1/2 preserves the order of repeated rows at each station; no Before/After face is inferred.')
    with st.expander('Mapped app rows / source metadata',expanded=False):
        st.dataframe(parsed.frame,use_container_width=True,hide_index=True)
    st.warning(ENVELOPE_NOTE+' Imported numerical PASS in coupled strength checks is REVIEW until corresponding FEA actions are available.')
    st.caption('Raw P→Nu is kept. Applying this import declares CSI tension-positive axial input; the existing solver converts Nu internally. No force is negated during import.')
    valid=_workflow_table_result(parsed.frame,table_name='CSiBridge girder ULS',
        numeric_columns=['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu'],unique_key_columns=['Case Name','Station x (m)'])
    errors=[*parsed.errors,*valid.errors]
    units_ok=force_unit=='kN' and moment_unit=='kN-m'
    if not units_ok:
        errors.append('This native import stores kN / kN-m. Select kN / kN-m in the Force unit and Moment unit controls on Loads before applying.')
    for error in errors:
        st.error(error)
    disabled=bool(errors) or parsed.frame.empty or not individual
    if not disabled:
        st.success('Validation passed. Every source row and all six force components are retained.')
    current=pd.DataFrame(st.session_state.get(state_key,[]),columns=parsed.frame.columns)
    # Normalize just the duplicate key, not source forces or signs.
    current['Station x (m)']=pd.to_numeric(current['Station x (m)'],errors='coerce')
    append_issues=append_errors(current,parsed.frame,current_is_csi=axial_convention(st.session_state)['input_sign']==CSI_TENSION_POSITIVE)
    for issue in append_issues:
        st.caption('Append unavailable: '+issue)
    buttons=st.columns(2)
    with buttons[0]:
        replace=st.button('Replace current rows',type='primary',use_container_width=True,disabled=disabled,key=key_prefix+'_csi_replace')
    with buttons[1]:
        append=st.button('Append imported rows',use_container_width=True,disabled=disabled or bool(append_issues),key=key_prefix+'_csi_append')
    if replace or append:
        st.session_state[state_key]=pd.concat([current,parsed.frame],ignore_index=True) if append else parsed.frame.copy(deep=True)
        st.session_state.pop(editor_key,None)
        cfg={'input_sign':CSI_TENSION_POSITIVE}
        st.session_state[SETTINGS_KEY]=cfg
        metadata=dict(st.session_state.get('project_metadata') or {})
        metadata[SETTINGS_KEY]=cfg
        st.session_state['project_metadata']=metadata
        st.session_state.pop('igird_axial_input_sign',None)
        _sync_workflow_load_tables_metadata()
        st.rerun()
