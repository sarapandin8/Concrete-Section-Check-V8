# UI.REBAR.INCLUSION2 — Bridge/Girder rebar exclusion state fix

## Scope
Fix Rebar-page status alignment when ordinary rebar is disabled in Section Builder, especially for Beam/Girder and saved/restored project workflows where the section-level flag can be available from project metadata before every page materializes the top-level session key.

## Included
- Reinforcement-system flag readers now fall back to `project_metadata` when the top-level session key is missing.
- The Rebar page preserves the stored table but publishes no active `rebars` while ordinary rebar is disabled.
- Disabled rebar metrics now distinguish stored rows/As from active analysis bars/As.
- Rebar preview remains visible as review-only/excluded, with dimension guides hidden.

## Out of scope
- No solver changes.
- No rebar parser, As calculation, geometry, section property, load, report, or project schema changes.
- Stored rebar table rows are not deleted when the section-level ordinary-rebar system is disabled.
