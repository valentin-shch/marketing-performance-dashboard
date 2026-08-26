import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
while not (_repo_root / "pipeline").is_dir():
    _repo_root = _repo_root.parent
sys.path[:0] = [str(_repo_root), str(_repo_root / "app")]

import streamlit as st

from lib import MOBILE_CSS, fmt_currency, load_ads, load_quality_summary
from pipeline import metrics

st.set_page_config(page_title="Data Quality - Marketing Performance", layout="wide")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

st.title("Data Quality")
st.caption("How much can you trust the numbers on the other pages, and why?")
st.write("No client selector here — this covers the pipeline behind every other page, across all three demo accounts.")

ads = load_ads()
q = load_quality_summary()

ads_in = sum(n for name, n in q["rows_in"].items() if name != "crm_deals.csv")
ads_out = q["rows_out"]["ads_clean"]
total_days = ads["date"].nunique()
imputed_rows = int(ads["conversion_value_imputed"].sum())
convertible_rows = int((ads["conversions"] > 0).sum())
imputed_pct = metrics.safe_divide(imputed_rows, convertible_rows) * 100
parsed = q["campaign_parsing"]
paid_parsed = parsed["A"] + parsed["B"] + parsed["C"]
paid_total = paid_parsed + parsed["unknown"]
parsed_pct = paid_parsed / paid_total * 100
linkedin_converted = q["fx_conversion"]["linkedin_rows_converted"]
gap_days = q["fx_conversion"]["gap_days_filled"]
linkedin_rows = int((ads["channel"] == "LinkedIn Ads").sum())
dup_pct = q["duplicates_removed"] / ads_in * 100
ISSUES_FIXED = 6


def stat_block(value: str, label: str, sublabel: str | None = None) -> None:
    # One custom-styled block, reused for all six stats — st.metric's own
    # styling doesn't match a hand-styled div, so mixing the two (as an
    # earlier version did) reads as two different design systems on one row.
    html = (
        f'<div style="font-size:1.8rem; font-weight:700; line-height:1.15;">{value}</div>'
        f'<div style="color:#6b6b6b;">{label}</div>'
    )
    if sublabel:
        html += f'<div style="color:#9e9e9e; font-size:0.85rem; margin-top:0.15rem;">{sublabel}</div>'
    st.markdown(html, unsafe_allow_html=True)


row1 = st.columns(3)
with row1[0]:
    stat_block(f"{ISSUES_FIXED}", "data issues caught and fixed automatically")
with row1[1]:
    stat_block(f"{ads_in:,} → {ads_out:,}", "raw ad rows in, clean rows out")
with row1[2]:
    stat_block(f"{q['duplicates_removed']:,}", "duplicate rows removed", f"{dup_pct:.1f}% of raw ad rows")

row2 = st.columns(3)
with row2[0]:
    stat_block(f"{parsed_pct:.0f}%", "campaign names understood", f"{parsed['unknown']} bucketed as unknown")
with row2[1]:
    stat_block(f"{linkedin_converted:,}", "currency rows converted", "LinkedIn, USD to EUR")
with row2[2]:
    stat_block(f"{imputed_rows:,}", "values estimated", f"{imputed_pct:.1f}% of rows with a conversion")

st.caption(f"Plus {q['rows_in']['crm_deals.csv']:,} CRM deal records — covered on the Pipeline & Attribution page.")
st.divider()

st.subheader("What got fixed")

with st.container(border=True):
    st.markdown(
        f"**Duplicate rows.** {q['duplicates_removed']:,} exact-duplicate rows from a re-export, "
        f"removed before any totals on this dashboard were calculated."
    )

with st.container(border=True):
    st.markdown(
        "**Mixed date formats.** Google, Meta, LinkedIn, and Organic Search each export dates "
        "differently — YYYY-MM-DD, DD/MM/YYYY, and so on. Every file was parsed against its own "
        "platform's format before any row was compared, joined, or plotted."
    )

with st.container(border=True):
    st.markdown(
        f"**A timezone bug.** LinkedIn logs its export in UTC while every other channel runs on "
        f"Europe/Madrid business days — left alone, this shows up as a one-day offset. All "
        f"{linkedin_rows:,} LinkedIn rows were corrected to the same local calendar day as everything else."
    )

with st.container(border=True):
    st.markdown(
        f"**Currency.** LinkedIn's {linkedin_converted:,} USD rows converted to EUR using the daily "
        f"rate; {gap_days} of {total_days} weekend days had no published rate and used the last "
        f"available one instead."
    )

with st.container(border=True):
    st.markdown(
        f"**Campaign names.** {parsed_pct:.1f}% parsed automatically across three different naming "
        f'conventions (e.g. "ES_Search_Brand_2024Q1" vs. "es-search-brand-q1" vs. "Brand Search ES '
        f'Q1"). The rest — {parsed["unknown"]} campaigns — didn\'t match any known pattern and were '
        f"bucketed honestly as unknown rather than force-fit into a guess."
    )

with st.container(border=True):
    st.markdown(
        f"**Missing values.** {imputed_rows:,} rows had a conversion but no revenue recorded — filled "
        f"with a same-client, same-channel average ({fmt_currency(q['conversion_value_imputed']['dollars_imputed'])} "
        f"total) and flagged internally so it's never mistaken for an actual reported number."
    )
