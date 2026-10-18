"""Shear-focused presentation of stored composite results; no solver calls."""
import math
from collections import Counter
import pandas as pd
import plotly.graph_objects as go

VERSION='IGIRDER.COMPOSITE51.shear-workspace'


def finite(v):
    try:return not isinstance(v,bool) and math.isfinite(float(v))
    except (ValueError,TypeError):return False


def governor(snapshot):
    return next((e for e in (snapshot or {}).get('governing_rows',[]) if e.get('Governing action')=='V'),None)


def summary_row(snapshot,member):
    item=governor(snapshot);calc=(item or {}).get('calculation',{})
    coverage=next(iter((snapshot or {}).get('coverage',[])),{})
    dc=calc.get('model_V_only_actual_MN_DC')
    exhausted=bool(calc.get('V_fixed_MN',{}).get('capacity_exhausted')) and item is not None and abs(item['actions']['vu_N'])>1e-9
    return {'Girder':member,'x (m)':(item or {}).get('x (m)'),
        'Case':(' / '.join(str(item[k]) for k in ('Case','Source StepType') if item.get(k)) if item else '—'),
        '|Vu| (kN)':abs(item['actions']['vu_N'])/1000 if item else None,
        'Model Vn · actual M/N (kN)':calc.get('model_V_only_actual_MN_kN'),
        'Nominal V D/C':dc,'Nominal V state':'ZERO CAPACITY' if exhausted else 'EXCEEDS NOMINAL' if finite(dc) and dc>1+1e-9 else 'WITHIN NOMINAL' if finite(dc) else 'UNAVAILABLE',
        'Rows':f"{coverage.get('Calculated rows',0)}/{coverage.get('Interior source rows',0)}",
        'Status':'MODEL INCOMPLETE' if coverage.get('Blocked / incomplete rows',0) or not item else 'MODEL REVIEW'}


def display_frame(records):
    frame=pd.DataFrame(records)
    # A missing number is not zero and should not appear as Python None.
    for key in ('x (m)','|Vu| (kN)','Model Vn · actual M/N (kN)','Nominal V D/C'):
        if key in frame:frame[key]=frame[key].map(lambda v:f'{float(v):,.3f}' if finite(v) else '—')
    return frame


def render_overview(state,fingerprints):
    import streamlit as st
    from . import igird_print50 as printed
    printed.install()
    from .igird_composite_steel45 import current
    st.markdown('#### Composite shear — I hoops + U-dowel')
    st.warning('MODEL REVIEW · Vn รวมปลอก I และ U สองขา ใช้เหล็กยาว I/พื้นร่วมกัน · '
        'เป็น nominal model ยังไม่มี φ และยังไม่ใช่กำลัง full composite ที่ตรวจยืนยันสำหรับออกแบบจริง')
    records=[]
    for member,fingerprint in fingerprints.items():
        saved=current(state,fingerprint)
        records.append(summary_row(saved,member))
        if saved and not governor(saved):
            reasons=Counter(r.get('Reason') or r.get('Status') for r in saved.get('station_rows',[]))
            st.error(member+': คำนวณ composite shear ไม่สำเร็จ · '+
                '; '.join(f'{reason} ({count} rows)' for reason,count in reasons.items()))
    printed.table(display_frame(records),member='overview',part='overview')
    st.caption('เลือกแถวที่ V-only D/C สูงสุดของแต่ละ girder โดยคง M3/N จริงและ Tu=0 สำหรับการตรวจเฉือนล้วน '
        'θ คงที่จากแถวแรงร่วมต้นทาง · เปิด girder เพื่อดูกราฟ วิธี composite และการใช้กำลังแต่ละส่วน')


def station_pairs(snapshot):
    """Use the actual worst V-only vector at each x; never envelope D and C separately."""
    rows=(snapshot or {}).get('station_rows',[])
    picked={}
    for row in rows:
        x=row.get('x (m)');dc=row.get('V-only D/C, actual M/N')
        if not finite(x):continue
        if x not in picked or (finite(dc) and (not finite(picked[x].get('V-only D/C, actual M/N')) or dc>picked[x]['V-only D/C, actual M/N'])):
            picked[x]=row
    return [picked[x] for x in sorted(picked)]


