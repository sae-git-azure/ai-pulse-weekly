# AI Pulse Weekly - Plan summary
Weekly (Fri 09:00 Germany) ES/EN report of AI news from official sources, published via GitHub Pages
(https://sae-git-azure.github.io/ai-pulse-weekly). Source: "AI Pulse Weekly - Plan.docx".

## Rules
Official sources only; last 7 days; max 10 items/section; no duplicates across sections; header with timestamp,
edition (+1/week) and KW; one archive file per week; failed source => page still builds with a note.

## Setup steps (manual)
1. Repo must be public. 2. Add secret `ANTHROPIC_API_KEY` (never in code/config).
3. Settings > Pages > Source: "GitHub Actions". 4. Actions > "AI Pulse Weekly" > Run workflow once to test.
Without the secret the page still builds, using the feed's own text for both languages.
