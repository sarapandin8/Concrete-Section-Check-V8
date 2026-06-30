# REBAR.AUTO.PERIMETER.OVERLAP1 — Auto perimeter rebar overlap guard

## Issue

Screenshot QA showed that the Auto perimeter rebar generator can place two longitudinal bars too close together at short step/chamfer transitions, especially on voided plank girder style sections. The prior corner-controlled algorithm placed a mandatory bar at every detected offset-perimeter corner/control point. When two adjacent offset vertices are close, the preview can show apparent bar collision near the section corner.

## Fix

The generator now applies a deterministic minimum center-spacing guard after the corner-controlled distances are generated:

- compute a minimum generated center spacing from bar diameter and target spacing;
- remove generated perimeter points that are closer than the guard;
- check the wrap-around pair on the closed perimeter;
- recompute maximum generated spacing after filtering;
- warn the user when closely spaced points were removed.

## Engineering boundary

This is a layout-preview guard, not a full detailing code check. Engineers must still review clear spacing, cover, constructability, layer arrangement, lap/splice zones, and local detailing requirements before final design.

## Regression

`tests/test_rebar_layout.py::test_perimeter_rebar_layout_filters_close_step_corner_bars_for_voided_plank` locks the voided plank regression case and verifies the generated bars no longer have near-collision spacing.
