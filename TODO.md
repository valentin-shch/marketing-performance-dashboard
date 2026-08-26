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
- README has no deploy section yet — add Streamlit Community Cloud steps
  once app/ exists.
