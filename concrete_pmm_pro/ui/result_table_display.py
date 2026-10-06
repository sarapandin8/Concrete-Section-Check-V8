"""Display copies of result tables with Arrow-compatible audit columns.

Engineering rows can contain a nested development trace at calculated stations
and "-" at stations where that trace does not apply. Arrow cannot represent
that mix in one column, and Streamlit's automatic fix depends on row order.
Keep structured solver/cache data intact and render mixed audit values as text.
"""
from __future__ import annotations

import json

import pandas as pd
from pandas.api.types import infer_dtype, is_object_dtype


def _audit_text(value: object) -> str:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def result_table_for_display(frame: pd.DataFrame) -> pd.DataFrame:
    """Preserve numeric/bool columns and stringify mixed audit columns only.

The returned copy is for st.dataframe, never for calculations, input hashes,
result caches, Project JSON, or governing-row decisions. Nulls remain nulls;
lists/dictionaries retain their complete content as JSON text.
"""
    display = frame.copy(deep=True)
    for name in display.columns:
        column = display[name]
        if is_object_dtype(column.dtype) and infer_dtype(column, skipna=True) in {
            "mixed", "mixed-integer", "complex",
        }:
            display[name] = column.map(_audit_text, na_action="ignore").astype("string")
    return display
