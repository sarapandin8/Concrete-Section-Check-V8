"""Small physical-geometry form; one calculation command remains on the page."""
import streamlit as st
from concrete_pmm_pro.analysis import slab_track77 as track


def inputs():
    try:
        cfg = track.config(st.session_state)
    except ValueError as exc:
        st.warning(str(exc))
        return
    with st.expander('Track distribution · 45°', expanded=not cfg['enabled']):
        st.caption('Project assumption: load spreads 1 horizontal : 1 vertical from the 2 m physical track footprint down to the structural top slab. Starting section: two tracks, 5 m centres. Review these physical dimensions once; the slab and girder flange geometry are read automatically.')
        with st.form('slab_shell55_track77_form'):
            a, b, c = st.columns(3)
            with a:
                width = st.number_input('Track footprint width (m)', min_value=.01, value=cfg['width_m'], step=.1,
                    key='slab_shell55_track77_width')
            with b:
                depth = st.number_input('Spread depth to top slab (mm)', min_value=0., value=cfg['depth_mm'], step=25.,
                    key='slab_shell55_track77_depth', help='Actual vertical separation below the physical footprint. Do not add the top-slab thickness or automatically add a structural track-slab thickness.')
            with c:
                spacing = st.number_input('Track centre spacing (m)', min_value=.01, value=cfg['spacing_m'], step=.1,
                    key='slab_shell55_track77_spacing')
            with st.expander('Alignment', expanded=False):
                count = st.number_input('Number of tracks', min_value=1, max_value=4, value=cfg['count'], step=1,
                    key='slab_shell55_track77_count')
                offset = st.number_input('Track-group offset from deck CL (m)', value=cfg['offset_m'], step=.1,
                    key='slab_shell55_track77_offset', help='Positive in the imported physical transverse direction; the default group is centred on the imported deck footprint.')
            apply = st.form_submit_button('Apply 45° track geometry')
        if apply:
            try:
                track.save(st.session_state, {'enabled': True, 'width_m': width, 'depth_mm': depth,
                    'count': count, 'spacing_m': spacing, 'offset_m': offset, 'exclude_flange': True})
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()
        if cfg['enabled'] and st.button('Use isolated load areas only', key='slab_shell55_track77_disable'):
            track.save(st.session_state, {'enabled': False})
            st.rerun()
        st.caption('Geometry is saved with Project JSON. Apply sets the inputs; Calculate Top slab below refreshes the result. Imported CSI forces are not dispersed a second time. The 45° angle is a project load-distribution assumption, not a punching failure angle or an AASHTO railway exemption.')


def trace(distribution):
    if not distribution or not distribution['config']['enabled']:
        return
    columns = ['Track', 'Offset from deck CL (m)', 'Distributed width (m)',
               'Girder contacts', 'Load path']
    st.dataframe(distribution['tracks'][columns],
                 hide_index=True, width='stretch')
    for note in distribution['notes']:
        st.caption(note)
    with st.expander('Track geometry / Equations', expanded=False):
        cfg = distribution['config']
        st.latex(r'B_{spread}=B_{track}+2h\tan45^\circ=B_{track}+2h')
        st.markdown(f"**Applied:** {cfg['width_m']:g} + 2 × {cfg['depth_mm']/1000:g} = **{distribution['distributed_width_m']:g} m**.")
        st.caption('h is the physical layer depth above the structural top slab. Longitudinal wheel/sleeper footprint length and a local design load are not reconstructed from full-span UDL. Colours show geometry and support scope, not D/C or a punching PASS. Native source masks and one-way shear checks are retained.')
        st.caption('Only the exact finite girder top-flange contact area is outside slab-only punching scope under the project full-contact assumption. Clear spaces between girders are retained, even when they lie inside the outer-girder envelope. A partly supported isolated patch keeps its existing local-load-path review.')
        st.dataframe(distribution['tracks'], hide_index=True, width='stretch')
        st.dataframe(distribution['elements'], hide_index=True, width='stretch')
