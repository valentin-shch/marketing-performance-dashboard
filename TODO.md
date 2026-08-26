# TODO

Things worth reconsidering later. Not blocking, just flagged.

- Generator reads the real system clock (`pd.Timestamp.today()`), so
  re-running it later shifts every date even with the same seed. Good for
  keeping the demo fresh, but raw output isn't byte-reproducible run to run.
  Maybe worth an env var to pin the end date for tests.
- LinkedIn's UTC-vs-Madrid date shift can push its first row a day before
  the nominal window start (e.g. Jan 31 when the window opens Feb 1). It's
  intentional messiness, but pipeline/clean.py needs to actually correct it,
  not just leave it documented in the generator.
- CRM `deal_value` is sampled uniform per client (inline TODO in
  generate.py). A real CRM's deal sizes are probably long-tailed, not flat.
- README has no deploy section yet — add Streamlit Community Cloud steps
  once app/ exists.
