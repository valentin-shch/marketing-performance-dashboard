"""Shared data loading and small helpers used by every page."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"

# displayModeBar off — it's a desktop-mouse feature that just eats vertical
# space on a phone with no way to use it anyway.
PLOTLY_CONFIG = {"responsive": True, "displayModeBar": False}


@st.cache_data
def load_ads() -> pd.DataFrame:
    return pd.read_parquet(CLEAN_DIR / "ads.parquet")


@st.cache_data
def load_crm() -> pd.DataFrame:
    return pd.read_parquet(CLEAN_DIR / "crm_deals.parquet")


@st.cache_data
def load_quality_summary() -> dict:
    with open(CLEAN_DIR / "data_quality_summary.json") as f:
        return json.load(f)


def client_selector(ads: pd.DataFrame) -> str:
    clients = sorted(ads["client"].unique())
    # key= binds this to session_state, so the choice carries over as you
    # move between pages instead of resetting on every navigation
    return st.selectbox("Client", clients, key="selected_client")


def fmt_currency(x: float) -> str:
    return "n/a" if pd.isna(x) else f"€{x:,.0f}"


def fmt_roas(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{x:.2f}x"


def fmt_pct_delta(x: float) -> str | None:
    return None if pd.isna(x) else f"{x * 100:+.1f}% vs prior 30 days"


# st.plotly_chart applies its own default theme over the figure unless told
# not to, which was silently overriding these sizes — see PLOTLY_THEME below.
# Set per-element, not just the global font, so nothing falls back to a
# smaller default regardless of template quirks. These are the desktop
# sizes; MOBILE_CSS below overrides them smaller on narrow viewports via
# a media query, since a Python-level constant can't vary by device.
AXIS_FONT_SIZE = 16
LEGEND_FONT_SIZE = 15

# Wrap a block in st.container(key=DESKTOP_ONLY_KEY) / MOBILE_ONLY_KEY to
# show it only above/below the 640px cutoff — e.g. a wide table on desktop,
# a stacked card list on mobile, for the same underlying data. Both still
# render server-side; MOBILE_CSS just hides one via display:none, since
# there's no way to know the viewport before the page is sent.
DESKTOP_ONLY_KEY = "desktop_only"
MOBILE_ONLY_KEY = "mobile_only"

# Plotly renders tick/legend text as SVG with an inline font-size attribute,
# which a CSS rule (even without !important) still outranks — so this can
# safely shrink text on phones without touching what desktop actually ships.
# 640px is a plain phone-width cutoff, not tied to Streamlit's own column-
# stacking breakpoint.
MOBILE_CSS = f"""
<style>
@media (max-width: 640px) {{
    h1 {{ font-size: 1.6rem !important; }}
    .js-plotly-plot .xtick text,
    .js-plotly-plot .ytick text,
    .js-plotly-plot .y2tick text,
    .js-plotly-plot .g-xtitle text,
    .js-plotly-plot .g-ytitle text,
    .js-plotly-plot .g-y2title text {{
        font-size: 13px !important;
    }}
    .js-plotly-plot .legend text {{
        font-size: 12px !important;
    }}
    .st-key-{DESKTOP_ONLY_KEY} {{ display: none !important; }}
}}
@media (min-width: 641px) {{
    .st-key-{MOBILE_ONLY_KEY} {{ display: none !important; }}
}}
</style>
"""

# Passed to every st.plotly_chart call so our own layout wins outright.
PLOTLY_THEME = None


def chart_layout(fig, y_title: str = "", y2_title: str | None = None) -> None:
    layout = dict(
        font=dict(size=AXIS_FONT_SIZE),
        legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, font=dict(size=LEGEND_FONT_SIZE)),
        # b=40 leaves room for a single line of AXIS_FONT_SIZE tick-label
        # text — b=10 clipped it once the font size got bumped for mobile.
        # l/r are just a fallback floor: automargin=True is what actually
        # sizes them, since tick-label width varies a lot by client (three-
        # digit spend for Vantia vs six-digit for Nordfit) — a fixed number
        # that fits one client's numbers clips another's.
        margin=dict(l=10, r=10, t=30, b=40),
        xaxis=dict(title="", tickfont=dict(size=AXIS_FONT_SIZE), automargin=True),
        yaxis=dict(title=y_title, tickfont=dict(size=AXIS_FONT_SIZE), automargin=True),
        # theme=None (see PLOTLY_THEME) drops Plotly's own default gray
        # plot background too, not just its font sizes — pin it explicitly
        # rather than depend on whichever template happens to apply.
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    if y2_title is not None:
        layout["yaxis2"] = dict(
            title=y2_title, overlaying="y", side="right",
            tickfont=dict(size=AXIS_FONT_SIZE), automargin=True,
        )
    fig.update_layout(**layout)
