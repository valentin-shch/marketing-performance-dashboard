import sys
from pathlib import Path

# Walk up to the repo root regardless of whether Streamlit runs this from
# app/ or app/pages/, so both `lib` (this folder) and `pipeline` (repo
# root) are always importable.
_repo_root = Path(__file__).resolve().parent
while not (_repo_root / "pipeline").is_dir():
    _repo_root = _repo_root.parent
sys.path[:0] = [str(_repo_root), str(_repo_root / "app")]

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import PLOTLY_CONFIG, PLOTLY_THEME, chart_layout, client_selector, fmt_currency, fmt_pct_delta, fmt_roas, load_ads
from pipeline import metrics

st.set_page_config(page_title="Overview - Marketing Performance", layout="wide")

st.title("Marketing Performance Dashboard")
st.caption(
    "Demo dashboard for a digital marketing agency's clients, covering Google Ads, Meta Ads, "
    "LinkedIn Ads, and organic search. It answers one question per account: is the marketing "
    "spend paying off, and is it getting better or worse? All data shown is synthetic."
)

st.subheader("Overview")
st.caption("Is this account's marketing spend paying off, and is it getting better or worse?")

ads = load_ads()
client = client_selector(ads)
client_ads = ads[ads["client"] == client]

summary = metrics.summarize(client_ads)
pop = metrics.period_over_period(client_ads, days=30)
trend = metrics.trend_label(pop["change_pct"]["roas"])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Blended ROAS", fmt_roas(summary["roas"]), fmt_pct_delta(pop["change_pct"]["roas"]))
col2.metric("Attributed Revenue", fmt_currency(summary["conversion_value"]), fmt_pct_delta(pop["change_pct"]["conversion_value"]))
col3.metric(
    "Spend", fmt_currency(summary["spend"]),
    fmt_pct_delta(pop["change_pct"]["spend"]), delta_color="off",
)
col4.metric(
    "Cost per Lead", fmt_currency(summary["cost_per_conversion"]),
    fmt_pct_delta(pop["change_pct"]["cost_per_conversion"]), delta_color="inverse",
)

roas_delta_pct = pop["change_pct"]["roas"]
if pd.isna(roas_delta_pct):
    st.info(f"Not enough recent history yet to compare {client}'s ROAS trend.")
elif trend == "up":
    st.success(f"{client}'s blended ROAS is trending up: {roas_delta_pct * 100:+.1f}% over the last 30 days.")
elif trend == "down":
    st.warning(f"{client}'s blended ROAS is trending down: {roas_delta_pct * 100:+.1f}% over the last 30 days.")
else:
    st.info(f"{client}'s blended ROAS has held steady over the last 30 days ({roas_delta_pct * 100:+.1f}%).")

weekly = (
    client_ads.assign(week=client_ads["date"].dt.to_period("W").dt.start_time)
    .groupby("week")
    .agg(spend=("spend", "sum"), conversion_value=("conversion_value", "sum"))
    .reset_index()
)
weekly["roas"] = weekly["conversion_value"] / weekly["spend"]
# 4-week centered average — spend and revenue are aggregated weekly already,
# but with e.g. Vantia's low weekly lead volume the week-to-week ROAS swing
# is real sampling noise, not signal; the smoothed line is what answers
# "trending better or worse", the raw points show it isn't being hidden.
weekly["roas_trend"] = weekly["roas"].rolling(4, min_periods=1, center=True).mean()

st.markdown("**Spend vs. attributed revenue** (weekly)")
fig_spend = go.Figure()
fig_spend.add_trace(go.Scatter(x=weekly["week"], y=weekly["spend"], name="Spend", line=dict(color="#1b4f91")))
fig_spend.add_trace(go.Scatter(
    x=weekly["week"], y=weekly["conversion_value"], name="Attributed Revenue",
    yaxis="y2", line=dict(color="#7fa8d9"),
))
chart_layout(fig_spend, "EUR", "EUR")
st.plotly_chart(fig_spend, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)

st.markdown("**Blended ROAS trend** (weekly)")
fig_roas = go.Figure()
fig_roas.add_trace(go.Scatter(x=weekly["week"], y=weekly["roas"], name="Weekly ROAS", line=dict(width=1, color="#a8c5e8")))
fig_roas.add_trace(go.Scatter(x=weekly["week"], y=weekly["roas_trend"], name="4-week trend", line=dict(width=3, color="#1b4f91")))
fig_roas.add_hline(y=1, line_dash="dot", annotation_text="breakeven", annotation_position="bottom right")
chart_layout(fig_roas, "ROAS (x)")
st.plotly_chart(fig_roas, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)