def make_shear_figure(snapshot,*,member):
    rows=station_pairs(snapshot)
    xs=[r['x (m)'] for r in rows]
    demand=[abs((r.get('Actions used') or {}).get('vu_N',float('nan')))/1000 for r in rows]
    capacity=[r.get('V-only capacity (kN), actual M/N') for r in rows]
    custom=[[r.get('Case'),r.get('Source StepType'),r.get('Source location type'),r.get('Source Excel row')] for r in rows]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=xs,y=demand,name='|Vu|',mode='lines+markers',line={'color':'#1f77b4','width':2.5},
        marker={'size':5},customdata=custom,connectgaps=False,
        hovertemplate='x=%{x:g} m · |Vu|=%{y:.2f} kN<br>%{customdata[0]} / %{customdata[1]} / %{customdata[2]} · row %{customdata[3]}<extra></extra>'))
    fig.add_trace(go.Scatter(x=xs,y=capacity,name='Model Vn',mode='lines+markers',line={'color':'#d62728','dash':'dash','width':2.5},
        marker={'size':5},customdata=custom,connectgaps=False,
        hovertemplate='x=%{x:g} m · Model Vn=%{y:.2f} kN<br>Actual M3/N held · same source row %{customdata[3]}<extra></extra>'))
    gov=governor(snapshot)
    if gov:
        fig.add_trace(go.Scatter(x=[gov['x (m)']],y=[abs(gov['actions']['vu_N'])/1000],mode='markers',name='Gov. shear',
            marker={'symbol':'diamond','size':10,'color':'#0f172a'},
            hovertemplate=f"Governing V-only · D/C={gov['calculation']['model_V_only_actual_MN_DC']:.3f}<extra></extra>"))
    ends=sorted({r['x (m)'] for r in (snapshot or {}).get('excluded_rows',[]) if finite(r.get('x (m)'))})
    for x in ends:fig.add_annotation(x=x,y=.03,xref='x',yref='paper',text='×',showarrow=False,font={'color':'#64748b','size':16})
    from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
    apply_global_plot_readability(fig)
    fig.update_layout(title='Composite shear — '+member,xaxis_title='Distance x (m)',yaxis_title='Shear V (kN)',
        template='plotly_white',legend={'orientation':'h','x':.5,'xanchor':'center','y':-.18},
        height=560,autosize=True,meta={'igird_vn49':VERSION,'paired_source_rows':len(rows),'physical_end_exclusions':ends})
    if ends:fig.update_xaxes(range=[min(ends),max(ends)])
    return fig


def contribution_frame(entry,*,actual_mn=True):
    calc=entry['calculation'];s=calc['supplies'];w=calc['V_fixed_MN' if actual_mn else 'V']
    return pd.DataFrame([
        {'Component':'I-girder hoops','Role':'Vertical shear path in I web','Allocated V (kN)':w.get('core_V_N',0)/1000},
        {'Component':'U-dowel · two legs','Role':'Shared leg force + joint clamping','Allocated V (kN)':w.get('U_V_N',0)/1000},
        {'Component':'Total','Role':'Same nominal equilibrium / actual M3,N','Allocated V (kN)':(w.get('core_V_N',0)+w.get('U_V_N',0))/1000},
    ])


def interface_frame(entry):
    """Actual Vu and unit-V witness are distinct load levels, same joint."""
    calc=entry['calculation'];s=calc['supplies'];w=calc['V_fixed_MN']
    depth=s.get('interface_dv_mm')
    if not finite(depth) or depth<=0:return pd.DataFrame()
    return pd.DataFrame([{'Interface source':'Whole girder: I path + U path',
        'd interface (mm)':depth,
        'At actual |Vu|: q (kN/m)':abs(entry['actions']['vu_N'])/depth,
        'At nominal Vn: q (kN/m)':w.get('interface_required_qx_N_per_mm'),
        'Reconstructed q (kN/m)':sum(w.get('contact_qx_N_per_mm',[]))}])


