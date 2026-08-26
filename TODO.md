# TODO

Things worth reconsidering later. Not blocking, just flagged.

- Generator reads the real system clock (`pd.Timestamp.today()`), so
  re-running it later shifts every date even with the same seed. Good for
  keeping the demo fresh, but raw output isn't byte-reproducible run to run.
  Maybe worth an env var to pin the end date for tests.
- CRM `deal_value` is sampled uniform per client (inline TODO in
  generate.py). A real CRM's deal sizes are probably long-tailed, not flat.
- Missing `conversion_value` is imputed with a mean revenue-per-conversion
  by client+channel (pipeline/clean.py). Coarse — a per-campaign or
  per-month rate would be more accurate if it turns out to skew any of the
  channel comparisons materially.
- Measured against the live deployment (not just local): the page shell
  clears its loading skeleton fast (~3.5-3.8s, genuinely faster than local's
  frontend-asset load), but the actual KPI values don't populate until
  8-20s+ depending on the run — and a warm rerun that should hit
  @st.cache_data's cache still took ~9.6s once, well past the brief's
  "cold load under 3 seconds" target for data. Root cause is unclear from
  outside (network RTT to wherever the free tier hosts this, and/or
  constrained shared compute) — worth watching if it's consistently this
  slow for real visitors, since right now the shell-vs-data distinction
  means a naive glance ("looks loaded") undersells how long the real
  numbers take to show up.
