"""Read-only dimension guide for the existing U-dowel input model.

The SVG is deliberately schematic. Supplied values are labels, never inferred
geometry or evidence of development/fit. No solver or project state is used.
"""
from __future__ import annotations

from html import escape
import math


VERSION = "IGIRDER.DOWEL32"

# Keep the existing configuration keys and editor order. These letters are also
# used on the drawing, so dimensions cannot drift between figure and form.
DIMENSION_GUIDE = (
    ("row_spacing_mm", "A", "U-leg centres a",
     "Centre to centre of the two U legs across the girder; not spacing along the span."),
    ("slab_ldh_available_mm", "B", "Interface to outside of top hook",
     "Vertical distance from the girder–slab interface to the OUTSIDE of the upper hook."),
    ("hook_tail_mm", "C", "Straight tail after 90° bend",
     "From the bend tangent to the bar end; exclude the curved part."),
    ("hook_inside_bend_mm", "D", "Inside bend diameter",
     "Full diameter of the circle inside the bend; not radius or outside diameter."),
    ("cover_required_mm", "E", "Required clear cover",
     "Required concrete surface to outside of bar; not distance to bar centre."),
    ("girder_ld_available_mm", "F", "Straight bonded leg below interface",
     "From the interface down to the start of the bottom U-return; exclude the return bend."),
)


def dimension_label(key: str) -> str:
    """A stable figure reference without altering any stored field name."""
    return next(f"{ref} · {label}" for field, ref, label, _ in DIMENSION_GUIDE if field == key)


def _value(value) -> str:
    if isinstance(value, bool):
        return "Not entered"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "Not entered"
    return f"{numeric:,.1f}".removesuffix(".0") + " mm" if math.isfinite(numeric) and numeric > 0 else "Not entered"


def u_dowel_detail_svg(dimensions: dict, *, section_params: dict | None = None) -> str:
    """Return a self-contained accessible SVG; do not change the input mapping."""
    section_params = section_params or {}
    values = {key: _value(dimensions.get(key)) for key, *_ in DIMENSION_GUIDE}
    accessible = "; ".join(f"{ref}: {label}, {values[key]}. {meaning}"
        for key, ref, label, meaning in DIMENSION_GUIDE)
    context = ("Current section: slab " + _value(section_params.get("Tslab_mm")) +
        " / girder " + _value(section_params.get("D1_mm")))
    rows = []
    for i, (key, ref, label, meaning) in enumerate(DIMENSION_GUIDE):
        y = 426 + i * 37
        display_label = {"B":"Interface → outside top hook",
            "F":"Straight leg below interface"}.get(ref,label)
        # Figure references are fixed trusted text; all values remain numeric or
        # a fixed missing label, not user-supplied HTML.
        rows.append(f'''<g data-dimension="{key}"><title>{escape(meaning)}</title>
<circle class="ref-bg" cx="845" cy="{y}" r="13"/>
<text class="ref" x="845" y="{y+7}">{ref}</text>
<text x="868" y="{y+7}" class="field">{escape(display_label)}</text>
<text x="1390" y="{y+7}" text-anchor="end" class="value">{escape(values[key])}</text></g>''')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 720"
 width="1440" height="720" role="img" aria-labelledby="dowel32-title dowel32-description"
 font-family="Arial,Inter,Segoe UI,sans-serif" font-size="21" fill="#0f172a"
 data-dowel-guide="{VERSION}" style="display:block;width:100%;height:auto">
<title id="dowel32-title">U-dowel — dimension guide A–F</title>
<desc id="dowel32-description">Schematic transverse section and enlarged 90-degree top hook.
All dimensions in millimetres; not to scale. {escape(accessible)}</desc>
<defs>
 <marker id="dowel32-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 10 5 L 0 1 L 0 9 Z" fill="#334155"/></marker>
</defs>
<rect x="1" y="1" width="1438" height="718" rx="16" fill="white" stroke="#cbd5e1"/>
<text x="32" y="39" font-size="27" font-weight="700">U-dowel · dimension guide</text>
<text x="1390" y="38" text-anchor="end" class="sub">A–F match the inputs · mm</text>
<line x1="32" y1="56" x2="1408" y2="56" class="ext"/>
<text x="42" y="89" class="heading">TRANSVERSE SECTION</text>
<text x="835" y="89" class="heading">TOP HOOK · ENLARGED</text>
<line x1="790" y1="76" x2="790" y2="647" stroke="#e2e8f0" stroke-width="2"/>

