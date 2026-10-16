"""Session-only editor seeds for continuous girder/interface input editing.

Streamlit edit deltas refer to the table that first opened. Keep that table
stable while its accepted output is saved into the model. Rebase when the
caller supplies different inputs or a widget returns after leaving the view.
No engineering result or extra Project JSON field is introduced.
"""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import streamlit as st


STATE_PREFIX = "igird_edit33_editor_"


def _signature(frame: pd.DataFrame) -> str:
    # The model stores records, not editor row indices. A deleted row must not
    # look like an external replacement just because its old index disappeared.
    payload = {"columns":list(frame.columns),
        "records":json.loads(frame.to_json(orient="records",double_precision=15))}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def input_editor(frame: pd.DataFrame, *, prefix: str, **kwargs) -> pd.DataFrame:
    """Return edited records with stable identity and cumulative deltas.

    The caller remains responsible for saving returned inputs. A genuinely
    external table change starts a fresh editor and discards obsolete deltas.
    """
    slot = STATE_PREFIX + prefix
    saved = st.session_state.get(slot)
    incoming = _signature(frame)
    if (not isinstance(saved,dict) or saved.get("accepted") != incoming
            or saved.get("widget_key") not in st.session_state):
        revision = int(saved.get("revision",0)) + 1 if isinstance(saved,dict) else 1
        if isinstance(saved,dict):
            st.session_state.pop(saved["widget_key"],None)
        saved = {"revision":revision,"base":frame.copy(deep=True),
            "widget_key":prefix+f"edit33_{revision}"}
    edited = st.data_editor(saved["base"].copy(deep=True),key=saved["widget_key"],**kwargs)
    saved["accepted"] = _signature(edited)
    st.session_state[slot] = saved
    return edited