def code_reference_frame(entry):
    joint=entry.get('interface_reference') or {};shear=entry.get('shear_trace') or {}
    if not joint:return pd.DataFrame()
    return pd.DataFrame([
        {'Code reference':'Web: Vc + Vs(I hoops)','Nominal V (kN)':joint.get('Vn_web_I_hoops_kN'),
            'Factored V (kN)':joint.get('phiVn_web_I_hoops_kN'),
            'Basis':f"Vc={shear.get('Vc kN',0):,.1f}; Vs(I)={shear.get('Vs kN',0):,.1f} kN"},
        {'Code reference':'Whole-girder interface','Nominal V (kN)':joint.get('Vn_interface_equivalent_kN'),
            'Factored V (kN)':joint.get('phiVn_interface_equivalent_kN'),
            'Basis':'U legs crossing joint; interface q × d interface'},
        {'Code reference':'Series minimum — shear reference','Nominal V (kN)':joint.get('reference_Vn_series_kN'),
            'Factored V (kN)':joint.get('reference_phiVn_series_kN'),
            'Basis':joint.get('reference_governing')},
    ])


def render(snapshot,*,member):
    import streamlit as st
    from .analysis_page import _render_analysis_summary_strip,_render_beam_uls_browser_plotly_figure
    item=governor(snapshot)
    if not item:
        st.info('Composite shear unavailable. ดูสาเหตุในตารางรวมด้านบน และผล code shear ที่แยกไว้ด้านล่าง')
        return
    calc=item['calculation'];s=calc['supplies'];section=item.get('section_definition',{})
    from . import igird_print50 as printed
    printed.install()
    record=summary_row(snapshot,member)
    def value(key,unit=''):
        v=record.get(key);return f'{float(v):,.3f}'+(' '+unit if unit else '') if finite(v) else '—'
    _render_analysis_summary_strip([
        {'title':'Model Vn · actual M/N','value':value('Model Vn · actual M/N (kN)','kN'),'detail':'I hoops + U · nominal, no φ','status':'info','strong':True},
        {'title':'|Vu|','value':value('|Vu| (kN)','kN'),'detail':record['Case']+f" @ x={item['x (m)']:g} m",'status':'info'},
        {'title':'Nominal V D/C','value':'∞' if record['Nominal V state']=='ZERO CAPACITY' else value('Nominal V D/C'),
            'detail':record['Nominal V state']+' · '+record['Status'],
            'status':'danger' if record['Nominal V state'] in {'ZERO CAPACITY','EXCEEDS NOMINAL'} else 'warning'},
    ],columns=3)
    fig=make_shear_figure(snapshot,member=member)
    with st.container(key=printed.key(member,'chart')):
        _render_beam_uls_browser_plotly_figure(fig,interactive=True,key='vn49_'+member)
    st.caption('ที่แต่ละสถานีใช้ Vu และ Model Vn จากแถว V-only D/C สูงสุดแถวเดียวกัน '
        'เส้นเชื่อมมีไว้ช่วยอ่าน · × ที่ปลายคานหมายถึงต้องตรวจ end region แยก ไม่ใช่กำลังเป็นศูนย์')
    st.markdown('##### วิธีใช้หน้าตัด composite')
    st.write('Slab ร่วมเป็น compression section เพื่อหาระยะ C–T / dv; '
        'ความกว้าง web และกำลังคอนกรีตของ web ใช้ I-girder จริง '
        'ปลอก I และ U สองขาถ่ายแรงด้วยงบเหล็กร่วม ส่วนเหล็กยาวพื้นเป็น longitudinal tie reserve ตามระยะพัฒนาแรง '
        'รอยต่อตรวจจากแรงเฉือนรวมของทั้ง girder โดยใช้ d interface ที่หาแยกจาก dv ของ web อัตโนมัติ')
    printed.table(pd.DataFrame([{'Be (mm)':section.get('Be_mm'),'Slab t (mm)':section.get('Tslab_mm'),
        'I depth (mm)':section.get('h_I_mm'),'dv web (mm)':s['core_dv_mm'],
        'd interface (mm)':s.get('interface_dv_mm'),
        'I f’c (MPa)':section.get('fc_I_MPa'),'Slab f’c (MPa)':section.get('fc_slab_MPa'),
        'Fixed θ (deg)':math.degrees(math.atan(1/s['cot_theta'])) if s.get('cot_theta') else None}]).round(2),member=member,part='geometry')
    printed.table(contribution_frame(item).round(2),member=member,part='allocation')
    legs=calc['V_fixed_MN'].get('U_force_each_N_per_mm')
    if legs and len(legs)==2:
        st.caption(f"แรงขา U ที่ใช้ร่วมกันในคำตอบนี้: ซ้าย {legs[0]:,.2f}, ขวา {legs[1]:,.2f} N/mm "
            f"· ขีดจำกัด {s['u_leg_N_per_mm']:,.2f} N/mm ต่อขา ต่อหน่วยความยาวคาน "
            '· แรงยึดนี้ใช้ถ่ายแรงเฉือนรวมผ่านรอยต่อ ส่วน V_U ในตารางคือแขนงเฉือนแนวดิ่งที่ solver จัดสรร')
    joint_frame=interface_frame(item)
    if not joint_frame.empty:printed.table(joint_frame.round(2),member=member,part='interface')
    st.caption('โมเดลนี้กำหนด Vc=0 และใช้ shared concrete-flow ceiling; '
        'จึงยังไม่ใช่สูตร AASHTO Vc+Vs ของหน้าตัดประกอบที่ตรวจยืนยันครบ '
        'การมีเหล็ก U/พื้นใน inventory ไม่ได้พิสูจน์ stress field และกำลังจุดต่อจริง')
    code_frame=code_reference_frame(item)
    if not code_frame.empty:
        st.markdown('##### AASHTO shear reference — แถวแรงเดียวกัน')
        printed.table(code_frame.round(2),member=member,part='code_reference')
        joint=item['interface_reference']
        st.caption('ค่าอ้างอิงนี้มี Vc และ Vs ของปลอก I; U เป็น Avf ที่รอยต่อ '
            'ใช้ค่าต่ำสุดของ web และรอยต่อ ไม่บวกสองกำลังเข้าด้วยกัน '
            'การให้ U เป็นปลอกเฉือนตาม code ยังต้องตรวจการยึดปลายล่างและการครอบคลุมหน้าตัด '
            'ค่าอ้างอิงนี้ไม่แทน Model V–T และไม่เป็นผลรับรอง full composite')
        if joint.get('unresolved_gates'):
            st.caption('เงื่อนไขที่ยังค้าง: '+'; '.join(joint['unresolved_gates']))
    with st.expander('Calculation trace / Equations — composite shear',expanded=False):
        st.latex(r'V=V_I+V_U,\qquad \eta_V=|V_u|/V_{n,\,M_3,N}')
        st.latex(r'\sum_j S_{x,j}=\frac{V_I+V_U}{d_{\rm interface}},\qquad '
                 r'd_{\rm interface}=y_{\rm slab,mid}-y_{\rm tension\ steel}')
        st.latex(r'\frac{V_I}{2d_{v,I}\cot\theta}\leq\frac{A_{I,leg}f_{y,I}}{s_I},\qquad '
                 r'\frac{V_U}{2d_{v,U}\cot\theta}\leq F_{U,i}\leq\frac{A_{U,leg}f_{y,U}}{s_U}')
        st.caption('V: N · dv: mm · A: mm² · fy: MPa · s: mm · F: N/mm ของแต่ละขา '
            'รอยต่อและเหล็กยาวอาจลดแรงที่จัดสรรได้; T=0 ใน V-only นี้ แรงร่วมดูใน Shear + Torsion')
        st.write('Active limits: '+', '.join(calc['V_fixed_MN'].get('active_limits',[])))
        st.write({'Source':{k:item.get(k) for k in ('Case','x (m)','Source StepType','Source location type','Source Excel row')},
            'Pure Vn at M=N=0 (kN)':calc['model_Vn_kN'],'Slab longitudinal reserve (kN)':item.get('slab_longitudinal_force_N',0)/1000})
        st.dataframe(pd.DataFrame([{k:v for k,v in bar.items() if k!='development'} for bar in item.get('inventory',[])]),hide_index=True,width='stretch')
    with st.expander('Source rows / Coverage — composite shear',expanded=False):
        columns=['x (m)','Case','Source StepType','Source location type','Source Excel row','V-only capacity (kN), actual M/N','V-only D/C, actual M/N',
            'Interface total demand (kN/m)','Interface flexural-shear D/C','Status','Reason']
        frame=pd.DataFrame((snapshot or {}).get('station_rows',[]))
        st.dataframe(frame[[c for c in columns if c in frame]],hide_index=True,width='stretch')
    from .igird_u_anchorage51 import render as render_anchorage
    render_anchorage(item,member=member,witness='V_fixed_MN')
