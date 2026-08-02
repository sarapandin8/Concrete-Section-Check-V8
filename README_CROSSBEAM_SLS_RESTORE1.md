# CROSSBEAM.SLS.RESTORE1

Makes the member-level Crossbeam Construction Type authoritative across Project
JSON save/load so legacy Cast-in-Place projects cannot reopen as Precast and be
blocked by invented physical Segment-joint coverage requirements.

- Saves canonical `construction_method` with Crossbeam member geometry.
- Migrates legacy `construction_method_last` as the member source.
- Prevents duplicated historical Prestress-Loss metadata from overriding the
  restored member type.
- Keeps the two-face physical-joint gate unchanged for true Precast Segmental
  projects.
- Replaces the truncated native selected-file pill with a readable themed
  review card, explicit Apply/Change actions, and a post-Apply confirmation.
- No concrete-stress equations, ACI limits, FEA sign conventions, ULS logic, or
  Project JSON model schema were changed.
