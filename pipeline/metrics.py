"""Business metric calculations over the clean ads and CRM tables.

Every function here is pure: it takes a DataFrame (already loaded from
data/clean/) and returns numbers or a new DataFrame. No file I/O, so
they're cheap to unit test and safe to call from inside a cached
Streamlit page.
"""

from __future__ import annotations

import pandas as pd


def safe_divide(numerator: float, denominator: float) -> float:
    if not denominator or pd.isna(denominator):
        return float("nan")
    return numerator / denominator


def summarize(df: pd.DataFrame) -> dict:
    spend = df["spend"].sum()
    conversions = df["conversions"].sum()
    conversion_value = df["conversion_value"].sum()
    # roas/cost-per-conversion are computed on the totals, not averaged
    # per row — averaging per-row ratios would let low-spend days with
    # freak ratios outweigh the days that actually moved the budget.
    return {
        "spend": spend,
        "impressions": df["impressions"].sum(),
        "clicks": df["clicks"].sum(),
        "conversions": conversions,
        "conversion_value": conversion_value,
        "roas": safe_divide(conversion_value, spend),
        "cost_per_conversion": safe_divide(spend, conversions),
    }


def pct_change(old: float, new: float) -> float:
    if not old or pd.isna(old):
        return float("nan")
    return (new - old) / old


def trend_label(change_pct: float, flat_band: float = 0.02) -> str:
    if pd.isna(change_pct):
        return "flat"
    if change_pct > flat_band:
        return "up"
    if change_pct < -flat_band:
        return "down"
    return "flat"


def trailing_windows(df: pd.DataFrame, date_col: str = "date", days: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split df into the last `days` days and the equal-length period before that."""
    end = df[date_col].max()
    current_start = end - pd.Timedelta(days=days - 1)
    prior_end = current_start - pd.Timedelta(days=1)
    prior_start = prior_end - pd.Timedelta(days=days - 1)
    current = df[df[date_col].between(current_start, end)]
    prior = df[df[date_col].between(prior_start, prior_end)]
    return current, prior


def period_over_period(df: pd.DataFrame, date_col: str = "date", days: int = 30) -> dict:
    current, prior = trailing_windows(df, date_col, days)
    current_summary = summarize(current)
    prior_summary = summarize(prior)
    change_pct = {
        key: pct_change(prior_summary[key], current_summary[key])
        for key in ("spend", "conversion_value", "roas", "cost_per_conversion")
    }
    return {"current": current_summary, "prior": prior_summary, "change_pct": change_pct}


def spend_decile_roas(df: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """For each channel, bucket days into spend deciles and compute ROAS per
    decile — the shape of this curve is what shows whether extra budget on a
    channel is still paying off or has flattened out.
    """
    rows = []
    for channel, sub in df.groupby("channel"):
        daily = sub.groupby("date").agg(spend=("spend", "sum"), conversion_value=("conversion_value", "sum"))
        daily = daily[daily["spend"] > 0].reset_index()
        if len(daily) < n_bins:
            continue
        daily["decile"] = pd.qcut(daily["spend"], q=n_bins, labels=False, duplicates="drop") + 1
        grouped = daily.groupby("decile").agg(
            avg_spend=("spend", "mean"),
            total_spend=("spend", "sum"),
            total_value=("conversion_value", "sum"),
            days=("spend", "size"),
        ).reset_index()
        grouped["roas"] = grouped["total_value"] / grouped["total_spend"]
        grouped["channel"] = channel
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["decile", "avg_spend", "total_spend", "total_value", "days", "roas", "channel"]
    )


def decile_ratio_to_peak(decile_df: pd.DataFrame) -> dict[str, float]:
    """Highest-spend decile's ROAS as a fraction of the channel's own peak-
    decile ROAS. This is the exact number diminishing_returns_channels()
    thresholds against — exposed on its own so it can be shown for every
    channel, not just the ones that cross the line.
    """
    ratios = {}
    for channel, sub in decile_df.groupby("channel"):
        sub = sub.sort_values("decile")
        peak_roas = sub["roas"].max()
        top_decile_roas = sub.iloc[-1]["roas"]
        ratios[channel] = safe_divide(top_decile_roas, peak_roas)
    return ratios


def diminishing_returns_channels(decile_df: pd.DataFrame, drop_threshold: float = 0.75) -> dict[str, bool]:
    """Flag a channel if its highest-spend decile's ROAS has fallen well below
    the channel's own peak-decile ROAS — the signature of a channel past the
    point where extra budget still pays for itself.
    """
    ratios = decile_ratio_to_peak(decile_df)
    flags = {}
    for channel, ratio in ratios.items():
        flags[channel] = bool(not pd.isna(ratio) and ratio < drop_threshold)
    return flags


def campaign_summary(df: pd.DataFrame) -> pd.DataFrame:
    # campaign_country/type/theme/period are constant within a campaign_name
    # by construction (parsed once per name in clean.py), so "first" is a
    # plain lookup here, not a lossy aggregation choice.
    grouped = df.groupby(["client", "channel", "campaign_name"]).agg(
        spend=("spend", "sum"),
        conversion_value=("conversion_value", "sum"),
        conversions=("conversions", "sum"),
        campaign_country=("campaign_country", "first"),
        campaign_type=("campaign_type", "first"),
        campaign_theme=("campaign_theme", "first"),
        campaign_period=("campaign_period", "first"),
    ).reset_index()
    grouped["roas"] = grouped.apply(lambda r: safe_divide(r["conversion_value"], r["spend"]), axis=1)
    return grouped


def flag_campaigns(summary_df: pd.DataFrame, spend_quantile: float = 0.75, roas_quantile: float = 0.25) -> pd.DataFrame:
    """Flag campaigns relative to their own client's peers, not globally —
    Solmar's smallest campaign can outspend all of Clinica Vantia's, so a
    global spend threshold would just flag "is this client big or small".
    """
    df = summary_df.copy()
    df["flag"] = "none"
    for _, sub in df.groupby("client"):
        spend_hi = sub["spend"].quantile(spend_quantile)
        spend_lo = sub["spend"].quantile(1 - spend_quantile)
        roas_hi = sub["roas"].quantile(1 - roas_quantile)
        roas_lo = sub["roas"].quantile(roas_quantile)
        high_spend_low_return = (sub["spend"] >= spend_hi) & (sub["roas"] <= roas_lo)
        high_return_underfunded = (sub["roas"] >= roas_hi) & (sub["spend"] <= spend_lo)
        df.loc[sub.index[high_spend_low_return], "flag"] = "high_spend_low_return"
        df.loc[sub.index[high_return_underfunded], "flag"] = "high_return_underfunded"
    return df


def attribution_breakdown(crm_df: pd.DataFrame) -> dict:
    counts = crm_df["attribution_status"].value_counts()
    total = len(crm_df)
    return {status: {"count": int(n), "pct": round(n / total * 100, 1)} for status, n in counts.items()}


def deals_summary(crm_df: pd.DataFrame) -> dict:
    won = crm_df[crm_df["stage"] == "Won"]
    matched = crm_df[crm_df["attribution_status"] == "matched"]
    return {
        "total_deals": len(crm_df),
        "won_deals": len(won),
        "win_rate": safe_divide(len(won), len(crm_df)),
        "total_value": crm_df["deal_value"].sum(),
        "won_value": won["deal_value"].sum(),
        "matched_value": matched["deal_value"].sum(),
        "unattributed_value": crm_df.loc[crm_df["attribution_status"] != "matched", "deal_value"].sum(),
    }
