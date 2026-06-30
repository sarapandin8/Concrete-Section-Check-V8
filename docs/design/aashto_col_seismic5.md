# AASHTO.COL.SEISMIC5 — Seismic advisor visual status and action summary

This milestone improves the AASHTO LRFD 9th Column/Pier seismic transverse advisor UX without changing the Section 5.11.4 calculations.

## Intent

The SEISMIC4 advisor correctly reported spacing, Ash/rho, and confinement-length checks, but the visible cards still used neutral/blue styling and the detailed calculation table remained expanded. That could make a failed seismic detailing row appear less severe than it is.

## Changes

- Replace the top Streamlit metric cards in the AASHTO seismic advisor with semantic HTML status cards.
- Use green, amber, and red left-border accents for PASS, REVIEW, and FAIL conditions.
- Add a prominent Required action summary callout.
- Keep the detailed AASHTO 5.11.4 calculation trace in a collapsed expander by default.
- Preserve all AASHTO spacing, confinement length, Ash/rho, D/C, and control-section calculations unchanged.

## Engineering note

A shear-strength PASS does not certify seismic transverse detailing. The overall seismic advisor remains FAIL/REVIEW whenever spacing or Ash/rho checks fail, even if the column/pier shear check passes.
