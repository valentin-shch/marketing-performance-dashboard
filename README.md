# Marketing Performance Dashboard

**[Live demo →](https://marketing-performance-dashboard-sc98m2xblpde4zh4yufbdb.streamlit.app/)**

A white-label performance dashboard built for how a digital marketing agency actually works: one dataset, several clients, and a client who needs to see spend, ROAS, and pipeline without learning to read raw ad exports.

Pick a client from the sidebar and every page (overview, channel efficiency, campaign-level
flags, CRM attribution) filters to that account. This is a portfolio piece, so the data is synthetic (details below), but the pipeline, the messiness clean up, and the dashboard logic are built the way I build them for real clients.

## What's in it

- **Overview** — spend, ROAS, and CPL trends over time, with a plain-language read on which way things are moving.
- **Channel Efficiency** — where each euro of spend is landing: marginal ROAS by spend decile, per channel, flagging channels past the point of diminishing returns.
- **Campaign Explorer** — every campaign for the selected client, auto-flagged for high spend/low return or high return/underfunded, filterable by channel, type, and theme.
- **Pipeline & Attribution** — how much of the CRM pipeline can actually be traced back to a campaign, and how much can't — stated plainly, not softened into a coverage number.
- **Data Quality** — what the cleaning pipeline actually fixed (duplicates, mixed currencies, a timezone bug, inconsistent campaign naming, missing values) and how much of the raw data needed it.

Every chart and table is responsive down to a phone screen — this is meant to be checked
from a client's phone in a meeting, not just from a laptop.

## The data

Nothing here is real. `data/generate.py` builds about 18 months of synthetic ad exports
(Google Ads, Meta Ads, LinkedIn Ads, Organic Search) and CRM deals for three fictional
clients, deliberately messy in the ways real exports are: duplicate rows, three different
date formats, one platform reporting in the wrong currency, a timezone bug, campaign names
that don't follow one convention, and deals that don't all cleanly match back to a
campaign. `pipeline/clean.py` fixes all of it — the Data Quality page shows the receipts.

## Stack

Python, pandas, Plotly, Streamlit. No database — data is generated to CSV, cleaned into
parquet, and read from disk. `pipeline/metrics.py` is a set of pure functions (ROAS, CPL,
trends, flags) covered by `tests/`, kept separate from the app so the numbers can be
checked without running Streamlit at all.

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

## Running it locally

    python data/generate.py
    python pipeline/clean.py
    pytest tests/
    streamlit run app/Overview.py

`generate.py` regenerates `data/raw/` with an 18-month window ending last month, so the
demo data doesn't go stale. The random seed keeps the *shape* of the data stable across
runs — only the calendar dates and campaign quarter labels shift with the run date.

`clean.py` reads `data/raw/`, fixes the messiness described above, and writes
`data/clean/*.parquet` plus a `data_quality_summary.json` that the Data Quality page reads
from directly.

## Deploying

Streamlit Community Cloud runs the repo as committed — `pip install -r requirements.txt`,
then `streamlit run app/Overview.py`. There's no separate pipeline step, so
`data/clean/*.parquet` (the pipeline's output, not just `data/raw/`) has to be committed
too, or every page fails to load. Regenerate and re-clean first if the data's gone stale:

    python data/generate.py
    python pipeline/clean.py

Then, from [share.streamlit.io](https://share.streamlit.io):

1. Connect the GitHub repo.
2. Main file path: `app/Overview.py`
3. Deploy.

No secrets or API keys to configure — nothing in this app calls an external service.
