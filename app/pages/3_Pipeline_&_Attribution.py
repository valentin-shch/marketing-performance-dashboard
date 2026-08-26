import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
while not (_repo_root / "pipeline").is_dir():
    _repo_root = _repo_root.parent
sys.path[:0] = [str(_repo_root), str(_repo_root / "app")]

import plotly.graph_objects as go
import streamlit as st

from lib import CHANNEL_COLORS, MOBILE_CSS, PLOTLY_CONFIG, PLOTLY_THEME, chart_layout, client_selector, fmt_currency, load_ads, load_crm
from pipeline import metrics

st.set_page_config(page_title="Pipeline & Attribution - Marketing Performance", layout="wide")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

st.title("Pipeline & Attribution")
st.caption("How much of the sales pipeline can actually be traced back to a specific campaign?")

ads = load_ads()
crm = load_crm()
client = client_selector(ads)
client_crm = crm[crm["client"] == client]

deals = metrics.deals_summary(client_crm)
attribution = metrics.attribution_breakdown(client_crm)
matched_pct = attribution.get("matched", {"pct": 0.0})["pct"]
unattributed_value_pct = metrics.safe_divide(deals["unattributed_value"], deals["total_value"]) * 100

col1, col2, col3, col4 = st.columns(4)
# Leads with the gap, not the coverage — this page exists to state the
# unattributed share plainly (see brief), so "41% unattributed" is the
# deliberate headline, not "59% matched" softened into a positive framing.
col1.metric("Unattributed", f"{100 - matched_pct:.0f}%")
col2.metric("Unattributed Value", fmt_currency(deals["unattributed_value"]))
col3.metric("Total Pipeline Value", fmt_currency(deals["total_value"]))
col4.metric("Total Deals", f"{deals['total_deals']:,}")

no_source = attribution.get("no_source_recorded", {"pct": 0.0})["pct"]
unmatched = attribution.get("unmatched_source", {"pct": 0.0})["pct"]
st.warning(
    f"{100 - matched_pct:.0f}% of {client}'s deals could not be traced back to a specific campaign — "
    f"{no_source:.0f}% had no source recorded at all, and {unmatched:.0f}% named a source that doesn't "
    f"match any known campaign. That's {fmt_currency(deals['unattributed_value'])} "
    f"({unattributed_value_pct:.0f}% of total pipeline value) sitting outside what any other page in "
    f"this dashboard can attribute to a channel or campaign. These deals are kept in the totals above, "
    f"not dropped — but it means the true ROI of some channels is likely higher than the Overview, "
    f"Channel Efficiency, and Campaign Explorer pages can show, since a share of the revenue they drive "
    f"never makes it back to a named campaign in the CRM."
)

STATUS_LABELS = {"matched": "Matched", "no_source_recorded": "No source recorded", "unmatched_source": "Unmatched source"}
STATUS_COLORS = {"matched": "#1b4f91", "no_source_recorded": "#9e9e9e", "unmatched_source": "#c98a2c"}

st.markdown("**Deal value by attribution status**")
status_order = [s for s in STATUS_LABELS if s in attribution]
value_by_status = client_crm.groupby("attribution_status")["deal_value"].sum()
fig_status = go.Figure()
fig_status.add_trace(go.Bar(
    x=[STATUS_LABELS[s] for s in status_order],
    y=[value_by_status.get(s, 0) for s in status_order],
    marker_color=[STATUS_COLORS[s] for s in status_order],
))
chart_layout(fig_status, "EUR")
st.plotly_chart(fig_status, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)

st.markdown("**Matched deal value by channel**")
st.caption("Only deals that could be traced to a specific campaign — the channel breakdown elsewhere in this dashboard doesn't see the rest.")
matched_deals = client_crm[client_crm["attribution_status"] == "matched"]
value_by_channel = matched_deals.groupby("attributed_channel")["deal_value"].sum()
channel_order = [c for c in CHANNEL_COLORS if c in value_by_channel.index]
fig_channel = go.Figure()
fig_channel.add_trace(go.Bar(
    x=channel_order, y=[value_by_channel[c] for c in channel_order],
    marker_color=[CHANNEL_COLORS[c] for c in channel_order],
))
chart_layout(fig_channel, "EUR")
st.plotly_chart(fig_channel, use_container_width=True, config=PLOTLY_CONFIG, theme=PLOTLY_THEME)
