from __future__ import annotations

import math

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_transfer import run_crossbeam_service_stress
from concrete_pmm_pro.ui.analysis_page import _make_crossbeam_transfer_stress_figure
from tests.test_crossbeam_analysis4c7d19_sls_audit_semantics import _service_source
from tests.test_crossbeam_sls1a_transfer_stress import _manual_preparation


def test_final_service_plot_shows_continuous_060fc_reference_without_reactivating_class_c_limit() -> None:
    class_u = run_crossbeam_service_stress(_manual_preparation(_service_source(moment_knm=500.0)))
    class_c = run_crossbeam_service_stress(_manual_preparation(_service_source(moment_knm=1300.0)))

    urow = dict(class_u["rows"][0])
    crow = dict(class_c["rows"][0])
    urow["Station s (m)"] = 0.0
    crow["Station s (m)"] = 10.0

    assert math.isfinite(float(urow["Class U/T compression limit MPa"]))
    assert math.isnan(float(crow["Class U/T compression limit MPa"]))
    assert math.isfinite(float(urow["0.60f'c reference MPa"]))
    assert math.isfinite(float(crow["0.60f'c reference MPa"]))

    rows = pd.DataFrame([urow, crow])
    fibers = pd.DataFrame(class_u["fiber_rows"] + class_c["fiber_rows"])
    figure = _make_crossbeam_transfer_stress_figure(
        rows,
        fibers,
        case_name="ULS-01",
        member_length_m=10.0,
        column_rows=[],
        stage_title="Concrete Stress At Final Service",
        joint_transfer_no_tension=False,
        compression_column="0.60f'c reference MPa",
        compression_trace_name="0.60f'c compression reference",
        tension_column="Class U threshold MPa",
        tension_trace_name="Class U threshold",
        upper_class_threshold_column="Class C threshold MPa",
        upper_class_threshold_trace_name="Class C threshold",
    )

    reference = next(trace for trace in figure.data if trace.name == "0.60f'c compression reference")
    assert list(reference.x) == [0.0, 10.0]
    assert all(math.isfinite(float(value)) for value in reference.y)
