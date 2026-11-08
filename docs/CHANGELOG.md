# Changelog
- Initial build: config, scripts, template, weekly workflow, Pages deployment.
- Anthropic via sitemap (no RSS); Copilot via Microsoft blog feed filtered by keyword.
- Meta source: about.fb.com newsroom feed filtered by whole-word keywords (AI, Llama).
- Schedule fix: scheduled runs were started ~7h late by GitHub and the old "Berlin hour == 9" gate exited silently (green, no edition, old site redeployed).
  Now `scripts/guard.py` builds from Friday 09:00 Berlin onward, once per ISO week; crons 07:17 / 08:43 / 12:23 UTC; concurrency group; checkout of latest main.
- Fail visibly: run is red if no new edition file is written or the page has 0 items (nothing is published in that case).
- Per-source counts (raw / last 7 days / after filter) in the log and GITHUB_STEP_SUMMARY; page note for sources that fail or return 0 raw items.
- Removed tracked __pycache__, added .gitignore.
