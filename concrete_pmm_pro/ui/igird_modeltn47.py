"""Case-study presentation of the stored U/slab nominal review model.

This module never calculates resistance or publishes an accepted design result.
The source selection scans every eligible interior concurrent vector.
"""
import math

import pandas as pd

VIEW_VERSION = 'IGIRDER.CODE52.case-study'
MAIN_CHECKS = {'Shear', 'Torsion', 'Shear + Torsion'}
REFERENCE_LABEL = 'Reference checks — I-girder hoop / code route'


def _finite(value):
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def primary_frame(result):
    """Project the with-U calculation only; never fall back to I-hoop Tn."""
    records = []
    for item in (result or {}).get('rows', []):
        calc = item.get('calculation') or {}
        dc = calc.get('model_VT_DC')
        ready = bool(calc) and all(calc.get(k, {}).get('ready') for k in ('V', 'T', 'VT'))
        records.append({
            'Girder': item.get('Girder', ''), 'x (m)': item.get('x (m)'),
            'Case / step': ' / '.join(str(item[k]) for k in ('Case', 'Source StepType') if item.get(k)),
            'Model Vn · U + slab (kN)': calc.get('model_Vn_kN'),
            'Model Tn · U + slab (kN-m)': calc.get('model_Tn_kNm'),
            'Model nominal V–T D/C': dc,
            'Nominal V–T state': 'EXCEEDS NOMINAL' if calc.get('VT',{}).get('capacity_exhausted') else
                ('EXCEEDS NOMINAL' if float(dc) > 1. + 1e-9 else 'WITHIN NOMINAL')
                if _finite(dc) else 'UNAVAILABLE',
            'Status': 'MODEL INCOMPLETE' if item.get('Status')=='MODEL INCOMPLETE' else 'MODEL REVIEW' if ready else
                ('MODEL INCOMPLETE' if calc else str(item.get('Status') or 'MODEL INCOMPLETE')),
        })
    return pd.DataFrame(records)


def collection_snapshot(state, fingerprints):
    """Read only current hash-bound snapshots, keeping unavailable members visible."""
    from .igird_composite_steel45 import current
    from .igird_composite_scan48 import SELECTION
    rows, coverage = [], []
    for member, fingerprint in fingerprints.items():
        snapshot = current(state, fingerprint)
        if snapshot and snapshot.get('rows'):
            # The normalized source name may omit the Bridge Object prefix.
            # Keep the collection identity visible and leave the saved row intact.
            rows.extend({**row, 'Girder': member, 'Model source girder': row.get('Girder')}
                for row in snapshot['rows'])
            coverage.extend({**row, 'Girder':member} for row in snapshot.get('coverage',[]))
        else:
            rows.append({'Girder': member, 'Status': 'NOT CALCULATED',
                'Reason': (snapshot or {}).get('reason') or
                    'No current composite model. Calculate the selected check with the current inputs.'})
    return {'version': VIEW_VERSION, 'enabled': True, 'rows': rows,'coverage':coverage,'selection':SELECTION}


def _heading(result):
    import streamlit as st
    st.markdown('#### Composite resistance — U + slab steel')
    st.warning('CASE STUDY / MODEL REVIEW — Model Tn รวม U สองขาและเหล็กยาวพื้น '
        'เป็นกำลัง nominal ยังไม่มี φ และยังไม่ใช่ผล PASS สำหรับรับรองการออกแบบ full composite')
    st.caption('Model Vn/Tn: M=N=0 และ θ คงที่จากแถวต้นทางที่เลือก · '
        'Model V–T: คง M3/N ของแถวจริงและเพิ่ม V2/T ด้วยตัวคูณร่วม ใช้กำลังเหล็กร่วมกันครั้งเดียว · '
        'ตารางหลักแสดงแถวควบคุม V–T ของแต่ละ girder')
    st.caption((result or {}).get('selection') or
        'คำนวณทุกแถวแรงร่วมภายในช่วงคาน และเลือก D/C ของ V–T สูงสุด โดยคง Max/Min และ Before/After แยกกัน')
    st.caption('Tu ใช้ค่าต้นทาง CSiBridge ณ จุดรายงานเดิม ไม่ย้ายไป centroid คาน I · '
        'Summary / Report / QA ใช้ผล code checks แยกจากกรณีศึกษานี้')
    st.caption('COMPOSITE50: รอยต่อรับ longitudinal shear จาก V รวมทั้ง girder ด้วย d interface แยกจาก dv web; '
        'ผลที่ไม่มี U เป็นการถอด connector จากโมเดลประกอบเดิม ไม่ใช่กำลังของ I-girder เดี่ยว')
    for row in (result or {}).get('coverage',[]):
        text = (f"{row['Girder']} · interior rows {row['Calculated rows']}/{row['Interior source rows']} · "
            f"blocked/incomplete {row['Blocked / incomplete rows']} · physical end rows outside model {row['Physical end rows excluded']}")
        if row['Blocked / incomplete rows']:
            st.warning(text+' · ผลควบคุมยังไม่ครอบคลุมแถวที่คำนวณไม่ได้')
        else:
            st.caption(text)


