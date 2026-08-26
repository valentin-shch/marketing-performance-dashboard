# Marketing Performance Dashboard

A white-label marketing performance dashboard for a digital marketing agency's
clients — spend, ROAS, campaign efficiency, and CRM-attributed pipeline
across Google Ads, Meta Ads, LinkedIn Ads, and organic search.

All data in this repo is synthetic, generated to mirror the structure (and
the mess) of real Google Ads, Meta, and CRM exports. There is no real client
data here.

## Status

Data generation, cleaning pipeline, and metrics are built and tested. All
five app pages are up: Overview, Channel Efficiency, Campaign Explorer,
Pipeline & Attribution, and Data Quality.

## Stack

Python, pandas, Plotly, Streamlit. No database — data is generated to CSV,
cleaned into parquet, and read from disk.

## Structure

    data/generate.py     synthetic data generator, seeded, reproducible
    data/raw/             generator output (messy, on purpose, committed)
    pipeline/clean.py    raw exports -> clean, joined parquet
    pipeline/metrics.py  business metric calculations, pure functions
    app/Overview.py       Streamlit app entry point (Overview page)
    app/lib.py            shared data loading, formatting, chart/CSS helpers
    app/pages/             Channel Efficiency, Campaign Explorer,
                            Pipeline & Attribution, Data Quality
    tests/                pytest for the metric functions

## Running the pipeline

    python data/generate.py
    python pipeline/clean.py
    pytest tests/
    streamlit run app/Overview.py

`generate.py` regenerates `data/raw/` with an 18-month window ending last
month, so the demo data doesn't go stale. The random seed keeps the
*shape* of the data stable across runs — only the calendar dates and
campaign quarter labels shift with the run date.

`clean.py` reads `data/raw/`, fixes the deliberate messiness (duplicates,
mixed currencies and date formats, a timezone bug, inconsistent campaign
names, unmatched CRM deals), and writes `data/clean/*.parquet` plus a
`data_quality_summary.json`.

`metrics.py` computes ROAS, cost per lead, period-over-period trends,
spend-decile marginal efficiency, and campaign/deal flags — all as pure
functions over the clean tables, covered by `tests/`.
