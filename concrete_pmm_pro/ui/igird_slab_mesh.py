"""Physical mesh inputs once; inner longitudinal positions are calculated."""
import json
import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis.igird_dowel_detail35 import mesh_rows,mesh_inventory,value
from concrete_pmm_pro.analysis.igird_slab_layers import RULE,ORDER_KEY,resolve,adopt


def render(cfg,params,*,state=None):
    cfg=dict(cfg);cfg[ORDER_KEY]=RULE
    cfg.setdefault('layer_order_previous_longitudinal_covers_mm',
        {face:params.get(f'deck_long_rebar_{face}_cover_mm') for face in ('top','bottom')})
    with st.expander('Slab mesh — top / bottom, both directions',expanded=False,key='igird_detail35_mesh_panel'):
        st.caption('Transverse bars are outside; longitudinal bars are directly inside each mat. Enter transverse clear cover once for each face. Longitudinal size / spacing come from Section Builder.')
        from .igird_input_editor import input_editor
        frame=pd.DataFrame(mesh_rows(cfg,params))
        for column in ('Diameter_mm','Spacing_mm','Clear_cover_mm','fy_MPa'):frame[column]=pd.to_numeric(frame[column],errors='coerce')
        edited=input_editor(frame,prefix='igird_detail35_mesh_',disabled=['Layer'],num_rows='fixed',hide_index=True,use_container_width=True,
            column_config={'Layer':st.column_config.TextColumn(width='small'),
                'Diameter_mm':st.column_config.NumberColumn('Transverse db (mm)',min_value=0.,width='small'),
                'Spacing_mm':st.column_config.NumberColumn('Spacing (mm)',min_value=0.,width='small'),
                'Clear_cover_mm':st.column_config.NumberColumn('Transverse cover (mm)',min_value=0.,width='small'),
                'fy_MPa':st.column_config.NumberColumn('fy (MPa)',min_value=0.,width='small')})
        records=json.loads(edited.to_json(orient='records',double_precision=15))
        cfg['slab_transverse_mesh']={face:{k:value(row.get(k)) for k in ('Diameter_mm','Spacing_mm','Clear_cover_mm','fy_MPa')}
            for face,row in zip(('top','bottom'),records)}
        layout=resolve(params,cfg)
        st.markdown('**Calculated longitudinal positions — inside the transverse bars**')
        fields=['Layer','Auto longitudinal cover (mm)','Longitudinal centre below top (mm)']
        st.dataframe(pd.DataFrame(layout['rows'])[fields],hide_index=True,use_container_width=True)
        from concrete_pmm_pro.visualization.igird_slab_layers import sketch
        st.markdown(sketch(layout),unsafe_allow_html=True)
        for issue in layout['issues']:st.info(issue)
        with st.expander('Calculation trace / Equations — slab positions',expanded=False):
            st.latex(r'c_L=c_T+d_T,\quad z_{L,top}=c_L+d_L/2,\quad z_{L,bottom}=h_s-c_L-d_L/2')
            st.caption('cT: clear cover to transverse steel; dT/dL: transverse/longitudinal diameters; cL: calculated longitudinal cover; z: depth below slab top; hs: slab thickness. All mm. Crossed bars touch; no extra interlayer gap is assumed.')
            st.dataframe(pd.DataFrame(mesh_inventory(cfg,layout['parameters'])),hide_index=True,use_container_width=True)
        st.caption('These positions feed the section and joint models. Cover minima, bar anchorage and composite shear–torsion acceptance remain separate checks.')
    if state is not None:adopt(state,cfg=cfg)
    return cfg
