# Make the complete BG40 calculation report the I girder default

The previous generic Draft Word export could produce a report without graphs
or editable calculations, and users had to find it inside extensive export QA
and choose content options. I-girder Report / QA now opens with the complete
BG40 R10 Word workflow: create the report, then download it. All chapters,
calculations, available figures and source appendices are included automatically.
Optional report metadata, previews, engineering review and source evidence sit
in collapsed sections. The legacy Draft Word builder is not exposed on this route.

The native exporter now applies the print layouts previously added outside the
app for the sample: readable ULS captions, debonding dimensions outside the
bitmap, visible slab bars, and prose separated from Word math. Required figure
failures block a complete download. Project/result/metadata changes invalidate
the download. Source case coupling, failure states and the original Word styles,
theme, margins and header/footer formats remain intact.

Validation: 218 targeted/regression tests passed, plus a full Streamlit AppTest
build using the real static renderer and the prior calculated sample state.
The actual download payload contains 10 chapters, 58 embedded figures, 219 native
Word equations and 79 tables, with no post-export document changes. No analysis
solver is invoked by the report workflow. These counts describe the sample,
not a fixed template quota for all projects.

Baseline: REPORT.BG40.80. Milestone: REPORT.DEFAULT81.
No engineering equations, ULS/SLS analysis algorithms, Project JSON behavior
or result-cache persistence changed. This release targets the existing
parametric I-girder BG40 route; other workflow reports retain their own scope.

The real-render QA flow can be reproduced from the app root with the installed
requirements:

```sh
PYTHONPATH=.:tests python qa/build_report_default81_sample.py --out qa_sample
PYTHONPATH=.:tests python qa/report_default81_ui_export.py --state qa_sample/calculated_example.pkl --out qa_export
```

The QA state is hypothetical and must not be used as a project design. The
download validation records the exact payload digest and the absence of
post-export document edits.

Commit summary:

Make complete BG40 Word reporting the I-girder default, integrate print layouts,
remove content-selection burden and block incomplete or stale downloads.
