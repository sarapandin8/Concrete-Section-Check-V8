"""Actual-thickness local shear review; no additional engineering inputs."""
import streamlit as st

from concrete_pmm_pro.ui.commercial import render_metric_cards
from concrete_pmm_pro.ui.slab_aashto63_workspace import number
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES
from concrete_pmm_pro.visualization.slab_print72 import export_config
from concrete_pmm_pro.visualization.slab_punching78 import figure


def _oneway():
    st.session_state['slab_shell55_shear64_group']='One-way shear'


def inputs():
    st.info('Actual-thickness local shear review · existing CSiBridge shear forces are the adopted design demand. Resistance uses the actual imported thickness at each source point and the existing reinforcement depths. No new load-area inputs are required for the local map.')
    st.caption('AASHTO LRFD 2020 concrete resistance coefficient lower bound. A local D/C below 1 describes that location only; it does not certify an actual punching perimeter crossing different slab thicknesses. Values above 1 require REVIEW, not an automatic punching FAIL.')
    st.button('Review one-way shear', key='slab_shell55_punch76_oneway', on_click=_oneway)


def render(result):
    screen = result['punching_screen78']
    gov = screen['governing']
    if result['punching']['status'] == 'FAIL':
        st.error('Explicit physical-perimeter check FAIL. The local index does not override that independently specified load check; review its table below.')
    detail = (f"{gov['OutputCase']} · X={gov['X (m)']:.3f}, Y={gov['Y (m)']:.3f} m" if gov else 'No evaluable source record')
    render_metric_cards([
        {'title': 'Local normal-shear D/C', 'value': number(screen['max_dc']), 'detail': detail,
         'status': 'warning' if screen['max_dc'] > 1 else 'neutral'},
        {'title': 'Thickness at governing point', 'value': number(gov['Thickness (mm)'])+' mm' if gov else '—',
         'detail': 'Native CSI thickness · same point as force', 'status': 'neutral'},
        {'title': 'Evaluated source records', 'value': f"{screen['evaluated_records']:,}",
         'detail': f"{screen['excluded_records']:,} contact / excluded / unavailable", 'status': 'neutral'}])
    st.caption('Punching scope: '+screen['status']+' · physical-perimeter acceptance remains separate from the local D/C map.')
    case = st.selectbox('Punching load case', [ALL_CASES, *screen['summary'].Case.tolist()],
        key='slab_shell55_punch78_case')
    st.plotly_chart(figure(result, case), width='stretch', key='slab_shell55_punch64_plan', config=export_config())
    st.caption('Colours show local D/C using actual thickness, not a physical-perimeter punching result. Warm colours above 1 require REVIEW. Grey cells contain omitted or incomplete source coverage; girder/diaphragm contacts and bearing-end exclusions remain outside the slab-only check. No D/C averaging or force rescaling is applied.')
    st.dataframe(screen['summary'][['Case','Max local D/C','Thickness (mm)','dv (mm)','X (m)','Y (m)','Status']], hide_index=True, width='stretch',
        column_config={c: st.column_config.NumberColumn(format='%.3f') for c in
            ('Max local D/C', 'X (m)', 'Y (m)', 'Thickness (mm)', 'dv (mm)', 'Q bound (kN/m)', 'phi v dv (kN/m)')})
    if screen['geometry_issues']:
        st.warning('; '.join(screen['geometry_issues']))
    if screen['source_incomplete']:
        st.warning('Missing, duplicate, invalid-depth or non-finite source coverage requires review.')
    st.caption(screen['scope'])
    with st.expander('Calculation trace / Equations', expanded=False):
        st.markdown('**AASHTO LRFD 9th Edition (2020), §5.12.8.6.3-1 · local normal-shear index**')
        st.latex(r'c(\beta_c)=\min(0.063+0.126/\beta_c,\,0.126)\ge0.063\quad(\beta_c\ge1)')
        st.latex(r'v_{min}=0.063\sqrt{f_c^\prime/6.894757293}\,(6.894757293)\ \mathrm{MPa}')
        st.latex(r'h=h_{CSI}(AreaElem,Joint),\quad d_v=\max[0.9(h-c_{steel}),\,0.72h],\quad r_{local}=0.90v_{min}d_v\ \mathrm{kN/m}')
        st.latex(r'Q_b=\sqrt{(\max_{saved\ steps}|Q_x|)^2+(\max_{saved\ steps}|Q_y|)^2},\qquad D/C_{local}=Q_b/r_{local}')
        st.caption('Qx/Qy are the rotated native V13/V23, in kN/m. h is the actual interpolated native-corner thickness from the CSI thickness overwrites; csteel is the largest existing reinforcement centre depth, in mm. Thickness elsewhere is not substituted into local resistance. The coefficient lower bound is retained without guessing L/B. This local index is not an AASHTO-prescribed pointwise punching equation. An actual critical perimeter must use appropriate geometry and thickness along its path, including additional critical sections at thickness changes (5.12.8.6.1).')
        if gov:
            st.markdown(f"Governing source: **{gov['OutputCase']}**, element **{gov['AreaElem']}**, joint **{gov['Joint']}**.")
            st.code(f"Qb = hypot({gov['Qx bound (kN/m)']:.4f}, {gov['Qy bound (kN/m)']:.4f}) = {gov['Q bound (kN/m)']:.4f} kN/m\nh = {gov['Thickness (mm)']:.3f} mm (same native corner)\ndv = {gov['dv (mm)']:.3f} mm\nrlocal = {gov['phi v dv (kN/m)']:.4f} kN/m\nLocal D/C = {gov['Q bound (kN/m)']:.4f} / {gov['phi v dv (kN/m)']:.4f} = {gov['Local D/C']:.6f}", language=None)
        st.download_button('Download punching source checks', screen['rows'].to_csv(index=False).encode('utf-8-sig'),
            file_name='Slab_Punching79_Local.csv', mime='text/csv', key='slab_shell55_punch78_csv')
