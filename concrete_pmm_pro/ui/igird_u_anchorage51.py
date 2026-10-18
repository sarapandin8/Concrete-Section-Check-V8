"""Stored U/slab geometry and conditional development screens; no solver."""
import pandas as pd


def plane_frame(trace):
    frame = pd.DataFrame([{
        'Inspection plane':r['plane'], 'Above joint (mm)':r['above_joint_mm'],
        'Available ldh from plane (mm)':r['hook_available_from_plane_mm'],
        'Required ldh (mm)':r['hook_required_mm'],
        'Node exit drop below plane (mm)':r['exit_drop_from_plane_needed_mm'],
        'Screen':r['screen'],
    } for r in trace.get('planes',[])])
    for key in ('Above joint (mm)','Available ldh from plane (mm)',
                'Required ldh (mm)','Node exit drop below plane (mm)'):
        if key in frame:
            frame[key]=frame[key].map(lambda value:'—' if pd.isna(value) else f'{value:,.2f}')
    return frame


def make_figure(trace, *, width_mm):
    """Elevation guide only. Do not draw an unverified hook orientation/node."""
    import plotly.graph_objects as go
    from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
    t=trace['slab_thickness_mm'];a=width_mm
    fig=go.Figure()
    # A cropped elevation guide has no known physical slab edge in this
    # window. Shade the viewport; never draw a fictitious slab width = 4a.
    fig.add_shape(type='rect',xref='paper',x0=0,x1=1,y0=0,y1=t,
        fillcolor='#f1f5f9',line={'width':0},layer='below')
    for i,x in enumerate((-a/2,a/2)):
        fig.add_trace(go.Scatter(x=[x,x],y=[0,trace['straight_leg_top_above_joint_mm']],
            mode='lines',name='U straight legs',legendgroup='u',showlegend=i==0,
            line={'color':'#d62728','width':5},hovertemplate='U straight leg · z=%{y:.2f} mm<extra></extra>'))
    for kind,color,dash in [('transverse','#1f77b4','solid'),('longitudinal','#0f766e','dot')]:
        for i,r in enumerate(p for p in trace['planes'] if kind in p['plane']):
            fig.add_trace(go.Scatter(x=[-1.8*a,1.8*a],y=[r['above_joint_mm']]*2,
                mode='lines',name='Slab '+kind+' levels',legendgroup=kind,showlegend=i==0,
                line={'color':color,'dash':dash,'width':2},
                hovertemplate=r['plane']+' · z=%{y:.2f} mm<extra></extra>'))
    fig.add_hline(y=trace['hook_outside_above_joint_mm'],line_dash='dash',line_color='#d62728',
        annotation_text='Outside of hook · E='+f"{trace['hook_depth_E_mm']:g} mm")
    fig.add_hline(y=trace['latest_fully_developed_exit_above_joint_mm'],
        line_dash='dot',line_color='#a16207',annotation_text='Highest exit for full hook length')
    apply_global_plot_readability(fig)
    fig.update_layout(title='U / slab levels — node geometry unverified',template='plotly_white',
        xaxis={'title':'Transverse coordinate relative to U centre (mm)','range':[-2.5*a,2.5*a]},
        yaxis={'title':'Height above construction joint (mm)','range':[min(-15.,trace['latest_fully_developed_exit_above_joint_mm']-10),t+20]},
        height=500,legend={'orientation':'h','y':-.25,'x':.5,'xanchor':'center'},
        meta={'geometry_scope':'Elevation guide; physical slab edges and hook directions not depicted'})
    return fig


def render(entry, *, member, witness='VT'):
    import streamlit as st
    trace=entry.get('nodal_anchorage') or {}
    if not trace:return
    with st.expander('U–slab anchorage / node — automatic geometry',expanded=False):
        st.caption('ใช้ hook E และ cover เหล็กพื้นเดิม ไม่เพิ่มช่องกรอก · '
            'ตรวจระดับเหล็กเป็น inspection planes ยังไม่ได้ระบุตำแหน่ง node จริง')
        if not trace.get('planes'):
            st.warning(trace.get('reason') or trace.get('status'))
            return
        from . import igird_print50 as printed
        printed.table(plane_frame(trace).round(2),member=member,part='node_planes_'+witness)
        st.caption(f"ldh จากรอยต่อ = {trace['hook_outside_above_joint_mm']:,.2f} mm · "
            f"ต้องการ {trace['hook_required_mm']:,.2f} mm · "
            f"ขอบเขต node ที่ยังมีระยะ hook ครบต้องอยู่สูงจากรอยต่อไม่เกิน "
            f"{trace['latest_fully_developed_exit_above_joint_mm']:,.2f} mm "
            'เมื่อใช้สูตร tension hook และไม่ลดระยะด้วย confinement หรือ excess steel')
        from .analysis_page import _render_beam_uls_browser_plotly_figure
        fig=make_figure(trace,width_mm=entry['U geometry']['a_mm'])
        _render_beam_uls_browser_plotly_figure(fig,interactive=True,
            key=printed.key(member,'node_levels_'+witness))
        st.caption('รูปแสดงระดับและขาตรงของ U เท่านั้น · แนว hook และขอบเขต node ยังไม่ยืนยัน '
            'เส้นระดับเหล็กยาวไม่ใช่เส้นเหล็กขวางที่ใช้ปิดปลอก')
        forces=[r for r in trace.get('U_forces',[]) if r['witness']==witness]
        if forces:
            st.write('แรงยึดต่อขา U ที่ขีดกำลังของโมเดล: '+', '.join(
                f"{r['leg']} {r['force_at_model_capacity_kN_per_bar']:,.2f} kN/ขา "
                f"(ขีดจำกัด {r['ceiling_kN_per_bar']:,.2f})" for r in forces))
        st.warning('NODAL TRANSFER UNVERIFIED · ระยะที่ขาดจาก inspection plane ไม่ใช่ข้อสรุปว่าโครงสร้างวิบัติ '
            'ต้องกำหนด strut / extended node และตรวจ splitting / anchorage ให้สอดคล้องกัน '
            'การตรวจนี้ยังไม่เปลี่ยน Vn/Tn/V–T และไม่ยืนยันว่า U กับตะแกรงพื้นเป็นปลอกปิดตาม code')
