import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
while not (_repo_root / "pipeline").is_dir():
    _repo_root = _repo_root.parent
sys.path[:0] = [str(_repo_root), str(_repo_root / "app")]

import html

import pandas as pd
import streamlit as st

from lib import DESKTOP_ONLY_KEY, MOBILE_CSS, MOBILE_ONLY_KEY, client_selector, fmt_currency, fmt_roas, load_ads
from pipeline import metrics

st.set_page_config(page_title="Campaign Explorer - Marketing Performance", layout="wide")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

st.title("Campaign Explorer")
st.caption("Which individual campaigns are working, and which ones need a second look?")

ads = load_ads()
client = client_selector(ads)
# Organic Search has no spend and isn't a "campaign" in the naming-convention
# sense (see data/generate.py) — the spend/return trade-off this page
# explores doesn't apply to it.
campaign_ads = ads[(ads["client"] == client) & (ads["channel"] != "Organic Search")]

summary = metrics.flag_campaigns(metrics.campaign_summary(campaign_ads))

FLAG_LABELS = {
    "high_spend_low_return": "High spend, low return",
    "high_return_underfunded": "High return, underfunded",
    "none": "—",
}
summary["flag_label"] = summary["flag"].map(FLAG_LABELS)

st.caption(
    "Auto-flagged relative to this client's own campaigns, not a global bar: \"high spend, low "
    "return\" is spend in the top quarter and ROAS in the bottom quarter; \"high return, "
    "underfunded\" is the reverse — ROAS in the top quarter, spend in the bottom quarter. Flags "
    "require both conditions to align at once, so a client whose high-spend and low-return "
    "campaigns don't overlap may show zero flagged campaigns — that's expected, and a good sign "
    "for that account, not a missing feature."
)

col1, col2, col3, col4 = st.columns(4)
channel_choices = col1.multiselect("Channel", sorted(summary["channel"].unique()), default=sorted(summary["channel"].unique()))
type_choices = col2.multiselect("Type", sorted(summary["campaign_type"].dropna().unique()), default=sorted(summary["campaign_type"].dropna().unique()))
theme_choices = col3.multiselect("Theme", sorted(summary["campaign_theme"].dropna().unique()), default=sorted(summary["campaign_theme"].dropna().unique()))
flag_choices = col4.multiselect(
    "Flag", list(FLAG_LABELS.values()), default=list(FLAG_LABELS.values()),
)

filtered = summary[
    summary["channel"].isin(channel_choices)
    & (summary["campaign_type"].isin(type_choices) | summary["campaign_type"].isna())
    & (summary["campaign_theme"].isin(theme_choices) | summary["campaign_theme"].isna())
    & summary["flag_label"].isin(flag_choices)
].sort_values("spend", ascending=False)

with st.container(key=DESKTOP_ONLY_KEY):
    st.dataframe(
        filtered[["campaign_name", "channel", "campaign_theme", "spend", "roas", "flag_label"]].rename(columns={
            "campaign_name": "Campaign", "channel": "Channel", "campaign_theme": "Theme",
            "spend": "Spend", "roas": "ROAS", "flag_label": "Flag",
        }),
        column_config={
            "Campaign": st.column_config.TextColumn(width="medium"),
            "Spend": st.column_config.NumberColumn(format="€%,.0f"),
            "ROAS": st.column_config.NumberColumn(format="%.2fx"),
            "Flag": st.column_config.TextColumn(width="medium"),
        },
        use_container_width=True,
        hide_index=True,
    )

with st.container(key=MOBILE_ONLY_KEY):
    # same rows, same sort order as the desktop table — just one bordered
    # card per campaign instead of a grid, so nothing needs a horizontal
    # scroll to read on a phone.
    for _, row in filtered.iterrows():
        with st.container(border=True):
            # Plain **bold** markdown renders at body text size, which next
            # to a small gray caption line reads as a headline, not a label
            # — sized down here so the name leads without dominating the card.
            st.markdown(
                f'<div style="font-weight:600; font-size:0.95rem; line-height:1.3;">'
                f'{html.escape(str(row["campaign_name"]))}</div>',
                unsafe_allow_html=True,
            )
            theme = row["campaign_theme"] if pd.notna(row["campaign_theme"]) else None
            details = [row["channel"]] + ([theme] if theme else []) + [fmt_currency(row["spend"]), fmt_roas(row["roas"])]
            st.caption(" · ".join(details))
            if row["flag"] != "none":
                st.caption(f":orange[{row['flag_label']}]")

st.caption(f"{len(filtered)} of {len(summary)} campaigns shown.")

csv_columns = [
    "campaign_name", "channel", "campaign_country", "campaign_type", "campaign_theme",
    "campaign_period", "spend", "conversions", "conversion_value", "roas", "flag_label",
]
csv_bytes = filtered[csv_columns].rename(columns={"flag_label": "flag"}).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download filtered campaigns (CSV)", csv_bytes,
    file_name=f"{client.lower().replace(' ', '_')}_campaigns.csv", mime="text/csv",
)
