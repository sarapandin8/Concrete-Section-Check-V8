"""Reusable commercial UI helpers for Concrete Section Pro.

Visual-only helpers.  They do not read/write solver state and do not change
analysis/data contracts; pages pass already-computed labels and metrics in.
"""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


_COMMERCIAL_CORE_CSS = """
<style>
.cpmm-commercial-page-shell {
  border: 1px solid rgba(13, 53, 93, 0.14);
  border-radius: 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fbff 64%, #eef6ff 100%);
  padding: 0.95rem 1.05rem;
  margin: 0.25rem 0 0.9rem 0;
  box-shadow: 0 9px 24px rgba(7, 26, 51, 0.07);
}
.cpmm-commercial-page-shell.accent-green {
  background: linear-gradient(135deg, #ffffff 0%, #f8fff9 64%, #edfdf3 100%);
  border-color: rgba(22, 131, 58, 0.18);
}
.cpmm-commercial-page-shell.accent-amber {
  background: linear-gradient(135deg, #ffffff 0%, #fffdf5 64%, #fff7df 100%);
  border-color: rgba(194, 120, 3, 0.20);
}
.cpmm-commercial-page-shell.accent-purple {
  background: linear-gradient(135deg, #ffffff 0%, #fbf8ff 64%, #f4edff 100%);
  border-color: rgba(104, 65, 165, 0.20);
}
.cpmm-commercial-page-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.85rem;
}
.cpmm-commercial-page-icon {
  width: 48px;
  height: 48px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0b3a66, #1d6fe7);
  color: #ffffff;
  font-size: 1.28rem;
  font-weight: 950;
  box-shadow: 0 8px 18px rgba(29, 111, 231, 0.20);
}
.accent-green .cpmm-commercial-page-icon { background: linear-gradient(135deg, #166534, #22a447); box-shadow: 0 8px 18px rgba(34, 164, 71, 0.18); }
.accent-amber .cpmm-commercial-page-icon { background: linear-gradient(135deg, #92400e, #f59e0b); box-shadow: 0 8px 18px rgba(245, 158, 11, 0.18); }
.accent-purple .cpmm-commercial-page-icon { background: linear-gradient(135deg, #4c1d95, #7c3aed); box-shadow: 0 8px 18px rgba(124, 58, 237, 0.18); }
.cpmm-commercial-page-kicker {
  color: #526f8d;
  font-size: 0.72rem;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.15rem;
}
.cpmm-commercial-page-title {
  color: #071a33;
  font-size: 1.28rem;
  font-weight: 950;
  line-height: 1.14;
  margin: 0;
}
.cpmm-commercial-page-subtitle {
  color: #475467;
  font-size: 0.88rem;
  line-height: 1.38;
  margin-top: 0.24rem;
}
.cpmm-commercial-page-badge {
  align-self: start;
  border-radius: 999px;
  padding: 0.24rem 0.68rem;
  background: #e8f1ff;
  color: #0b3a66;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.055em;
  text-transform: uppercase;
  border: 1px solid rgba(29, 111, 231, 0.18);
}
.accent-green .cpmm-commercial-page-badge { background: #e9f9ef; color: #166534; border-color: rgba(34, 164, 71, 0.20); }
.accent-amber .cpmm-commercial-page-badge { background: #fff7df; color: #92400e; border-color: rgba(245, 158, 11, 0.22); }
.accent-purple .cpmm-commercial-page-badge { background: #f4edff; color: #4c1d95; border-color: rgba(124, 58, 237, 0.20); }
.cpmm-commercial-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 0.55rem;
  margin: 0.64rem 0 0.4rem 0;
}
.cpmm-commercial-metric-card {
  border: 1px solid #d7e2ee;
  border-left: 5px solid #5b728a;
  border-radius: 13px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  padding: 0.72rem 0.82rem;
  min-height: 84px;
  box-shadow: 0 4px 12px rgba(7, 26, 51, 0.055);
}
.cpmm-commercial-metric-card.ready { border-left-color: #22a447; background: linear-gradient(180deg, #ffffff 0%, #f3fff6 100%); }
.cpmm-commercial-metric-card.warning { border-left-color: #f59e0b; background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%); }
.cpmm-commercial-metric-card.danger { border-left-color: #d92d20; background: linear-gradient(180deg, #ffffff 0%, #fff5f4 100%); }
.cpmm-commercial-metric-card.info { border-left-color: #1d6fe7; background: linear-gradient(180deg, #ffffff 0%, #f2f8ff 100%); }
.cpmm-commercial-metric-title {
  color: #526f8d;
  font-size: 0.68rem;
  font-weight: 950;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 0.22rem;
}
.cpmm-commercial-metric-value {
  color: #071a33;
  font-size: 1.08rem;
  font-weight: 950;
  line-height: 1.16;
  overflow-wrap: anywhere;
}
.cpmm-commercial-metric-detail {
  color: #667085;
  font-size: 0.76rem;
  line-height: 1.30;
  margin-top: 0.20rem;
}
.cpmm-commercial-section-bar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid rgba(7, 26, 51, 0.10);
  border-left: 6px solid #0b3a66;
  border-radius: 12px;
  background: linear-gradient(90deg, #ffffff 0%, #f7fbff 100%);
  padding: 0.64rem 0.78rem;
  margin: 0.55rem 0 0.45rem 0;
  box-shadow: 0 3px 10px rgba(7, 26, 51, 0.045);
}
.cpmm-commercial-section-bar .mark {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #e8f1ff;
  color: #0b3a66;
  font-weight: 950;
  font-size: 0.84rem;
}
.cpmm-commercial-section-bar .title {
  color: #071a33;
  font-size: 0.98rem;
  font-weight: 950;
}
.cpmm-commercial-section-bar .detail {
  color: #667085;
  font-size: 0.78rem;
  margin-left: auto;
}
@media (max-width: 900px) {
  .cpmm-commercial-page-header { grid-template-columns: auto minmax(0, 1fr); }
  .cpmm-commercial-page-badge { grid-column: 2; justify-self: start; }
}
</style>
"""


