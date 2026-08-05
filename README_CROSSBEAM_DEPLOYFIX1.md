# CROSSBEAM.DEPLOYFIX1 — Streamlit / Starlette compatibility pin

## Scope

Deployment-only hotfix from `CROSSBEAM.ANALYSIS4C6B`.

The 2026-08-05 Community Cloud rebuild resolved `streamlit==1.61.0` together with newly released `starlette==1.4.0`. Starlette 1.4.0 added the keyword-only `thread_minimum_size` constructor parameter to its GZip responder, while Streamlit 1.61.0 still instantiated the responder using the prior signature. The ASGI health endpoint therefore returned HTTP 500 before `app.py` was executed.

## Change

- Pin `streamlit==1.61.0`.
- Pin `starlette==1.3.1`.
- Preserve every application and engineering source file from `ANALYSIS4C6B` unchanged.

## Engineering impact

- No engineering equations changed.
- No ULS/SLS solver logic changed.
- No station/geometry routing changed.
- No Project JSON behavior changed.
- No UI behavior changed after successful server startup.

## Required deployment validation

Redeploy from a clean environment and verify the Streamlit `/_stcore/health` endpoint responds successfully before visual/engineering QA.