def render_overview(result):
    """Collection overview: only the chosen model supplies the capacity columns."""
    import streamlit as st
    _heading(result)
    frame = primary_frame(result)
    if not frame.empty:
        st.dataframe(frame, hide_index=True, width='stretch')
    else:
        st.info((result or {}).get('reason') or 'Calculate Torsion or Shear + Torsion to populate the composite model.')


def render(result):
    """Stored-results-only case study, with separate reinforcement comparisons."""
    import streamlit as st
    if result is not None and not result.get('enabled'):
        return
    _heading(result)
    frame = primary_frame(result)
    if frame.empty:
        st.info((result or {}).get('reason') or
            'Model Tn ยังไม่พร้อมสำหรับข้อมูลปัจจุบัน ใช้ Run case study ในแผงกรณีศึกษาเพื่อคำนวณ')
        return
    if len(frame) == 1:
        from .analysis_page import _render_analysis_summary_strip
        row = frame.iloc[0]
        def number(key, unit=''):
            return f'{float(row[key]):,.3f}' + (' '+unit if unit else '') if _finite(row.get(key)) else 'Unavailable'
        _render_analysis_summary_strip([
            {'title': 'Model Tn · U + slab', 'value': number('Model Tn · U + slab (kN-m)', 'kN-m'),
                'detail': 'Nominal pure torsion · M=N=0', 'status': 'info', 'strong': True},
            {'title': 'Model Vn · U + slab', 'value': number('Model Vn · U + slab (kN)', 'kN'),
                'detail': 'Nominal pure shear · M=N=0', 'status': 'info'},
            {'title': 'Model nominal V–T D/C', 'value': number('Model nominal V–T D/C'),
                'detail': str(row['Nominal V–T state'])+' · MODEL REVIEW',
                'status': 'danger' if row['Nominal V–T state'] == 'EXCEEDS NOMINAL' else 'warning'},
        ], columns=3)
    st.dataframe(frame, hide_index=True, width='stretch')
    st.caption('ใช้ข้อมูล U-dowel, เหล็กพื้น และระยะพัฒนาแรงเดิม ไม่มีข้อมูลใหม่ที่ต้องกรอก '
        'กำลัง full composite สำหรับออกแบบยังต้องยืนยัน stress field / node ของ U–พื้น '
        'และผลเทียบอิสระของระบบประกอบจริง')
    if result.get('governing_rows'):
        records = []
        for item in result['governing_rows']:
            calc = item['calculation']; action = item['Governing action']
            records.append({'Girder':item['Girder'],'Action':action,'x (m)':item['x (m)'],
                'Case':item.get('Case'),'Step':item.get('Source StepType'),
                'Location':item.get('Source location type'),'Excel row':item.get('Source Excel row'),
                'Nominal D/C':calc.get({'V':'model_V_only_actual_MN_DC','T':'model_T_only_actual_MN_DC','VT':'model_VT_DC'}[action]),
                'Status':'MODEL REVIEW'})
        st.dataframe(pd.DataFrame(records),hide_index=True,width='stretch')
        st.caption('แถวควบคุมแยก V-only, T-only และ V–T: คง M3/N จริงในแต่ละแถว '
            'จึงต่างจากค่า Model Vn/Tn ที่ M=N=0 ด้านบน · ไม่มีการรวมค่าสูงสุดจากคนละแถวแรง')
    with st.expander('Source rows / Scan coverage',expanded=False):
        if result.get('station_rows'):
            st.dataframe(pd.DataFrame([{k:v for k,v in row.items() if k!='CSI actions'}
                for row in result['station_rows']]),hide_index=True,width='stretch')
        if result.get('excluded_rows'):
            st.dataframe(pd.DataFrame(result['excluded_rows']),hide_index=True,width='stretch')
    for item in result['rows']:
        if 'calculation' not in item:
            st.info(str(item.get('Girder', 'Girder'))+': '+str(item.get('Reason', 'Model unavailable')))
            continue
        active = item['calculation'].get('T', {}).get('active_limits', [])
        st.caption(f"{item['Girder']} · x={item['x (m)']:g} m · Model Tn controls: "+', '.join(active))
        from .igird_u_anchorage51 import render as render_anchorage
        render_anchorage(item,member=item['Girder'])
    with st.expander('Same-model comparison — reinforcement contribution', expanded=False):
        records = []
        for item in result['rows']:
            for label, key in [('With U + slab steel', 'calculation'), ('Without U', 'without_U'),
                               ('Without slab longitudinal steel', 'without_slab_longitudinal')]:
                value = item.get(key)
                if not value:
                    continue
                records.append({'Girder': item['Girder'], 'x (m)': item['x (m)'], 'Reinforcement': label,
                    'Model Vn (kN)': value.get('model_Vn_kN'), 'Model Tn (kN-m)': value.get('model_Tn_kNm'),
                    'Model nominal V–T D/C': value.get('model_VT_DC'), 'Status': 'MODEL REVIEW'})
        if records:
            st.dataframe(pd.DataFrame(records), hide_index=True, width='stretch')
        st.caption('เปรียบเทียบภายใต้คอนกรีต θ และเงื่อนไขเดียวกัน '
            'กำลังจากเหล็กปลอก I ใน Reference checks มีนิยามและข้อจำกัดต่างจาก Model Tn นี้')
    with st.expander('Calculation trace / Equations — composite model', expanded=False):
        if result.get('design_evidence'):
            st.json(result['design_evidence'])
        st.latex(r'V=V_I+V_U,\qquad T=2A_{o,I}q_I+2A_{o,U}q_U')
        st.latex(r'\sum_j S_{x,j}=(V_I+V_U)/d_{\rm interface}')
        st.latex(r'F_{U,i}\geq\frac{|V_U|}{2d_{v,U}\cot\theta}+\frac{|q_U|}{\cot\theta},\quad F_{U,i}\leq\frac{A_{U,leg}f_{y,U}}{s_U}')
        st.caption('Ao: พื้นที่ภายในเส้นทาง shear flow (mm²) · q: shear flow (N/mm) · '
            'dv: effective shear depth (mm) · θ: มุม compression field · '
            'At ของ torsion ใช้พื้นที่หนึ่งขา ส่วน shear ใช้สองขาจริงร่วมกับงบกำลังเดียวกัน')
        st.caption('ข้อจำกัดเดิมยังใช้ครบ: fixed-angle fully cracked truss, zero Vc/cohesion, '
            'shared concrete flow จาก web คาน I และการแบ่งเหล็กยาวตามเส้นทาง '
            'ค่าต่ำกว่าผลปลอก I ไม่ได้พิสูจน์ว่าโมเดลนี้แทนกำลังหน้าตัดจริงได้ถูกต้อง')
        for item in result['rows']:
            if 'calculation' not in item:
                continue
            st.markdown(f"**{item['Girder']} at x={item['x (m)']:g} m**")
            st.write(item.get('detail_status', ''))
            st.json({'Case': item.get('Case'), 'Step': item.get('Source StepType'),
                'Source Excel row': item.get('Source Excel row'), 'CSI actions': item.get('source_CSI'),
                'torsion_reference': item.get('torsion_reference'), 'actions_used': item.get('actions'),
                'physical_I_hoop':item.get('physical_I_hoop'),
                'supplies': item['calculation']['supplies'], 'U geometry': item.get('U geometry'),
                'V witness': item['calculation']['V'], 'T witness': item['calculation']['T'],
                'VT witness': item['calculation']['VT']})
            st.dataframe(pd.DataFrame([{k: v for k, v in bar.items() if k != 'development'}
                for bar in item.get('inventory', [])]), hide_index=True, width='stretch')


