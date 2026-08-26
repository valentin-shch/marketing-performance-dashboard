# Marketing Performance Dashboard

A white-label marketing performance dashboard for a digital marketing agency's
clients — spend, ROAS, campaign efficiency, and CRM-attributed pipeline
across Google Ads, Meta Ads, LinkedIn Ads, and organic search.

All data in this repo is synthetic, generated to mirror the structure (and
the mess) of real Google Ads, Meta, and CRM exports. There is no real client
data here.

## Status

Data generation only, right now. Cleaning pipeline, metrics, and the
Streamlit app aren't built yet.

## Stack

Python, pandas, Plotly, Streamlit. No database — data is generated to CSV,
cleaned into parquet, and read from disk.

## Structure

    data/generate.py   synthetic data generator, seeded, reproducible
    data/raw/           generator output (messy, on purpose, committed)
    pipeline/            cleaning + metrics (not yet built)
    app/                 Streamlit app (not yet built)
    tests/               pytest for the metric functions (not yet built)

## Running the generator

    python data/generate.py

Regenerates `data/raw/` with an 18-month window ending last month, so the
demo data doesn't go stale. The random seed keeps the *shape* of the data
stable across runs — only the calendar dates and campaign quarter labels
shift with the run date.
