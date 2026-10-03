"""Reuse PMM display/slice preparation inside one I-girder flexure calculation."""
from __future__ import annotations

from concrete_pmm_pro.analysis.result_models import PMMSolverResult, pmm_result_to_display_dataframe


class PreparedPMMCheck:
    def __init__(self, result: PMMSolverResult) -> None:
        # Local import avoids the capacity-check/dashboard import cycle.
        from concrete_pmm_pro.visualization.pmm_dashboard import PreparedPMMSlice

        self.result = result
        self.display_dataframe = pmm_result_to_display_dataframe(result)
        self._slices = PreparedPMMSlice(self.display_dataframe)

    def slice_at_pu(self, Pu_kN: float):
        return self._slices.at_pu(Pu_kN)


class PreparedFlexureCloud:
    def __init__(self, result: PMMSolverResult) -> None:
        self.reduced = PreparedPMMCheck(result)
        # Identical nominal view to the accepted ULS2P route, prepared once per
        # physical cloud instead of copying all PMM points at every station.
        nominal_points = [point.model_copy(update={
            "phi": 1.0,
            "phiPn_N": float(point.Pn_N),
            "phiPn_capped_N": float(point.Pn_N),
            "phiMnx_Nmm": float(point.Mnx_Nmm),
            "phiMny_Nmm": float(point.Mny_Nmm),
            "strain_condition": "phi-not-applied",
        }) for point in result.points]
        nominal = PMMSolverResult(
            points=nominal_points, warnings=list(result.warnings),
            info=[*list(result.info), "IGIRDER.ULS2P nominal-capacity view reused the solved PMM point cloud."],
        )
        self.nominal = PreparedPMMCheck(nominal)
