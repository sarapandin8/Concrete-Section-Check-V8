"""Scoped AASHTO RC strip references and source-record check explanations.

These references never replace the coupled shell field. A singly reinforced
one-metre strip has N=0. Nonzero membrane actions, non-tension-controlled
reinforcement or unsupported material strength therefore prevent reference
acceptance. Failing the sufficient 1.33 Mu minimum screen is REVIEW, because
the lesser cracking-moment branch may still satisfy 5.6.3.3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis.slab_shell56 import GROUPS, wood_armer
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_alpha1, aashto_beta1, aashto_tension_controlled_strain_limit,
)

FLEXURE_VIEW = "Code flexure reference"
MINIMUM_VIEW = "Minimum sufficient screen"
REFERENCE_VIEWS = {FLEXURE_VIEW: "Code flexure reference D/C",
                   MINIMUM_VIEW: "Minimum sufficient screen D/C"}
MEMBRANE_TOLERANCE = 1e-8  # numerical zero, kN/m; not a demand-discard threshold


def strip_references(h, membrane, moment, steel):
    """Vectorized tension-mat-only N=0 reference, retaining actual covers.

    A 1 m strip: a=As fy/(alpha1 fc b), c=a/beta1,
    Mn=As fy(d-a/2). Opposite-mat strength is not credited. Only a physically
    fitting, tension-controlled section receives phi=0.9. The moment triad is
    converted per source row by conservative Wood-Armer, before enveloping.
    """
    h = np.asarray(h, dtype=float)
    n, m = np.asarray(membrane, dtype=float), np.asarray(moment, dtype=float)
    if h.ndim != 1 or n.shape != (len(h), 3) or m.shape != n.shape:
        raise ValueError("Strip reference requires complete thickness and N/M triplets")
    if not np.isfinite(np.column_stack((h, n, m))).all() or np.any(h <= 0):
        raise ValueError("Strip reference requires finite actions and positive thickness")
    alpha, beta = aashto_alpha1(steel.fc), aashto_beta1(steel.fc)
    d = h[:, None]-steel.centre
    a = steel.area*steel.fy/(alpha*steel.fc*1000.)
    c = a/beta
    eps = .003*(d/c-1.)
    eps_limit = np.array([aashto_tension_controlled_strain_limit(fy) for fy in steel.fy])
    material_ok = (steel.fy <= 100*6.894757293) & (steel.fc <= 15*6.894757293)
    tension_controlled = (eps >= eps_limit) & (a[None, :] < h[:, None]) & (d > a/2) & material_ok
    resistance = .9*steel.area*steel.fy*(d-a/2)/1e6  # kN.m per metre
    resistance = np.where(tension_controlled, resistance, np.nan)
    membrane_free = np.max(abs(n), axis=1) <= MEMBRANE_TOLERANCE
    demand = wood_armer(m)
    applicable = membrane_free[:, None] & tension_controlled
    ratios = np.divide(demand, resistance)
    output = {"Code reference membrane-free": membrane_free}
    for i, group in enumerate(GROUPS):
        output[group+" reference phiMn (kN·m/m)"] = resistance[:, i]
        output[group+" reference c (mm)"] = np.full(len(h), c[i])
        output[group+" reference tensile strain"] = eps[:, i]
        output[group+" reference D/C"] = np.where(applicable[:, i], ratios[:, i], np.nan)
        output[group+" minimum sufficient D/C"] = np.where(applicable[:, i], 1.33*ratios[:, i], np.nan)
    all_qualified = applicable.all(axis=1)
    flexure_ratio = np.max(np.where(applicable, ratios, -np.inf), axis=1)
    output[REFERENCE_VIEWS[FLEXURE_VIEW]] = np.where(all_qualified, flexure_ratio, np.nan)
    output[REFERENCE_VIEWS[MINIMUM_VIEW]] = np.where(all_qualified, 1.33*flexure_ratio, np.nan)
    # Unknown applicability takes precedence; no nonzero membrane demand is
    # hidden merely because the independent bending ratio is small.
    output["Code flexure reference status"] = np.where(~all_qualified, "REVIEW",
        np.where(flexure_ratio > 1+1e-8, "Reference exceeded", "Reference PASS"))
    output["Minimum sufficient screen status"] = np.where(all_qualified & (1.33*flexure_ratio <= 1+1e-8),
        "Sufficient screen PASS", "REVIEW")
    output["Code reference reason"] = np.where(~membrane_free, "Membrane actions require coupled N–M review",
        np.where(~tension_controlled.all(axis=1), "Tension-control / material scope not established",
        np.where(1.33*flexure_ratio > 1+1e-8, "1.33Mu screen exceeded; lesser Mcr branch not evaluated",
                 "N=0 tension-controlled bending reference")))
    return pd.DataFrame(output)


def component_columns():
    return [(g, g+" Strength D/C") for g in GROUPS]+[
        ("Concrete compression", "Concrete D/C"), ("One-way shear", "Shear D/C"),
        ("Shrinkage minimum", "Shrinkage D/C"), ("Bar maximum spacing", "Spacing D/C")]


def controlling_checks(rows):
    values = rows[[column for _, column in component_columns()]].to_numpy(float)
    # All rows have finite steel / concrete checks, including zero demand.
    chosen = np.where(np.isfinite(values), values, -np.inf).argmax(axis=1)
    return np.array([label for label, _ in component_columns()], dtype=object)[chosen]


def check_breakdown(rows):
    """Each mechanism has its own maximum actual concurrent source record."""
    summary = []
    for label, column in component_columns():
        known = rows.loc[rows[column].notna()]
        if known.empty:
            peak = None
            status = "REVIEW"
        else:
            peak = known.loc[known[column].idxmax()]
            status = "Preview FAIL" if peak[column] > 1+1e-8 else "REVIEW" if rows[column].isna().any() else "Preview PASS"
        summary.append({"Check": label, "Peak D/C": float(peak[column]) if peak is not None else np.nan,
            "Status": status, "Exceeded elements": rows.loc[rows[column] > 1+1e-8, "AreaElem"].nunique(),
            "Review elements": rows.loc[rows[column].isna(), "AreaElem"].nunique(),
            "Case": peak["OutputCase"] if peak is not None else "",
            "Step": peak["StepType"] if peak is not None else "",
            "AreaElem": peak["AreaElem"] if peak is not None else "",
            "Joint": peak["Joint"] if peak is not None else ""})
    return pd.DataFrame(summary)


def source_check_ledger(row):
    """Explain a single governing vector; never mix different record maxima."""
    data = []
    for label, column in component_columns():
        value = row[column]
        data.append({"Check": label, "D/C": value,
            "Status": "REVIEW" if pd.isna(value) else "Preview FAIL" if value > 1+1e-8 else "Preview PASS"})
    return pd.DataFrame(data)
