import math

import pandas as pd
import pytest

from pipeline import metrics


def test_safe_divide():
    assert metrics.safe_divide(10, 2) == 5
    assert math.isnan(metrics.safe_divide(10, 0))
    assert math.isnan(metrics.safe_divide(10, float("nan")))


def test_summarize_sums_then_divides():
    df = pd.DataFrame({
        "spend": [100, 200],
        "impressions": [1000, 2000],
        "clicks": [50, 80],
        "conversions": [5, 10],
        "conversion_value": [300, 900],
    })
    result = metrics.summarize(df)
    assert result["spend"] == 300
    assert result["conversion_value"] == 1200
    assert result["roas"] == pytest.approx(4.0)
    assert result["cost_per_conversion"] == pytest.approx(20.0)


def test_summarize_zero_conversions_is_nan_not_error():
    df = pd.DataFrame({
        "spend": [50], "impressions": [100], "clicks": [10],
        "conversions": [0], "conversion_value": [0],
    })
    assert math.isnan(metrics.summarize(df)["cost_per_conversion"])


def test_pct_change():
    assert metrics.pct_change(100, 150) == pytest.approx(0.5)
    assert metrics.pct_change(100, 100) == pytest.approx(0.0)
    assert math.isnan(metrics.pct_change(0, 50))


def test_trend_label():
    assert metrics.trend_label(0.5) == "up"
    assert metrics.trend_label(-0.5) == "down"
    assert metrics.trend_label(0.01) == "flat"  # inside the default 2% band
    assert metrics.trend_label(float("nan")) == "flat"


def _daily_df(spend_by_day, value_by_day, start="2025-01-01"):
    dates = pd.date_range(start, periods=len(spend_by_day), freq="D")
    return pd.DataFrame({
        "date": dates,
        "spend": spend_by_day,
        "impressions": [100] * len(spend_by_day),
        "clicks": [10] * len(spend_by_day),
        "conversions": [1] * len(spend_by_day),
        "conversion_value": value_by_day,
    })


def test_period_over_period_splits_on_trailing_window():
    # 30 days at spend=10/roas=2, then 30 days at spend=20/roas=2 —
    # spend should show as up, but roas flat since efficiency didn't change.
    df = _daily_df([10] * 30 + [20] * 30, [20] * 30 + [40] * 30)
    result = metrics.period_over_period(df, days=30)
    assert result["prior"]["spend"] == 300
    assert result["current"]["spend"] == 600
    assert result["change_pct"]["spend"] == pytest.approx(1.0)
    assert result["change_pct"]["roas"] == pytest.approx(0.0)


def _channel_df(channel, spends, roas_values, start="2025-01-01"):
    dates = pd.date_range(start, periods=len(spends), freq="D")
    values = [s * r for s, r in zip(spends, roas_values)]
    return pd.DataFrame({"date": dates, "channel": channel, "spend": spends, "conversion_value": values})


def test_spend_decile_roas_and_diminishing_returns_flag():
    # low-spend days return roas=4, high-spend days return roas=1 — a classic
    # "extra budget stops paying" shape.
    saturating = _channel_df("Saturating", list(range(1, 21)), [4] * 10 + [1] * 10)
    # constant roas regardless of spend — healthy, no diminishing returns.
    healthy = _channel_df("Healthy", list(range(1, 21)), [3] * 20)
    df = pd.concat([saturating, healthy], ignore_index=True)

    deciles = metrics.spend_decile_roas(df, n_bins=10)
    assert len(deciles[deciles["channel"] == "Saturating"]) == 10
    sat = deciles[deciles["channel"] == "Saturating"].sort_values("decile")
    assert sat.iloc[0]["roas"] == pytest.approx(4.0)
    assert sat.iloc[-1]["roas"] == pytest.approx(1.0)

    flags = metrics.diminishing_returns_channels(deciles)
    assert flags["Saturating"] is True
    assert flags["Healthy"] is False

    ratios = metrics.decile_ratio_to_peak(deciles)
    assert ratios["Saturating"] == pytest.approx(0.25)  # top decile 1.0 / peak 4.0
    assert ratios["Healthy"] == pytest.approx(1.0)  # constant roas, top decile == peak


def test_campaign_summary_aggregates_by_campaign():
    df = pd.DataFrame({
        "client": ["A", "A"], "channel": ["Google Ads", "Google Ads"],
        "campaign_name": ["Brand", "Brand"],
        "spend": [100, 50], "conversion_value": [300, 150], "conversions": [3, 2],
    })
    result = metrics.campaign_summary(df)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["spend"] == 150
    assert row["roas"] == pytest.approx(3.0)


def test_flag_campaigns_uses_per_client_thresholds():
    summary = pd.DataFrame({
        "client": ["X"] * 4,
        "channel": ["Google Ads"] * 4,
        "campaign_name": ["HighSpendLowReturn", "LowSpendHighReturn", "Mid1", "Mid2"],
        "spend": [1000, 100, 500, 500],
        "conversion_value": [500, 800, 1000, 1000],
        "conversions": [10, 10, 10, 10],
        "roas": [0.5, 8.0, 2.0, 2.0],
    })
    flagged = metrics.flag_campaigns(summary)
    flags = flagged.set_index("campaign_name")["flag"]
    assert flags["HighSpendLowReturn"] == "high_spend_low_return"
    assert flags["LowSpendHighReturn"] == "high_return_underfunded"
    assert flags["Mid1"] == "none"
    assert flags["Mid2"] == "none"


def test_attribution_breakdown():
    crm = pd.DataFrame({"attribution_status": ["matched", "matched", "no_source_recorded", "unmatched_source"]})
    result = metrics.attribution_breakdown(crm)
    assert result["matched"]["count"] == 2
    assert result["matched"]["pct"] == pytest.approx(50.0)
    assert result["no_source_recorded"]["count"] == 1


def test_deals_summary():
    crm = pd.DataFrame({
        "stage": ["Won", "Lost", "Won", "New"],
        "deal_value": [100, 50, 200, 30],
        "attribution_status": ["matched", "matched", "no_source_recorded", "unmatched_source"],
    })
    result = metrics.deals_summary(crm)
    assert result["total_deals"] == 4
    assert result["won_deals"] == 2
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["total_value"] == 380
    assert result["won_value"] == 300
    assert result["matched_value"] == 150
    assert result["unattributed_value"] == 230
