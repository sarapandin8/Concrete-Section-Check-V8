"""Streamlit data-editor patch reconstruction for Crossbeam input tables.

``st.data_editor`` stores the first cell change as an ``edited_rows`` patch in
widget state before rerunning the page.  CROSSBEAM.RB-EDIT1 uses this small,
Streamlit-independent helper so callbacks can merge that first patch into the
canonical longitudinal, transverse, or Zone table immediately.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


def data_editor_payload_to_records(
    payload: Any,
    fallback_rows: list[dict[str, Any]] | pd.DataFrame,
) -> list[dict[str, Any]]:
    """Return full editor rows from a dataframe/list or Streamlit patch dict."""

    fallback = pd.DataFrame(fallback_rows).reset_index(drop=True).copy()
    if isinstance(payload, pd.DataFrame):
        table = payload.reset_index(drop=True).copy()
    elif isinstance(payload, (list, tuple)):
        table = pd.DataFrame(payload).reset_index(drop=True)
    elif payload is None:
        table = fallback
    elif isinstance(payload, Mapping) and {
        "edited_rows",
        "added_rows",
        "deleted_rows",
    }.intersection(payload):
        table = fallback
        edited_rows = payload.get("edited_rows") or {}
        if isinstance(edited_rows, Mapping):
            for raw_index, changes in edited_rows.items():
                try:
                    row_index = int(raw_index)
                except (TypeError, ValueError):
                    continue
                if row_index < 0 or not isinstance(changes, Mapping):
                    continue
                while row_index >= len(table.index):
                    table.loc[len(table.index)] = {column: None for column in table.columns}
                for column, value in changes.items():
                    if column not in table.columns:
                        table[column] = None
                    table.at[row_index, column] = value

        delete_indices: list[int] = []
        for raw_index in payload.get("deleted_rows") or []:
            try:
                delete_indices.append(int(raw_index))
            except (TypeError, ValueError):
                continue
        if delete_indices and not table.empty:
            table = table.drop(
                index=[index for index in set(delete_indices) if index in table.index]
            ).reset_index(drop=True)

        added_rows = payload.get("added_rows") or []
        if added_rows:
            table = pd.concat([table, pd.DataFrame(added_rows)], ignore_index=True)
    elif isinstance(payload, Mapping):
        try:
            table = pd.DataFrame(payload).reset_index(drop=True)
        except ValueError:
            table = pd.DataFrame([payload]).reset_index(drop=True)
    else:
        table = pd.DataFrame(payload).reset_index(drop=True)

    return [dict(row) for row in table.to_dict(orient="records")]
