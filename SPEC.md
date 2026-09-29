# am0muk.github.io — findings page (spec for the implementing agent)

## Goal
One static page (GitHub Pages, repo Am0MuK/Am0MuK.github.io, served from main root) that shows two measured
findings as a portfolio for freelance on-chain data work. Every number on the page must come from a script in
this repo that reads the local databases, never typed by hand (one exception below).

## Output files (all in this repo)
- `scripts/export_liquidations.py` -> `data/liquidations.json`
- `scripts/export_lpsim.py` -> `data/lpsim.json`
- `index.html` (+ `assets/style.css`, `assets/app.js`): loads the JSON files, draws charts with Chart.js from
  https://cdn.jsdelivr.net/npm/chart.js (pinned version), works on phone width, light/dark via prefers-color-scheme.
- `README.md`: what the page is, how to regenerate (commands), data sources.
- `data/lpsim_validation.json`: the ONE hand-copied input (needs RPC to regenerate), with a "source" field
  pointing to https://github.com/Am0MuK/lp-sim README. Values: USDC/USDT0 0.01% sim/on-chain 1.0000 (token0) and
  0.9992 (token1); GHO/USDC 0.05% 1.0000 and 1.0000; USDe/USDT0 0.05% 0.9971 and 1.0001; mismatches 0 on all three;
  swaps 62,484 / 1,389 / 508; window blocks 478,933,740 -> 509,690,000.

## Section A: Aave V3 liquidations on Arbitrum (chain_id 42161), 12 months
Source: /data/projects/mev-scout/data/scout365.db (open READ-ONLY, sqlite URI mode=ro), valued with mev-scout's
OWN valuation code (package at /data/projects/mev-scout/src, venv /data/projects/mev-scout/.venv). Read its
README and src first to see how `value` / `report` compute gross profit, gas and net per liquidation (USD and EUR)
and which cache they use. It must run OFFLINE from the cached oracle calls (call_cache). If valuation would need a
network call for any event, stop and report how many events are affected; do NOT add a fallback price.
Export: per month (12): event count, net USD, net EUR; liquidator concentration over the year (number of distinct
liquidators, top-1 / top-3 / top-10 share of net profit); top 10 days by net profit with share of the year; unpriced
event count. Known published figures to reconcile against (print a reconciliation line for each in the script
output and in README): 276 liquidators; net ~ $3.18M per year (2.77M EUR); top-1 26.9%; top-3 45.9%; top 5 days =
66% of the year; 2025-10-10 alone = 29%. If a figure differs, report the difference, do not force it.

## Section B: stable-pair LP versus lending (lp-sim)
Source: /data/projects/lp-sim/results/2026-09-29/*.json (1,464 strategy runs: 8 Uniswap V3 pools on Arbitrum x
sizes 50/1000/10000 USD x 61 strategies). Export per (pool, size): best strategy by average monthly net APY, its
monthly net APYs, count of PASS (0 everywhere); plus for USDC/USDT0 at 1000 and 10000 the AUTOBALANCER_1 line
(403 rebalances, total net USD) versus the best static strategy. Mark the 3 pools that count for the decision
(USDC/USDT0 0.01%, GHO/USDC 0.05%, USDe/USDT0 0.05%) versus info-only pools. Threshold line: 15% per year.

## Page text (English, short, plain, no marketing words)
Title: "What on-chain data says about two DeFi strategies". Per section: the question, the rule fixed in advance,
the result, how it was checked, limits. Link the repos github.com/Am0MuK/mev-scout, /lp-sim, /onchain-tieout and the
profile github.com/Am0MuK. Contact: kontakt@defisteuer.de. No invented facts: only what the data, the repos'
READMEs and this spec say. No em dashes. Not investment advice line at the bottom.

## Rules
- Work only inside /data/projects/am0muk.github.io. Never write to mev-scout, lp-sim or their databases.
- No network except none: no RPC, no .env, no API keys. Do not push. Do not touch "Central Memory".
- Python stdlib + the mev-scout package only for the scripts. Commit locally with clear messages.
- Final answer: files created, reconciliation table (published vs recomputed), anything that did not match,
  deviations from this spec.
