"""Session-only view choices survive Streamlit widget cleanup on navigation."""
import streamlit as st

KEY='igird_cover38_view_choices'


def selected(state,key,default=None):
    return state.get(key,(state.get(KEY) or {}).get(key,default))


def radio(label,options,*,key,**kwargs):
    choices=dict(st.session_state.get(KEY) or {})
    previous=choices.get(key)
    if key not in st.session_state and previous in options:st.session_state[key]=previous
    result=st.radio(label,options,key=key,**kwargs)
    choices[key]=result;st.session_state[KEY]=choices
    return result
