# CROSSBEAM ANALYSIS4C7D4 — Segmental Flexure φMn trace cleanup

## Summary
Clean up the Precast Segmental tendon-only Flexure φMn display so the continuous red capacity line is built from canonical display rows only, while exact one-sided physical-joint capacities remain visible as separate markers and audit evidence.

## Why
The previous Segmental tendon-only flexure plot could show narrow zigzags where exact joint-side rows, near-joint rows, and other closely spaced solved rows were all connected into one continuous line. Those artifacts made the φMn envelope look irregular even when the underlying tendon-only capacity basis was sound.

## Changes
- Exclude exact `PHYSICAL SEGMENT JOINT` rows from the continuous red `Adopted tendon-only φMn` line.
- Keep exact one-sided joint capacities as separate orange joint markers and audit rows.
- Build the continuous red line from one canonical display row per x-station using stable de-duplication.
- Update the Segmental flexure caption to explain that the continuous line is a clean display envelope and exact joint-side capacities remain separately available.

## Engineering intent
This milestone does **not** change the tendon-only flexure equations, station-dependent prestress logic, Demand Mux continuity, or the stored joint-side results. It only cleans the displayed φMn trace so plotting artifacts do not appear as false local capacity spikes or dips.
