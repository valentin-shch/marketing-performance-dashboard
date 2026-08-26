"""Raw ad-platform exports + CRM export -> clean, joined parquet.

Reads data/raw/*.csv, fixes the deliberately-messy bits (mixed date
formats, USD vs EUR, a timezone-bucketing artefact, duplicate rows,
missing values, inconsistent campaign naming), and writes
data/clean/ads.parquet and data/clean/crm_deals.parquet plus a
data-quality summary describing exactly what was done and why.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"

RAW_FILES = {
    "Google Ads": ("google_ads.csv", "%Y-%m-%d"),
    "Meta Ads": ("meta_ads.csv", "%d/%m/%Y"),
    "LinkedIn Ads": ("linkedin_ads.csv", "%Y-%m-%d"),
    "Organic Search": ("organic_search.csv", "%Y-%m-%d"),
}


def load_raw_ads() -> tuple[pd.DataFrame, dict[str, int]]:
    frames = []
    rows_in = {}
    for channel, (fname, fmt) in RAW_FILES.items():
        df = pd.read_csv(RAW_DIR / fname)
        rows_in[fname] = len(df)
        df["date"] = pd.to_datetime(df["date"], format=fmt)
        frames.append(df)
    return pd.concat(frames, ignore_index=True), rows_in


def dedupe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    return df, before - len(df)


def fix_linkedin_dates(df: pd.DataFrame) -> pd.DataFrame:
    # generate.py's raw export logs LinkedIn in UTC while everything else runs
    # on Europe/Madrid business days, which leaves LinkedIn's date column one
    # day behind. Correct it before joining anything on date.
    df = df.copy()
    mask = df["channel"] == "LinkedIn Ads"
    df.loc[mask, "date"] = df.loc[mask, "date"] + pd.Timedelta(days=1)
    return df


def load_fx_rates(date_range: pd.DatetimeIndex) -> tuple[pd.Series, int]:
    fx = pd.read_csv(RAW_DIR / "fx_rates.csv", parse_dates=["date"])
    # fx_rates.csv only has weekday rows (markets are closed weekends); carry
    # the last trading rate forward. Reindexed against the ads data's own
    # date range, not the fx file's — if the window opens on a weekend,
    # fx_rates.csv's first row is a few days later than day one of the ads
    # data, so back-fill covers that leading gap too.
    gap_days = int(len(date_range) - date_range.isin(fx["date"]).sum())
    rates = fx.set_index("date")["usd_eur"].reindex(date_range).ffill().bfill()
    return rates, gap_days


def apply_fx(df: pd.DataFrame, fx_by_date: pd.Series) -> tuple[pd.DataFrame, int]:
    df = df.copy()
    mask = df["channel"] == "LinkedIn Ads"
    rates = df.loc[mask, "date"].map(fx_by_date)
    df.loc[mask, "spend"] = (df.loc[mask, "spend"] * rates).round(2)
    return df, int(mask.sum())


def impute_missing_conversion_value(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    missing = df["conversion_value"].isna()

    # average revenue-per-conversion for the same client+channel, from rows
    # where we actually have a value — a coarse but defensible stand-in for
    # "what would this have been worth"
    rate_by_group = (
        df.loc[~missing & (df["conversions"] > 0)]
        .assign(rate=lambda d: d["conversion_value"] / d["conversions"])
        .groupby(["client", "channel"])["rate"].mean()
    )
    filled = df.loc[missing].apply(
        lambda r: round(r["conversions"] * rate_by_group.get((r["client"], r["channel"]), 0.0), 2),
        axis=1,
    )
    df.loc[missing, "conversion_value"] = filled
    df["conversion_value_imputed"] = missing

    return df, {"rows_imputed": int(missing.sum()), "dollars_imputed": round(float(filled.sum()), 2)}


# --- campaign name parsing ---------------------------------------------------
# Three agencies, three conventions (see data/generate.py for the source of
# each). Matched in order; anything that fits none of them — a legacy name
# from before a client's naming convention existed, a typo, whatever — goes
# to the explicit "unknown" bucket instead of being forced into a guess.
CAMPAIGN_PATTERNS = [
    ("A", re.compile(r"^(?P<country>[A-Z]{2})_(?P<type>[A-Za-z]+)_(?P<theme>[A-Za-z]+)_(?P<period>\d{4}Q[1-4])$")),
    ("B", re.compile(r"^(?P<country>[a-z]{2})-(?P<type>[a-z]+)-(?P<theme>[a-z]+)-(?P<period>q[1-4])$")),
    ("C", re.compile(r"^(?P<theme>[A-Za-z]+) (?P<type>[A-Za-z]+) (?P<country>[A-Z]{2}) (?P<period>Q[1-4])$")),
]


def parse_campaign_name(channel: str, name: str) -> dict:
    if channel == "Organic Search":
        return dict(convention="organic", country="ES", type="Organic", theme="Organic", period=None)
    for label, pattern in CAMPAIGN_PATTERNS:
        m = pattern.match(name)
        if m:
            g = m.groupdict()
            return dict(
                convention=label, country=g["country"].upper(),
                type=g["type"].title(), theme=g["theme"].title(), period=g["period"].upper(),
            )
    return dict(convention="unknown", country=None, type=None, theme=None, period=None)


def parse_campaign_names(df: pd.DataFrame) -> pd.DataFrame:
    parsed = df.apply(lambda r: parse_campaign_name(r["channel"], r["campaign_name"]), axis=1, result_type="expand")
    parsed = parsed.rename(columns={
        "country": "campaign_country", "type": "campaign_type",
        "theme": "campaign_theme", "period": "campaign_period", "convention": "campaign_convention",
    })
    return pd.concat([df.reset_index(drop=True), parsed.reset_index(drop=True)], axis=1)


def load_crm_deals() -> tuple[pd.DataFrame, int]:
    df = pd.read_csv(RAW_DIR / "crm_deals.csv")
    df["created_date"] = pd.to_datetime(df["created_date"])
    df["closed_date"] = pd.to_datetime(df["closed_date"])
    return df, len(df)


def attribute_deals(crm: pd.DataFrame, ads: pd.DataFrame) -> pd.DataFrame:
    # Exact match only, scoped to the same client. Fuzzy-matching the
    # malformed source_campaign values would recover a few more deals but
    # would also hide how much of the CRM export is genuinely unusable —
    # better to report that plainly (see data_quality_summary.json).
    known_by_client = ads.groupby("client")["campaign_name"].apply(set).to_dict()
    channel_by_name = ads.drop_duplicates(["client", "campaign_name"]).set_index(["client", "campaign_name"])["channel"]

    def status(row):
        if pd.isna(row["source_campaign"]):
            return "no_source_recorded"
        if row["source_campaign"] in known_by_client.get(row["client"], set()):
            return "matched"
        return "unmatched_source"

    crm = crm.copy()
    crm["attribution_status"] = crm.apply(status, axis=1)
    crm["attributed_channel"] = crm.apply(
        lambda r: channel_by_name.get((r["client"], r["source_campaign"]))
        if r["attribution_status"] == "matched" else None,
        axis=1,
    )
    return crm


def print_summary(summary: dict) -> None:
    print("rows in:")
    for name, n in summary["rows_in"].items():
        print(f"  {name}: {n}")

    ads_in = sum(n for name, n in summary["rows_in"].items() if name != "crm_deals.csv")
    dup = summary["duplicates_removed"]
    print(f"\nduplicates removed: {dup} ({dup / ads_in * 100:.1f}% of ads rows)")

    fx = summary["fx_conversion"]
    print(f"\nLinkedIn spend rows converted USD -> EUR: {fx['linkedin_rows_converted']}")
    print(f"days with no native FX rate (weekend/gap, carried from nearest trading day): {fx['gap_days_filled']}")

    mv = summary["conversion_value_imputed"]
    print(f"\nconversion_value imputed: {mv['rows_imputed']} rows (EUR {mv['dollars_imputed']:,.2f})")

    print("\ncampaign name parsing:")
    for k, v in summary["campaign_parsing"].items():
        print(f"  {k}: {v}")

    print("\nCRM source_campaign attribution:")
    total_crm = summary["rows_out"]["crm_deals_clean"]
    for k, v in summary["crm_attribution"].items():
        print(f"  {k}: {v} ({v / total_crm * 100:.1f}%)")

    print(f"\nrows out: ads={summary['rows_out']['ads_clean']}  crm_deals={summary['rows_out']['crm_deals_clean']}")


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    ads, rows_in_ads = load_raw_ads()
    ads, dup_removed = dedupe(ads)
    ads = fix_linkedin_dates(ads)

    fx_by_date, fx_gap_days = load_fx_rates(pd.date_range(ads["date"].min(), ads["date"].max(), freq="D"))
    ads, linkedin_converted = apply_fx(ads, fx_by_date)

    ads, missing_stats = impute_missing_conversion_value(ads)
    ads = parse_campaign_names(ads)
    ads.to_parquet(CLEAN_DIR / "ads.parquet", index=False)

    crm, rows_in_crm = load_crm_deals()
    crm = attribute_deals(crm, ads)
    crm.to_parquet(CLEAN_DIR / "crm_deals.parquet", index=False)

    summary = {
        "rows_in": {**rows_in_ads, "crm_deals.csv": rows_in_crm},
        "duplicates_removed": dup_removed,
        "fx_conversion": {"linkedin_rows_converted": linkedin_converted, "gap_days_filled": fx_gap_days},
        "conversion_value_imputed": missing_stats,
        "campaign_parsing": ads["campaign_convention"].value_counts().to_dict(),
        "crm_attribution": crm["attribution_status"].value_counts().to_dict(),
        "rows_out": {"ads_clean": len(ads), "crm_deals_clean": len(crm)},
    }
    with open(CLEAN_DIR / "data_quality_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print_summary(summary)


if __name__ == "__main__":
    main()
