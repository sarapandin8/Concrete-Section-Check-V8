# CROSSBEAM.PTLOSS3B2B2 — Incremental Tendon-Group Compression-Contact Stages

This milestone advances the accepted rigid vertical compression-only falsework kernel from the isolated gravity stage through the user-confirmed symmetric tendon-group sequence. The stage route is:

`Gravity → G1 → G2 → G3 → G4`

At every tendon stage, the solver preserves all earlier groups, adds the selected group's accepted station-by-station tendon force after Friction and Anchorage Set, and repeats the unilateral active-set solve. Active contact enforces vertical `v = 0`; tensile contact reaction causes automatic lift-off; penetrated open contact is re-closed. Axial translation, rotation, interface friction, falsework settlement, and finite support-spring stiffness remain outside the adopted rigid-contact idealization.

The incremental implementation adds:

- explicit group filtering from the verified symmetric-pair source and user-confirmed construction sequence;
- cumulative post-anchor equivalent tendon nodal loads with no `fpj` restart;
- gravity plus stage-by-stage contact states, raw/equivalent reactions, gaps, fixed-base reactions, frame actions, displacement, complementarity, equilibrium, and active-set histories;
- contact-state interval summaries and selected-stage reaction/gap plus `N/V/M/v` charts;
- an independent final cumulative one-shot solve that must match the warm-start staged result;
- synthetic benchmarks for prestress-induced lift-off, cumulative load retention, mirrored contact response, and staged-versus-one-shot consistency;
- current-input mesh evidence at 0.50, 0.25, and 0.125 m. The numerical gate uses final total contact reaction, maximum gap, maximum moment, and maximum displacement. Open tributary length is reported separately because the exact active/open boundary remains limited by contact-node spacing; the finest half-grid boundary resolution is shown explicitly.

For the default regression project, all five stages satisfy complementarity and equilibrium. Gravity remains fully active. Tendon groups cause partial lift-off, and the final staged solution matches the independent one-shot cumulative solution exactly within the adopted QA tolerances. The global final-stage mesh metrics are stable under the 1% last-refinement criterion, while the open-length percentage remains informational rather than being silently treated as a mesh-independent quantity.

This remains a diagnostic construction-stage response foundation. It does **not** extract or route source-derived `f_cgp`, apply bonded/unbonded stress-location rules, calculate Elastic Shortening, reduce tendon force to `P after ES`, assemble `Pe/Pe_eff`, save results to Project JSON, feed Result Summary, or feed Report/QA. Those downstream handoffs remain locked.
