from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.crossbeam.later_permanent_response import (
    PERMANENT_EVENT_SCHEDULE_COLUMNS,
    default_td_permanent_event_schedule,
)
from concrete_pmm_pro.ui.loads_page import (
    _data_editor_payload_to_dataframe,
    _stringify_table,
)


def test_schedule_editor_normalization_accepts_adopt_without_active_column() -> None:
    source = pd.DataFrame(default_td_permanent_event_schedule())

    normalized = _stringify_table(source, list(PERMANENT_EVENT_SCHEDULE_COLUMNS))

    assert list(normalized.columns) == list(PERMANENT_EVENT_SCHEDULE_COLUMNS)
    assert "Active" not in normalized.columns
    assert normalized["Adopt"].dtype == bool
    assert normalized["Adopt"].tolist() == [False] * len(source.index)


def test_schedule_editor_first_edit_patch_preserves_rows_and_adopt_checkbox() -> None:
    fallback = _stringify_table(
        pd.DataFrame(default_td_permanent_event_schedule()),
        list(PERMANENT_EVENT_SCHEDULE_COLUMNS),
    )
    payload = {
        "edited_rows": {
            0: {
                "Adopt": True,
                "Activation age (days)": 60.0,
                "Case Name": "GIRDER_INC",
            }
        },
        "added_rows": [],
        "deleted_rows": [],
    }

    reconstructed = _data_editor_payload_to_dataframe(payload, fallback)
    normalized = _stringify_table(reconstructed, list(PERMANENT_EVENT_SCHEDULE_COLUMNS))

    assert normalized.loc[0, "Adopt"]
    assert normalized.loc[0, "Activation age (days)"] == "60.0"
    assert normalized.loc[0, "Case Name"] == "GIRDER_INC"
    assert "Active" not in normalized.columns


def test_existing_load_editor_active_default_is_unchanged() -> None:
    columns = ["Active", "Case Name", "P"]
    source = pd.DataFrame([{"Case Name": "DL", "P": 10.0}])

    normalized = _stringify_table(source, columns)

    assert normalized.loc[0, "Active"]
    assert normalized.loc[0, "Case Name"] == "DL"
    assert normalized.loc[0, "P"] == "10.0"