def render_reference(state, rows, entry, *, check_name, code_label):
    """Render existing code-check evidence without replacing or recalculating it."""
    import streamlit as st
    from . import analysis_page as ap
    with st.expander(REFERENCE_LABEL, expanded=False):
        st.caption('ผลตรวจเดิมของปลอก I-girder เป็น reference แยกจาก Model Tn รวม U + พื้น '
            'สถานะนี้ยังเป็นฐานของ Summary / Report / QA')
        if check_name in {'Shear','Torsion'}:
            from .igird_vt_workspace import render_strength_chart
            kind = check_name.lower()
            frame = entry.get(kind+'_check_df')
            render_strength_chart(rows, frame, check_name=check_name, code_label=code_label+' · I-hoop reference',
                state=state, boundary=entry.get(kind+'_boundary_capacity_df'),
                critical=entry.get('shear_critical_section_df') if check_name=='Shear' else None,
                diagram=entry.get(kind+'_diagram_capacity_df'), key_prefix='modeltn47_reference')
            gov = ap._beam_uls_governing_shear_row(frame) if check_name=='Shear' else ap._beam_uls_governing_torsion_row(frame)
            if gov:
                st.caption(f"I-hoop reference: {gov.get('Status', 'REVIEW')} · D/C {gov.get('D/C value', '-')} · {gov.get('Case', '-')} @ x={gov.get('Governing x', '-')}")
                from .csi_reference_analysis import render_trace
                render_trace(gov)
                trace = ap._beam_uls_shear_calculation_trace_dataframe if check_name=='Shear' else ap._beam_uls_torsion_calculation_trace_dataframe
                st.dataframe(trace(gov), hide_index=True, width='stretch')
        else:
            from .igird_combined_vt import render_workspace
            frame = entry.get('combined_vt_df')
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                render_workspace(frame, code_label=code_label+' · I-hoop reference')
        if isinstance(frame, pd.DataFrame):
            st.dataframe(frame, hide_index=True, width='stretch')