def install_commercial_core_styles() -> None:
    st.markdown(_COMMERCIAL_CORE_CSS, unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: str,
    *,
    icon: str = "▣",
    kicker: str = "Workspace",
    badge: str = "Commercial UI",
    accent: str = "blue",
) -> None:
    install_commercial_core_styles()
    accent_class = {
        "green": "accent-green",
        "amber": "accent-amber",
        "purple": "accent-purple",
    }.get(str(accent).lower(), "")
    st.markdown(
        f"""
<div class="cpmm-commercial-page-shell {accent_class}">
  <div class="cpmm-commercial-page-header">
    <div class="cpmm-commercial-page-icon">{escape(icon)}</div>
    <div>
      <div class="cpmm-commercial-page-kicker">{escape(kicker)}</div>
      <div class="cpmm-commercial-page-title">{escape(title)}</div>
      <div class="cpmm-commercial-page-subtitle">{escape(subtitle)}</div>
    </div>
    <div class="cpmm-commercial-page-badge">{escape(badge)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_metric_cards(cards: Iterable[dict[str, object]]) -> None:
    install_commercial_core_styles()
    items = []
    for card in cards:
        status = str(card.get("status", "neutral") or "neutral").lower()
        if status not in {"ready", "warning", "danger", "info", "neutral"}:
            status = "neutral"
        title = escape(str(card.get("title", "")))
        value = escape(str(card.get("value", "")))
        detail = escape(str(card.get("detail", "")))
        detail_html = f'<div class="cpmm-commercial-metric-detail">{detail}</div>' if detail else ""
        items.append(
            f"""
<div class="cpmm-commercial-metric-card {status}">
  <div class="cpmm-commercial-metric-title">{title}</div>
  <div class="cpmm-commercial-metric-value">{value}</div>
  {detail_html}
</div>
"""
        )
    if not items:
        return
    st.markdown('<div class="cpmm-commercial-metric-grid">' + "".join(items) + "</div>", unsafe_allow_html=True)


def render_section_bar(title: str, detail: str = "", *, mark: str = "•") -> None:
    install_commercial_core_styles()
    detail_html = f'<div class="detail">{escape(detail)}</div>' if detail else ""
    st.markdown(
        f"""
<div class="cpmm-commercial-section-bar">
  <span class="mark">{escape(mark)}</span>
  <span class="title">{escape(title)}</span>
  {detail_html}
</div>
""",
        unsafe_allow_html=True,
    )
