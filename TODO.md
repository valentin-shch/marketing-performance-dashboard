# TODO

Not blocking, just things I'd revisit if I had more time.

- The generator uses today's date as the end of its window, so re-running
  it later shifts every date, even with the same seed. Good for keeping
  the demo fresh, but output isn't byte-identical run to run. Would want
  a pinned end date if this ever needed reproducible tests.
- CRM deal sizes are sampled uniform per client (see the TODO in
  generate.py). Real deal sizes are usually long-tailed, not flat.
- Missing conversion value gets filled with a same-client-and-channel
  average (pipeline/clean.py). Coarse — a per-campaign or per-month rate
  would be closer if it ever skews a channel comparison.
- The live app takes longer to show real numbers than I'd like — the page
  shell loads in ~3.5s, but KPIs don't populate for 8-20s+. Checked twice
  back to back and the second visit wasn't any faster, so it's not just a
  sleepy container waking up — looks like per-session startup cost on the
  free hosting tier (network plus shared compute), not the data itself.
  Can't fix that from the code; living with it unless it turns out to
  actually bother people.
