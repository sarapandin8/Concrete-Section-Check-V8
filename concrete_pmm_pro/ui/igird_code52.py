"""Code-based I-girder workspace policy; stored data only, no strength solver."""
import math

VERSION = 'IGIRDER.CODE52.compact-code-first'
CHECKS = {'Shear', 'Torsion', 'Shear + Torsion'}


def default_member(names, controls):
    """Open a controlling member so Calculate does not leave every chart hidden."""
    def score(name):
        control = controls.get(name) or {}
        ratio = control.get('ratio')
        if not isinstance(ratio,(int,float)) or math.isnan(ratio):ratio = -math.inf
        return (bool(control.get('failed_rows')), bool(control.get('review_rows')), ratio)
    return max(names,key=score) if names else None


def render_heading(check_name):
    import streamlit as st
    from . import igird_print50 as printed
    printed.install()
    # Reuse the verified print adapter for the native code Plotly figures.
    # This marker does not calculate, rasterize or persist a result.
    with st.container(key=printed.key('code52_'+check_name,'chart_scope')):
        st.empty()
    st.markdown('#### AASHTO code-based — '+check_name)
