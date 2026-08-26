import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
while not (_repo_root / "pipeline").is_dir():
    _repo_root = _repo_root.parent
sys.path[:0] = [str(_repo_root), str(_repo_root / "app")]

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import MOBILE_CSS, PLOTLY_CONFIG, PLOTLY_THEME, chart_layout, client_selector, load_ads
from pipeline import metrics

st.set_page_config(page_title="Channel Efficiency - Marketing Performance", layout="wide")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

st.title("Channel Efficiency")
st.caption("Which channels are worth the spend, and which ones have stopped paying off?")

ads = load_ads()
client = client_selector(ads)
client_ads = ads[ads["client"] == client]

channel_summary = (
    client_ads.groupby("channel")
    .agg(spend=("spend", "sum"), conversion_value=("conversion_value", "sum"))
    .reset_index()
)
channel_summary["roas"] = channel_summary.apply(
    lambda r: metrics.safe_divide(r["conversion_value"], r["spend"]), axis=1
)

st.markdown("**Spend vs. return by channel**")
fig_channels = go.Figure()
fig_channels.add_trace(go.Bar(x=channel_summary["channel"], y=channel_summary["spend"], name="Spend", marker_color="#1b4f91"))
fig_channels.add_trace(go.Bar(
    x=channel_summary["channel"], y=channel_summary["conversion_value"],
    name="Attributed Revenue", marker_color="#7fa8d9",
))
fig_channels.update_layout(barmode="group")
# Both series share one EUR axis on purpose — unlike Overview's time series,
# collapsing to a single scale here is honest (Organic's zero spend bar is
# supposed to look tiny next to its revenue) and sidesteps a dual-axis
# rotated title fight over a categorical x-axis.
chart_layout(fig_channels, "EUR")
st.plotly_chart(fig_channels, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)

deciles = metrics.spend_decile_roas(client_ads)
flags = metrics.diminishing_returns_channels(deciles)
ratios = metrics.decile_ratio_to_peak(deciles)

st.markdown("**Marginal efficiency** — ROAS by spend decile")
st.caption(
    "Days are split into ten equal groups by that day's spend, lowest to highest. A channel is "
    "flagged once its highest-spend days return less than 75% of its own best decile's ROAS — a "
    "sign extra budget on that channel has stopped paying off as well as it used to."
)

CHANNEL_COLORS = {"Google Ads": "#1b4f91", "Meta Ads": "#7fa8d9", "LinkedIn Ads": "#c98a2c"}
channel_order = [c for c in CHANNEL_COLORS if c in deciles["channel"].unique()]
decile_cols = st.columns(len(channel_order)) if channel_order else []
for col, channel in zip(decile_cols, channel_order):
    sub = deciles[deciles["channel"] == channel].sort_values("decile")
    with col:
        # title -> chart -> caption, same three elements in the same order
        # for every column regardless of flag status, so the three charts'
        # plot areas line up — an extra line only on flagged columns used to
        # push that chart down relative to the other two.
        st.markdown(f"*{channel}*")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sub["decile"], y=sub["roas"], mode="lines+markers", line=dict(color=CHANNEL_COLORS[channel])))
        chart_layout(fig, "ROAS (x)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)

        # secondary detail, not a headline number — visible for every channel
        # so a near-miss (e.g. 77%, just above the 75% cutoff) doesn't read
        # as indistinguishable from a comfortable 90%.
        ratio = ratios.get(channel)
        ratio_text = "n/a" if pd.isna(ratio) else f"{ratio * 100:.0f}% of peak"
        if flags.get(channel):
            st.caption(f":orange[{ratio_text} — past diminishing returns]")
        else:
            st.caption(ratio_text)

flagged = [c for c, is_flagged in flags.items() if is_flagged]
if flagged:
    channels_text = flagged[0] if len(flagged) == 1 else ", ".join(flagged)
    st.warning(f"Past the point of diminishing return: {channels_text}. Extra budget there is returning less than it did on lower-spend days.")
else:
    st.success("No channel shows signs of diminishing returns at current spend levels.")