<!-- Diagram coordinates are fixed schematic geometry, not calculated lengths. -->
<rect class="concrete" x="120" y="116" width="540" height="166"/>
<path class="concrete" d="M210 282 H570 V326 L495 380 V526 L570 585 V625 H210 V585 L285 526 V380 L210 326 Z"/>
<path class="axis" d="M390 104 V641"/>
<path d="M100 282 H730" stroke="#475569" stroke-dasharray="10 5" stroke-width="2"/>
<text x="123" y="259" class="sub">Top slab</text>
<text x="507" y="309" class="sub">Interface</text>
<text x="390" y="489" text-anchor="middle" class="sub">I-girder</text>
<path class="bar" stroke-width="12" d="M225 160 H305 Q330 160 330 185 V538 C330 598 450 598 450 538 V185 Q450 160 475 160 H555"/>
<circle cx="490" cy="160" r="40" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="5 5"/>

<!-- A is centre-to-centre, across the girder. -->
<path class="ext" d="M330 366 V421 M450 366 V421"/>
<path class="dim" d="M330 402 H450"/>
<rect x="365" y="366" width="50" height="28" rx="5" fill="white"/>
<text x="390" y="388" text-anchor="middle" class="tag">A · a</text>

<!-- B ends at y154, the OUTSIDE of the 12-unit bar at y160. -->
<path class="ext" d="M555 154 H726 M660 282 H726"/>
<path class="dim" d="M706 154 V282"/>
<text x="723" y="210" class="tag">B</text>
<text x="723" y="235" class="sub">ldh</text>

<!-- F stops at the start of the curved bottom return, y538. -->
<path class="ext" d="M157 282 H330 M157 538 H330"/>
<path class="dim" d="M174 282 V538"/>
<text x="135" y="403" class="tag">F</text>
<text x="133" y="429" class="sub">ld</text>
<path class="ext" d="M450 538 H602 L648 570"/>
<text x="578" y="598" class="sub">Start of</text>
<text x="578" y="621" class="sub">U-return</text>

<!-- Enlarged 90-degree hook. Inner radius 70; diameter D is 140. -->
<rect x="835" y="113" width="565" height="284" rx="8" fill="#f8fafc"/>
<path d="M854 126 H1382" stroke="#64748b" stroke-width="2"/>
<text x="858" y="151" class="sub">Concrete surface</text>
<path class="bar" stroke-width="20" d="M950 381 V300 A80 80 0 0 1 1030 220 H1290"/>
<circle class="axis" cx="1030" cy="300" r="70"/>
<path class="axis" d="M1015 300 H1045 M1030 285 V315"/>
<path class="ext" d="M1030 220 V168 M1290 220 V168"/>
<path class="dim" d="M1030 181 H1290"/>
<rect x="1141" y="162" width="37" height="30" rx="4" fill="#f8fafc"/>
<text x="1160" y="184" text-anchor="middle" class="tag">C</text>
<path class="dim" d="M960 300 H1100"/>
<text x="1030" y="283" text-anchor="middle" class="tag">D · Ø</text>
<text x="1123" y="305" class="sub">Inside diameter</text>
<text x="1123" y="331" class="sub">Guide circle</text>
<path class="ext" d="M1290 210 H1374"/>
<path class="dim" d="M1357 126 V210"/>
<text x="1371" y="178" class="tag">E</text>
<text x="858" y="390" class="sub">C starts at the tangent; D is a full diameter.</text>

{''.join(rows)}
<line x1="32" y1="648" x2="1408" y2="648" class="ext"/>
<text x="32" y="676" class="sub">Schematic · not to scale. Enter provided dimensions; the drawing does not verify fit or anchorage.</text>
<text x="32" y="701" class="sub">{escape(context)}. E is required cover; actual cover is checked separately.</text>
</svg>'''
    # Inline attributes keep SVG styling local. A <style> with bare selectors
    # would also restyle Plotly figures elsewhere in the Streamlit document.
    attributes = {
        "sub":'font-size="18" fill="#475569"',
        "heading":'font-size="19" font-weight="700" letter-spacing="1"',
        "field":'font-size="19"', "value":'font-size="20" font-weight="700"',
        "concrete":'fill="#f1f5f9" stroke="#64748b" stroke-width="2"',
        "dim":'fill="none" stroke="#334155" stroke-width="1.7" marker-start="url(#dowel32-arrow)" marker-end="url(#dowel32-arrow)"',
        "ext":'fill="none" stroke="#94a3b8" stroke-width="1.4"',
        "axis":'fill="none" stroke="#94a3b8" stroke-width="1.3" stroke-dasharray="8 7"',
        "bar":'fill="none" stroke="#1f2937" stroke-linecap="butt" stroke-linejoin="round"',
        "ref-bg":'fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"',
        "ref":'font-size="20" font-weight="700" text-anchor="middle" fill="#1d4ed8"',
        "tag":'font-size="22" font-weight="700" fill="#1d4ed8"',
    }
    for css_class, text in attributes.items():
        svg = svg.replace(f'class="{css_class}"',f'class="{css_class}" {text}')
    return svg
